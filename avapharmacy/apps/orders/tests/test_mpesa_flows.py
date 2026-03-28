from decimal import Decimal
from datetime import datetime
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.orders.models import Order, PaymentIntent
from apps.orders.payment_helpers import build_paybill_account_reference


@override_settings(
    MPESA_ENVIRONMENT='sandbox',
    MPESA_CONSUMER_KEY='test-key',
    MPESA_CONSUMER_SECRET='test-secret',
    MPESA_SHORTCODE='174379',
    MPESA_PASSKEY='test-passkey',
    MPESA_CALLBACK_URL='https://example.com/api/payments/mpesa/callback/',
    MPESA_TRANSACTION_TYPE='CustomerPayBillOnline',
    MPESA_TIMEOUT_SECONDS=30,
    MPESA_PAYBILL_NUMBER='174379',
    MPESA_C2B_SHORTCODE='174379',
    MPESA_C2B_VALIDATION_URL='https://example.com/api/payments/mpesa/paybill/validation/',
    MPESA_C2B_CONFIRMATION_URL='https://example.com/api/payments/mpesa/paybill/confirmation/',
    MPESA_C2B_URLS_REGISTERED=True,
    MPESA_REQUIRE_PUBLIC_CALLBACK_URLS=True,
    MPESA_STATUS_SYNC_MIN_INTERVAL_SECONDS=15,
    MPESA_STATUS_SYNC_RETRY_AFTER_429_SECONDS=65,
    MPESA_STATUS_SYNC_RETRY_AFTER_403_SECONDS=180,
    FLUTTERWAVE_SECRET_KEY='flw-secret',
    FLUTTERWAVE_SECRET_HASH='flw-hash',
    FLUTTERWAVE_BASE_URL='https://api.flutterwave.com',
    FLUTTERWAVE_TIMEOUT_SECONDS=30,
    FLUTTERWAVE_REDIRECT_URL='http://localhost:3000/checkout',
)
class MpesaFlowTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            email='customer@example.com',
            password='testpass123',
            first_name='Test',
            last_name='Customer',
            role=User.CUSTOMER,
        )
        self.client.force_authenticate(self.user)

    def _create_order(self, *, payment_method, total=Decimal('300.00')):
        return Order.objects.create(
            customer=self.user,
            status=Order.STATUS_DRAFT,
            payment_method=payment_method,
            payment_status=Order.PAYMENT_STATUS_PENDING,
            delivery_method='standard',
            shipping_first_name='Test',
            shipping_last_name='Customer',
            shipping_email='customer@example.com',
            shipping_phone='0727808457',
            shipping_street='Moi Avenue',
            shipping_city='Nairobi',
            shipping_county='Nairobi',
            subtotal=total,
            discount_total=Decimal('0.00'),
            shipping_fee=Decimal('0.00'),
            total=total,
        )

    @patch('apps.orders.views.FlutterwaveClient')
    def test_flutterwave_initiate_sets_checkout_link_and_order_tx_ref(self, flutterwave_client_cls):
        order = self._create_order(payment_method=Order.PAYMENT_CARD, total=Decimal('1200.00'))
        flutterwave_client_cls.return_value.create_card_checkout.return_value = {
            'status': 'success',
            'message': 'Hosted link created',
            'data': {
                'link': 'https://checkout.flutterwave.com/v3/hosted/pay/test-link',
                'tx_ref': 'PAY-TX-REF-001',
            },
        }

        response = self.client.post(
            reverse('orders-payment-flutterwave-initiate'),
            {'order_id': order.id, 'return_url': 'http://localhost:3000/checkout'},
            format='json',
        )
        self.assertEqual(response.status_code, 201)

        intent = PaymentIntent.objects.get(order=order, provider=PaymentIntent.PROVIDER_CARD)
        order.refresh_from_db()
        self.assertEqual(intent.status, PaymentIntent.STATUS_REQUIRES_ACTION)
        self.assertEqual(intent.client_secret, 'https://checkout.flutterwave.com/v3/hosted/pay/test-link')
        self.assertEqual(intent.external_reference, 'PAY-TX-REF-001')
        self.assertEqual(order.flutterwave_tx_ref, 'PAY-TX-REF-001')
        self.assertEqual(order.payment_status, Order.PAYMENT_STATUS_REQUIRES_ACTION)

    @patch('apps.orders.views.FlutterwaveClient')
    def test_flutterwave_redirect_verifies_payment_and_redirects_to_checkout(self, flutterwave_client_cls):
        order = self._create_order(payment_method=Order.PAYMENT_CARD, total=Decimal('1200.00'))
        intent = PaymentIntent.objects.create(
            order=order,
            initiated_by=self.user,
            provider=PaymentIntent.PROVIDER_CARD,
            status=PaymentIntent.STATUS_REQUIRES_ACTION,
            amount=order.total,
            external_reference='PAY-TX-REF-002',
        )
        order.flutterwave_tx_ref = intent.reference
        order.payment_status = Order.PAYMENT_STATUS_REQUIRES_ACTION
        order.save(update_fields=['flutterwave_tx_ref', 'payment_status', 'updated_at'])
        flutterwave_client_cls.return_value.verify_transaction.return_value = {
            'status': 'success',
            'message': 'Verification successful',
            'data': {
                'id': 987654,
                'tx_ref': intent.reference,
                'flw_ref': 'FLW-REF-002',
                'status': 'successful',
                'amount': '1200.00',
                'currency': 'KES',
            },
        }

        response = self.client.get(
            reverse('orders-payment-flutterwave-redirect'),
            {
                'tx_ref': intent.reference,
                'transaction_id': '987654',
                'return_url': 'http://localhost:3000/checkout',
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn('status=successful', response['Location'])
        self.assertIn(f'intent_id={intent.id}', response['Location'])

        order.refresh_from_db()
        intent.refresh_from_db()
        self.assertEqual(order.payment_status, Order.PAYMENT_STATUS_PAID)
        self.assertEqual(order.status, Order.STATUS_PAID)
        self.assertEqual(order.flutterwave_tx_ref, intent.reference)
        self.assertEqual(order.flutterwave_tx_id, '987654')
        self.assertEqual(intent.status, PaymentIntent.STATUS_SUCCEEDED)
        self.assertEqual(intent.provider_reference, 'FLW-REF-002')

    @patch('apps.orders.views.FlutterwaveClient')
    def test_flutterwave_status_endpoint_verifies_existing_transaction(self, flutterwave_client_cls):
        order = self._create_order(payment_method=Order.PAYMENT_CARD, total=Decimal('900.00'))
        intent = PaymentIntent.objects.create(
            order=order,
            initiated_by=self.user,
            provider=PaymentIntent.PROVIDER_CARD,
            status=PaymentIntent.STATUS_REQUIRES_ACTION,
            amount=order.total,
            external_reference='PAY-TX-REF-003',
        )
        order.flutterwave_tx_ref = intent.reference
        order.flutterwave_tx_id = '111222333'
        order.payment_status = Order.PAYMENT_STATUS_REQUIRES_ACTION
        order.save(update_fields=['flutterwave_tx_ref', 'flutterwave_tx_id', 'payment_status', 'updated_at'])
        flutterwave_client_cls.return_value.verify_transaction.return_value = {
            'status': 'success',
            'message': 'Verification successful',
            'data': {
                'id': 111222333,
                'tx_ref': intent.reference,
                'flw_ref': 'FLW-REF-003',
                'status': 'successful',
                'amount': '900.00',
                'currency': 'KES',
            },
        }

        response = self.client.get(reverse('orders-payment-flutterwave-status', args=[intent.reference]))
        self.assertEqual(response.status_code, 200)
        intent.refresh_from_db()
        order.refresh_from_db()
        self.assertEqual(intent.status, PaymentIntent.STATUS_SUCCEEDED)
        self.assertEqual(order.payment_status, Order.PAYMENT_STATUS_PAID)

    @patch('apps.orders.views.FlutterwaveClient')
    def test_flutterwave_webhook_verifies_signature_and_marks_paid(self, flutterwave_client_cls):
        order = self._create_order(payment_method=Order.PAYMENT_CARD, total=Decimal('650.00'))
        intent = PaymentIntent.objects.create(
            order=order,
            initiated_by=self.user,
            provider=PaymentIntent.PROVIDER_CARD,
            status=PaymentIntent.STATUS_REQUIRES_ACTION,
            amount=order.total,
            external_reference='PAY-TX-REF-004',
        )
        flutterwave_client_cls.return_value.verify_signature.return_value = True
        flutterwave_client_cls.return_value.verify_transaction.return_value = {
            'status': 'success',
            'message': 'Verification successful',
            'data': {
                'id': 444555666,
                'tx_ref': intent.reference,
                'flw_ref': 'FLW-REF-004',
                'status': 'successful',
                'amount': '650.00',
                'currency': 'KES',
            },
        }

        response = self.client.post(
            reverse('orders-payment-flutterwave-callback'),
            {'data': {'id': 444555666, 'tx_ref': intent.reference}},
            format='json',
            HTTP_VERIF_HASH='flw-hash',
        )
        self.assertEqual(response.status_code, 200)
        order.refresh_from_db()
        intent.refresh_from_db()
        self.assertEqual(order.payment_status, Order.PAYMENT_STATUS_PAID)
        self.assertEqual(intent.status, PaymentIntent.STATUS_SUCCEEDED)

    @patch('apps.orders.views.MpesaClient')
    def test_stk_push_callback_marks_order_paid_and_sync_reuses_terminal_state(self, mpesa_client_cls):
        order = self._create_order(payment_method=Order.PAYMENT_MPESA_STK)
        mpesa_client = mpesa_client_cls.return_value
        mpesa_client.initiate_stk_push.return_value = (
            '254727808457',
            {
                'ResponseCode': '0',
                'CustomerMessage': 'Success. Request accepted for processing',
                'MerchantRequestID': 'MID-123',
                'CheckoutRequestID': 'CID-123',
            },
        )

        create_response = self.client.post(
            reverse('payment-intents'),
            {'order_id': order.id, 'provider': PaymentIntent.PROVIDER_MPESA, 'phone': '0727808457'},
            format='json',
        )
        self.assertEqual(create_response.status_code, 201)

        intent = PaymentIntent.objects.get(order=order, provider=PaymentIntent.PROVIDER_MPESA)
        self.assertEqual(intent.status, PaymentIntent.STATUS_REQUIRES_ACTION)
        self.assertEqual(intent.checkout_request_id, 'CID-123')

        callback_payload = {
            'Body': {
                'stkCallback': {
                    'MerchantRequestID': 'MID-123',
                    'CheckoutRequestID': 'CID-123',
                    'ResultCode': 0,
                    'ResultDesc': 'The service request is processed successfully.',
                    'CallbackMetadata': {
                        'Item': [
                            {'Name': 'Amount', 'Value': 300},
                            {'Name': 'MpesaReceiptNumber', 'Value': 'UCGI29M26J'},
                            {'Name': 'PhoneNumber', 'Value': 254727808457},
                        ]
                    },
                }
            }
        }
        callback_response = self.client.post(
            reverse('payment-mpesa-callback'),
            callback_payload,
            format='json',
        )
        self.assertEqual(callback_response.status_code, 200)

        order.refresh_from_db()
        intent.refresh_from_db()
        self.assertEqual(order.payment_status, Order.PAYMENT_STATUS_PAID)
        self.assertEqual(order.status, Order.STATUS_PAID)
        self.assertEqual(order.payment_reference, 'UCGI29M26J')
        self.assertEqual(intent.status, PaymentIntent.STATUS_SUCCEEDED)
        self.assertEqual(intent.provider_reference, 'UCGI29M26J')
        self.assertEqual(intent.last_error, '')

        sync_response = self.client.post(reverse('payment-intent-sync', args=[intent.id]), {}, format='json')
        self.assertEqual(sync_response.status_code, 200)
        intent.refresh_from_db()
        self.assertEqual(intent.status, PaymentIntent.STATUS_SUCCEEDED)
        mpesa_client.query_stk_status.assert_not_called()

    @patch('apps.orders.views.MpesaClient')
    def test_stk_sync_keeps_waiting_state_for_processing_response(self, mpesa_client_cls):
        order = self._create_order(payment_method=Order.PAYMENT_MPESA_STK)
        intent = PaymentIntent.objects.create(
            order=order,
            initiated_by=self.user,
            provider=PaymentIntent.PROVIDER_MPESA,
            status=PaymentIntent.STATUS_REQUIRES_ACTION,
            amount=order.total,
            phone_number='254727808457',
            external_reference=order.order_number,
            merchant_request_id='MID-444',
            checkout_request_id='CID-444',
        )
        order.payment_status = Order.PAYMENT_STATUS_REQUIRES_ACTION
        order.save(update_fields=['payment_status', 'updated_at'])

        mpesa_client_cls.return_value.query_stk_status.return_value = {
            'ResultCode': '1037',
            'ResultDesc': 'The transaction is still under processing',
        }

        sync_response = self.client.post(reverse('payment-intent-sync', args=[intent.id]), {}, format='json')
        self.assertEqual(sync_response.status_code, 202)
        intent.refresh_from_db()
        order.refresh_from_db()
        self.assertEqual(intent.status, PaymentIntent.STATUS_REQUIRES_ACTION)
        self.assertEqual(intent.last_error, '')
        self.assertEqual(order.payment_status, Order.PAYMENT_STATUS_REQUIRES_ACTION)

    @override_settings(MPESA_STATUS_SYNC_MIN_INTERVAL_SECONDS=30)
    @patch('apps.orders.views.MpesaClient')
    def test_stk_sync_respects_min_interval_before_next_query(self, mpesa_client_cls):
        order = self._create_order(payment_method=Order.PAYMENT_MPESA_STK)
        intent = PaymentIntent.objects.create(
            order=order,
            initiated_by=self.user,
            provider=PaymentIntent.PROVIDER_MPESA,
            status=PaymentIntent.STATUS_REQUIRES_ACTION,
            amount=order.total,
            phone_number='254727808457',
            external_reference=order.order_number,
            merchant_request_id='MID-555',
            checkout_request_id='CID-555',
            payload={'status_sync': {'last_attempt_at': '2026-03-16T10:00:00+03:00'}},
        )
        with patch('apps.orders.views.timezone.now') as mocked_now:
            from django.utils import timezone
            mocked_now.return_value = datetime(2026, 3, 16, 10, 0, 10, tzinfo=timezone.get_current_timezone())
            response = self.client.post(reverse('payment-intent-sync', args=[intent.id]), {}, format='json')
        self.assertEqual(response.status_code, 202)
        mpesa_client_cls.return_value.query_stk_status.assert_not_called()

    @patch('apps.orders.views.MpesaClient')
    def test_customer_can_cancel_pending_payment_intent(self, mpesa_client_cls):
        order = self._create_order(payment_method=Order.PAYMENT_MPESA_STK)
        mpesa_client_cls.return_value.initiate_stk_push.return_value = (
            '254727808457',
            {
                'ResponseCode': '0',
                'CustomerMessage': 'Success. Request accepted for processing',
                'MerchantRequestID': 'MID-CANCEL',
                'CheckoutRequestID': 'CID-CANCEL',
            },
        )

        create_response = self.client.post(
            reverse('payment-intents'),
            {'order_id': order.id, 'provider': PaymentIntent.PROVIDER_MPESA, 'phone': '0727808457'},
            format='json',
        )
        self.assertEqual(create_response.status_code, 201)

        intent = PaymentIntent.objects.get(order=order, provider=PaymentIntent.PROVIDER_MPESA)
        cancel_response = self.client.post(reverse('payment-intent-cancel', args=[intent.id]), {}, format='json')
        self.assertEqual(cancel_response.status_code, 200)

        intent.refresh_from_db()
        order.refresh_from_db()
        self.assertEqual(intent.status, PaymentIntent.STATUS_CANCELLED)
        self.assertEqual(intent.last_error, 'Payment cancelled by customer.')
        self.assertEqual(order.payment_status, Order.PAYMENT_STATUS_PENDING)

    @override_settings(MPESA_C2B_URLS_REGISTERED=False)
    def test_paybill_create_fails_until_callbacks_marked_registered(self):
        order = self._create_order(payment_method=Order.PAYMENT_MPESA_PAYBILL)
        response = self.client.post(
            reverse('payment-intents'),
            {'order_id': order.id, 'provider': PaymentIntent.PROVIDER_PAYBILL},
            format='json',
        )
        self.assertEqual(response.status_code, 503)
        body = response.json()
        message = body.get('detail') or body.get('error', {}).get('message', '')
        self.assertIn('MPESA_C2B_URLS_REGISTERED=true', message)

    def test_paybill_validation_and_confirmation_mark_order_paid(self):
        order = self._create_order(payment_method=Order.PAYMENT_MPESA_PAYBILL, total=Decimal('850.00'))

        create_response = self.client.post(
            reverse('payment-intents'),
            {'order_id': order.id, 'provider': PaymentIntent.PROVIDER_PAYBILL},
            format='json',
        )
        self.assertEqual(create_response.status_code, 201)

        intent = PaymentIntent.objects.get(order=order, provider=PaymentIntent.PROVIDER_PAYBILL)
        self.assertEqual(intent.status, PaymentIntent.STATUS_REQUIRES_ACTION)
        self.assertEqual(intent.external_reference, build_paybill_account_reference(order))

        validation_payload = {
            'TransactionType': 'Pay Bill',
            'TransID': 'QWE123PAY',
            'TransTime': '20260316130500',
            'TransAmount': '850.00',
            'BusinessShortCode': '174379',
            'BillRefNumber': order.order_number,
            'MSISDN': '254727808457',
            'FirstName': 'Test',
            'LastName': 'Customer',
        }
        validation_response = self.client.post(
            reverse('payment-mpesa-paybill-validation'),
            validation_payload,
            format='json',
        )
        self.assertEqual(validation_response.status_code, 200)
        self.assertEqual(validation_response.json()['ResultCode'], 0)

        confirmation_payload = {
            **validation_payload,
            'TransID': 'QWE123PAYCONF',
        }
        confirmation_response = self.client.post(
            reverse('payment-mpesa-paybill-confirmation'),
            confirmation_payload,
            format='json',
        )
        self.assertEqual(confirmation_response.status_code, 200)
        self.assertEqual(confirmation_response.json()['ResultCode'], 0)

        order.refresh_from_db()
        intent.refresh_from_db()
        self.assertEqual(order.payment_status, Order.PAYMENT_STATUS_PAID)
        self.assertEqual(order.status, Order.STATUS_PAID)
        self.assertEqual(order.payment_reference, 'QWE123PAYCONF')
        self.assertEqual(intent.status, PaymentIntent.STATUS_SUCCEEDED)
        self.assertEqual(intent.provider_reference, 'QWE123PAYCONF')
        self.assertEqual(intent.last_error, '')

        sync_response = self.client.post(reverse('payment-intent-sync', args=[intent.id]), {}, format='json')
        self.assertEqual(sync_response.status_code, 200)
        self.assertEqual(sync_response.data['status'], PaymentIntent.STATUS_SUCCEEDED)

    def test_paybill_validation_rejects_wrong_amount(self):
        order = self._create_order(payment_method=Order.PAYMENT_MPESA_PAYBILL, total=Decimal('500.00'))
        PaymentIntent.objects.create(
            order=order,
            initiated_by=self.user,
            provider=PaymentIntent.PROVIDER_PAYBILL,
            status=PaymentIntent.STATUS_REQUIRES_ACTION,
            amount=order.total,
            external_reference=order.order_number,
        )
        order.payment_status = Order.PAYMENT_STATUS_REQUIRES_ACTION
        order.save(update_fields=['payment_status', 'updated_at'])

        response = self.client.post(
            reverse('payment-mpesa-paybill-validation'),
            {
                'BusinessShortCode': '174379',
                'BillRefNumber': order.order_number,
                'TransAmount': '100.00',
            },
            format='json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['ResultCode'], 1)
        self.assertIn('Expected KES 500.00', response.json()['ResultDesc'])
