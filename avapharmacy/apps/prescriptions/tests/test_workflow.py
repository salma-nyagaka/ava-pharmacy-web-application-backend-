import json

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.prescriptions.models import Prescription, PrescriptionClarificationMessage, PrescriptionFile
from apps.products.models import Product


class PrescriptionWorkflowTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.customer = User.objects.create_user(
            email='rx-customer@example.com',
            password='testpass123',
            first_name='Rx',
            last_name='Customer',
            role=User.CUSTOMER,
        )
        self.pharmacist = User.objects.create_user(
            email='rx-pharmacist@example.com',
            password='testpass123',
            first_name='Rx',
            last_name='Pharmacist',
            role=User.PHARMACIST,
        )
        self.product = Product.objects.create(
            sku='RX-APPROVED-001',
            name='Approved Medication',
            price='1200.00',
            is_active=True,
            requires_prescription=True,
        )

    def test_upload_queue_assign_and_approve_prescription(self):
        self.client.force_authenticate(self.customer)
        upload_response = self.client.post(
            reverse('prescription-upload'),
            {
                'patient_name': self.customer.full_name,
                'doctor_name': 'Dr Example',
                'notes': 'Patient taking tramadol at night',
                'items_json': json.dumps([{'name': 'Tramadol', 'dose': '50mg', 'frequency': 'once daily', 'quantity': 1}]),
                'files': [SimpleUploadedFile('rx.pdf', b'pdf-bytes', content_type='application/pdf')],
            },
            format='multipart',
        )
        self.assertEqual(upload_response.status_code, 201)
        prescription = Prescription.objects.get(patient=self.customer)
        self.assertTrue(prescription.items.first().is_controlled_substance)

        self.client.force_authenticate(self.pharmacist)
        queue_response = self.client.get(reverse('pharmacist-prescriptions'))
        self.assertEqual(queue_response.status_code, 200)
        self.assertEqual(queue_response.data['results'][0]['id'], prescription.id)

        assign_response = self.client.post(reverse('pharmacist-prescription-assign', args=[prescription.id]), format='json')
        self.assertEqual(assign_response.status_code, 200)

        review_response = self.client.post(
            reverse('pharmacist-prescription-review', args=[prescription.id]),
            {
                'action': 'approve',
                'notes': 'Verified and approved',
                'items': [{
                    'name': 'Tramadol',
                    'product_id': self.product.id,
                    'dose': '50mg',
                    'frequency': 'once daily',
                    'quantity': 1,
                }],
            },
            format='json',
        )
        self.assertEqual(review_response.status_code, 200)
        prescription.refresh_from_db()
        self.assertEqual(prescription.status, Prescription.STATUS_APPROVED)

    def test_customer_can_resubmit_after_clarification(self):
        prescription = Prescription.objects.create(
            patient=self.customer,
            patient_name=self.customer.full_name,
            status=Prescription.STATUS_CLARIFICATION,
            clarification_message='Please upload a clearer image.',
        )
        self.client.force_authenticate(self.customer)

        response = self.client.patch(
            reverse('prescription-resubmit', args=[prescription.id]),
            {
                'notes': 'Uploaded a clearer image',
                'files': [SimpleUploadedFile('clearer.png', b'png-bytes', content_type='image/png')],
            },
            format='multipart',
        )

        self.assertEqual(response.status_code, 200)
        prescription.refresh_from_db()
        self.assertEqual(prescription.status, Prescription.STATUS_PENDING)
        self.assertTrue(prescription.files.exists())

    def test_pharmacist_clarification_and_customer_reply_create_message_thread(self):
        prescription = Prescription.objects.create(
            patient=self.customer,
            patient_name=self.customer.full_name,
            status=Prescription.STATUS_PENDING,
        )

        self.client.force_authenticate(self.pharmacist)
        review_response = self.client.post(
            reverse('pharmacist-prescription-review', args=[prescription.id]),
            {
                'action': 'request_clarification',
                'notes': 'Please confirm the dosage schedule for the evening medicine.',
            },
            format='json',
        )
        self.assertEqual(review_response.status_code, 200)
        prescription.refresh_from_db()
        self.assertEqual(prescription.status, Prescription.STATUS_CLARIFICATION)
        self.assertEqual(prescription.clarification_messages.count(), 1)

        self.client.force_authenticate(self.customer)
        reply_response = self.client.post(
            reverse('prescription-clarification-reply', args=[prescription.id]),
            {'message': 'The evening medicine should be taken after supper only.'},
            format='json',
        )
        self.assertEqual(reply_response.status_code, 201)
        prescription.refresh_from_db()
        self.assertEqual(prescription.status, Prescription.STATUS_PENDING)
        self.assertEqual(prescription.clarification_messages.count(), 2)

        latest_message = prescription.clarification_messages.order_by('-created_at').first()
        self.assertEqual(latest_message.sender_role, PrescriptionClarificationMessage.SENDER_PATIENT)
        self.assertIn('after supper', latest_message.message)

    def test_missing_uploaded_file_is_omitted_from_prescription_payload(self):
        prescription = Prescription.objects.create(
            patient=self.customer,
            patient_name=self.customer.full_name,
            status=Prescription.STATUS_PENDING,
        )
        PrescriptionFile.objects.create(
            prescription=prescription,
            file='prescriptions/999/missing-scan.png',
            filename='missing-scan.png',
        )

        self.client.force_authenticate(self.customer)
        response = self.client.get(reverse('prescriptions'))

        self.assertEqual(response.status_code, 200)
        payload = response.data.get('results', response.data)
        self.assertEqual(len(payload), 1)
        self.assertEqual(payload[0]['files'], [])
