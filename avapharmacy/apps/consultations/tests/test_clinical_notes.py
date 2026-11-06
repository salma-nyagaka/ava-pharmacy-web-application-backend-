from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from avapharmacy.test_compliance_fixtures import clinician_fixture

from apps.accounts.models import User
from apps.consultations.models import ClinicianProfile, Consultation, ConsultationAuditLog


class ClinicalNotesTests(TestCase):
    def setUp(self):
        self.patient = User.objects.create_user(email='notes-patient@example.test', role='customer')
        self.doctor = User.objects.create_user(email='notes-doctor@example.test', role='doctor')
        self.other = User.objects.create_user(email='notes-other@example.test', role='doctor')
        self.profile = ClinicianProfile.objects.create(user=self.doctor, provider_type='doctor', status='active', name='Doctor',
            **clinician_fixture(exclude=('user', 'provider_type', 'status', 'name')))
        self.consultation = Consultation.objects.create(patient=self.patient, clinician=self.profile, patient_name='Patient', issue='Symptoms')
        self.url = reverse('consultation-clinical-notes', args=[self.consultation.pk])
        self.client = APIClient()

    def test_assigned_doctor_saves_and_patient_can_read_after_reload(self):
        self.client.force_authenticate(self.doctor)
        self.assertEqual(self.client.put(self.url, {'notes': {'diagnosis': 'Recorded assessment', 'plan': 'Follow-up plan'}}, format='json').status_code, 200)
        self.consultation.refresh_from_db()
        self.assertEqual(self.consultation.clinical_notes['plan'], 'Follow-up plan')
        self.assertIsNotNone(self.consultation.clinical_notes_updated_at)
        self.assertTrue(ConsultationAuditLog.objects.filter(consultation=self.consultation, action='save_clinical_notes').exists())
        self.client.force_authenticate(self.patient)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertIn('Recorded assessment', str(response.data))
        self.assertEqual(self.client.put(self.url, {'notes': {}}, format='json').status_code, 403)

    def test_unrelated_clinician_cannot_read_or_write(self):
        self.client.force_authenticate(self.other)
        self.assertEqual(self.client.get(self.url).status_code, 404)
        self.assertEqual(self.client.put(self.url, {'notes': {'plan': 'overwrite'}}, format='json').status_code, 404)

    def test_unrelated_patient_cannot_read_notes(self):
        outsider = User.objects.create_user(email='outsider@example.test', role='customer')
        self.client.force_authenticate(outsider)
        self.assertEqual(self.client.get(self.url).status_code, 404)

    def test_suspended_clinician_cannot_read_or_write(self):
        self.profile.status = 'suspended'
        self.profile.save()
        self.client.force_authenticate(self.doctor)
        self.assertEqual(self.client.get(self.url).status_code, 404)
        self.assertEqual(self.client.put(self.url, {'notes': {}}, format='json').status_code, 404)

    def test_invalid_notes_do_not_replace_saved_notes(self):
        self.client.force_authenticate(self.doctor)
        for notes in ([], {'plan': 123}, {'unknown': 'text'}, {'plan': 'x' * 10001}):
            self.assertEqual(self.client.put(self.url, {'notes': notes}, format='json').status_code, 400)
        self.consultation.refresh_from_db()
        self.assertEqual(self.consultation.clinical_notes, {})

    def test_pediatrician_notes_are_available_to_guardian(self):
        self.doctor.role = 'pediatrician'
        self.doctor.save()
        self.profile.provider_type = 'pediatrician'
        self.profile.save()
        self.client.force_authenticate(self.doctor)
        self.assertEqual(self.client.put(self.url, {'notes': {'assessment': 'Pediatric assessment'}}, format='json').status_code, 200)
        self.client.force_authenticate(self.patient)
        self.assertEqual(self.client.get(self.url).status_code, 200)
