from datetime import timedelta
from decimal import Decimal
from django.db.models import Sum
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from apps.accounts.models import User
from apps.orders.models import Cart, CartItem, Coupon, Order, PaymentIntent
from . import test_order_creation as creation_fixtures


class OrdersModuleAcceptanceTests(TestCase):
    setUp = creation_fixtures.OrderCreationFlowTests.setUp
    _direct_order = creation_fixtures.OrderCreationFlowTests._direct_order

    def test_cart_quantity_remove_clear_and_refresh(self):
        self.client.force_authenticate(self.customer)
        cart = Cart.objects.create(user=self.customer)
        item = CartItem.objects.create(cart=cart, variant=self.variant, quantity=2)
        response = self.client.patch(reverse('cart-item-update', args=[item.pk]), {'quantity': 3}, format='json')
        self.assertEqual(response.status_code, 200)
        item.refresh_from_db()
        self.assertEqual(item.quantity, 3)
        self.assertEqual(cart.total, Decimal('2100'))
        self.assertEqual(self.client.get(reverse('cart')).status_code, 200)
        self.assertEqual(self.client.delete(reverse('cart-item-delete', args=[item.pk])).status_code, 200)
        self.assertEqual(cart.items.count(), 0)
        CartItem.objects.create(cart=cart, variant=self.variant, quantity=1)
        self.assertEqual(self.client.delete(reverse('cart-clear')).status_code, 200)
        self.assertEqual(cart.items.count(), 0)

    def test_coupon_expiry_minimum_replacement_and_removal(self):
        self.client.force_authenticate(self.customer)
        cart = Cart.objects.create(user=self.customer)
        CartItem.objects.create(cart=cart, variant=self.variant, quantity=2)
        valid = Coupon.objects.create(code='ORDVALID', value=10, minimum_subtotal=1000)
        Coupon.objects.create(code='ORDEXPIRED', value=50, ends_at=timezone.now()-timedelta(days=1))
        Coupon.objects.create(code='ORDMIN', value=10, minimum_subtotal=2000)
        second = Coupon.objects.create(code='ORDSECOND', value=20)
        for code in ['ORDEXPIRED', 'ORDMIN']:
            self.assertEqual(self.client.post(reverse('cart-apply-coupon'), {'code': code}, format='json').status_code, 400)
        self.assertEqual(self.client.post(reverse('cart-apply-coupon'), {'code': valid.code}, format='json').status_code, 200)
        cart.refresh_from_db()
        self.assertEqual(cart.discount_total, Decimal('140'))
        self.assertEqual(self.client.post(reverse('cart-apply-coupon'), {'code': second.code}, format='json').status_code, 200)
        cart.refresh_from_db()
        self.assertEqual(cart.discount_total, Decimal('280'))
        self.assertEqual(self.client.delete(reverse('cart-remove-coupon')).status_code, 200)
        cart.refresh_from_db()
        self.assertEqual(cart.discount_total, 0)

    def test_customer_cannot_access_other_order_payment_or_cart_item(self):
        order = self._direct_order()
        intent = PaymentIntent.objects.create(order=order, provider=PaymentIntent.PROVIDER_CARD, amount=order.total)
        cart = Cart.objects.create(user=self.customer)
        item = CartItem.objects.create(cart=cart, variant=self.variant)
        other = User.objects.create_user(email='unrelated-orders@avapharmacy.test', password='synthetic-only')
        self.client.force_authenticate(other)
        for name in ['order-detail', 'order-tracking']:
            self.assertEqual(self.client.get(reverse(name, args=[order.pk])).status_code, 404)
        for name, pk in [('order-cancel', order.pk), ('checkout-finalize', order.pk), ('payment-intent-sync', intent.pk), ('payment-intent-cancel', intent.pk)]:
            self.assertEqual(self.client.post(reverse(name, args=[pk]), {}, format='json').status_code, 404)
        self.assertEqual(self.client.patch(reverse('cart-item-update', args=[item.pk]), {'quantity': 3}, format='json').status_code, 404)
        item.refresh_from_db()
        self.assertEqual(item.quantity, 1)

    def test_delivered_refund_does_not_restock_and_replay_has_one_event(self):
        from unittest.mock import patch
        from apps.orders.models import OrderItem, OrderEvent
        from apps.orders.stock import commit_order_inventory
        order = self._direct_order(status=Order.STATUS_DELIVERED, payment_status=Order.PAYMENT_STATUS_PAID)
        OrderItem.objects.create(order=order, variant=self.variant, quantity=2, unit_price=700)
        commit_order_inventory(order)
        before = self.variant.inventories.aggregate(total=Sum('stock_quantity'))['total']
        self.client.force_authenticate(self.admin)
        with patch('apps.orders.views._save_order_push_result'), patch('apps.orders.views.notify_order_update'):
            for _ in range(2):
                self.assertEqual(self.client.post(reverse('admin-order-refund', args=[order.pk]), {}, format='json').status_code, 200)
        after = self.variant.inventories.aggregate(total=Sum('stock_quantity'))['total']
        self.assertEqual(before, after)
        self.assertEqual(OrderEvent.objects.filter(order=order, event_type='refunded').count(), 1)

    def test_order_scoped_return_uses_url_order_and_protects_ownership(self):
        from apps.orders.models import ReturnRequest
        order = self._direct_order(status=Order.STATUS_DELIVERED)
        other = self._direct_order(status=Order.STATUS_DELIVERED)
        self.client.force_authenticate(self.customer)
        response = self.client.post(reverse('order-return', args=[order.pk]), {'reason': 'Synthetic damaged pack', 'order_id': other.pk}, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(ReturnRequest.objects.get().order_id, order.pk)

    def test_staff_cannot_fulfill_unpaid_order_or_reopen_terminal_order(self):
        order = self._direct_order()
        self.client.force_authenticate(self.admin)
        response = self.client.patch(reverse('admin-order-detail', args=[order.pk]), {'status': Order.STATUS_SHIPPED}, format='json')
        self.assertEqual(response.status_code, 400)
        order.status = Order.STATUS_CANCELLED
        order.save()
        response = self.client.patch(reverse('admin-order-detail', args=[order.pk]), {'status': Order.STATUS_PROCESSING}, format='json')
        self.assertEqual(response.status_code, 400)

    def test_unpaid_draft_does_not_consume_coupon_usage(self):
        coupon = Coupon.objects.create(code='ORDDRAFT', value=10, usage_limit=1, per_user_limit=1)
        order = self._direct_order(status=Order.STATUS_DRAFT, coupon=coupon)
        self.assertTrue(coupon.is_available(self.customer))
        order.status = Order.STATUS_PENDING
        order.save()
        self.assertFalse(coupon.is_available(self.customer))

    def test_paid_finalize_preserves_cart_items_added_after_payment(self):
        from unittest.mock import patch
        from apps.orders.models import OrderItem
        order = self._direct_order(status=Order.STATUS_PAID, payment_status=Order.PAYMENT_STATUS_PAID)
        OrderItem.objects.create(order=order, variant=self.variant, quantity=1, unit_price=700)
        cart = Cart.objects.create(user=self.customer)
        newer = CartItem.objects.create(cart=cart, variant=self.variant, quantity=1)
        self.client.force_authenticate(self.customer)
        with patch('apps.orders.views._save_order_push_result'), patch('apps.orders.views.notify_order_update'):
            response = self.client.post(reverse('checkout-finalize', args=[order.pk]), {}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(CartItem.objects.filter(pk=newer.pk).exists())

    def test_scoped_checkout_shipping_uses_selected_items_only(self):
        from django.test import override_settings
        from apps.orders.views import build_order_totals
        cart = Cart.objects.create(user=self.customer)
        item = CartItem.objects.create(cart=cart, variant=self.variant, quantity=10)
        class SelectedItem:
            variant = self.variant
            quantity = 1
            subtotal = Decimal('700')
        with override_settings(FREE_SHIPPING_THRESHOLD=3000, SHIPPING_FEE=300):
            self.assertEqual(build_order_totals(cart, items=[SelectedItem()]),
                             (Decimal('700'), Decimal('0'), Decimal('300'), Decimal('1000')))

    def test_return_rejects_invalid_amount_and_unplaced_order(self):
        order = self._direct_order(status=Order.STATUS_DELIVERED)
        self.client.force_authenticate(self.customer)
        for amount in ['-1', '1001']:
            response = self.client.post(reverse('order-return', args=[order.pk]), {'reason': 'Synthetic return', 'requested_refund_amount': amount}, format='json')
            self.assertEqual(response.status_code, 400)
        order.status = Order.STATUS_DRAFT
        order.save()
        self.assertEqual(self.client.post(reverse('order-return', args=[order.pk]), {'reason': 'Synthetic return'}, format='json').status_code, 400)

    def test_sku_promotion_matches_catalog_cart_and_snapshot_without_sibling_leak(self):
        from apps.products.models import Promotion
        from apps.products.services import calculate_variant_pricing
        from apps.orders.views import snapshot_cart_to_order
        today = timezone.now().date()
        Promotion.objects.create(title='Synthetic SKU offer', type='percentage', value=10,
                                 scope='product', targets=[self.variant.sku], status='active',
                                 start_date=today, end_date=today)
        sibling = self.product.variants.create(sku='ORDER-SIBLING', name='Other pack', price=1000)
        cart = Cart.objects.create(user=self.customer)
        item = CartItem.objects.create(cart=cart, variant=self.variant, quantity=2)
        self.assertEqual(calculate_variant_pricing(self.variant)['final_price'], Decimal('630'))
        self.assertEqual(calculate_variant_pricing(sibling)['final_price'], Decimal('1000'))
        self.assertEqual(item.unit_price, Decimal('630'))
        self.assertEqual(cart.total, Decimal('1260'))
        order = self._direct_order()
        snapshot_cart_to_order(order, [item])
        self.assertEqual(order.items.get().unit_price, Decimal('630'))

    def test_stackable_promotions_respect_order_minimum_and_coupon_applies_after_them(self):
        from apps.products.models import Promotion
        today = timezone.now().date()
        for title in ['First', 'Second']:
            Promotion.objects.create(title=title, type='percentage', value=10, scope='all',
                                     is_stackable=True, minimum_order_amount=1000, status='active',
                                     start_date=today, end_date=today)
        cart = Cart.objects.create(user=self.customer, coupon=Coupon.objects.create(code='STACKCOUPON', value=10))
        item = CartItem.objects.create(cart=cart, variant=self.variant, quantity=1)
        self.assertEqual(item.unit_price, Decimal('700'))
        item.quantity = 2
        item.save()
        self.assertEqual(item.unit_price, Decimal('567'))
        self.assertEqual(cart.total, Decimal('1134'))
        self.assertEqual(cart.discount_total, Decimal('113.40'))

    def test_guest_cart_merge_failure_is_atomic(self):
        self.client.force_authenticate(self.customer)
        response = self.client.post(reverse('cart-merge'), {'items': [
            {'product_id': self.product.pk, 'variant_id': self.variant.pk, 'quantity': 2},
            {'product_id': self.product.pk, 'quantity': 1},
        ]}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertFalse(CartItem.objects.filter(cart__user=self.customer).exists())

    def test_return_review_requires_quarantine_and_recorded_refund(self):
        from apps.orders.models import ReturnRequest
        from unittest.mock import patch
        order = self._direct_order(status=Order.STATUS_DELIVERED, payment_status=Order.PAYMENT_STATUS_PAID)
        self.client.force_authenticate(self.customer)
        response = self.client.post(reverse('order-return', args=[order.pk]), {'reason': 'Synthetic damaged pack'}, format='json')
        self.assertEqual(response.status_code, 201)
        request = ReturnRequest.objects.get(order=order)
        self.client.force_authenticate(self.admin)
        url = reverse('admin-return-request-detail', args=[request.pk])
        self.assertEqual(self.client.patch(url, {'status': 'approved'}, format='json').status_code, 200)
        self.assertEqual(self.client.patch(url, {'status': 'received'}, format='json').status_code, 400)
        disposition = {'returned_medicine_quarantined': True, 'non_resale_acknowledged': True,
                       'inventory_disposition': 'Synthetic non-resale quarantine'}
        self.assertEqual(self.client.patch(url, {'status': 'received', **disposition}, format='json').status_code, 200)
        self.assertEqual(self.client.patch(url, {'status': 'refunded'}, format='json').status_code, 400)
        with patch('apps.orders.views._save_order_push_result'), patch('apps.orders.views.notify_order_update'):
            self.assertEqual(self.client.post(reverse('admin-order-refund', args=[order.pk]), {'reason': 'QA-EXTERNAL-RECORD-ONLY'}, format='json').status_code, 200)
        self.assertEqual(self.client.patch(url, {'status': 'refunded'}, format='json').status_code, 200)

    def test_finance_csv_matches_order_and_is_staff_only(self):
        import csv
        from io import StringIO
        order = self._direct_order(payment_status=Order.PAYMENT_STATUS_PAID)
        url = reverse('admin-finance-reports-download')
        self.client.force_authenticate(self.customer)
        self.assertEqual(self.client.get(url).status_code, 403)
        self.client.force_authenticate(self.admin)
        response = self.client.get(url, {'type': 'orders', 'range': 1})
        self.assertEqual(response.status_code, 200)
        rows = list(csv.DictReader(StringIO(response.content.decode())))
        row = next(row for row in rows if row['Order #'] == order.order_number)
        self.assertEqual(Decimal(row['Total (KSh)']), Decimal('1000'))
        self.assertEqual(row['Payment Status'], Order.PAYMENT_STATUS_PAID)

    def test_cart_uses_current_price_and_rejects_parent_deactivation(self):
        from apps.orders.views import build_order_totals, _product_availability_error
        cart = Cart.objects.create(user=self.customer)
        CartItem.objects.create(cart=cart, variant=self.variant, quantity=2)
        self.variant.price = Decimal('800')
        self.variant.save()
        self.assertEqual(build_order_totals(cart)[0], Decimal('1600'))
        self.product.is_active = False
        self.product.save()
        self.variant.refresh_from_db()
        self.assertIsNotNone(_product_availability_error(self.variant, 1))
