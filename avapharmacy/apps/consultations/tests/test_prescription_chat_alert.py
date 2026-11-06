from unittest.mock import patch
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from avapharmacy.test_compliance_fixtures import clinician_fixture
from apps.accounts.models import User
from apps.consultations.models import ClinicianProfile, Consultation, ClinicianPrescription, ConsultationMessage


class PrescriptionChatAlertTests(TestCase):
    @patch('apps.consultations.views._broadcast_consultation_event')
    def test_issue_persists_and_broadcasts_one_alert_for_doctor_and_pediatrician(self, broadcast):
        patient = User.objects.create_user(email='alert-patient@example.test', role='customer')
        client = APIClient()
        for role in ['doctor', 'pediatrician']:
            with self.subTest(role=role):
                clinician_user = User.objects.create_user(email=f'alert-{role}@example.test', role=role)
                provider = ClinicianProfile.objects.create(user=clinician_user, provider_type=role, name='Clinician', status='active',
                    **clinician_fixture(exclude=('user', 'provider_type', 'name', 'status')))
                consultation = Consultation.objects.create(patient=patient, clinician=provider, patient_name='Patient', issue='Symptoms', is_pediatric=role == 'pediatrician', consent_status='granted')
                prescription = ClinicianPrescription.objects.create(clinician=provider, consultation=consultation, patient_name='Patient', items=[{'drug_name': 'Medication', 'dose': '1 tablet', 'frequency': 'BD', 'duration': '5/7', 'quantity': 1, 'catalog_fallback': True}])
                self.assertFalse(consultation.messages.exists())
                client.force_authenticate(clinician_user)
                url = reverse(f'{role}-prescription-send', args=[prescription.id])
                broadcast.reset_mock()
                with self.captureOnCommitCallbacks(execute=True):
                    response = client.post(url, format='json')
                self.assertEqual(response.status_code, 200, response.content)
                alert = consultation.messages.get(message_type=ConsultationMessage.TYPE_E_PRESCRIPTION)
                self.assertIn(prescription.reference, alert.message)
                self.assertEqual(alert.sender_id, clinician_user.pk)
                broadcast.assert_called_once()
                self.assertEqual(broadcast.call_args.args[:2], (consultation.pk, 'message.new'))
                consultation.refresh_from_db()
                self.assertEqual(consultation.last_message_at, alert.sent_at)
                with self.captureOnCommitCallbacks(execute=True):
                    self.assertEqual(client.post(url, format='json').status_code, 200)
                self.assertEqual(consultation.messages.filter(message_type='e_prescription').count(), 1)
                client.force_authenticate(patient)
                detail = client.get(reverse('consultation-detail', args=[consultation.pk]))
                self.assertEqual(detail.status_code, 200)
                self.assertIn(prescription.reference, str(detail.data['messages']))
