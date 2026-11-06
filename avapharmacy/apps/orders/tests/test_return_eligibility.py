from types import SimpleNamespace
from unittest.mock import Mock, patch
from django.test import SimpleTestCase
from rest_framework.exceptions import ValidationError
from apps.orders.views import ReturnRequestListCreateView


class ReturnEligibilityTests(SimpleTestCase):
    @patch('apps.orders.views.Order.objects.get')
    def test_undelivered_orders_are_rejected(self, get_order):
        view = ReturnRequestListCreateView()
        view.kwargs = {}
        view.request = SimpleNamespace(data={'order_id': 20}, user=Mock())
        for status in ['draft', 'pending', 'paid', 'processing', 'shipped', 'cancelled', 'refunded']:
            with self.subTest(status=status):
                get_order.return_value = SimpleNamespace(status=status)
                serializer = Mock()
                with self.assertRaises(ValidationError) as raised:
                    view.perform_create(serializer)
                self.assertIn('Only delivered orders', str(raised.exception))
                serializer.save.assert_not_called()

    @patch('apps.orders.views.create_order_event')
    @patch('apps.orders.views.Order.objects.get')
    def test_delivered_order_can_create_request(self, get_order, create_event):
        view = ReturnRequestListCreateView()
        view.kwargs = {}
        view.request = SimpleNamespace(data={'order_id': 20}, user=Mock())
        order = SimpleNamespace(id=20, status='delivered', total=100)
        get_order.return_value = order
        serializer = Mock(validated_data={})
        view.perform_create(serializer)
        serializer.save.assert_called_once_with(order=order, customer=view.request.user)
