from decimal import Decimal
from unittest.mock import patch
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APIClient
from apps.accounts.models import User
from apps.orders.models import Order, PaymentIntent
from apps.orders.mpesa import MpesaConfigurationError


class PaymentSecurityTests(TestCase):
    def setUp(self):
        self.customer = User.objects.create_user(email='payment-security@avapharmacy.test', password='test-only-password', role=User.CUSTOMER)
        self.order = Order.objects.create(customer=self.customer, status=Order.STATUS_DRAFT, total='1000.00')
        self.client = APIClient()
        self.client.force_authenticate(self.customer)

    def test_customer_cannot_mark_own_order_paid_with_manual_provider(self):
        response = self.client.post(reverse('payment-intents'), {'order_id': self.order.pk, 'provider': 'manual'}, format='json')
        self.assertEqual(response.status_code, 400)
        self.order.refresh_from_db()
        self.assertNotEqual(self.order.payment_status, Order.PAYMENT_STATUS_PAID)
        self.assertFalse(self.order.payment_intents.exists())

    @override_settings(PAYMENT_WEBHOOK_SECRET='')
    def test_unconfigured_generic_payment_webhooks_fail_closed(self):
        self.client.force_authenticate(None)
        for name in ['payment-webhook', 'payment-mpesa-paybill-webhook']:
            with self.subTest(endpoint=name):
                response = self.client.post(reverse(name), {}, format='json')
                self.assertEqual(response.status_code, 403)

    @patch('apps.orders.views.MpesaClient', side_effect=MpesaConfigurationError('Test provider unavailable'))
    def test_mpesa_alias_reports_provider_failure_and_ignores_client_amount(self, provider):
        response = self.client.post(reverse('payment-mpesa-initiate'), {'order_id': self.order.pk, 'phone': '0700001234', 'amount': '0.01'}, format='json')
        self.assertEqual(response.status_code, 503)
        self.assertNotIn('checkout_request_id', response.data)
        intent = self.order.payment_intents.get()
        from apps.orders.views import resolve_mpesa_stk_amount
        self.assertEqual(intent.amount, Decimal(str(resolve_mpesa_stk_amount(self.order.total))))
        self.assertEqual(intent.status, PaymentIntent.STATUS_FAILED)

    @patch('apps.orders.views.MpesaClient')
    def test_mpesa_alias_rejects_cancelled_order_without_contacting_provider(self, provider):
        self.order.status = Order.STATUS_CANCELLED
        self.order.save()
        response = self.client.post(reverse('payment-mpesa-initiate'), {'order_id': self.order.pk}, format='json')
        self.assertEqual(response.status_code, 400)
        provider.assert_not_called()
        self.assertFalse(self.order.payment_intents.exists())

    @patch('apps.orders.views.MpesaClient')
    def test_mpesa_alias_reuses_pending_request(self, provider):
        PaymentIntent.objects.create(order=self.order, provider=PaymentIntent.PROVIDER_MPESA,
                                    amount='1000', status=PaymentIntent.STATUS_REQUIRES_ACTION,
                                    checkout_request_id='synthetic-pending')
        response = self.client.post(reverse('payment-mpesa-initiate'), {'order_id': self.order.pk}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['checkout_request_id'], 'synthetic-pending')
        provider.assert_not_called()
        self.assertEqual(self.order.payment_intents.count(), 1)

    @override_settings(MPESA_CALLBACK_SECRET='')
    def test_mpesa_callbacks_fail_closed_without_configuration(self):
        for name in ['payment-mpesa-callback', 'payment-mpesa-paybill-validation', 'payment-mpesa-paybill-confirmation']:
            with self.subTest(endpoint=name):
                response = self.client.post(reverse(name), {}, format='json')
                self.assertEqual(response.status_code, 403)

    @override_settings(MPESA_CALLBACK_SECRET='expected-token')
    def test_forged_mpesa_callback_is_rejected(self):
        response = self.client.post(reverse('payment-mpesa-callback') + '?token=wrong-token', {}, format='json')
        self.assertEqual(response.status_code, 403)
        self.order.refresh_from_db()
        self.assertNotEqual(self.order.payment_status, Order.PAYMENT_STATUS_PAID)

    @override_settings(PAYMENT_WEBHOOK_SECRET='synthetic-secret')
    @patch('apps.orders.views._save_order_push_result')
    @patch('apps.orders.views.notify_order_update')
    def test_success_replay_and_late_failure_do_not_duplicate_or_reverse_payment(self, notify, push):
        from apps.orders.models import OrderEvent
        intent = PaymentIntent.objects.create(order=self.order, provider=PaymentIntent.PROVIDER_CARD,
                                             amount='1000', status=PaymentIntent.STATUS_REQUIRES_ACTION)
        url = reverse('payment-webhook')
        for state in ['succeeded', 'succeeded', 'failed']:
            response = self.client.post(url, {'reference': intent.reference, 'status': state}, format='json',
                                        HTTP_X_AVA_WEBHOOK_SECRET='synthetic-secret')
            self.assertEqual(response.status_code, 200)
        self.order.refresh_from_db()
        intent.refresh_from_db()
        self.assertEqual(self.order.payment_status, Order.PAYMENT_STATUS_PAID)
        self.assertEqual(intent.status, PaymentIntent.STATUS_SUCCEEDED)
        self.assertEqual(OrderEvent.objects.filter(order=self.order, event_type='payment_succeeded').count(), 1)
        self.assertEqual(notify.call_count, 1)
        self.assertEqual(push.call_count, 1)

    @override_settings(MPESA_CALLBACK_SECRET='test-callback-token', MPESA_CALLBACK_URL='https://example.test/callback?existing=1',
                       MPESA_C2B_VALIDATION_URL='https://example.test/validate', MPESA_C2B_CONFIRMATION_URL='https://example.test/confirm')
    def test_mpesa_client_includes_token_in_registered_urls(self):
        from urllib.parse import urlsplit, parse_qs
        from apps.orders.mpesa import MpesaClient
        client = MpesaClient()
        for url in [client.callback_url, client.c2b_validation_url, client.c2b_confirmation_url]:
            self.assertEqual(parse_qs(urlsplit(url).query)['token'], ['test-callback-token'])
        self.assertEqual(parse_qs(urlsplit(client.callback_url).query)['existing'], ['1'])

    @patch('apps.orders.views.FlutterwaveClient')
    def test_card_transaction_for_another_reference_cannot_pay_this_order(self, provider):
        from apps.orders.views import _sync_flutterwave_intent
        intent = PaymentIntent.objects.create(order=self.order, provider=PaymentIntent.PROVIDER_CARD,
                                             amount='1000', status=PaymentIntent.STATUS_REQUIRES_ACTION)
        provider.return_value.verify_transaction.return_value = {'status': 'success', 'data': {
            'id': 123, 'status': 'successful', 'amount': 1000, 'currency': 'KES', 'tx_ref': 'ANOTHER-CUSTOMER-REFERENCE'}}
        _sync_flutterwave_intent(intent, '123')
        intent.refresh_from_db()
        self.assertEqual(intent.status, PaymentIntent.STATUS_FAILED)
        self.assertNotEqual(intent.external_reference, 'ANOTHER-CUSTOMER-REFERENCE')
        self.order.refresh_from_db()
        self.assertNotEqual(self.order.payment_status, Order.PAYMENT_STATUS_PAID)

    @patch('apps.orders.views.MpesaClient')
    def test_failed_stk_request_can_retry_on_same_order(self, provider):
        failed = PaymentIntent.objects.create(order=self.order, provider=PaymentIntent.PROVIDER_MPESA,
                                             amount=1000, status=PaymentIntent.STATUS_FAILED)
        provider.return_value.initiate_stk_push.return_value = ('254700001234', {
            'CheckoutRequestID': 'synthetic-retry', 'MerchantRequestID': 'synthetic-merchant'})
        response = self.client.post(reverse('payment-mpesa-initiate'), {'order_id': self.order.pk, 'phone': '0700001234'}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Order.objects.filter(customer=self.customer).count(), 1)
        self.assertEqual(self.order.payment_intents.count(), 2)
        self.assertEqual(self.order.payment_intents.filter(status=PaymentIntent.STATUS_REQUIRES_ACTION).count(), 1)
        failed.refresh_from_db()
        self.assertEqual(failed.status, PaymentIntent.STATUS_FAILED)

    @override_settings(MPESA_ENVIRONMENT='production', MPESA_STK_PUSH_AMOUNT_OVERRIDE='1')
    def test_sandbox_amount_override_cannot_reduce_production_payment(self):
        from apps.orders.views import resolve_mpesa_stk_amount
        self.assertEqual(resolve_mpesa_stk_amount(1000), 1000)

    @override_settings(PAYMENT_PUBLIC_CALLBACK_BASE_URL='https://qa-payments.example.test')
    def test_card_redirect_uses_configured_public_callback_gateway(self):
        from rest_framework.test import APIRequestFactory
        from apps.orders.views import _build_flutterwave_redirect_url
        intent = PaymentIntent.objects.create(order=self.order, provider=PaymentIntent.PROVIDER_CARD, amount=1000)
        url = _build_flutterwave_redirect_url(APIRequestFactory().get('/'), self.order, intent)
        self.assertTrue(url.startswith('https://qa-payments.example.test/api/orders/payments/flutterwave/redirect/?'))

    @patch('apps.orders.views._save_order_push_result')
    @patch('apps.orders.views.notify_order_update')
    @patch('apps.orders.views.FlutterwaveClient')
    def test_card_return_can_recover_missing_parameters_using_verified_stored_reference(self, provider, notify, push):
        intent = PaymentIntent.objects.create(order=self.order, provider=PaymentIntent.PROVIDER_CARD,
                                             amount=1000, status=PaymentIntent.STATUS_REQUIRES_ACTION)
        verified = {'status': 'success', 'data': {'id': 987, 'tx_ref': intent.reference,
                    'amount': 1000, 'currency': 'KES', 'status': 'successful'}}
        provider.return_value.verify_transaction_by_reference.return_value = verified
        provider.return_value.verify_transaction.return_value = verified
        response = self.client.get(reverse('orders-payment-flutterwave-redirect'), {'intent_id':intent.pk,'order_id':self.order.pk})
        self.assertEqual(response.status_code, 302)
        self.order.refresh_from_db()
        self.assertEqual(self.order.payment_status, Order.PAYMENT_STATUS_PAID)
        provider.return_value.verify_transaction_by_reference.assert_called_once_with(intent.reference)
        provider.return_value.verify_transaction.assert_called_once_with('987')

    @patch('apps.orders.views.FlutterwaveClient')
    def test_card_reference_recovery_rejects_other_transaction(self, provider):
        from apps.orders.views import _flutterwave_transaction_id_for_reference
        from apps.orders.flutterwave import FlutterwaveAPIError
        intent = PaymentIntent.objects.create(order=self.order, provider=PaymentIntent.PROVIDER_CARD, amount=1000)
        provider.return_value.verify_transaction_by_reference.return_value = {'status':'success','data':{'id':987,'tx_ref':'unrelated'}}
        with self.assertRaises(FlutterwaveAPIError):
            _flutterwave_transaction_id_for_reference(intent)
