from decimal import Decimal
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from avapharmacy.test_compliance_fixtures import clinician_fixture
from apps.accounts.models import User
from apps.consultations.models import ClinicianProfile, Consultation, ConsultationPaymentIntent, ClinicianEarning
from apps.payouts.models import Payout


class ConsultationPayoutPageTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_user(email='sync-admin@example.test', role='admin', status='active')
        self.client.force_authenticate(self.admin)
        self.url = reverse('admin-sync-consultation-payouts')

    def consultation(self, role='doctor', status='completed', paid=True, earning=True):
        user = User.objects.create_user(email=f'{role}-{Consultation.objects.count()}@sync.test', role=role)
        clinician = ClinicianProfile.objects.create(user=user, provider_type=role, name=f'QA {role}', status='active', **clinician_fixture(exclude=('user', 'provider_type', 'name', 'status')))
        consultation = Consultation.objects.create(clinician=clinician, status=status, patient_name='QA')
        if paid:
            ConsultationPaymentIntent.objects.create(clinician=clinician, consultation=consultation, provider='mpesa', amount='1500', status='succeeded')
        if earning:
            ClinicianEarning.objects.create(clinician=clinician, consultation=consultation, amount='1000')
        return consultation

    def test_page_sync_lists_completed_doctors_and_pediatricians_once(self):
        doctor = self.consultation()
        pediatrician = self.consultation('pediatrician')
        waiting = self.consultation(status='waiting')
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.data['created'], 2)
        self.assertEqual(set(Payout.objects.values_list('source_reference', flat=True)), {doctor.reference, pediatrician.reference})
        self.assertFalse(Payout.objects.filter(source_reference=waiting.reference).exists())
        self.assertEqual(self.client.post(self.url).data['created'], 0)
        result = self.client.get(reverse('admin-payouts'))
        self.assertIn(doctor.reference, str(result.data))
        self.assertIn(pediatrician.reference, str(result.data))

    def test_old_fixed_share_is_recovered_and_unpaid_work_is_held(self):
        paid = self.consultation(earning=False)
        unpaid = self.consultation('pediatrician', paid=False)
        self.client.post(self.url)
        self.assertEqual(Payout.objects.get(source_reference=paid.reference).amount, Decimal('1000'))
        self.assertEqual(Payout.objects.get(source_reference=paid.reference).status, 'pending')
        self.assertEqual(Payout.objects.get(source_reference=unpaid.reference).status, 'on_hold')

    def test_paid_rows_and_audits_remain_unchanged_after_reload(self):
        consultation = self.consultation()
        self.client.post(self.url)
        payout = Payout.objects.get(source_reference=consultation.reference)
        payout.status = 'paid'; payout.payment_reference = 'SYNC-EXISTING'; payout.save()
        self.client.post(self.url)
        payout.refresh_from_db()
        self.assertEqual(payout.status, 'paid')
        self.assertEqual(payout.payment_reference, 'SYNC-EXISTING')
        self.assertEqual(payout.audit_logs.count(), 1)

    def test_only_finance_admin_can_sync(self):
        consultation = self.consultation()
        self.client.force_authenticate(consultation.clinician.user)
        self.assertEqual(self.client.post(self.url).status_code, 403)
        self.assertFalse(Payout.objects.exists())
