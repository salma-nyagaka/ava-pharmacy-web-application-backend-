import importlib.util

from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.models import Pharmacist, User
from apps.consultations.models import (
    ChildPatient,
    ConsultationAuditLog,
    ClinicianEarning,
    ClinicianPrescription,
    ClinicianProfile,
    Consultation,
    ConsultationPaymentIntent,
)
from apps.consultations.serializers import ConsultationCreateSerializer
from apps.notifications.models import Notification
from apps.orders.models import Order, OrderItem
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
        self.pharmacist_user = User.objects.create_user(
            email='consult-rx-pharmacist@example.com',
            password='testpass123',
            first_name='Review',
            last_name='Pharmacist',
            role=User.PHARMACIST,
            status=User.STATUS_ACTIVE,
            is_active=True,
        )
        Pharmacist.objects.create(
            user=self.pharmacist_user,
            license_number='RX-CONSULT-001',
            permissions=[Pharmacist.PERMISSION_PRESCRIPTION_REVIEW],
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

        queue_response = self.client.get(reverse('doctor-consultations'))
        self.assertEqual(queue_response.status_code, 200)
        queue_rows = queue_response.data.get('results', queue_response.data) if isinstance(queue_response.data, dict) else queue_response.data
        queue_record = next(row for row in queue_rows if row['id'] == self.consultation.id)
        self.assertEqual(queue_record['doctor'], self.doctor.id)
        self.assertEqual(queue_record['messages'][0]['message'], 'Please rest and hydrate.')

        end_response = self.client.post(reverse('consultation-end', args=[self.consultation.id]), format='json')
        self.assertEqual(end_response.status_code, 200)
        self.assertTrue(ClinicianEarning.objects.filter(consultation=self.consultation).exists())

        prescription = ClinicianPrescription.objects.create(
            clinician=self.doctor,
            consultation=self.consultation,
            patient_name=self.patient.full_name,
            items=[{'drug_name': 'Ibuprofen', 'dose': '400mg', 'frequency': 'twice daily', 'quantity': 10, 'catalog_fallback': True}],
            notes='Take after meals and avoid if stomach irritation worsens.',
        )
        send_response = self.client.post(reverse('doctor-prescription-send', args=[prescription.id]), format='json')
        self.assertEqual(send_response.status_code, 200)
        self.assertTrue(Prescription.objects.filter(clinician_prescription=prescription, source=Prescription.SOURCE_E_PRESCRIPTION).exists())

        self.client.force_authenticate(self.patient)
        detail_response = self.client.get(reverse('consultation-detail', args=[self.consultation.id]))
        self.assertEqual(detail_response.status_code, 200)
        self.assertEqual(detail_response.data['prescriptions'][0]['reference'], prescription.reference)
        self.assertEqual(detail_response.data['prescriptions'][0]['items_count'], 1)
        self.assertEqual(detail_response.data['prescriptions'][0]['notes'], prescription.notes)
        self.assertEqual(detail_response.data['prescriptions'][0]['items'][0]['drug_name'], 'Ibuprofen')
        self.assertEqual(detail_response.data['prescriptions'][0]['items'][0]['dose'], '400mg')
        self.assertEqual(detail_response.data['prescriptions'][0]['items'][0]['frequency'], 'twice daily')
        self.assertEqual(detail_response.data['prescriptions'][0]['items'][0]['quantity'], 10)
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

    def test_doctor_prescription_edit_reuses_reference_and_replaces_items(self):
        self.doctor.status = ClinicianProfile.STATUS_ACTIVE
        self.doctor.save(update_fields=['status', 'updated_at'])
        product = Product.objects.create(
            name='Edit Safe Medicine',
            sku='EDIT-RX-MED',
            slug='edit-rx-med',
            is_active=True,
        )
        first_variant = Variant.objects.create(
            product=product,
            sku='EDIT-RX-MED-250',
            name='250mg',
            price='150.00',
            requires_prescription=True,
            is_active=True,
        )
        second_variant = Variant.objects.create(
            product=product,
            sku='EDIT-RX-MED-500',
            name='500mg',
            price='250.00',
            requires_prescription=True,
            is_active=True,
        )
        for variant in (first_variant, second_variant):
            VariantInventory.objects.update_or_create(
                variant=variant,
                location=Product.STOCK_BRANCH,
                defaults={'stock_quantity': 8, 'low_stock_threshold': 2},
            )

        self.client.force_authenticate(self.doctor_user)
        first_response = self.client.post(
            reverse('doctor-prescriptions'),
            {
                'consultation': self.consultation.id,
                'patient_name': self.patient.full_name,
                'items': [{
                    'variant_id': first_variant.id,
                    'dose': '250mg',
                    'frequency': 'once daily',
                    'quantity': 1,
                }],
            },
            format='json',
        )
        self.assertEqual(first_response.status_code, 201, first_response.content)

        second_response = self.client.post(
            reverse('doctor-prescriptions'),
            {
                'consultation': self.consultation.id,
                'patient_name': self.patient.full_name,
                'items': [{
                    'variant_id': second_variant.id,
                    'dose': '500mg',
                    'frequency': 'twice daily',
                    'quantity': 1,
                }],
            },
            format='json',
        )

        self.assertEqual(second_response.status_code, 201, second_response.content)
        self.assertEqual(second_response.data['id'], first_response.data['id'])
        self.assertEqual(second_response.data['reference'], first_response.data['reference'])
        prescription = ClinicianPrescription.objects.get(pk=first_response.data['id'])
        self.assertEqual(len(prescription.items), 1)
        self.assertEqual(prescription.items[0]['variant_id'], second_variant.id)
        self.assertEqual(ClinicianPrescription.objects.filter(consultation=self.consultation, clinician=self.doctor).count(), 1)

    def test_doctor_cannot_edit_prescription_after_customer_payment(self):
        self.doctor.status = ClinicianProfile.STATUS_ACTIVE
        self.doctor.save(update_fields=['status', 'updated_at'])
        product = Product.objects.create(
            name='Paid Locked Medicine',
            sku='PAID-RX-MED',
            slug='paid-rx-med',
            is_active=True,
        )
        variant = Variant.objects.create(
            product=product,
            sku='PAID-RX-MED-500',
            name='500mg',
            price='250.00',
            requires_prescription=True,
            is_active=True,
        )
        VariantInventory.objects.update_or_create(
            variant=variant,
            location=Product.STOCK_BRANCH,
            defaults={'stock_quantity': 8, 'low_stock_threshold': 2},
        )

        self.client.force_authenticate(self.doctor_user)
        create_response = self.client.post(
            reverse('doctor-prescriptions'),
            {
                'consultation': self.consultation.id,
                'patient_name': self.patient.full_name,
                'items': [{
                    'variant_id': variant.id,
                    'dose': '500mg',
                    'frequency': 'twice daily',
                    'quantity': 1,
                }],
            },
            format='json',
        )
        self.assertEqual(create_response.status_code, 201, create_response.content)
        prescription = ClinicianPrescription.objects.get(pk=create_response.data['id'])
        send_response = self.client.post(reverse('doctor-prescription-send', args=[prescription.id]), format='json')
        self.assertEqual(send_response.status_code, 200, send_response.content)
        dispensing_rx = Prescription.objects.get(clinician_prescription=prescription)
        dispensing_item = dispensing_rx.items.get()
        order = Order.objects.create(
            customer=self.patient,
            status=Order.STATUS_PAID,
            payment_status=Order.PAYMENT_STATUS_PAID,
            payment_method=Order.PAYMENT_MPESA_STK,
            shipping_first_name='Consult',
            shipping_last_name='Patient',
            shipping_email=self.patient.email,
            shipping_phone='0700000000',
            shipping_street='Test Street',
            shipping_city='Nairobi',
            shipping_county='Nairobi',
            subtotal='250.00',
            shipping_fee='0.00',
            total='250.00',
        )
        OrderItem.objects.create(
            order=order,
            variant=variant,
            product_name=product.name,
            product_sku=variant.sku,
            variant_name=variant.name,
            variant_sku=variant.sku,
            quantity=1,
            unit_price='250.00',
            prescription_reference=dispensing_rx.reference,
            prescription=dispensing_rx,
            prescription_item=dispensing_item,
        )

        edit_response = self.client.post(
            reverse('doctor-prescriptions'),
            {
                'consultation': self.consultation.id,
                'patient_name': self.patient.full_name,
                'items': [{
                    'variant_id': variant.id,
                    'dose': '500mg',
                    'frequency': 'nightly',
                    'quantity': 1,
                }],
            },
            format='json',
        )
        self.assertEqual(edit_response.status_code, 400)
        self.assertIn('already been paid', str(edit_response.data))

        resend_response = self.client.post(reverse('doctor-prescription-send', args=[prescription.id]), format='json')
        self.assertEqual(resend_response.status_code, 400)
        self.assertIn('already been paid', resend_response.data['detail'])

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

        with self.captureOnCommitCallbacks(execute=True):
            paid_response = self.client.post(
                reverse('consultation-payment-finalize'),
                {'payment_intent_id': intent.id},
                format='json',
            )
        self.assertEqual(paid_response.status_code, 201)
        intent.refresh_from_db()
        self.assertIsNotNone(intent.consultation_id)
        self.assertEqual(intent.consultation.patient, self.patient)
        self.assertIsNotNone(intent.receipt_emailed_at)
        self.assertTrue(any(intent.reference in message.subject for message in mail.outbox))

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
        self.assertEqual(dispensing_rx.status, Prescription.STATUS_PENDING)
        self.assertEqual(dispensing_rx.items.get().variant_id, variant.id)
        self.assertIsNone(dispensing_rx.pharmacist_id)

        self.client.force_authenticate(self.pharmacist_user)
        queue_response = self.client.get(reverse('pharmacist-prescriptions'), {'status': Prescription.STATUS_PENDING})
        self.assertEqual(queue_response.status_code, 200, queue_response.content)
        queue_rows = queue_response.data.get('results', queue_response.data)
        self.assertIn(dispensing_rx.id, [row['id'] for row in queue_rows])
        review_response = self.client.post(
            reverse('pharmacist-prescription-review', args=[dispensing_rx.id]),
            {'action': 'approve', 'notes': 'Approved after pharmacist review.'},
            format='json',
        )
        self.assertEqual(review_response.status_code, 200, review_response.content)
        dispensing_rx.refresh_from_db()
        self.assertEqual(dispensing_rx.status, Prescription.STATUS_APPROVED)
        self.assertEqual(dispensing_rx.pharmacist_id, self.pharmacist_user.id)
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
        product = Product.objects.create(
            name='Pediatric Flow Amoxicillin',
            sku='PED-FLOW-AMOX',
            slug='pediatric-flow-amoxicillin',
            is_active=True,
        )
        variant = Variant.objects.create(
            product=product,
            sku='PED-FLOW-AMOX-125',
            name='125mg suspension',
            price='180.00',
            requires_prescription=True,
            is_active=True,
        )
        VariantInventory.objects.update_or_create(
            variant=variant,
            location=Product.STOCK_BRANCH,
            defaults={'stock_quantity': 10, 'low_stock_threshold': 2},
        )

        self.client.force_authenticate(self.patient)
        first_child_response = self.client.post(
            reverse('guardian-children'),
            {
                'first_name': 'Flow',
                'last_name': 'Child',
                'age_years': 6,
                'gender': 'female',
                'weight_kg': '21.50',
                'allergies': ['Penicillin review needed'],
            },
            format='json',
        )
        self.assertEqual(first_child_response.status_code, 201, first_child_response.content)
        second_child_response = self.client.post(
            reverse('guardian-children'),
            {'first_name': 'Second', 'last_name': 'Child', 'age_years': 3},
            format='json',
        )
        self.assertEqual(second_child_response.status_code, 201, second_child_response.content)
        children_response = self.client.get(reverse('guardian-children'))
        self.assertEqual(children_response.status_code, 200)
        child_rows = children_response.data.get('results', children_response.data)
        self.assertEqual(len(child_rows), 2)
        child_id = first_child_response.data['id']

        blocked_response = self.client.post(
            reverse('consultations'),
            {
                'pediatrician': pediatrician.id,
                'child_patient_id': child_id,
                'patient_name': self.patient.full_name,
                'patient_email': self.patient.email,
                'patient_phone': self.patient.phone,
                'issue': 'Child has fever',
                'priority': Consultation.PRIORITY_ROUTINE,
                'is_pediatric': True,
            },
            format='json',
        )
        self.assertEqual(blocked_response.status_code, 402)

        intent = ConsultationPaymentIntent.objects.create(
            initiated_by=self.patient,
            clinician=pediatrician,
            provider=ConsultationPaymentIntent.PROVIDER_PAYBILL,
            status=ConsultationPaymentIntent.STATUS_SUCCEEDED,
            amount='1.00',
            consultation_payload={
                'pediatrician': pediatrician.id,
                'child_patient_id': child_id,
                'patient_name': self.patient.full_name,
                'patient_email': self.patient.email,
                'patient_phone': self.patient.phone,
                'issue': 'Child has fever',
                'priority': Consultation.PRIORITY_ROUTINE,
                'is_pediatric': True,
                'guardian_name': self.patient.full_name,
                'child_name': first_child_response.data['full_name'],
                'child_age': first_child_response.data['age_years'],
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
        self.assertEqual(finalize_response.data['child_patient'], child_id)
        self.assertEqual(finalize_response.data['child_name'], 'Flow Child')
        consultation_id = finalize_response.data['id']
        consultation = Consultation.objects.get(pk=consultation_id)
        self.assertEqual(consultation.child_patient_id, child_id)
        self.assertEqual(consultation.patient_id, self.patient.id)
        self.assertEqual(consultation.child_snapshot['full_name'], 'Flow Child')

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

        queue_response = self.client.get(reverse('pediatrician-consultations'))
        self.assertEqual(queue_response.status_code, 200)
        results = queue_response.data.get('results', queue_response.data)
        self.assertTrue(any(item['id'] == consultation_id for item in results))

        patients_response = self.client.get(reverse('pediatrician-patients'))
        self.assertEqual(patients_response.status_code, 200)
        patient_rows = patients_response.data['results']
        self.assertEqual(patient_rows[0]['child']['id'], child_id)
        self.assertEqual(patient_rows[0]['guardian']['id'], self.patient.id)

        patient_detail_response = self.client.get(reverse('pediatrician-patient-detail', args=[child_id]))
        self.assertEqual(patient_detail_response.status_code, 200)
        self.assertEqual(patient_detail_response.data['child']['full_name'], 'Flow Child')

        catalog_response = self.client.get(reverse('pediatrician-catalog-variants'), {'q': 'amox'})
        self.assertEqual(catalog_response.status_code, 200)
        self.assertEqual(catalog_response.data['results'][0]['id'], variant.id)

        prescription_response = self.client.post(
            reverse('pediatrician-prescriptions'),
            {
                'consultation': consultation_id,
                'patient_name': 'Flow Child',
                'items': [{
                    'variant_id': variant.id,
                    'dose': '125mg',
                    'frequency': 'twice daily',
                    'duration': '5 days',
                    'quantity': 1,
                }],
            },
            format='json',
        )
        self.assertEqual(prescription_response.status_code, 201, prescription_response.content)
        self.assertEqual(prescription_response.data['child_patient'], child_id)
        prescription = ClinicianPrescription.objects.get(pk=prescription_response.data['id'])
        send_response = self.client.post(reverse('pediatrician-prescription-send', args=[prescription.id]), format='json')
        self.assertEqual(send_response.status_code, 200, send_response.content)
        dispensing_rx = Prescription.objects.get(clinician_prescription=prescription)
        self.assertEqual(dispensing_rx.patient_id, self.patient.id)
        self.assertEqual(dispensing_rx.patient_name, 'Flow Child')
        self.assertEqual(dispensing_rx.items.get().variant_id, variant.id)

        self.client.force_authenticate(self.patient)
        customer_prescriptions = self.client.get(reverse('prescriptions'))
        self.assertEqual(customer_prescriptions.status_code, 200)
        customer_rows = customer_prescriptions.data.get('results', customer_prescriptions.data)
        customer_row = next(item for item in customer_rows if item['id'] == dispensing_rx.id)
        self.assertEqual(customer_row['clinician_prescription'], prescription.id)

        self.assertTrue(Notification.objects.filter(
            recipient=pediatrician_user,
            type='new_consultation',
            data__url=f'/pediatrician/consultations/{consultation_id}',
            data__child_patient_id=child_id,
        ).exists())
        self.assertTrue(Notification.objects.filter(
            recipient=self.patient,
            type='prescription_status',
            data__child_patient_id=child_id,
        ).exists())

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
            'issue': 'Rash on arm',
            'requested_specialty': 'Dermatology',
            'priority': Consultation.PRIORITY_ROUTINE,
        })
        self.assertTrue(specialty_serializer.is_valid(), specialty_serializer.errors)
        self.assertEqual(specialty_serializer.validated_data['clinician'], self.doctor)
        specialty_consultation = specialty_serializer.save(patient=self.patient)
        self.assertIsNone(specialty_consultation.clinician_id)
        self.assertEqual(specialty_consultation.requested_specialty, 'Dermatology')

        general_serializer = ConsultationCreateSerializer(data={
            'patient_name': self.patient.full_name,
            'patient_email': self.patient.email,
            'patient_phone': self.patient.phone,
            'issue': 'General body weakness',
            'priority': Consultation.PRIORITY_ROUTINE,
        })
        self.assertTrue(general_serializer.is_valid(), general_serializer.errors)
        self.assertIn(general_serializer.validated_data['clinician'], {self.doctor, cardiology_doctor})
        general_consultation = general_serializer.save(patient=self.patient)
        self.assertIsNone(general_consultation.clinician_id)

        self.client.force_authenticate(self.doctor_user)
        dermatology_queue = self.client.get(reverse('doctor-consultations'))
        dermatology_ids = {item['id'] for item in dermatology_queue.data.get('results', dermatology_queue.data)}
        self.assertIn(specialty_consultation.id, dermatology_ids)
        self.assertIn(general_consultation.id, dermatology_ids)
        dermatology_rows = dermatology_queue.data.get('results', dermatology_queue.data)
        general_row = next(item for item in dermatology_rows if item['id'] == general_consultation.id)
        self.assertEqual(general_row['patient_name'], 'Consult P.')
        self.assertNotEqual(general_row['patient_name'], self.patient.full_name)

        self.client.force_authenticate(cardiology_user)
        cardiology_queue = self.client.get(reverse('doctor-consultations'))
        cardiology_ids = {item['id'] for item in cardiology_queue.data.get('results', cardiology_queue.data)}
        self.assertNotIn(specialty_consultation.id, cardiology_ids)
        self.assertIn(general_consultation.id, cardiology_ids)
        denied_specialty_detail = self.client.get(reverse('consultation-detail', args=[specialty_consultation.id]))
        self.assertEqual(denied_specialty_detail.status_code, 404)

        detail_response = self.client.get(reverse('consultation-detail', args=[general_consultation.id]))
        self.assertEqual(detail_response.status_code, 200, detail_response.content)
        self.assertEqual(detail_response.data['patient_name'], self.patient.full_name)
        general_consultation.refresh_from_db()
        self.assertEqual(general_consultation.clinician_id, cardiology_doctor.id)
        self.assertEqual(general_consultation.status, Consultation.STATUS_IN_PROGRESS)

        self.client.force_authenticate(self.doctor_user)
        dermatology_queue = self.client.get(reverse('doctor-consultations'))
        dermatology_ids = {item['id'] for item in dermatology_queue.data.get('results', dermatology_queue.data)}
        self.assertNotIn(general_consultation.id, dermatology_ids)

        unmatched_serializer = ConsultationCreateSerializer(data={
            'patient_name': self.patient.full_name,
            'patient_email': self.patient.email,
            'patient_phone': self.patient.phone,
            'issue': 'Headache with dizziness',
            'requested_specialty': 'Neurology',
            'priority': Consultation.PRIORITY_ROUTINE,
        })
        self.assertTrue(unmatched_serializer.is_valid(), unmatched_serializer.errors)
        unmatched_consultation = unmatched_serializer.save(patient=self.patient)

        self.client.force_authenticate(self.doctor_user)
        dermatology_queue = self.client.get(reverse('doctor-consultations'))
        dermatology_ids = {item['id'] for item in dermatology_queue.data.get('results', dermatology_queue.data)}
        self.assertIn(unmatched_consultation.id, dermatology_ids)

        self.client.force_authenticate(cardiology_user)
        cardiology_queue = self.client.get(reverse('doctor-consultations'))
        cardiology_ids = {item['id'] for item in cardiology_queue.data.get('results', cardiology_queue.data)}
        self.assertIn(unmatched_consultation.id, cardiology_ids)

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
                'doctor': None,
                'patient_name': self.patient.full_name,
                'patient_email': self.patient.email,
                'patient_phone': self.patient.phone,
                'issue': 'Rash on arm',
                'requested_specialty': 'Dermatology',
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
                'doctor': None,
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

        Notification.objects.filter(type='new_consultation').delete()
        unmatched_specialty_intent = ConsultationPaymentIntent.objects.create(
            initiated_by=self.patient,
            clinician=cardiology_doctor,
            provider=ConsultationPaymentIntent.PROVIDER_PAYBILL,
            status=ConsultationPaymentIntent.STATUS_SUCCEEDED,
            amount='500.00',
            consultation_payload={
                'doctor': None,
                'patient_name': self.patient.full_name,
                'patient_email': self.patient.email,
                'patient_phone': self.patient.phone,
                'issue': 'Need a specialist',
                'requested_specialty': 'Neurology',
                'priority': Consultation.PRIORITY_ROUTINE,
            },
        )
        self.client.post(
            reverse('consultation-payment-finalize'),
            {'payment_intent_id': unmatched_specialty_intent.id},
            format='json',
        )
        notified = set(Notification.objects.filter(type='new_consultation').values_list('recipient__email', flat=True))
        self.assertEqual(notified, {self.doctor_user.email, cardiology_user.email})
