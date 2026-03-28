import hashlib
import hmac
import json
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.orders.models import Order, OrderEvent, OutboundOrderPush


class ExternalOrderWorkflowTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_user(
            email='orders-admin@example.com',
            password='testpass123',
            first_name='Orders',
            last_name='Admin',
            role=User.ADMIN,
            is_staff=True,
        )
        self.customer = User.objects.create_user(
            email='orders-customer@example.com',
            password='testpass123',
            first_name='Order',
            last_name='Customer',
            role=User.CUSTOMER,
        )
        self.pharmacist = User.objects.create_user(
            email='pharmacist@example.com',
            password='testpass123',
            first_name='Pharma',
            last_name='Cist',
            role=User.PHARMACIST,
        )
        self.order = Order.objects.create(
            customer=self.customer,
            status=Order.STATUS_PENDING,
            payment_method=Order.PAYMENT_COD,
            payment_status=Order.PAYMENT_STATUS_PENDING,
            shipping_first_name='Order',
            shipping_last_name='Customer',
            shipping_email='orders-customer@example.com',
            shipping_phone='0700000000',
            shipping_street='Street 1',
            shipping_city='Nairobi',
            shipping_county='Nairobi',
            subtotal='1000.00',
            shipping_fee='0.00',
            total='1000.00',
        )

    def _signature(self, body, secret):
        return hmac.new(secret.encode('utf-8'), body, hashlib.sha256).hexdigest()

    @override_settings(ORDER_STATUS_WEBHOOK_SECRET='order-status-secret')
    def test_order_status_webhook_updates_order_and_tracking_returns_events(self):
        payload = {'order_number': self.order.order_number, 'status': Order.STATUS_SHIPPED, 'message': 'Sent to courier'}
        body = json.dumps(payload).encode('utf-8')

        response = self.client.generic(
            'POST',
            reverse('order-status-webhook'),
            body,
            content_type='application/json',
            HTTP_X_SYNC_SIGNATURE=self._signature(body, 'order-status-secret'),
        )

        self.assertEqual(response.status_code, 200)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.STATUS_SHIPPED)
        self.assertTrue(OrderEvent.objects.filter(order=self.order, event_type='status_shipped').exists())

        self.client.force_authenticate(self.customer)
        tracking_response = self.client.get(reverse('order-tracking', args=[self.order.id]))
        self.assertEqual(tracking_response.status_code, 200)
        self.assertIn('events', tracking_response.data)
        self.assertTrue(any(event['event_type'] == 'status_shipped' for event in tracking_response.data['events']))

    def test_public_tracking_lookup_matches_phone_and_returns_order_payload(self):
        response = self.client.post(
            reverse('order-tracking-lookup'),
            {
                'order_number': self.order.order_number.lower(),
                'contact': '+254700000000',
            },
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['order_number'], self.order.order_number)
        self.assertEqual(response.data['order']['shipping_phone'], self.order.shipping_phone)
        self.assertEqual(response.data['current_status'], self.order.status)
        self.assertIn('tracking_steps', response.data)

    def test_public_tracking_lookup_rejects_wrong_contact(self):
        response = self.client.post(
            reverse('order-tracking-lookup'),
            {
                'order_number': self.order.order_number,
                'contact': 'wrong@example.com',
            },
            format='json',
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data['error']['code'], 'not_found')

    def test_pharmacist_can_view_and_update_operational_order_status(self):
        self.client.force_authenticate(self.pharmacist)

        list_response = self.client.get(reverse('admin-orders'))
        self.assertEqual(list_response.status_code, 200)

        detail_response = self.client.patch(
            reverse('admin-order-detail', args=[self.order.id]),
            {'status': Order.STATUS_PROCESSING},
            format='json',
        )
        self.assertEqual(detail_response.status_code, 200)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.STATUS_PROCESSING)
        self.assertTrue(OrderEvent.objects.filter(order=self.order, event_type='status_processing').exists())

    def test_pharmacist_cannot_refund_or_change_payment_status(self):
        self.client.force_authenticate(self.pharmacist)

        payment_update = self.client.patch(
            reverse('admin-order-detail', args=[self.order.id]),
            {'payment_status': Order.PAYMENT_STATUS_PAID},
            format='json',
        )
        self.assertEqual(payment_update.status_code, 403)

        refund_response = self.client.post(reverse('admin-order-refund', args=[self.order.id]))
        self.assertEqual(refund_response.status_code, 403)

    def test_admin_failed_order_push_list_and_retry(self):
        push = OutboundOrderPush.objects.create(
            order=self.order,
            action='paid',
            status=OutboundOrderPush.STATUS_EXHAUSTED,
            payload={'id': self.order.id},
            attempt_count=5,
            max_attempts=5,
            last_error='Timeout',
        )
        self.client.force_authenticate(self.admin)

        list_response = self.client.get(reverse('admin-order-push-list'))
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(list_response.data['results'][0]['id'], push.id)

        with patch('apps.orders.views.push_order_to_pos') as mock_push:
            mock_push.return_value = {'ok': True, 'queue_status': OutboundOrderPush.STATUS_SUCCEEDED}
            retry_response = self.client.post(reverse('admin-order-push-retry', args=[push.id]), format='json')

        self.assertEqual(retry_response.status_code, 200)
        self.assertEqual(retry_response.data['id'], push.id)
