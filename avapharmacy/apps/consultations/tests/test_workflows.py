import importlib.util

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.consultations.models import (
    ConsultationAuditLog,
    ClinicianEarning,
    ClinicianPrescription,
    ClinicianProfile,
    Consultation,
    ConsultationPaymentIntent,
)
from apps.consultations.serializers import ConsultationCreateSerializer
from apps.notifications.models import Notification
from apps.prescriptions.models import Prescription
from apps.products.models import Product, Variant, VariantInventory


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
        self.doctor.status = ClinicianProfile.STATUS_ACTIVE
        self.doctor.save(update_fields=['status', 'updated_at'])
        self.client.force_authenticate(self.doctor_user)
        message_response = self.client.post(
            reverse('consultation-messages', args=[self.consultation.id]),
            {'message': 'Please rest and hydrate.', 'message_type': 'text'},
            format='json',
        )
        self.assertEqual(message_response.status_code, 201, message_response.content)

        list_response = self.client.get(reverse('consultation-messages', args=[self.consultation.id]))
        self.assertEqual(list_response.status_code, 200)

        end_response = self.client.post(reverse('consultation-end', args=[self.consultation.id]), format='json')
        self.assertEqual(end_response.status_code, 200)
        self.assertTrue(ClinicianEarning.objects.filter(consultation=self.consultation).exists())

        prescription = ClinicianPrescription.objects.create(
            clinician=self.doctor,
            consultation=self.consultation,
            patient_name=self.patient.full_name,
            items=[{'drug_name': 'Ibuprofen', 'dose': '400mg', 'frequency': 'twice daily', 'quantity': 10, 'catalog_fallback': True}],
        )
        send_response = self.client.post(reverse('doctor-prescription-send', args=[prescription.id]), format='json')
        self.assertEqual(send_response.status_code, 200)
        self.assertTrue(Prescription.objects.filter(clinician_prescription=prescription, source=Prescription.SOURCE_E_PRESCRIPTION).exists())

        self.client.force_authenticate(self.patient)
        detail_response = self.client.get(reverse('consultation-detail', args=[self.consultation.id]))
        self.assertEqual(detail_response.status_code, 200)
        self.assertEqual(detail_response.data['prescriptions'][0]['reference'], prescription.reference)
        self.assertEqual(detail_response.data['prescriptions'][0]['items_count'], 1)
        self.assertTrue(ConsultationAuditLog.objects.filter(
            consultation=self.consultation,
            actor=self.patient,
            action=ConsultationAuditLog.ACTION_VIEW_DETAIL,
        ).exists())
        self.assertTrue(Notification.objects.filter(
            recipient=self.patient,
            type='prescription_status',
            data__sensitive=True,
        ).exists())

        self.client.force_authenticate(self.doctor_user)
        pdf_response = self.client.get(reverse('doctor-prescription-pdf', args=[prescription.id]))
        if importlib.util.find_spec('reportlab'):
            self.assertEqual(pdf_response.status_code, 200)
            self.assertEqual(pdf_response['Content-Type'], 'application/pdf')
        else:
            self.assertEqual(pdf_response.status_code, 503)

    def test_doctor_cannot_access_another_doctors_consultation_detail(self):
        self.doctor.status = ClinicianProfile.STATUS_ACTIVE
        self.doctor.save(update_fields=['status', 'updated_at'])
        other_doctor_user = User.objects.create_user(
            email='other-confidential-doctor@example.com',
            password='testpass123',
            first_name='Other',
            last_name='Doctor',
            role=User.DOCTOR,
            phone='0711111199',
        )
        ClinicianProfile.objects.create(
            provider_type=ClinicianProfile.TYPE_DOCTOR,
            user=other_doctor_user,
            name='Dr Other Confidential',
            specialty='General Practice',
            email=other_doctor_user.email,
            phone=other_doctor_user.phone,
            license_number='KMD-2999',
            status=ClinicianProfile.STATUS_ACTIVE,
        )

        self.client.force_authenticate(other_doctor_user)
        detail_response = self.client.get(reverse('consultation-detail', args=[self.consultation.id]))
        self.assertEqual(detail_response.status_code, 404)

        update_response = self.client.patch(
            reverse('consultation-detail', args=[self.consultation.id]),
            {'status': Consultation.STATUS_COMPLETED},
            format='json',
        )
        self.assertEqual(update_response.status_code, 404)

    def test_consultation_attachments_are_served_through_protected_endpoint(self):
        self.doctor.status = ClinicianProfile.STATUS_ACTIVE
        self.doctor.save(update_fields=['status', 'updated_at'])
        self.client.force_authenticate(self.patient)
        upload_response = self.client.post(
            reverse('consultation-messages', args=[self.consultation.id]),
            {
                'message': 'Attached file',
                'message_type': 'file',
                'attachment': SimpleUploadedFile('symptom-note.txt', b'private note', content_type='text/plain'),
            },
            format='multipart',
        )
        self.assertEqual(upload_response.status_code, 201, upload_response.content)
        self.assertIn('/consultations/messages/', upload_response.data['attachment_url'])
        self.assertNotIn('/media/', upload_response.data['attachment_url'])

        message_id = upload_response.data['id']
        self.client.force_authenticate(self.doctor_user)
        attachment_response = self.client.get(reverse('consultation-message-attachment', args=[message_id]))
        self.assertEqual(attachment_response.status_code, 200)
        self.assertTrue(ConsultationAuditLog.objects.filter(
            consultation=self.consultation,
            actor=self.doctor_user,
            action=ConsultationAuditLog.ACTION_DOWNLOAD_ATTACHMENT,
        ).exists())

        other_doctor_user = User.objects.create_user(
            email='attachment-other-doctor@example.com',
            password='testpass123',
            first_name='Attachment',
            last_name='Doctor',
            role=User.DOCTOR,
            phone='0711111188',
        )
        ClinicianProfile.objects.create(
            provider_type=ClinicianProfile.TYPE_DOCTOR,
            user=other_doctor_user,
            name='Dr Attachment Other',
            specialty='General Practice',
            email=other_doctor_user.email,
            phone=other_doctor_user.phone,
            license_number='KMD-2888',
            status=ClinicianProfile.STATUS_ACTIVE,
        )
        self.client.force_authenticate(other_doctor_user)
        denied_response = self.client.get(reverse('consultation-message-attachment', args=[message_id]))
        self.assertEqual(denied_response.status_code, 404)

    def test_doctor_prescription_items_use_catalog_variants(self):
        self.doctor.status = ClinicianProfile.STATUS_ACTIVE
        self.doctor.save(update_fields=['status', 'updated_at'])
        product = Product.objects.create(
            name='Amoxicillin',
            sku='AMOX-CAT',
            slug='amoxicillin-cat',
            is_active=True,
        )
        variant = Variant.objects.create(
            product=product,
            sku='AMOX-CAT-500',
            name='500mg capsules',
            price='120.00',
            requires_prescription=True,
            is_active=True,
        )
        VariantInventory.objects.update_or_create(
            variant=variant,
            location=Product.STOCK_BRANCH,
            defaults={
                'stock_quantity': 8,
                'low_stock_threshold': 2,
            },
        )

        self.client.force_authenticate(self.doctor_user)
        search_response = self.client.get(reverse('doctor-catalog-variants'), {'q': 'amox'})
        self.assertEqual(search_response.status_code, 200)
        self.assertEqual(search_response.data['results'][0]['id'], variant.id)

        create_response = self.client.post(
            reverse('doctor-prescriptions'),
            {
                'consultation': self.consultation.id,
                'patient_name': self.patient.full_name,
                'items': [{
                    'variant_id': variant.id,
                    'dose': '500mg',
                    'frequency': 'three times daily',
                    'duration': '5 days',
                    'quantity': 2,
                }],
            },
            format='json',
        )
        self.assertEqual(create_response.status_code, 201, create_response.content)
        self.assertEqual(create_response.data['items'][0]['variant_id'], variant.id)
        self.assertEqual(create_response.data['items'][0]['product_id'], product.id)

        prescription = ClinicianPrescription.objects.get(pk=create_response.data['id'])
        send_response = self.client.post(reverse('doctor-prescription-send', args=[prescription.id]), format='json')
        self.assertEqual(send_response.status_code, 200)
        dispensing_item = Prescription.objects.get(clinician_prescription=prescription).items.get()
        self.assertEqual(dispensing_item.product_id, product.id)
        self.assertEqual(dispensing_item.variant_id, variant.id)

        bad_response = self.client.post(
            reverse('doctor-prescriptions'),
            {
                'consultation': self.consultation.id,
                'patient_name': self.patient.full_name,
                'items': [{
                    'variant_id': variant.id,
                    'dose': '500mg',
                    'frequency': 'three times daily',
                    'quantity': 99,
                }],
            },
            format='json',
        )
        self.assertEqual(bad_response.status_code, 400)

    def test_paid_consultation_finalize_requires_successful_payment(self):
        self.doctor.status = ClinicianProfile.STATUS_ACTIVE
        self.doctor.consult_fee = '500.00'
        self.doctor.save(update_fields=['status', 'consult_fee', 'updated_at'])
        self.client.force_authenticate(self.patient)

        intent = ConsultationPaymentIntent.objects.create(
            initiated_by=self.patient,
            clinician=self.doctor,
            provider=ConsultationPaymentIntent.PROVIDER_PAYBILL,
            status=ConsultationPaymentIntent.STATUS_REQUIRES_ACTION,
            amount='500.00',
            consultation_payload={
                'doctor': self.doctor.id,
                'patient_name': self.patient.full_name,
                'patient_email': self.patient.email,
                'patient_phone': self.patient.phone,
                'issue': 'Headache and fever',
                'priority': Consultation.PRIORITY_ROUTINE,
            },
        )

        unpaid_response = self.client.post(
            reverse('consultation-payment-finalize'),
            {'payment_intent_id': intent.id},
            format='json',
        )
        self.assertEqual(unpaid_response.status_code, 402)

        intent.status = ConsultationPaymentIntent.STATUS_SUCCEEDED
        intent.provider_reference = 'RG123ABC'
        intent.save(update_fields=['status', 'provider_reference', 'updated_at'])

        paid_response = self.client.post(
            reverse('consultation-payment-finalize'),
            {'payment_intent_id': intent.id},
            format='json',
        )
        self.assertEqual(paid_response.status_code, 201)
        intent.refresh_from_db()
        self.assertIsNotNone(intent.consultation_id)
        self.assertEqual(intent.consultation.patient, self.patient)

    def test_customer_books_paid_doctor_consultation_chat_and_doctor_prescribes(self):
        self.doctor.status = ClinicianProfile.STATUS_ACTIVE
        self.doctor.consult_fee = '1.00'
        self.doctor.save(update_fields=['status', 'consult_fee', 'updated_at'])
        product = Product.objects.create(
            name='Doctor Flow Amoxicillin',
            sku='DOC-FLOW-AMOX',
            slug='doctor-flow-amoxicillin',
            is_active=True,
        )
        variant = Variant.objects.create(
            product=product,
            sku='DOC-FLOW-AMOX-500',
            name='500mg capsules',
            price='150.00',
            requires_prescription=True,
            is_active=True,
        )
        VariantInventory.objects.update_or_create(
            variant=variant,
            location=Product.STOCK_BRANCH,
            defaults={'stock_quantity': 6, 'low_stock_threshold': 2},
        )

        self.client.force_authenticate(self.patient)
        blocked_response = self.client.post(
            reverse('consultations'),
            {
                'doctor': self.doctor.id,
                'patient_name': self.patient.full_name,
                'patient_age': 32,
                'issue': 'Sore throat and fever',
                'priority': Consultation.PRIORITY_ROUTINE,
            },
            format='json',
        )
        self.assertEqual(blocked_response.status_code, 402)

        intent = ConsultationPaymentIntent.objects.create(
            initiated_by=self.patient,
            clinician=self.doctor,
            provider=ConsultationPaymentIntent.PROVIDER_PAYBILL,
            status=ConsultationPaymentIntent.STATUS_SUCCEEDED,
            amount='1.00',
            consultation_payload={
                'doctor': self.doctor.id,
                'patient_name': self.patient.full_name,
                'patient_email': self.patient.email,
                'patient_phone': self.patient.phone,
                'patient_age': 32,
                'issue': 'Sore throat and fever',
                'priority': Consultation.PRIORITY_ROUTINE,
            },
        )
        create_response = self.client.post(
            reverse('consultations'),
            {
                'payment_intent_id': intent.id,
                'doctor': self.doctor.id,
                'patient_name': self.patient.full_name,
                'patient_age': 32,
                'issue': 'Sore throat and fever',
                'priority': Consultation.PRIORITY_ROUTINE,
            },
            format='json',
        )
        self.assertEqual(create_response.status_code, 201, create_response.content)
        consultation_id = create_response.data['id']
        intent.refresh_from_db()
        self.assertEqual(intent.consultation_id, consultation_id)

        patient_message = self.client.post(
            reverse('consultation-messages', args=[consultation_id]),
            {'message': 'I also have chills.', 'message_type': 'text'},
            format='json',
        )
        self.assertEqual(patient_message.status_code, 201, patient_message.content)

        self.client.force_authenticate(self.doctor_user)
        doctor_message = self.client.post(
            reverse('consultation-messages', args=[consultation_id]),
            {'message': 'I will prescribe an antibiotic course.', 'message_type': 'text'},
            format='json',
        )
        self.assertEqual(doctor_message.status_code, 201, doctor_message.content)

        prescription_response = self.client.post(
            reverse('doctor-prescriptions'),
            {
                'consultation': consultation_id,
                'patient_name': self.patient.full_name,
                'items': [{
                    'variant_id': variant.id,
                    'dose': '500mg',
                    'frequency': 'twice daily',
                    'duration': '5 days',
                    'quantity': 2,
                }],
                'notes': 'Complete the course.',
            },
            format='json',
        )
        self.assertEqual(prescription_response.status_code, 201, prescription_response.content)
        prescription = ClinicianPrescription.objects.get(pk=prescription_response.data['id'])
        send_response = self.client.post(reverse('doctor-prescription-send', args=[prescription.id]), format='json')
        self.assertEqual(send_response.status_code, 200, send_response.content)

        dispensing_rx = Prescription.objects.get(clinician_prescription=prescription)
        self.assertEqual(dispensing_rx.status, Prescription.STATUS_APPROVED)
        self.assertEqual(dispensing_rx.items.get().variant_id, variant.id)
        self.assertTrue(Notification.objects.filter(
            recipient=self.patient,
            type='prescription_status',
            data__prescription_id=dispensing_rx.id,
        ).exists())

    def test_customer_books_paid_pediatrician_consultation_and_chat(self):
        pediatrician_user = User.objects.create_user(
            email='pediatric-flow-user@example.com',
            password='testpass123',
            first_name='Pediatric',
            last_name='Clinician',
            role=User.PEDIATRICIAN,
            phone='0711111133',
        )
        pediatrician = ClinicianProfile.objects.create(
            provider_type=ClinicianProfile.TYPE_PEDIATRICIAN,
            user=pediatrician_user,
            name='Dr Pediatric Flow',
            specialty='Paediatrics',
            email=pediatrician_user.email,
            phone=pediatrician_user.phone,
            license_number='PED-FLOW-001',
            status=ClinicianProfile.STATUS_ACTIVE,
            consult_fee='1.00',
        )
        self.client.force_authenticate(self.patient)
        intent = ConsultationPaymentIntent.objects.create(
            initiated_by=self.patient,
            clinician=pediatrician,
            provider=ConsultationPaymentIntent.PROVIDER_PAYBILL,
            status=ConsultationPaymentIntent.STATUS_SUCCEEDED,
            amount='1.00',
            consultation_payload={
                'pediatrician': pediatrician.id,
                'patient_name': self.patient.full_name,
                'patient_email': self.patient.email,
                'patient_phone': self.patient.phone,
                'issue': 'Child has fever',
                'priority': Consultation.PRIORITY_ROUTINE,
                'is_pediatric': True,
                'guardian_name': self.patient.full_name,
                'child_name': 'Flow Child',
                'child_age': 6,
                'weight_kg': '21.50',
            },
        )
        finalize_response = self.client.post(
            reverse('consultation-payment-finalize'),
            {'payment_intent_id': intent.id},
            format='json',
        )
        self.assertEqual(finalize_response.status_code, 201, finalize_response.content)
        self.assertTrue(finalize_response.data['is_pediatric'])
        self.assertEqual(finalize_response.data['pediatrician'], pediatrician.id)
        consultation_id = finalize_response.data['id']

        guardian_message = self.client.post(
            reverse('consultation-messages', args=[consultation_id]),
            {'message': 'The fever started last night.', 'message_type': 'text'},
            format='json',
        )
        self.assertEqual(guardian_message.status_code, 201, guardian_message.content)

        self.client.force_authenticate(pediatrician_user)
        pediatrician_message = self.client.post(
            reverse('consultation-messages', args=[consultation_id]),
            {'message': 'Please keep the child hydrated while I review symptoms.', 'message_type': 'text'},
            format='json',
        )
        self.assertEqual(pediatrician_message.status_code, 201, pediatrician_message.content)
        dashboard_response = self.client.get(reverse('doctor-consultations'))
        self.assertEqual(dashboard_response.status_code, 200)
        results = dashboard_response.data.get('results', dashboard_response.data)
        self.assertTrue(any(item['id'] == consultation_id for item in results))

    def test_consultation_create_auto_routes_doctor_by_specialty_without_patient_selection(self):
        self.doctor.status = ClinicianProfile.STATUS_ACTIVE
        self.doctor.specialty = 'Dermatology'
        self.doctor.consult_fee = '500.00'
        self.doctor.save(update_fields=['status', 'specialty', 'consult_fee', 'updated_at'])
        cardiology_user = User.objects.create_user(
            email='cardiology-routing@example.com',
            password='testpass123',
            first_name='Cardio',
            last_name='Route',
            role=User.DOCTOR,
            phone='0711111122',
        )
        cardiology_doctor = ClinicianProfile.objects.create(
            provider_type=ClinicianProfile.TYPE_DOCTOR,
            user=cardiology_user,
            name='Dr Cardiology Route',
            specialty='Cardiology',
            email=cardiology_user.email,
            phone=cardiology_user.phone,
            license_number='KMD-2010',
            status=ClinicianProfile.STATUS_ACTIVE,
            consult_fee='500.00',
        )

        specialty_serializer = ConsultationCreateSerializer(data={
            'patient_name': self.patient.full_name,
            'patient_email': self.patient.email,
            'patient_phone': self.patient.phone,
            'issue': 'Rash on arm\n\nPreferred specialty: Dermatology',
            'priority': Consultation.PRIORITY_ROUTINE,
        })
        self.assertTrue(specialty_serializer.is_valid(), specialty_serializer.errors)
        self.assertEqual(specialty_serializer.validated_data['clinician'], self.doctor)

        general_serializer = ConsultationCreateSerializer(data={
            'patient_name': self.patient.full_name,
            'patient_email': self.patient.email,
            'patient_phone': self.patient.phone,
            'issue': 'General body weakness',
            'priority': Consultation.PRIORITY_ROUTINE,
        })
        self.assertTrue(general_serializer.is_valid(), general_serializer.errors)
        self.assertIn(general_serializer.validated_data['clinician'], {self.doctor, cardiology_doctor})

    def test_new_consultation_notifications_are_routed_by_specialty(self):
        self.doctor.status = ClinicianProfile.STATUS_ACTIVE
        self.doctor.specialty = 'Dermatology'
        self.doctor.save(update_fields=['status', 'specialty', 'updated_at'])
        cardiology_user = User.objects.create_user(
            email='cardiology-doctor@example.com',
            password='testpass123',
            first_name='Cardio',
            last_name='Doctor',
            role=User.DOCTOR,
            phone='0711111112',
        )
        cardiology_doctor = ClinicianProfile.objects.create(
            provider_type=ClinicianProfile.TYPE_DOCTOR,
            user=cardiology_user,
            name='Dr Cardiology',
            specialty='Cardiology',
            email=cardiology_user.email,
            phone=cardiology_user.phone,
            license_number='KMD-2001',
            status=ClinicianProfile.STATUS_ACTIVE,
            consult_fee='500.00',
        )

        self.client.force_authenticate(self.patient)
        specialty_intent = ConsultationPaymentIntent.objects.create(
            initiated_by=self.patient,
            clinician=self.doctor,
            provider=ConsultationPaymentIntent.PROVIDER_PAYBILL,
            status=ConsultationPaymentIntent.STATUS_SUCCEEDED,
            amount='500.00',
            consultation_payload={
                'doctor': self.doctor.id,
                'patient_name': self.patient.full_name,
                'patient_email': self.patient.email,
                'patient_phone': self.patient.phone,
                'issue': 'Rash on arm\n\nPreferred specialty: Dermatology',
                'priority': Consultation.PRIORITY_ROUTINE,
            },
        )
        self.client.post(
            reverse('consultation-payment-finalize'),
            {'payment_intent_id': specialty_intent.id},
            format='json',
        )
        self.assertTrue(Notification.objects.filter(recipient=self.doctor_user, type='new_consultation').exists())
        self.assertFalse(Notification.objects.filter(recipient=cardiology_user, type='new_consultation').exists())

        Notification.objects.filter(type='new_consultation').delete()
        general_intent = ConsultationPaymentIntent.objects.create(
            initiated_by=self.patient,
            clinician=cardiology_doctor,
            provider=ConsultationPaymentIntent.PROVIDER_PAYBILL,
            status=ConsultationPaymentIntent.STATUS_SUCCEEDED,
            amount='500.00',
            consultation_payload={
                'doctor': cardiology_doctor.id,
                'patient_name': self.patient.full_name,
                'patient_email': self.patient.email,
                'patient_phone': self.patient.phone,
                'issue': 'General body weakness',
                'priority': Consultation.PRIORITY_ROUTINE,
            },
        )
        self.client.post(
            reverse('consultation-payment-finalize'),
            {'payment_intent_id': general_intent.id},
            format='json',
        )
        notified = set(Notification.objects.filter(type='new_consultation').values_list('recipient__email', flat=True))
        self.assertEqual(notified, {self.doctor_user.email, cardiology_user.email})
