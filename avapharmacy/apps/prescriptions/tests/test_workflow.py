import json
from datetime import timedelta

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
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
                'notes': 'Patient taking amoxicillin after meals',
                'items_json': json.dumps([{'name': 'Amoxicillin', 'dose': '500mg', 'frequency': 'three times daily', 'quantity': 1}]),
                'files': [SimpleUploadedFile('rx.pdf', b'pdf-bytes', content_type='application/pdf')],
            },
            format='multipart',
        )
        self.assertEqual(upload_response.status_code, 201)
        prescription = Prescription.objects.get(patient=self.customer)
        self.assertFalse(prescription.items.first().is_controlled_substance)

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
                    'name': 'Amoxicillin',
                    'variant_id': self.variant.id,
                    'dose': '500mg',
                    'frequency': 'three times daily',
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

    def test_controlled_drug_prescription_cannot_be_approved_online(self):
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
        review_response = self.client.post(
            reverse('pharmacist-prescription-review', args=[prescription.id]),
            {
                'action': 'approve',
                'notes': 'Verified',
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

        self.assertEqual(review_response.status_code, 400)
        prescription.refresh_from_db()
        self.assertEqual(prescription.status, Prescription.STATUS_PENDING)

    def test_pharmacist_queue_orders_latest_activity_first(self):
        older_assigned = Prescription.objects.create(
            patient=self.customer,
            patient_name=self.customer.full_name,
            doctor_name='Dr Older',
            pharmacist=self.pharmacist,
            status=Prescription.STATUS_PENDING,
        )
        newer_unassigned = Prescription.objects.create(
            patient=self.customer,
            patient_name=self.customer.full_name,
            doctor_name='Dr Newer',
            status=Prescription.STATUS_PENDING,
        )
        now = timezone.now()
        Prescription.objects.filter(pk=older_assigned.pk).update(
            submitted_at=now - timedelta(days=1),
            updated_at=now - timedelta(days=1),
        )
        Prescription.objects.filter(pk=newer_unassigned.pk).update(
            submitted_at=now - timedelta(minutes=5),
            updated_at=now - timedelta(minutes=5),
        )

        self.client.force_authenticate(self.pharmacist)
        queue_response = self.client.get(reverse('pharmacist-prescriptions'))

        self.assertEqual(queue_response.status_code, 200)
        rows = queue_response.data.get('results', queue_response.data)
        self.assertEqual(rows[0]['id'], newer_unassigned.id)
        self.assertEqual(rows[1]['id'], older_assigned.id)

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

    def test_upload_validation_rejects_invalid_files_and_missing_patient(self):
        self.client.force_authenticate(self.customer)
        for payload in [
            {'patient_name': 'Synthetic QA', 'files': [SimpleUploadedFile('bad.txt', b'bad', content_type='text/plain')]},
            {'patient_name': 'Synthetic QA', 'files': [SimpleUploadedFile('large.pdf', b'x' * (5 * 1024 * 1024 + 1), content_type='application/pdf')]},
            {'files': [SimpleUploadedFile('rx.pdf', b'qa', content_type='application/pdf')]},
            {'patient_name': 'Synthetic QA'},
        ]:
            with self.subTest(fields=list(payload)):
                response = self.client.post(reverse('prescription-upload'), payload, format='multipart')
                self.assertEqual(response.status_code, 400, response.data)
        self.assertFalse(Prescription.objects.filter(patient=self.customer).exists())

    def test_unrelated_customer_cannot_read_reply_resubmit_or_add(self):
        other = User.objects.create_user(email='rx-other@example.com', password='testpass123', role=User.CUSTOMER)
        prescription = Prescription.objects.create(patient=self.customer, patient_name='Synthetic QA', status=Prescription.STATUS_APPROVED)
        item = prescription.items.create(name='QA', product=self.product, variant=self.variant, quantity=1)
        self.client.force_authenticate(other)
        self.assertEqual(self.client.get(reverse('prescription-detail', args=[prescription.id])).status_code, 404)
        self.assertEqual(self.client.post(reverse('prescription-clarification-reply', args=[prescription.id]), {'message': 'QA'}).status_code, 404)
        self.assertEqual(self.client.patch(reverse('prescription-resubmit', args=[prescription.id]), {'notes': 'QA'}).status_code, 404)
        self.assertEqual(self.client.post(reverse('prescription-item-add-to-cart', args=[prescription.id, item.id]), {'quantity': 1}).status_code, 404)

    def test_pending_rejected_and_excess_quantity_cannot_enter_cart(self):
        prescription = Prescription.objects.create(patient=self.customer, patient_name='Synthetic QA')
        item = prescription.items.create(name='QA', product=self.product, variant=self.variant, quantity=2)
        self.client.force_authenticate(self.customer)
        url = reverse('prescription-item-add-to-cart', args=[prescription.id, item.id])
        for state in [Prescription.STATUS_PENDING, Prescription.STATUS_REJECTED]:
            prescription.status = state
            prescription.save()
            self.assertEqual(self.client.post(url, {'quantity': 1}).status_code, 404)
        prescription.status = Prescription.STATUS_APPROVED
        prescription.save()
        self.assertEqual(self.client.post(url, {'quantity': 3}).status_code, 400)
        self.assertEqual(self.client.post(url, {'quantity': 2}).status_code, 201)
        self.assertEqual(self.client.post(url, {'quantity': 1}).status_code, 400)
        self.assertEqual(CartItem.objects.get(prescription_item=item).quantity, 2)

    def test_restricted_pharmacist_cannot_use_alternate_prescription_routes(self):
        restricted = User.objects.create_user(email='rx-no-review@example.com', password='testpass123', role=User.PHARMACIST)
        Pharmacist.objects.create(user=restricted, permissions=[Pharmacist.PERMISSION_DISPENSE_ORDERS])
        prescription = Prescription.objects.create(patient=self.customer, patient_name='Synthetic QA')
        self.client.force_authenticate(restricted)
        self.assertEqual(self.client.get(reverse('admin-prescriptions')).status_code, 403)
        for method, name, payload in [
            ('get', 'prescription-detail', {}),
            ('patch', 'prescription-update', {'status': Prescription.STATUS_APPROVED}),
            ('post', 'prescription-audit', {'action': 'Unauthorized review'}),
        ]:
            with self.subTest(route=name):
                response = getattr(self.client, method)(reverse(name, args=[prescription.id]), payload, format='json')
                self.assertIn(response.status_code, (403, 404), response.data)

    def test_rejection_reason_and_dispatch_history_are_visible_to_owner(self):
        prescription = Prescription.objects.create(patient=self.customer, patient_name='Synthetic QA')
        self.client.force_authenticate(self.pharmacist)
        response = self.client.post(reverse('pharmacist-prescription-review', args=[prescription.id]),
            {'action': 'reject', 'notes': 'Synthetic scan is unreadable.'}, format='json')
        self.assertEqual(response.status_code, 200)
        self.client.force_authenticate(self.customer)
        response = self.client.get(reverse('prescription-detail', args=[prescription.id]))
        self.assertEqual(response.data['clarification_message'], 'Synthetic scan is unreadable.')
        self.assertEqual(response.data['review_decisions'][0]['pharmacist'], self.pharmacist.id)
        prescription.status = Prescription.STATUS_APPROVED
        prescription.save()
        prescription.items.create(name='QA', product=self.product, variant=self.variant, quantity=1)
        self.client.force_authenticate(self.pharmacist)
        for state in ['queued', 'packed', 'dispatched', 'delivered']:
            response = self.client.patch(reverse('prescription-update', args=[prescription.id]),
                {'dispatch_status': state}, format='json')
            self.assertEqual(response.status_code, 200, response.data)
            prescription.refresh_from_db()
            self.assertEqual(prescription.dispatch_status, state)
        self.client.force_authenticate(self.customer)
        response = self.client.get(reverse('prescription-detail', args=[prescription.id]))
        self.assertEqual(response.data['dispatch_status'], 'delivered')
        self.assertEqual(len(response.data['audit_logs']), 5)
        self.assertTrue(all(row['performed_by'] == self.pharmacist.id for row in response.data['audit_logs']))

    def test_private_download_grants_and_legacy_media_are_protected(self):
        from unittest.mock import patch
        from django.core import signing
        prescription = Prescription.objects.create(patient=self.customer, patient_name='Synthetic QA')
        upload = PrescriptionFile.objects.create(prescription=prescription,
            file=SimpleUploadedFile('private.pdf', b'%PDF-1.4 synthetic QA', content_type='application/pdf'), filename='private.pdf')
        self.addCleanup(upload.file.delete, save=False)
        self.client.force_authenticate(self.customer)
        response = self.client.get(reverse('prescription-detail', args=[prescription.pk]))
        link = response.data['files'][0]['file']
        self.assertIn('/download/private.pdf?token=', link)
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get('/media/' + upload.file.name).status_code, 404)
        self.assertEqual(self.client.get(reverse('prescription-file-download', args=[prescription.pk, upload.pk])).status_code, 404)
        response = self.client.get(link)
        self.assertEqual(response.status_code, 200)
        with patch('django.core.signals.request_finished.send'):
            self.assertEqual(b''.join(response.streaming_content), b'%PDF-1.4 synthetic QA')
        self.assertEqual(response['Cache-Control'], 'private, no-store')
        with patch('django.core.signing.time.time', return_value=0):
            expired = signing.dumps({'file': upload.pk, 'user': self.customer.pk}, salt='prescription-download')
        self.assertEqual(self.client.get(reverse('prescription-file-download', args=[prescription.pk, upload.pk]), {'token': expired}).status_code, 404)
        other = User.objects.create_user(email='rx-file-other@example.com', password='testpass123', role=User.CUSTOMER)
        grant = signing.dumps({'file': upload.pk, 'user': other.pk}, salt='prescription-download')
        self.assertEqual(self.client.get(reverse('prescription-file-download', args=[prescription.pk, upload.pk]), {'token': grant}).status_code, 404)
        self.customer.status = User.STATUS_SUSPENDED
        self.customer.save()
        self.assertEqual(self.client.get(link).status_code, 404)

    def test_variant_substitution_and_unpaid_order_reservation_are_rejected(self):
        from apps.orders.views import _prescription_cart_error
        from apps.prescriptions.dispensing import dispensing_error
        prescription = Prescription.objects.create(patient=self.customer, patient_name='Synthetic QA', status=Prescription.STATUS_APPROVED)
        item = prescription.items.create(name='QA', product=self.product, variant=self.variant, quantity=2)
        substitute = Variant.objects.create(product=self.product, sku='RX-SUBSTITUTE', name='Other strength', price='1200', is_active=True, requires_prescription=True)
        self.assertIn('variant', _prescription_cart_error(self.customer, self.product, prescription.reference, 1,
            prescription=prescription, prescription_item=item, variant=substitute))
        order = Order.objects.create(customer=self.customer, status=Order.STATUS_PENDING, payment_method=Order.PAYMENT_MPESA_PAYBILL,
            subtotal=2400, total=2400)
        OrderItem.objects.create(order=order, variant=self.variant, quantity=2, unit_price=1200,
            prescription=prescription, prescription_item=item, prescription_reference=prescription.reference)
        self.assertIn('reserved', dispensing_error(item, self.variant, 1))
        self.assertIsNone(dispensing_error(item, self.variant, 2, exclude_order=order))
        order.status = Order.STATUS_CANCELLED
        order.save()
        self.assertIsNone(dispensing_error(item, self.variant, 2))

    def test_invalid_approval_rolls_back_replacement_and_preserves_instructions(self):
        prescription = Prescription.objects.create(patient=self.customer, patient_name='Synthetic QA')
        original = prescription.items.create(name='Original QA', product=self.product, variant=self.variant, quantity=1)
        self.client.force_authenticate(self.pharmacist)
        response = self.client.post(reverse('pharmacist-prescription-review', args=[prescription.pk]),
            {'action': 'approve', 'items': [{'name': 'Unmapped QA', 'quantity': 1}]}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertTrue(prescription.items.filter(pk=original.pk).exists())
        response = self.client.post(reverse('pharmacist-prescription-review', args=[prescription.pk]),
            {'action': 'approve', 'items': [{'name': 'QA', 'variant_id': self.variant.pk, 'quantity': 1,
                'dose': 'QA dose', 'frequency': 'QA frequency', 'duration': 'QA duration', 'quantity_measurement': 'packs'}]}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(prescription.items.get().duration, 'QA duration')
        self.assertEqual(prescription.items.get().quantity_measurement, 'packs')

    def test_dispatch_requires_approval_and_ordered_transitions_and_notifies_once(self):
        prescription = Prescription.objects.create(patient=self.customer, patient_name='Synthetic QA')
        prescription.items.create(name='QA', product=self.product, variant=self.variant, quantity=1)
        self.client.force_authenticate(self.pharmacist)
        url = reverse('prescription-update', args=[prescription.pk])
        self.assertEqual(self.client.patch(url, {'dispatch_status': 'queued'}, format='json').status_code, 400)
        prescription.status = Prescription.STATUS_APPROVED
        prescription.save()
        self.assertEqual(self.client.patch(url, {'dispatch_status': 'delivered'}, format='json').status_code, 400)
        count = Notification.objects.filter(recipient=self.customer).count()
        self.assertEqual(self.client.patch(url, {'dispatch_status': 'queued'}, format='json').status_code, 200)
        self.assertEqual(self.client.patch(url, {'dispatch_status': 'queued'}, format='json').status_code, 200)
        self.assertEqual(Notification.objects.filter(recipient=self.customer).count(), count + 1)
        self.assertTrue(prescription.audit_logs.filter(action='Dispatch changed from not_started to queued', performed_by=self.pharmacist).exists())

    def test_approved_checkout_paid_finalization_and_reuse_limits(self):
        from unittest.mock import patch
        from apps.orders.models import Cart
        prescription = Prescription.objects.create(patient=self.customer, patient_name='Synthetic QA', status=Prescription.STATUS_APPROVED)
        item = prescription.items.create(name='QA', product=self.product, variant=self.variant, quantity=1)
        self.client.force_authenticate(self.customer)
        self.assertEqual(self.client.post(reverse('prescription-item-add-to-cart', args=[prescription.pk, item.pk]), {'quantity': 1}, format='json').status_code, 201)
        payload = {'first_name': 'Synthetic', 'last_name': 'QA', 'email': self.customer.email, 'phone': '0727808457',
            'street': 'Synthetic QA street', 'city': 'Nairobi', 'county': 'Nairobi',
            'payment_method': Order.PAYMENT_MPESA_PAYBILL, 'delivery_method': 'standard'}
        with patch('apps.orders.views.queue_order_confirmation_email'):
            response = self.client.post(reverse('order-create'), payload, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        order = Order.objects.get(customer=self.customer)
        snapshot = order.items.get()
        self.assertEqual(snapshot.variant_id, self.variant.pk)
        self.assertEqual(snapshot.prescription_item_id, item.pk)
        self.assertEqual(self.client.post(reverse('prescription-item-add-to-cart', args=[prescription.pk, item.pk]), {'quantity': 1}).status_code, 400)
        # Simulate a trusted provider confirmation; this test never contacts a payment provider.
        order.payment_status = Order.PAYMENT_STATUS_PAID
        order.status = Order.STATUS_PAID
        order.save()
        start = VariantInventory.objects.get(variant=self.variant).stock_quantity
        for _ in range(2):
            response = self.client.post(reverse('checkout-finalize', args=[order.pk]), {}, format='json')
            self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(VariantInventory.objects.get(variant=self.variant).stock_quantity, start - 1)
        self.assertEqual(self.client.post(reverse('prescription-item-add-to-cart', args=[prescription.pk, item.pk]), {'quantity': 1}).status_code, 400)
        self.assertFalse(Cart.objects.get(user=self.customer).items.exists())
        # Releasing a cancelled dispensing allocation must remain possible even if approval was revoked.
        from apps.orders.stock import release_order_inventory
        prescription.status = Prescription.STATUS_REJECTED
        prescription.save()
        release_order_inventory(order)
        release_order_inventory(order)
        self.assertEqual(VariantInventory.objects.get(variant=self.variant).stock_quantity, start)

    def test_checkout_revalidates_rejected_prescription_and_variant_substitution(self):
        from apps.orders.views import validate_cart_items
        from apps.orders.models import Cart
        prescription = Prescription.objects.create(patient=self.customer, patient_name='Synthetic QA', status=Prescription.STATUS_APPROVED)
        item = prescription.items.create(name='QA', product=self.product, variant=self.variant, quantity=1)
        cart = Cart.objects.create(user=self.customer)
        line = cart.items.create(variant=self.variant, quantity=1, prescription=prescription, prescription_item=item,
            prescription_reference=prescription.reference)
        prescription.status = Prescription.STATUS_REJECTED
        prescription.save()
        self.assertTrue(validate_cart_items([line]))
        prescription.status = Prescription.STATUS_APPROVED
        prescription.save()
        substitute = Variant.objects.create(product=self.product, sku='RX-CHECKOUT-SUB', name='Different pack', price=1200, requires_prescription=True)
        VariantInventory.objects.create(variant=substitute, location=Product.STOCK_BRANCH, stock_quantity=5)
        line.variant = substitute
        self.assertTrue(any('variant' in error for error in validate_cart_items([line])))
