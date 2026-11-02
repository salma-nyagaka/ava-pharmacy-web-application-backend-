from decimal import Decimal
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from unittest.mock import patch
from apps.accounts.models import User
from apps.orders.models import Order, PaymentIntent
from apps.orders.serializers import CheckoutSerializer, PaymentIntentCreateSerializer


class MpesaOnlyPolicyTests(TestCase):
    def setUp(self):
        self.user=User.objects.create_user(email='mpesa-only@avapharmacy.test',password='synthetic-only')
        self.client=APIClient(); self.client.force_authenticate(self.user)

    def test_checkout_rejects_card_and_cod_and_accepts_mpesa(self):
        payload=dict(first_name='QA',last_name='Only',email=self.user.email,phone='0700001234',street='QA',city='Nairobi',county='Nairobi')
        for method in [Order.PAYMENT_CARD,Order.PAYMENT_COD]:
            serializer=CheckoutSerializer(data={**payload,'payment_method':method})
            self.assertFalse(serializer.is_valid()); self.assertIn('payment_method',serializer.errors)
        for method in [Order.PAYMENT_MPESA_STK,Order.PAYMENT_MPESA_PAYBILL]:
            serializer=CheckoutSerializer(data={**payload,'payment_method':method})
            self.assertTrue(serializer.is_valid(),serializer.errors)

    @patch('apps.orders.views.FlutterwaveClient')
    def test_card_provider_cannot_be_initiated(self, provider):
        response=self.client.post(reverse('orders-payment-flutterwave-initiate'),{},format='json')
        self.assertEqual(response.status_code,410); provider.assert_not_called()
        for name in ['card','manual']:
            serializer=PaymentIntentCreateSerializer(data={'order_id':1,'provider':name})
            self.assertFalse(serializer.is_valid()); self.assertIn('provider',serializer.errors)

    def test_legacy_non_mpesa_orders_remain_readable_but_cannot_finalize(self):
        for method in [Order.PAYMENT_CARD,Order.PAYMENT_COD]:
            order=Order.objects.create(customer=self.user,status=Order.STATUS_PAID,payment_status=Order.PAYMENT_STATUS_PAID,payment_method=method,total=Decimal('100'))
            self.assertEqual(self.client.get(reverse('order-detail',args=[order.pk])).status_code,200)
            self.assertEqual(self.client.post(reverse('checkout-finalize',args=[order.pk]),{},format='json').status_code,400)
            order.refresh_from_db();self.assertFalse(order.inventory_committed)

    def test_saved_cards_are_rejected_and_mpesa_reference_is_accepted(self):
        url=reverse('payment-methods')
        card={'brand':'visa','last4':'4242','expiry_month':12,'expiry_year':2030,'cardholder_name':'Synthetic QA'}
        self.assertEqual(self.client.post(url,card,format='json').status_code,400)
        mpesa={**card,'brand':'mpesa','last4':'1234','expiry_month':0,'expiry_year':0}
        self.assertEqual(self.client.post(url,mpesa,format='json').status_code,201)

    def test_admin_creates_only_mpesa_orders_and_retains_readonly_legacy_method(self):
        from django.contrib import admin
        from django.test import RequestFactory
        from apps.orders.admin import OrderAdmin
        model_admin=OrderAdmin(Order,admin.site)
        request=RequestFactory().get('/admin/')
        field=model_admin.formfield_for_choice_field(Order._meta.get_field('payment_method'),request)
        self.assertEqual({value for value,label in field.choices if value},{Order.PAYMENT_MPESA_STK,Order.PAYMENT_MPESA_PAYBILL})
        legacy=Order.objects.create(customer=self.user,payment_method=Order.PAYMENT_COD)
        self.assertIn('payment_method',model_admin.get_readonly_fields(request,legacy))
