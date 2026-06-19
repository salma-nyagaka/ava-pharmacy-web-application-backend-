import json

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.models import Pharmacist, User
from apps.notifications.models import Notification
from apps.orders.models import CartItem, Order, OrderItem
from apps.prescriptions.models import (
    Prescription,
    PrescriptionClarificationMessage,
    PrescriptionFile,
    PrescriptionReviewDecision,
)
from apps.products.models import Product, Variant, VariantInventory


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
        Pharmacist.objects.create(
            user=self.pharmacist,
            permissions=[Pharmacist.PERMISSION_PRESCRIPTION_REVIEW],
        )
        self.product = Product.objects.create(
            sku='RX-APPROVED-001',
            name='Approved Medication',
            price='1200.00',
            is_active=True,
            requires_prescription=True,
        )
        self.variant = Variant.objects.create(
            product=self.product,
            sku='RX-APPROVED-001-500',
            name='500mg tablets',
            price='1200.00',
            requires_prescription=True,
            is_active=True,
        )
        VariantInventory.objects.update_or_create(
            variant=self.variant,
            location=Product.STOCK_BRANCH,
            defaults={'stock_quantity': 10, 'low_stock_threshold': 2},
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
                    'variant_id': self.variant.id,
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
        decision = PrescriptionReviewDecision.objects.get(prescription=prescription)
        self.assertEqual(decision.action, PrescriptionReviewDecision.ACTION_APPROVE)
        self.assertEqual(decision.from_status, Prescription.STATUS_PENDING)
        self.assertEqual(decision.to_status, Prescription.STATUS_APPROVED)
        self.assertEqual(decision.pharmacist, self.pharmacist)
        item = prescription.items.get()
        self.assertEqual(item.product_id, self.product.id)
        self.assertEqual(item.variant_id, self.variant.id)

        self.client.force_authenticate(self.customer)
        add_response = self.client.post(
            reverse('prescription-item-add-to-cart', args=[prescription.id, item.id]),
            {'quantity': 1},
            format='json',
        )
        self.assertEqual(add_response.status_code, 201, add_response.content)
        cart_item = CartItem.objects.get(cart__user=self.customer, prescription=prescription)
        self.assertEqual(cart_item.variant_id, self.variant.id)
        self.assertEqual(cart_item.prescription_item_id, item.id)
        self.assertTrue(Notification.objects.filter(
            recipient=self.customer,
            type='prescription_status',
            data__prescription_id=prescription.id,
        ).exists())

    def test_customer_cannot_add_prescription_item_again_after_paid_order(self):
        prescription = Prescription.objects.create(
            patient=self.customer,
            patient_name=self.customer.full_name,
            status=Prescription.STATUS_APPROVED,
        )
        item = prescription.items.create(
            name='Approved Medication',
            product=self.product,
            variant=self.variant,
            quantity=1,
        )
        order = Order.objects.create(
            customer=self.customer,
            status=Order.STATUS_PAID,
            payment_status=Order.PAYMENT_STATUS_PAID,
            payment_method=Order.PAYMENT_MPESA_STK,
            shipping_first_name='Rx',
            shipping_last_name='Customer',
            shipping_email=self.customer.email,
            shipping_phone='0700000000',
            shipping_street='Test Street',
            shipping_city='Nairobi',
            shipping_county='Nairobi',
            subtotal='1200.00',
            shipping_fee='0.00',
            total='1200.00',
        )
        OrderItem.objects.create(
            order=order,
            variant=self.variant,
            product_name=self.product.name,
            product_sku=self.variant.sku,
            variant_name=self.variant.name,
            variant_sku=self.variant.sku,
            quantity=1,
            unit_price='1200.00',
            prescription_reference=prescription.reference,
            prescription=prescription,
            prescription_item=item,
        )

        self.client.force_authenticate(self.customer)
        response = self.client.post(
            reverse('prescription-item-add-to-cart', args=[prescription.id, item.id]),
            {'quantity': 1},
            format='json',
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn('already been paid', response.data['detail'])
        self.assertFalse(CartItem.objects.filter(cart__user=self.customer, prescription_item=item).exists())

    def test_customer_cannot_add_approved_prescription_item_to_cart_when_variant_is_out_of_stock(self):
        out_of_stock_product = Product.objects.create(
            sku='RX-OUT-001',
            name='Out Of Stock Medication',
            price='900.00',
            is_active=True,
            requires_prescription=True,
        )
        out_of_stock_variant = Variant.objects.create(
            product=out_of_stock_product,
            sku='RX-OUT-001-500',
            name='500mg tablets',
            price='900.00',
            requires_prescription=True,
            is_active=True,
        )
        VariantInventory.objects.update_or_create(
            variant=out_of_stock_variant,
            location=Product.STOCK_BRANCH,
            defaults={'stock_quantity': 0, 'low_stock_threshold': 2},
        )
        prescription = Prescription.objects.create(
            patient=self.customer,
            patient_name=self.customer.full_name,
            status=Prescription.STATUS_PENDING,
        )

        self.client.force_authenticate(self.pharmacist)
        review_response = self.client.post(
            reverse('pharmacist-prescription-review', args=[prescription.id]),
            {
                'action': 'approve',
                'notes': 'Approved but stock has run out',
                'items': [{
                    'name': 'Out Of Stock Medication',
                    'variant_id': out_of_stock_variant.id,
                    'dose': '500mg',
                    'frequency': 'once daily',
                    'quantity': 1,
                }],
            },
            format='json',
        )
        self.assertEqual(review_response.status_code, 200, review_response.content)
        item = prescription.items.get()

        self.client.force_authenticate(self.customer)
        add_response = self.client.post(
            reverse('prescription-item-add-to-cart', args=[prescription.id, item.id]),
            {'quantity': 1},
            format='json',
        )
        self.assertEqual(add_response.status_code, 400)
        self.assertIn('out of stock', add_response.data['detail'].lower())
        self.assertFalse(CartItem.objects.filter(cart__user=self.customer, variant=out_of_stock_variant).exists())

    def test_pharmacist_requires_prescription_review_permission(self):
        restricted = User.objects.create_user(
            email='rx-restricted@example.com',
            password='testpass123',
            first_name='Restricted',
            last_name='Pharmacist',
            role=User.PHARMACIST,
        )
        Pharmacist.objects.create(
            user=restricted,
            permissions=[Pharmacist.PERMISSION_DISPENSE_ORDERS],
        )
        prescription = Prescription.objects.create(
            patient=self.customer,
            patient_name=self.customer.full_name,
            status=Prescription.STATUS_PENDING,
        )

        self.client.force_authenticate(restricted)
        queue_response = self.client.get(reverse('pharmacist-prescriptions'))
        review_response = self.client.post(
            reverse('pharmacist-prescription-review', args=[prescription.id]),
            {'action': 'request_clarification', 'notes': 'Need clearer instructions.'},
            format='json',
        )

        self.assertEqual(queue_response.status_code, 403)
        self.assertEqual(review_response.status_code, 403)

    def test_pharmacist_can_search_catalog_variants_for_prescription_mapping(self):
        self.client.force_authenticate(self.pharmacist)

        response = self.client.get(reverse('pharmacist-catalog-variants'), {'q': 'approved'})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['results'][0]['id'], self.variant.id)
        self.assertEqual(response.data['results'][0]['product_id'], self.product.id)
        self.assertEqual(response.data['results'][0]['sku'], self.variant.sku)
        self.assertTrue(response.data['results'][0]['can_select'])

    def test_approval_requires_mapped_medications(self):
        prescription = Prescription.objects.create(
            patient=self.customer,
            patient_name=self.customer.full_name,
            status=Prescription.STATUS_PENDING,
        )

        self.client.force_authenticate(self.pharmacist)
        response = self.client.post(
            reverse('pharmacist-prescription-review', args=[prescription.id]),
            {
                'action': 'approve',
                'notes': 'Cannot approve unmapped product',
                'items': [{
                    'name': 'Unmapped medication',
                    'dose': '1 tablet',
                    'frequency': 'daily',
                    'quantity': 1,
                }],
            },
            format='json',
        )

        self.assertEqual(response.status_code, 400)
        prescription.refresh_from_db()
        self.assertEqual(prescription.status, Prescription.STATUS_PENDING)
        self.assertFalse(PrescriptionReviewDecision.objects.filter(prescription=prescription).exists())

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
