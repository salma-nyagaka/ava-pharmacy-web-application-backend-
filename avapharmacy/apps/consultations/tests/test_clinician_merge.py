from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.consultations.models import ClinicianProfile, Consultation, ConsultationPaymentIntent


class ClinicianMergeCompatibilityTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_user(
            email='consult-admin@example.com',
            password='Testpass123!',
            first_name='Admin',
            last_name='Consult',
            role=User.ADMIN,
            is_staff=True,
        )
        self.patient = User.objects.create_user(
            email='patient@example.com',
            password='Testpass123!',
            first_name='Patient',
            last_name='User',
            role=User.CUSTOMER,
        )

    def test_doctor_onboarding_creates_unified_clinician_profile(self):
        response = self.client.post(
            reverse('doctor-register'),
            {
                'name': 'Dr Test Kariuki',
                'specialty': 'General Practice',
                'email': 'doctor-onboard@example.com',
                'phone': '0712345000',
                'license_number': 'KMD-90001',
                'facility': 'City Clinic',
                'background_consent': 'true',
                'compliance_declaration': 'true',
                'agreed_to_terms': 'true',
            },
            format='multipart',
        )

        self.assertEqual(response.status_code, 201)
        clinician = ClinicianProfile.objects.get(email='doctor-onboard@example.com')
        self.assertEqual(clinician.provider_type, ClinicianProfile.TYPE_DOCTOR)
        self.assertEqual(clinician.status, ClinicianProfile.STATUS_PENDING)

    def test_doctor_detail_resolves_legacy_doctor_identifier(self):
        clinician = ClinicianProfile.objects.create(
            provider_type=ClinicianProfile.TYPE_DOCTOR,
            legacy_doctor_id=77,
            name='Dr Legacy',
            specialty='Family Medicine',
            email='legacy-doctor@example.com',
            phone='0712000001',
            license_number='KMD-77000',
            status=ClinicianProfile.STATUS_ACTIVE,
        )

        response = self.client.get(reverse('doctor-detail', args=[77]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['id'], clinician.id)
        self.assertEqual(response.data['type'], ClinicianProfile.TYPE_DOCTOR)

    def test_pediatrician_detail_resolves_legacy_pediatrician_identifier(self):
        clinician = ClinicianProfile.objects.create(
            provider_type=ClinicianProfile.TYPE_PEDIATRICIAN,
            legacy_pediatrician_id=88,
            name='Dr Legacy Child',
            specialty='Pediatrics',
            email='legacy-ped@example.com',
            phone='0712000002',
            license_number='KMD-88000',
            status=ClinicianProfile.STATUS_ACTIVE,
        )

        response = self.client.get(reverse('pediatrician-detail', args=[88]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['id'], clinician.id)
        self.assertEqual(response.data['specialty'], 'Pediatrics')

    def test_consultation_create_uses_unified_clinician_from_legacy_identifier(self):
        clinician = ClinicianProfile.objects.create(
            provider_type=ClinicianProfile.TYPE_DOCTOR,
            legacy_doctor_id=101,
            name='Dr Consultation',
            specialty='Internal Medicine',
            email='consultation-doctor@example.com',
            phone='0712000003',
            license_number='KMD-10100',
            status=ClinicianProfile.STATUS_ACTIVE,
        )
        self.client.force_authenticate(self.patient)
        intent = ConsultationPaymentIntent.objects.create(
            initiated_by=self.patient,
            clinician=clinician,
            provider=ConsultationPaymentIntent.PROVIDER_PAYBILL,
            status=ConsultationPaymentIntent.STATUS_SUCCEEDED,
            amount='1.00',
            consultation_payload={
                'doctor': 101,
                'patient_name': 'Patient User',
                'patient_age': 30,
                'issue': 'Recurring headaches',
                'priority': Consultation.PRIORITY_ROUTINE,
            },
            processed_at=None,
        )

        response = self.client.post(
            reverse('consultations'),
            {
                'doctor': 101,
                'payment_intent_id': intent.id,
                'patient_name': 'Patient User',
                'patient_age': 30,
                'issue': 'Recurring headaches',
                'priority': Consultation.PRIORITY_ROUTINE,
            },
            format='json',
        )

        self.assertEqual(response.status_code, 201)
        consultation = Consultation.objects.get(patient=self.patient)
        self.assertEqual(consultation.clinician_id, clinician.id)
        self.assertFalse(consultation.is_pediatric)

    def test_admin_doctor_and_pediatrician_detail_endpoints_use_unified_profiles(self):
        doctor = ClinicianProfile.objects.create(
            provider_type=ClinicianProfile.TYPE_DOCTOR,
            name='Admin Doctor',
            specialty='General Practice',
            email='admin-doctor@example.com',
            phone='0712000004',
            license_number='KMD-10200',
            status=ClinicianProfile.STATUS_PENDING,
        )
        pediatrician = ClinicianProfile.objects.create(
            provider_type=ClinicianProfile.TYPE_PEDIATRICIAN,
            name='Admin Pediatrician',
            specialty='Pediatrics',
            email='admin-pediatrician@example.com',
            phone='0712000005',
            license_number='KMD-10300',
            status=ClinicianProfile.STATUS_PENDING,
        )
        self.client.force_authenticate(self.admin)

        doctor_response = self.client.get(reverse('admin-doctor-detail', args=[doctor.id]))
        pediatrician_response = self.client.get(reverse('admin-pediatrician-detail', args=[pediatrician.id]))

        self.assertEqual(doctor_response.status_code, 200)
        self.assertEqual(pediatrician_response.status_code, 200)
        self.assertEqual(doctor_response.data['id'], doctor.id)
        self.assertEqual(pediatrician_response.data['id'], pediatrician.id)

    def test_user_can_own_multiple_clinician_profiles(self):
        clinician_user = User.objects.create_user(
            email='multi-clinician@example.com',
            password='Testpass123!',
            first_name='Multi',
            last_name='Clinician',
            role=User.DOCTOR,
        )
        doctor = ClinicianProfile.objects.create(
            user=clinician_user,
            provider_type=ClinicianProfile.TYPE_DOCTOR,
            name='Dr Multi Clinician',
            specialty='General Practice',
            email='multi-doctor@example.com',
            phone='0712000006',
            license_number='KMD-10400',
            status=ClinicianProfile.STATUS_ACTIVE,
        )
        pediatrician = ClinicianProfile.objects.create(
            user=clinician_user,
            provider_type=ClinicianProfile.TYPE_PEDIATRICIAN,
            name='Dr Multi Clinician',
            specialty='Pediatrics',
            email='multi-pediatrician@example.com',
            phone='0712000007',
            license_number='KMD-10500',
            status=ClinicianProfile.STATUS_ACTIVE,
        )

        self.assertEqual(clinician_user.clinician_profiles.count(), 2)
        self.assertEqual(
            set(clinician_user.clinician_profiles.values_list('id', flat=True)),
            {doctor.id, pediatrician.id},
        )
