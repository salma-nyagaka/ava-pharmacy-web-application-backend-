from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.payouts.models import Payout, PayoutAuditLog


class PayoutWorkflowTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.maker = User.objects.create_user(
            email='finance-maker@example.com', password='testpass123', first_name='Finance', last_name='Maker', role=User.ADMIN,
        )
        self.checker = User.objects.create_user(
            email='finance-checker@example.com', password='testpass123', first_name='Finance', last_name='Checker', role=User.ADMIN,
        )
        self.provider = User.objects.create_user(
            email='payout-doctor@example.com', password='testpass123', first_name='Payout', last_name='Doctor', role=User.DOCTOR,
        )

    def _create(self):
        self.client.force_authenticate(self.maker)
        return self.client.post(reverse('admin-payouts'), {
            'recipient': self.provider.id,
            'recipient_name': self.provider.full_name,
            'role': Payout.ROLE_DOCTOR,
            'period': 'July 2026',
            'source_type': 'consultation',
            'source_reference': 'CONS-PAYOUT-001',
            'idempotency_key': 'payout:consultation:001',
            'gross_amount': '1500.00',
            'commission_amount': '150.00',
            'withholding_amount': '75.00',
            'deduction_amount': '0.00',
            'currency': 'KES',
            'method': Payout.METHOD_MPESA,
        }, format='json')

    def test_maker_checker_paid_workflow_and_audit(self):
        created = self._create()
        self.assertEqual(created.status_code, 201, created.content)
        payout_id = created.data['id']
        self.assertEqual(created.data['status'], Payout.STATUS_DRAFT)
        self.assertEqual(created.data['amount'], '1275.00')

        submitted = self.client.post(reverse('admin-payout-action', args=[payout_id]), {'action': 'submit'}, format='json')
        self.assertEqual(submitted.status_code, 200)
        self.assertEqual(submitted.data['status'], Payout.STATUS_PENDING)

        rejected_approval = self.client.post(reverse('admin-payout-action', args=[payout_id]), {'action': 'approve'}, format='json')
        self.assertEqual(rejected_approval.status_code, 403)

        self.client.force_authenticate(self.checker)
        approved = self.client.post(reverse('admin-payout-action', args=[payout_id]), {'action': 'approve'}, format='json')
        self.assertEqual(approved.status_code, 200)
        self.assertEqual(approved.data['status'], Payout.STATUS_APPROVED)

        processed = self.client.post(reverse('admin-payout-action', args=[payout_id]), {
            'action': 'process', 'batch_reference': 'BATCH-JUL-001',
        }, format='json')
        self.assertEqual(processed.status_code, 200)
        paid = self.client.post(reverse('admin-payout-action', args=[payout_id]), {
            'action': 'mark_paid', 'payment_reference': 'SHX123ABC', 'provider_transaction_id': 'SHX123ABC',
        }, format='json')
        self.assertEqual(paid.status_code, 200)
        self.assertEqual(paid.data['status'], Payout.STATUS_PAID)
        self.assertIsNotNone(paid.data['paid_at'])
        self.assertGreaterEqual(PayoutAuditLog.objects.filter(payout_id=payout_id).count(), 5)

        summary = self.client.get(reverse('admin-payout-summary'))
        self.assertEqual(summary.status_code, 200)
        self.assertEqual(summary.data['paid'], 1275)

    def test_duplicate_source_and_idempotency_are_rejected(self):
        first = self._create()
        self.assertEqual(first.status_code, 201)
        duplicate = self._create()
        self.assertEqual(duplicate.status_code, 409)

    def test_state_transition_and_required_reference_are_enforced(self):
        created = self._create()
        payout_id = created.data['id']
        invalid_paid = self.client.post(reverse('admin-payout-action', args=[payout_id]), {'action': 'mark_paid'}, format='json')
        self.assertEqual(invalid_paid.status_code, 409)
        cancel_without_reason = self.client.post(reverse('admin-payout-action', args=[payout_id]), {'action': 'cancel'}, format='json')
        self.assertEqual(cancel_without_reason.status_code, 400)

    def test_payment_references_cannot_be_reused(self):
        first = self._create()
        self.assertEqual(first.status_code, 201)
        payout_one = first.data['id']
        self.client.post(reverse('admin-payout-action', args=[payout_one]), {'action': 'submit'}, format='json')

        self.client.force_authenticate(self.maker)
        second = self.client.post(reverse('admin-payouts'), {
            'recipient': self.provider.id, 'recipient_name': self.provider.full_name,
            'role': Payout.ROLE_DOCTOR, 'period': 'July 2026', 'source_type': 'consultation',
            'source_reference': 'CONS-PAYOUT-002', 'idempotency_key': 'payout:consultation:002',
            'gross_amount': '900.00', 'currency': 'KES', 'method': Payout.METHOD_MPESA,
        }, format='json')
        self.assertEqual(second.status_code, 201)
        payout_two = second.data['id']
        self.client.post(reverse('admin-payout-action', args=[payout_two]), {'action': 'submit'}, format='json')

        self.client.force_authenticate(self.checker)
        for payout_id in (payout_one, payout_two):
            self.client.post(reverse('admin-payout-action', args=[payout_id]), {'action': 'approve'}, format='json')
        paid = self.client.post(reverse('admin-payout-action', args=[payout_one]), {
            'action': 'mark_paid', 'payment_reference': 'MPESA-UNIQUE-1',
        }, format='json')
        duplicate = self.client.post(reverse('admin-payout-action', args=[payout_two]), {
            'action': 'mark_paid', 'payment_reference': 'MPESA-UNIQUE-1',
        }, format='json')
        self.assertEqual(paid.status_code, 200)
        self.assertEqual(duplicate.status_code, 409)
