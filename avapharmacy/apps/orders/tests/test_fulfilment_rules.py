from decimal import Decimal
from types import SimpleNamespace
from django.test import SimpleTestCase
from rest_framework.test import APITestCase
from django.urls import reverse
from apps.orders.models import Order, ShippingMethod
from apps.orders.views import build_order_totals
from apps.accounts.models import User


class PickupQuoteTests(SimpleTestCase):
    def test_store_pickup_is_free_even_if_shipping_method_charges(self):
        cart = SimpleNamespace(total=Decimal('1000'), discount_total=Decimal('100'))
        shipping = SimpleNamespace(calculate_fee=lambda subtotal: Decimal('300'))
        self.assertEqual(build_order_totals(cart, shipping, delivery_method='store_pickup'), (Decimal('1000'), Decimal('100'), Decimal('0'), Decimal('900')))
        self.assertEqual(build_order_totals(cart, shipping, delivery_method='doorstep_delivery')[-1], Decimal('1200'))


class OrderFulfilmentRoleTests(APITestCase):
    def test_pickup_saved_order_has_no_shipping_charge(self):
        order = Order.objects.create(delivery_method='store_pickup', subtotal=1000, discount_total=100, shipping_fee=300, total=1200)
        order.refresh_from_db()
        self.assertEqual(order.shipping_fee, 0)
        self.assertEqual(order.total, 900)

    def test_admin_oversees_but_pharmacist_processes(self):
        order = Order.objects.create(status='pending', payment_status='paid')
        admin = User.objects.create_user(email='oversee@example.com', password='test123', role='admin', status='active')
        pharmacist = User.objects.create_user(email='fulfil@example.com', password='test123', role='pharmacist', status='active')
        from apps.orders.views import AdminOrderDetailView
        from rest_framework.test import APIRequestFactory, force_authenticate
        for user, expected in ((admin, 403), (pharmacist, 200)):
            request = APIRequestFactory().patch('/admin/orders/', {'status': 'processing'}, format='json')
            force_authenticate(request, user)
            response = AdminOrderDetailView.as_view()(request, pk=order.pk)
            self.assertEqual(response.status_code, expected, response.data)
