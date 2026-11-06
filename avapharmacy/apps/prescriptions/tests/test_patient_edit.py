from tempfile import TemporaryDirectory

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.prescriptions.models import Prescription, PrescriptionFile, PrescriptionAuditLog


class PendingPrescriptionEditTests(TestCase):
    def setUp(self):
        media = TemporaryDirectory()
        self.addCleanup(media.cleanup)
        settings = override_settings(MEDIA_ROOT=media.name)
        settings.enable()
        self.addCleanup(settings.disable)
        self.patient = User.objects.create_user(email='edit-patient@example.invalid', role='customer')
        self.other = User.objects.create_user(email='edit-other@example.invalid', role='customer')
        self.rx = Prescription.objects.create(patient=self.patient, patient_name='Original Patient', doctor_name='Dr Original', notes='Original notes')
        self.file = PrescriptionFile.objects.create(prescription=self.rx, file=SimpleUploadedFile('original.pdf', b'%PDF-1.4 original'), filename='original.pdf')
        self.client = APIClient()
        self.client.force_authenticate(self.patient)
        self.url = reverse('prescription-edit', args=[self.rx.pk])
        self.payload = {'patient_name': 'Edited Patient', 'doctor_name': 'Dr Updated', 'notes': 'Updated notes'}

    def test_owner_edits_pending_upload_and_adds_document_with_audit(self):
        response = self.client.patch(self.url, {**self.payload, 'files': [SimpleUploadedFile('extra.pdf', b'%PDF-1.4 extra', content_type='application/pdf')], 'status': 'approved', 'patient': self.other.pk}, format='multipart')
        self.assertEqual(response.status_code, 200, response.data)
        self.rx.refresh_from_db()
        self.assertEqual(self.rx.doctor_name, 'Dr Updated')
        self.assertEqual(self.rx.patient_name, 'Edited Patient')
        self.assertEqual(self.rx.notes, 'Updated notes')
        self.assertEqual(self.rx.patient_id, self.patient.pk)
        self.assertEqual(self.rx.status, 'pending')
        self.assertEqual(self.rx.files.count(), 2)
        self.assertTrue(self.rx.files.filter(pk=self.file.pk).exists())
        audit = self.rx.audit_logs.get(action='Pending prescription edited by patient')
        self.assertEqual(audit.performed_by, self.patient)
        self.assertIn('Dr Original', audit.notes)

    def test_other_patient_and_anonymous_user_cannot_edit(self):
        self.client.force_authenticate(self.other)
        self.assertEqual(self.client.patch(self.url, self.payload, format='multipart').status_code, 404)
        self.client.force_authenticate(None)
        self.assertIn(self.client.patch(self.url, self.payload, format='multipart').status_code, (401, 403))
        self.rx.refresh_from_db()
        self.assertEqual(self.rx.doctor_name, 'Dr Original')

    def test_status_is_rechecked_at_save_and_eprescriptions_are_not_editable(self):
        for status in ('approved', 'rejected', 'clarification'):
            Prescription.objects.filter(pk=self.rx.pk).update(status=status)
            with self.subTest(status=status):
                self.assertEqual(self.client.patch(self.url, self.payload, format='multipart').status_code, 400)
        Prescription.objects.filter(pk=self.rx.pk).update(status='pending', source='e_prescription')
        self.assertEqual(self.client.patch(self.url, self.payload, format='multipart').status_code, 400)
        self.rx.refresh_from_db()
        self.assertEqual(self.rx.doctor_name, 'Dr Original')

    def test_doctor_is_required_and_whitespace_is_rejected(self):
        for doctor in (None, '', '   '):
            payload = {**self.payload}
            if doctor is None:
                payload.pop('doctor_name')
            else:
                payload['doctor_name'] = doctor
            with self.subTest(doctor=doctor):
                self.assertEqual(self.client.patch(self.url, payload, format='multipart').status_code, 400)
        self.rx.refresh_from_db()
        self.assertEqual(self.rx.notes, 'Original notes')

    def test_invalid_documents_do_not_partially_update(self):
        for upload in (
            SimpleUploadedFile('bad.txt', b'bad', content_type='text/plain'),
            SimpleUploadedFile('large.pdf', b'x' * (5 * 1024 * 1024 + 1), content_type='application/pdf'),
        ):
            response = self.client.patch(self.url, {**self.payload, 'files': [upload]}, format='multipart')
            self.assertEqual(response.status_code, 400, response.data)
        self.rx.refresh_from_db()
        self.assertEqual(self.rx.doctor_name, 'Dr Original')
        self.assertEqual(self.rx.files.count(), 1)
        self.assertFalse(PrescriptionAuditLog.objects.filter(prescription=self.rx).exists())

    def test_combined_file_limit_is_enforced(self):
        uploads = [SimpleUploadedFile(f'extra-{i}.pdf', b'%PDF-1.4', content_type='application/pdf') for i in range(5)]
        response = self.client.patch(self.url, {**self.payload, 'files': uploads}, format='multipart')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.rx.files.count(), 1)

    def test_patient_edit_clears_previous_authenticity_verification(self):
        Prescription.objects.filter(pk=self.rx.pk).update(verified_by=self.other, verified_at=timezone.now(), authenticity_method='old', authenticity_evidence='old', prescriber_verification_reference='old')
        response = self.client.patch(self.url, self.payload, format='multipart')
        self.assertEqual(response.status_code, 200, response.data)
        self.rx.refresh_from_db()
        self.assertIsNone(self.rx.verified_by_id)
        self.assertIsNone(self.rx.verified_at)
        self.assertEqual(self.rx.authenticity_evidence, '')
