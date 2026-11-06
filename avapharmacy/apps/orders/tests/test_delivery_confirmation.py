from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.orders.models import Order


class DeliveryConfirmationTests(TestCase):
    @patch('apps.orders.views._save_order_push_result')
    @patch('apps.orders.views.notify_order_status')
    def test_recording_recipient_confirmation_unblocks_delivered(self, notify, push):
        admin = User.objects.create_user(email='delivery-admin@example.test', role=User.ADMIN)
        order = Order.objects.create(customer=admin, status='shipped', payment_status='paid', inventory_committed=True)
        client = APIClient()
        client.force_authenticate(admin)
        detail = reverse('admin-order-detail', args=[order.pk])
        blocked = client.patch(detail, {'status': 'delivered'}, format='json')
        self.assertEqual(blocked.status_code, 400)
        audit = client.post(reverse('admin-order-delivery-audits', args=[order.pk]), {
            'event_type': 'delivered', 'recipient_name': 'Test recipient',
            'recipient_verified': True,
        }, format='json')
        self.assertEqual(audit.status_code, 201, audit.data)
        result = client.patch(detail, {'status': 'delivered'}, format='json')
        self.assertEqual(result.status_code, 200, result.data)
        order.refresh_from_db()
        self.assertEqual(order.status, 'delivered')
