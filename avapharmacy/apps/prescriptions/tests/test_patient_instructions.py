import json
from unittest.mock import patch
from datetime import timedelta
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient
from . import test_workflow as fixtures
from avapharmacy.test_compliance_fixtures import prescription_fixture, prescription_payload
from apps.prescriptions.models import Prescription
from apps.prescriptions.serializers import PrescriptionSerializer, PharmacistPrescriptionReviewItemSerializer


class PatientInstructionsTests(TestCase):
    def setUp(self):
        from apps.accounts.models import User, Pharmacist
        from apps.products.models import Product, Variant, VariantInventory
        from avapharmacy.test_compliance_fixtures import credential_fixture, catalogue_fixture, inventory_fixture
        self.client = APIClient()
        self.customer = User.objects.create_user(email='new-rx-patient@example.test', password='test123', role='customer', status='active')
        self.pharmacist = User.objects.create_user(email='new-rx-pharmacist@example.test', password='test123', role='pharmacist', status='active')
        Pharmacist.objects.create(user=self.pharmacist, permissions=[Pharmacist.PERMISSION_PRESCRIPTION_REVIEW], **credential_fixture())
        self.product = Product.objects.create(name='Synthetic Prescription Medicine')
        self.variant = Variant.objects.create(product=self.product, name='Synthetic tablet', price=100, requires_prescription=True, **catalogue_fixture(medicine=True))
        VariantInventory.objects.create(variant=self.variant, stock_quantity=10, **inventory_fixture())

    def upload(self, items=None):
        self.client.force_authenticate(self.customer)
        payload = {'patient_name': 'Synthetic Patient', 'doctor_name': 'Synthetic doctor', 'files': [SimpleUploadedFile('test.pdf', b'%PDF-1.4 synthetic', content_type='application/pdf')]}
        if items is not None:
            payload['items_json'] = json.dumps(items)
        return self.client.post(reverse('prescription-upload'), payload, format='multipart')

    @patch('apps.prescriptions.views.enforce_public_bot_controls')
    def test_upload_requires_prescription_product(self, bot_controls):
        self.assertEqual(self.upload().status_code, 400)
        self.assertEqual(self.upload([{'name': 'Handwritten line'}]).status_code, 400)
        response = self.upload([{'name': self.product.name, 'product_id': self.product.pk, 'variant_id': self.variant.pk}])
        self.assertEqual(response.status_code, 201, response.data)

    def test_pharmacist_instructions_and_refills_reach_patient(self):
        rx = Prescription.objects.create(patient=self.customer, patient_name='Synthetic Patient', **prescription_fixture())
        self.client.force_authenticate(self.pharmacist)
        payload = {'action': 'approve', 'notes': 'Please contact the pharmacist with any questions.', 'items': [{'name': self.product.name, 'product_id': self.product.pk, 'variant_id': self.variant.pk, 'quantity': 1, 'dose': '1 tablet', 'frequency': 'Daily', 'duration': '30 days', 'administration_route': 'Oral', 'instructions': 'Take after food.', 'is_refill': True, 'refill_interval': 7, 'refill_unit': 'days'}]}
        response = self.client.post(reverse('pharmacist-prescription-review', args=[rx.pk]), payload, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        rx.refresh_from_db()
        item = rx.items.get()
        self.assertEqual(item.administration_route, 'Oral')
        self.assertEqual(item.instructions, 'Take after food.')
        self.assertEqual(item.next_refill_at, timezone.localdate() + timedelta(days=7))
        self.client.force_authenticate(self.customer)
        detail = self.client.get(reverse('prescription-detail', args=[rx.pk]))
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.data['items'][0]['instructions'], 'Take after food.')
        self.assertEqual(detail.data['pharmacist_notes'], payload['notes'])

    def test_refill_requires_a_positive_interval(self):
        serializer = PharmacistPrescriptionReviewItemSerializer(data={'name': 'Medicine', 'quantity': 1, 'is_refill': True, 'refill_interval': 0})
        self.assertFalse(serializer.is_valid())
