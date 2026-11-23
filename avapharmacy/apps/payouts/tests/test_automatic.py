from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient, APITestCase

from avapharmacy.test_compliance_fixtures import clinician_fixture
from apps.accounts.models import User
from apps.consultations.models import ClinicianProfile, Consultation, ConsultationPaymentIntent
from apps.lab.models import LabRequest, LabResult
from apps.lab.tests import test_workflow_security as lab_fixtures
from apps.payouts.models import LabRevenueAgreement, LabRevenueAllocation, Payout


class AutomaticConsultationPayoutTests(TestCase):
    def test_doctor_and_pediatrician_completion_creates_one_payable_row(self):
        for role in ('doctor', 'pediatrician'):
            with self.subTest(role=role):
                user = User.objects.create_user(email=f'{role}@auto.test', role=role)
                profile = ClinicianProfile.objects.create(user=user, provider_type=role, name='QA Provider', status='active', **clinician_fixture(exclude=('user', 'provider_type', 'name', 'status')))
                consultation = Consultation.objects.create(clinician=profile, patient_name='QA', status='in_progress')
                ConsultationPaymentIntent.objects.create(consultation=consultation, clinician=profile, amount='1500.00', status='succeeded', provider='mpesa')
                client = APIClient(); client.force_authenticate(user)
                for _ in range(2):
                    response = client.post(reverse('consultation-end', args=[consultation.pk]), {}, format='json')
                    self.assertEqual(response.status_code, 200, response.content)
                payout = Payout.objects.get(source_reference=consultation.reference)
                self.assertEqual(payout.role, role)
                self.assertEqual(payout.status, 'pending')
                self.assertEqual(payout.amount, Decimal('1000'))
                self.assertEqual(payout.commission_amount, Decimal('500'))
                self.assertIsNone(payout.created_by_id)
                self.assertEqual(payout.audit_logs.count(), 1)
                admin = User.objects.create_user(email=f'admin-{role}@auto.test', role='admin')
                client.force_authenticate(admin)
                result = client.get(reverse('admin-payouts'))
                self.assertIn(payout.reference, str(result.data))
                for action, extras in [('approve', {}), ('mark_paid', {'payment_reference': f'AUTO-{role}'})]:
                    result = client.post(reverse('admin-payout-action', args=[payout.pk]), {'action': action, **extras}, format='json')
                    self.assertEqual(result.status_code, 200, result.content)


class AutomaticLabPayoutTests(APITestCase):
    setUp = lab_fixtures.LabWorkflowSecurityTests.setUp
    make_user = staticmethod(lab_fixtures.LabWorkflowSecurityTests.make_user)
    authenticate = lab_fixtures.LabWorkflowSecurityTests.authenticate

    def agreement(self):
        return LabRevenueAgreement.objects.create(partner=self.partner, partner_percent=60, technician_percent=10, ava_percent=30)

    def complete(self, paid=True):
        self.request.status = LabRequest.STATUS_READY
        self.request.payment_status = 'paid' if paid else 'pending'
        self.request.quoted_test_price = Decimal('1500')
        self.request.save()
        LabResult.objects.get_or_create(request=self.request, defaults={'summary': 'QA only'})
        self.authenticate(self.technician)
        response = self.client.patch(reverse('lab-request-update', args=[self.request.pk]), {'status': 'completed'}, format='json')
        self.assertEqual(response.status_code, 200, response.content)

    def test_completion_creates_split_rows_and_freezes_agreement(self):
        agreement = self.agreement(); self.complete()
        self.assertEqual(Payout.objects.count(), 2)
        self.assertEqual(Payout.objects.get(role='lab_partner').amount, Decimal('900'))
        self.assertEqual(Payout.objects.get(role='lab_technician').amount, Decimal('150'))
        self.assertEqual(set(Payout.objects.values_list('status', flat=True)), {'pending'})
        agreement.partner_percent = 50; agreement.ava_percent = 40; agreement.save()
        self.test.price = 9000; self.test.save()
        self.client.patch(reverse('lab-request-update', args=[self.request.pk]), {'status': 'completed'}, format='json')
        self.assertEqual(Payout.objects.count(), 2)
        self.assertEqual(Payout.objects.get(role='lab_partner').amount, Decimal('900'))
        allocation = LabRevenueAllocation.objects.get(request=self.request)
        self.assertEqual(allocation.terms['ava_amount'], '450.00')
        self.assertEqual(allocation.terms['partner_percent'], '60.00')

    def test_missing_agreement_holds_then_applies_one_snapshot_on_release(self):
        self.complete()
        self.assertEqual(set(Payout.objects.values_list('status', flat=True)), {'on_hold'})
        self.authenticate(self.admin)
        payout = Payout.objects.get(role='lab_partner')
        url = reverse('admin-payout-action', args=[payout.pk])
        self.assertEqual(self.client.post(url, {'action': 'release'}, format='json').status_code, 400)
        agreement = self.agreement()
        self.assertEqual(self.client.post(url, {'action': 'release'}, format='json').status_code, 200)
        payout.refresh_from_db(); self.assertEqual(payout.amount, Decimal('900'))
        self.assertEqual(payout.status, 'pending')
        self.assertEqual(self.client.post(url, {'action': 'approve'}, format='json').status_code, 200)
        agreement.partner_percent = 50; agreement.technician_percent = 20; agreement.save()
        technician = Payout.objects.get(role='lab_technician')
        response = self.client.post(reverse('admin-payout-action', args=[technician.pk]), {'action': 'release'}, format='json')
        self.assertEqual(response.status_code, 200, response.content)
        technician.refresh_from_db(); self.assertEqual(technician.amount, Decimal('150'))

    def test_unpaid_lab_is_held_and_cannot_release(self):
        self.agreement(); self.complete(paid=False); self.authenticate(self.admin)
        payout = Payout.objects.get(role='lab_partner')
        self.assertEqual(payout.status, 'on_hold')
        self.assertEqual(self.client.post(reverse('admin-payout-action', args=[payout.pk]), {'action': 'release'}, format='json').status_code, 400)

    def test_payout_failure_rolls_back_clinical_completion(self):
        self.request.status = 'result_ready'; self.request.save()
        LabResult.objects.create(request=self.request, summary='QA')
        self.authenticate(self.technician)
        with patch('apps.payouts.services.create_lab_payouts', side_effect=RuntimeError('QA failure')):
            response = self.client.patch(reverse('lab-request-update', args=[self.request.pk]), {'status': 'completed'}, format='json')
            self.assertEqual(response.status_code, 500)
        self.request.refresh_from_db(); self.assertEqual(self.request.status, 'result_ready')

    def test_agreements_validate_totals_and_require_finance_admin(self):
        payload = {'partner': self.partner.pk, 'partner_percent': '60', 'technician_percent': '10', 'ava_percent': '30'}
        url = reverse('admin-lab-revenue-agreements')
        self.authenticate(self.technician)
        self.assertEqual(self.client.post(url, payload, format='json').status_code, 403)
        self.authenticate(self.admin)
        self.assertEqual(self.client.post(url, {**payload, 'ava_percent': '40'}, format='json').status_code, 400)
        result = self.client.post(url, payload, format='json')
        self.assertEqual(result.status_code, 201, result.content)
        self.assertEqual(result.data['updated_by'], self.admin.pk)
