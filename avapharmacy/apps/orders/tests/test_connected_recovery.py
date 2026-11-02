"""Connected recovery regression. Provider responses are mocked in the test DB only."""
import csv
from decimal import Decimal
from io import StringIO
from unittest.mock import patch

from django.db.models import Sum
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.orders.models import Order, OrderItem, OrderEvent, PaymentIntent, ReturnRequest
from apps.support.models import SupportTicket
from . import test_order_creation as fixtures


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class ConnectedRecoveryTests(TestCase):
    setUp = fixtures.OrderCreationFlowTests.setUp
    _direct_order = fixtures.OrderCreationFlowTests._direct_order

    @patch('apps.orders.views._save_order_push_result')
    @patch('apps.orders.views.notify_order_update')
    @patch('apps.orders.views.MpesaClient')
    def test_failed_payment_retry_return_refund_and_support(self, gateway, notify, pos):
        self.client.force_authenticate(self.customer)
        order = self._direct_order(payment_method=Order.PAYMENT_MPESA_STK)
        OrderItem.objects.create(order=order, variant=self.variant, quantity=1, unit_price=700)
        before = self.variant.inventories.aggregate(n=Sum('stock_quantity'))['n']
        gateway.return_value.initiate_stk_push.side_effect = [
            ('254700000010', {'ResponseCode': '0', 'CheckoutRequestID': 'QA-FIRST', 'MerchantRequestID': 'QA-M1'}),
            ('254700000010', {'ResponseCode': '0', 'CheckoutRequestID': 'QA-RETRY', 'MerchantRequestID': 'QA-M2'}),
        ]
        gateway.return_value.query_stk_status.side_effect = [
            {'ResultCode': '1032', 'ResultDesc': 'Request cancelled by user'},
            {'ResultCode': '0', 'ResultDesc': 'Success', 'MpesaReceiptNumber': 'SYNTHETIC-RECEIPT'},
        ]
        payload = {'order_id': order.pk, 'provider': 'mpesa', 'phone': '0700000010'}
        self.assertEqual(self.client.post(reverse('payment-intents'), payload, format='json').status_code, 201)
        first = order.payment_intents.get()
        self.assertEqual(self.client.post(reverse('payment-intent-sync', args=[first.pk]), {}, format='json').status_code, 200)
        first.refresh_from_db()
        self.assertEqual(first.status, PaymentIntent.STATUS_FAILED)
        self.assertEqual(self.client.post(reverse('checkout-finalize', args=[order.pk]), {}, format='json').status_code, 400)
        self.assertEqual(self.client.post(reverse('payment-intents'), payload, format='json').status_code, 201)
        retry = order.payment_intents.exclude(pk=first.pk).get()
        self.assertEqual(self.client.post(reverse('payment-intent-sync', args=[retry.pk]), {}, format='json').status_code, 200)
        for _ in range(2):
            self.assertEqual(self.client.post(reverse('checkout-finalize', args=[order.pk]), {}, format='json').status_code, 200)
        self.assertEqual(order.payment_intents.filter(status='succeeded').count(), 1)
        self.assertEqual(OrderEvent.objects.filter(order=order, event_type='order_finalized').count(), 1)
        self.assertEqual(self.variant.inventories.aggregate(n=Sum('stock_quantity'))['n'], before - 1)
        self.client.force_authenticate(self.admin)
        for status in ['processing', 'shipped', 'delivered']:
            self.assertEqual(self.client.patch(reverse('admin-order-detail', args=[order.pk]), {'status': status}, format='json').status_code, 200)
        self.client.force_authenticate(self.customer)
        self.assertEqual(self.client.post(reverse('order-return', args=[order.pk]), {'reason': 'Synthetic damaged pack', 'requested_refund_amount': '1000'}, format='json').status_code, 201)
        ret = ReturnRequest.objects.get(order=order)
        self.assertEqual(self.client.post(reverse('admin-order-refund', args=[order.pk]), {}, format='json').status_code, 403)
        self.assertEqual(self.client.post(reverse('support-tickets'), {'channel': 'order', 'reference_id': order.order_number, 'subject': 'Synthetic refund inquiry', 'priority': 'medium'}, format='json').status_code, 201)
        ticket = SupportTicket.objects.get(reference_id=order.order_number)
        self.client.force_authenticate(self.admin)
        url = reverse('admin-return-request-detail', args=[ret.pk])
        self.assertEqual(self.client.patch(url, {'status': 'received'}, format='json').status_code, 400)
        self.assertEqual(self.client.patch(url, {'status': 'received', 'returned_medicine_quarantined': True, 'non_resale_acknowledged': True, 'inventory_disposition': 'Synthetic non-resale quarantine'}, format='json').status_code, 200)
        self.assertEqual(self.client.patch(url, {'status': 'refunded'}, format='json').status_code, 400)
        for _ in range(2):
            self.assertEqual(self.client.post(reverse('admin-order-refund', args=[order.pk]), {'reason': 'SYNTHETIC external-refund fixture; no transfer'}, format='json').status_code, 200)
        self.assertEqual(self.client.patch(url, {'status': 'refunded'}, format='json').status_code, 200)
        self.assertEqual(OrderEvent.objects.filter(order=order, event_type='refunded').count(), 1)
        self.assertEqual(self.variant.inventories.aggregate(n=Sum('stock_quantity'))['n'], before - 1)
        report = self.client.get(reverse('admin-finance-reports-download'), {'type': 'orders', 'range': 1})
        row = next(r for r in csv.DictReader(StringIO(report.content.decode())) if r['Order #'] == order.order_number)
        self.assertEqual(row['Payment Status'], 'refunded')
        self.assertEqual(Decimal(row['Total (KSh)']), order.total)
        self.assertEqual(self.client.post(reverse('support-ticket-notes', args=[ticket.pk]), {'message': 'Synthetic refund record checked; no provider transfer claimed.', 'is_internal': False}, format='json').status_code, 200)
        self.assertEqual(self.client.patch(reverse('support-ticket-detail', args=[ticket.pk]), {'status': 'resolved'}, format='json').status_code, 200)
        self.client.force_authenticate(self.customer)
        response = self.client.get(reverse('support-ticket-detail', args=[ticket.pk]))
        self.assertEqual(response.status_code, 200)
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, 'resolved')

    @patch('apps.orders.views._save_order_push_result')
    @patch('apps.orders.views.notify_order_update')
    def test_unpaid_cancellation_never_moves_stock_and_cannot_be_finalized(self, notify, pos):
        self.client.force_authenticate(self.customer)
        order = self._direct_order(payment_method=Order.PAYMENT_MPESA_STK)
        OrderItem.objects.create(order=order, variant=self.variant, quantity=2, unit_price=700)
        before = self.variant.inventories.aggregate(n=Sum('stock_quantity'))['n']
        self.assertEqual(self.client.post(reverse('order-cancel', args=[order.pk]), {}, format='json').status_code, 200)
        order.refresh_from_db()
        self.assertEqual(order.status, 'cancelled')
        self.assertFalse(order.inventory_committed)
        self.assertEqual(self.variant.inventories.aggregate(n=Sum('stock_quantity'))['n'], before)
        self.assertEqual(self.client.post(reverse('checkout-finalize', args=[order.pk]), {}, format='json').status_code, 400)
