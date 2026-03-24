import importlib.util

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.consultations.models import ClinicianEarning, ClinicianPrescription, ClinicianProfile, Consultation
from apps.prescriptions.models import Prescription


class ConsultationWorkflowTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_user(
            email='consult-admin2@example.com',
            password='testpass123',
            first_name='Consult',
            last_name='Admin',
            role=User.ADMIN,
            is_staff=True,
        )
        self.doctor_user = User.objects.create_user(
            email='doctor-user@example.com',
            password='testpass123',
            first_name='Doctor',
            last_name='User',
            role=User.DOCTOR,
            phone='0711111111',
        )
        self.patient = User.objects.create_user(
            email='consult-patient@example.com',
            password='testpass123',
            first_name='Consult',
            last_name='Patient',
            role=User.CUSTOMER,
        )
        self.doctor = ClinicianProfile.objects.create(
            provider_type=ClinicianProfile.TYPE_DOCTOR,
            user=self.doctor_user,
            name='Dr Workflow',
            specialty='General Practice',
            email=self.doctor_user.email,
            phone=self.doctor_user.phone,
            license_number='KMD-2000',
            status=ClinicianProfile.STATUS_PENDING,
        )
        self.consultation = Consultation.objects.create(
            clinician=self.doctor,
            patient=self.patient,
            patient_name=self.patient.full_name,
            issue='Back pain',
            status=Consultation.STATUS_IN_PROGRESS,
        )

    def test_doctor_onboarding_steps_and_admin_verify_suspend(self):
        self.client.force_authenticate(self.doctor_user)

        profile_response = self.client.patch(
            reverse('doctor-onboarding-profile'),
            {'name': 'Dr Workflow Updated', 'gender': 'female', 'bio': 'GP'},
            format='json',
        )
        self.assertEqual(profile_response.status_code, 200)

        documents_response = self.client.post(
            reverse('doctor-onboarding-documents'),
            {
                'medical_license_number': 'KMD-3000',
                'specialty': 'Family Medicine',
                'years_of_experience': 8,
                'documents': [SimpleUploadedFile('license.pdf', b'pdf', content_type='application/pdf')],
            },
            format='multipart',
        )
        self.assertEqual(documents_response.status_code, 201)

        availability_response = self.client.patch(
            reverse('doctor-onboarding-availability'),
            {
                'consult_fee': '1500.00',
                'currency': 'KES',
                'availability_schedule': [{'day': 'Mon', 'start_time': '08:00', 'end_time': '17:00'}],
            },
            format='json',
        )
        self.assertEqual(availability_response.status_code, 200)

        payout_response = self.client.patch(
            reverse('doctor-onboarding-payout'),
            {'payout_method': 'mpesa', 'payout_account_number': '254700000000'},
            format='json',
        )
        self.assertEqual(payout_response.status_code, 200)

        self.client.force_authenticate(self.admin)
        verify_response = self.client.post(reverse('admin-doctor-verify', args=[self.doctor.id]), format='json')
        self.assertEqual(verify_response.status_code, 200)
        suspend_response = self.client.post(
            reverse('admin-doctor-suspend', args=[self.doctor.id]),
            {'reason': 'Compliance review'},
            format='json',
        )
        self.assertEqual(suspend_response.status_code, 200)

    def test_consultation_messages_end_and_send_prescription(self):
        self.client.force_authenticate(self.doctor_user)
        message_response = self.client.post(
            reverse('consultation-messages', args=[self.consultation.id]),
            {'message': 'Please rest and hydrate.', 'message_type': 'text'},
            format='json',
        )
        self.assertEqual(message_response.status_code, 201)

        list_response = self.client.get(reverse('consultation-messages', args=[self.consultation.id]))
        self.assertEqual(list_response.status_code, 200)

        end_response = self.client.post(reverse('consultation-end', args=[self.consultation.id]), format='json')
        self.assertEqual(end_response.status_code, 200)
        self.assertTrue(ClinicianEarning.objects.filter(consultation=self.consultation).exists())

        prescription = ClinicianPrescription.objects.create(
            clinician=self.doctor,
            consultation=self.consultation,
            patient_name=self.patient.full_name,
            items=[{'drug_name': 'Ibuprofen', 'dose': '400mg', 'frequency': 'twice daily', 'quantity': 10}],
        )
        send_response = self.client.post(reverse('doctor-prescription-send', args=[prescription.id]), format='json')
        self.assertEqual(send_response.status_code, 200)
        self.assertTrue(Prescription.objects.filter(clinician_prescription=prescription, source=Prescription.SOURCE_E_PRESCRIPTION).exists())

        pdf_response = self.client.get(reverse('doctor-prescription-pdf', args=[prescription.id]))
        if importlib.util.find_spec('reportlab'):
            self.assertEqual(pdf_response.status_code, 200)
            self.assertEqual(pdf_response['Content-Type'], 'application/pdf')
        else:
            self.assertEqual(pdf_response.status_code, 503)
