from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase
from apps.accounts.models import User
from apps.consultations.models import ClinicianProfile, Consultation
from apps.lab.models import LabRequest
from avapharmacy.test_compliance_fixtures import clinician_fixture
from . import test_workflow_security as fixtures


class ClinicianLabOrderTests(APITestCase):
    setUp = fixtures.LabWorkflowSecurityTests.setUp
    make_user = staticmethod(fixtures.LabWorkflowSecurityTests.make_user)
    authenticate = fixtures.LabWorkflowSecurityTests.authenticate

    def consultation(self, role='doctor', status='in_progress'):
        doctor = self.make_user(f'{role}@clinic.example.com', role)
        profile = ClinicianProfile.objects.create(user=doctor, provider_type=role, status='active', name='Test Clinician', email=doctor.email, **clinician_fixture())
        return doctor, Consultation.objects.create(clinician=profile, patient=self.patient, patient_name='Patient One', patient_phone='0711111111', status=status)

    def test_customer_and_admin_cannot_create_lab_orders(self):
        for user in (self.patient, self.admin):
            self.authenticate(user)
            self.assertEqual(self.client.post(reverse('lab-requests'), {'test': self.test.pk}).status_code, 403)

    def test_doctor_and_paediatrician_order_for_consultation_patient(self):
        for role in ('doctor', 'pediatrician'):
            doctor, consultation = self.consultation(role)
            self.authenticate(doctor)
            response = self.client.post(reverse('lab-requests'), {'test': self.test.pk, 'consultation': consultation.pk, 'assigned_partner': self.partner.pk, 'channel': 'walk_in'}, format='json')
            self.assertEqual(response.status_code, 201, response.data)
            order = LabRequest.objects.get(pk=response.data['id'])
            self.assertEqual(order.patient, self.patient)
            self.assertEqual(order.assigned_partner, self.partner)
            self.assertIsNone(order.laboratory)
            self.assertEqual(order.consultation, consultation)
            self.assertEqual(order.patient_name, 'Patient One')

    def test_clinician_cannot_order_for_someone_elses_consultation(self):
        _, consultation = self.consultation()
        other, _ = self.consultation('pediatrician')
        self.authenticate(other)
        response = self.client.post(reverse('lab-requests'), {'test': self.test.pk, 'consultation': consultation.pk, 'assigned_partner': self.partner.pk, 'channel': 'walk_in'}, format='json')
        self.assertEqual(response.status_code, 400)

    def test_walk_in_samples_can_be_received_without_ava_dispatch(self):
        self.request.channel = 'walk_in'
        self.request.status = 'awaiting_sample'
        self.request.save()
        self.authenticate(self.partner_user)
        response = self.client.post(reverse('lab-samples-received', args=[self.request.pk]))
        self.assertEqual(response.status_code, 200, response.data)
        self.request.refresh_from_db()
        self.assertEqual(self.request.status, 'sample_received')
        self.authenticate(self.technician)
        response = self.client.patch(reverse('lab-request-update', args=[self.request.pk]), {'status': 'processing'}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
