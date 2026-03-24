import json

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.prescriptions.models import Prescription
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
