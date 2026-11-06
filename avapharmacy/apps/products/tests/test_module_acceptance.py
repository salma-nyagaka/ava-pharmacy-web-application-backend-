from avapharmacy.test_compliance_fixtures import delivery_fixture
"""Catalog pagination and stock safety acceptance regressions."""
from avapharmacy.test_compliance_fixtures import catalogue_fixture
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from decimal import Decimal

from django.db import close_old_connections, connections
from django.test import TestCase, TransactionTestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.orders.models import Order, OrderItem
from apps.orders.stock import commit_order_inventory, release_order_inventory
from apps.products.models import Brand, Product, Store, StoreVariantListing, Variant, VariantInventory, VariantReview


def make_order(customer, variant, quantity=1):
    order = Order.objects.create(customer=customer, status=Order.STATUS_PENDING,
        payment_method=Order.PAYMENT_COD, shipping_first_name='Synthetic', shipping_last_name='QA',
        shipping_email=customer.email, shipping_phone='+254700000001', shipping_street='QA Street',
        shipping_city='Nairobi', shipping_county='Nairobi')
    OrderItem.objects.create(order=order, variant=variant, product_name=variant.product.name,
        product_sku=variant.product.sku, variant_name=variant.name, variant_sku=variant.sku,
        quantity=quantity, unit_price=variant.price)
    return order


class ModuleAcceptanceTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_user(email='module-admin@avapharmacy.test', role=User.ADMIN, is_staff=True)
        self.customer = User.objects.create_user(email='module-customer@avapharmacy.test')
        self.brand = Brand.objects.create(name='Synthetic QA Brand')
        self.product = Product.objects.create(name='Synthetic QA Medicine', sku='MODULE-QA', brand=self.brand)
        self.a = Variant.objects.create(product=self.product, name='Synthetic QA 100mg', sku='MODULE-A', price=100,**catalogue_fixture(medicine=False, exclude=('product', 'name', 'sku', 'price')))
        self.product_b = Product.objects.create(name='Synthetic QA Medicine B', sku='MODULE-QA-B', brand=self.brand)
        self.b = Variant.objects.create(product=self.product_b, name='Synthetic QA 200mg', sku='MODULE-B', price=400,**catalogue_fixture(medicine=False, exclude=('product', 'name', 'sku', 'price')))
        self.rows = []
        for code, quantities in [('module-store-1', (50, 20)), ('module-store-2', (30, 10))]:
            store = Store.objects.create(name=code, code=code)
            for variant, qty in zip((self.a, self.b), quantities):
                listing = StoreVariantListing.objects.create(store=store, variant=variant, price=variant.price)
                self.rows.append(VariantInventory.objects.create(variant=variant, store_listing=listing,
                    stock_quantity=qty, low_stock_threshold=5))

    def balances(self):
        return list(VariantInventory.objects.filter(pk__in=[r.pk for r in self.rows]).order_by('pk').values_list('stock_quantity', flat=True))

    def test_two_pack_sale_and_repeated_commit_release_keep_exact_balances(self):
        order = make_order(self.customer, self.a, 2)
        commit_order_inventory(order)
        self.assertEqual(self.balances(), [48, 20, 30, 10])
        commit_order_inventory(Order.objects.get(pk=order.pk))
        self.assertEqual(self.balances(), [48, 20, 30, 10])
        release_order_inventory(order)
        release_order_inventory(Order.objects.get(pk=order.pk))
        self.assertEqual(self.balances(), [50, 20, 30, 10])
        order.refresh_from_db()
        self.assertFalse(order.inventory_committed)

    def test_inv02_paid_checkout_deducts_exact_store_and_cancellation_restores_once(self):
        from django.test import override_settings
        from apps.orders.models import Cart, CartItem, PaymentIntent, OrderEvent
        self.client.force_authenticate(self.customer)
        cart = Cart.objects.create(user=self.customer)
        screening = dict(intended_user='self', age_group='adult', allergies='None',
                         current_medicines='None', symptoms_or_reason='Synthetic QA only',
                         pregnant_or_breastfeeding='not_applicable', counseling_acknowledged=True)
        CartItem.objects.create(cart=cart, variant=self.a, quantity=2, otc_screening=screening)
        response = self.client.post(reverse('checkout-draft'), dict(first_name='Synthetic', last_name='QA',
            email=self.customer.email, phone='0700001234', street='QA only', city='Nairobi', county='Nairobi',
            payment_method=Order.PAYMENT_MPESA_STK, delivery_method='standard'), format='json')
        self.assertEqual(response.status_code, 201, response.data)
        order = Order.objects.get(customer=self.customer)
        self.assertEqual(self.balances(), [50, 20, 30, 10])
        self.assertEqual(self.client.post(reverse('checkout-finalize', args=[order.pk])).status_code, 400)
        intent = PaymentIntent.objects.create(order=order, initiated_by=self.customer, provider=PaymentIntent.PROVIDER_MPESA,
            amount=order.total, status=PaymentIntent.STATUS_REQUIRES_ACTION,
            payload={'source':'INV-02 controlled test notification'})
        payload = {'reference':intent.reference, 'status':'succeeded',
                   'provider_reference':'QA-INV02-SIMULATED', 'payload':{'synthetic_test':True}}
        with override_settings(PAYMENT_WEBHOOK_SECRET='inv02-test-secret'):
            self.assertEqual(self.client.post(reverse('payment-webhook'), payload, format='json').status_code, 403)
            for _ in range(2):
                self.assertEqual(self.client.post(reverse('payment-webhook'), payload, format='json',
                    HTTP_X_AVA_WEBHOOK_SECRET='inv02-test-secret').status_code, 200)
        self.assertEqual(self.balances(), [50, 20, 30, 10])
        response = self.client.post(reverse('checkout-finalize', args=[order.pk]))
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(self.balances(), [48, 20, 30, 10])
        new_item = CartItem.objects.create(cart=cart, variant=self.b, quantity=1)
        self.assertEqual(self.client.post(reverse('checkout-finalize', args=[order.pk])).status_code, 200)
        self.assertTrue(CartItem.objects.filter(pk=new_item.pk).exists())
        self.assertEqual(OrderEvent.objects.filter(order=order, event_type='order_finalized').count(), 1)
        self.assertEqual(self.balances(), [48, 20, 30, 10])
        self.assertEqual(self.client.post(reverse('order-cancel', args=[order.pk])).status_code, 200)
        self.assertEqual(self.client.post(reverse('order-cancel', args=[order.pk])).status_code, 400)
        self.assertEqual(self.balances(), [50, 20, 30, 10])

    def test_excess_purchase_rolls_back_all_stock(self):
        order = make_order(self.customer, self.a, 81)
        with self.assertRaises(ValueError):
            commit_order_inventory(order)
        self.assertEqual(self.balances(), [50, 20, 30, 10])
        order.refresh_from_db()
        self.assertFalse(order.inventory_committed)

    def test_release_cannot_invent_stock_and_deduct_requires_checkout(self):
        self.client.force_authenticate(self.admin)
        payload = {'items': [{'variant_id': self.a.pk, 'quantity': 200}]}
        self.assertEqual(self.client.post(reverse('admin-inventory-release'), payload, format='json').status_code, 400)
        self.assertEqual(self.client.post(reverse('admin-inventory-deduct'), payload, format='json').status_code, 400)
        order = make_order(self.customer, self.a, 2)
        payload['order_id'] = order.pk
        self.assertEqual(self.client.post(reverse('admin-inventory-deduct'), payload, format='json').status_code, 409)
        self.assertEqual(self.balances(), [50, 20, 30, 10])
        commit_order_inventory(order)
        order.status = Order.STATUS_CANCELLED
        order.save(update_fields=['status'])
        for _ in range(2):
            response = self.client.post(reverse('admin-inventory-release'), payload, format='json')
            self.assertEqual(response.status_code, 200)
        self.assertEqual(self.balances(), [50, 20, 30, 10])

    def test_availability_check_is_explicit_and_rejects_bad_quantities(self):
        self.client.force_authenticate(self.admin)
        for quantity in [-1, 0, '1.5', None, True]:
            response = self.client.post(reverse('admin-inventory-reserve'),
                {'items': [{'variant_id': self.a.pk, 'quantity': quantity}]}, format='json')
            self.assertEqual(response.status_code, 400, quantity)
        response = self.client.post(reverse('admin-inventory-reserve'),
            {'items': [{'variant_id': self.a.pk, 'quantity': 2}]}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['reserved'], [])
        self.assertEqual(self.balances(), [50, 20, 30, 10])

    def test_cart_serializes_the_selected_variant_unit_price(self):
        from apps.orders.models import Cart, CartItem
        self.client.force_authenticate(self.customer)
        cart = Cart.objects.create(user=self.customer)
        CartItem.objects.create(cart=cart, variant=self.a, quantity=2)
        CartItem.objects.create(cart=cart, variant=self.b, quantity=1)
        response = self.client.get(reverse('cart'))
        self.assertEqual(response.status_code, 200)
        prices = {item['variant']['id']: item['unit_price'] for item in response.data['items']}
        self.assertEqual(prices, {self.a.pk: '100.00', self.b.pk: '400.00'})
        self.assertEqual(response.data['subtotal'], Decimal('600.00'))

    def test_reviews_target_exact_variant_and_enforce_purchase_ownership(self):
        order = make_order(self.customer, self.b)
        delivery_fixture(order)
        order.status = Order.STATUS_DELIVERED
        order.save(update_fields=['status'])
        self.client.force_authenticate(self.customer)
        url = reverse('variant-reviews', kwargs={'variant_pk': self.b.pk})
        response = self.client.post(url, {'rating': 5, 'comment':'Synthetic QA'}, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(VariantReview.objects.get(user=self.customer).variant_id, self.b.pk)
        self.assertEqual(self.client.post(url, {'rating': 6}, format='json').status_code, 400)
        self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.post(url, {'rating': 1, 'user':self.customer.pk}, format='json').status_code, 403)
        self.assertEqual(VariantReview.objects.get(user=self.customer).rating, 5)
        for variant, expected in ((self.a, 0), (self.b, 1)):
            response = self.client.get(reverse('product-detail-by-id', args=[variant.product_id]))
            self.assertEqual(response.status_code, 200, response.data)
            ratings = {row['id']: row.get('review_count') for row in response.data['variants']}
            self.assertEqual(ratings[variant.pk], expected)

    def test_multiple_reviews_do_not_multiply_inventory_quantities(self):
        VariantReview.objects.create(variant=self.a, user=self.customer, rating=5, is_approved=True)
        VariantReview.objects.create(variant=self.a, user=self.admin, rating=4, is_approved=True)
        response = self.client.get(reverse('products'), {'search': self.a.sku})
        self.assertEqual(response.data['results'][0]['available_quantity'], 80)
        self.client.force_authenticate(self.admin)
        response = self.client.get(reverse('admin-inventory'), {'search': self.a.sku, 'page_size': 1})
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['stock_quantity'], 80)
        response = self.client.get(reverse('products'), {'search': self.a.sku})
        self.assertEqual(response.data['results'][0]['review_count'], 2)

    def test_customer_cannot_write_stock(self):
        self.client.force_authenticate(self.customer)
        for route in ['admin-inventory-reserve', 'admin-inventory-release', 'admin-inventory-deduct', 'admin-inventory-bulk-update', 'admin-inventory-pos-sync']:
            self.assertEqual(self.client.post(reverse(route), {}, format='json').status_code, 403, route)

    def test_catalog_pagination_search_brand_rating_and_sort(self):
        VariantReview.objects.create(variant=self.b, user=self.customer, rating=5, comment='Synthetic QA review', is_approved=True)
        response = self.client.get(reverse('products'), {'page_size': 1, 'ordering': 'price'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['id'], self.a.pk)
        self.assertIsNotNone(response.data['next'])
        response = self.client.get(reverse('products'), {'search': '200mg', 'brands': self.brand.slug, 'min_rating': 4})
        self.assertEqual([row['id'] for row in response.data['results']], [self.b.pk])
        response = self.client.get(reverse('products'), {'ordering': '-approved_average_rating'})
        self.assertEqual(response.data['results'][0]['id'], self.b.pk)

    def test_low_stock_and_backorder_purchase_limit(self):
        VariantInventory.objects.filter(variant=self.a).update(stock_quantity=0)
        row = self.rows[0]
        row.refresh_from_db()
        row.allow_backorder = True
        row.max_backorder_quantity = 3
        row.save()
        response = self.client.get(reverse('products'), {'inventory_status': 'purchasable'})
        self.assertIn(self.a.pk, [r['id'] for r in response.data['results']])
        order = make_order(self.customer, self.a, 3)
        commit_order_inventory(order)
        row.refresh_from_db()
        self.assertEqual(row.stock_quantity, 0)
        self.assertEqual(row.max_backorder_quantity, 0)
        with self.assertRaises(ValueError):
            commit_order_inventory(make_order(self.customer, self.a))
        release_order_inventory(order)
        row.refresh_from_db()
        self.assertEqual(row.max_backorder_quantity, 3)
        VariantInventory.objects.filter(variant=self.b).update(stock_quantity=1)
        response = self.client.get(reverse('products'), {'inventory_status': 'low_stock'})
        self.assertIn(self.b.pk, [r['id'] for r in response.data['results']])


class LastUnitConcurrencyTests(TransactionTestCase):
    def test_only_one_of_two_customers_can_commit_last_unit(self):
        product = Product.objects.create(name='Synthetic Last Unit', sku='LAST-UNIT')
        variant = Variant.objects.create(product=product, name='Last Unit', sku='LAST-UNIT-A', price=100,**catalogue_fixture(medicine=False, exclude=('product', 'name', 'sku', 'price')))
        inventory = VariantInventory.objects.create(variant=variant, stock_quantity=1)
        orders = [make_order(User.objects.create_user(email=f'last-unit-{i}@avapharmacy.test'), variant) for i in range(2)]
        barrier = Barrier(2)
        def purchase(pk):
            close_old_connections()
            try:
                order = Order.objects.get(pk=pk)
                barrier.wait(timeout=10)
                try:
                    commit_order_inventory(order)
                    return 'committed'
                except ValueError:
                    return 'rejected'
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(purchase, [order.pk for order in orders]))
        self.assertCountEqual(outcomes, ['committed', 'rejected'])
        inventory.refresh_from_db()
        self.assertEqual(inventory.stock_quantity, 0)
        self.assertEqual(Order.objects.filter(pk__in=[o.pk for o in orders], inventory_committed=True).count(), 1)


class ContentAndPOSAcceptanceTests(TestCase):
    setUp = ModuleAcceptanceTests.setUp
    balances = ModuleAcceptanceTests.balances

    def test_pos_repeat_unknown_mapping_and_downtime(self):
        from unittest.mock import patch
        from urllib.error import URLError
        from django.test import override_settings
        from apps.products.inventory_sync import normalize_inventory_payload, apply_inventory_sync
        from apps.products.models import StockMovement
        from apps.products.pos import fetch_pos_inventory
        row = self.rows[0]
        payload = {'items': [{'sku': self.a.sku, 'store_listing_id': row.store_listing_id,
                             'location': 'branch', 'quantity_on_hand': 45}]}
        normalized = normalize_inventory_payload(payload)
        for _ in range(2):
            result = apply_inventory_sync(normalized)
            self.assertTrue(result[0]['updated'])
        self.assertEqual(self.balances(), [45, 20, 30, 10])
        self.assertEqual(StockMovement.objects.filter(variant_inventory=row).count(), 1)
        unknown = apply_inventory_sync(normalize_inventory_payload({'items': [{'sku': 'UNKNOWN-QA', 'quantity_on_hand': 500}]}))
        self.assertFalse(unknown[0]['matched'])
        with override_settings(POS_INVENTORY_LOOKUP_URL='https://pos.invalid/qa'):
            with patch('apps.products.pos.request.urlopen', side_effect=URLError('Synthetic downtime')):
                self.assertEqual(fetch_pos_inventory([{'sku': self.a.sku}]), {})
        self.assertEqual(self.balances(), [45, 20, 30, 10])

    def test_content_visibility_and_promotion_dates(self):
        from datetime import timedelta
        from django.utils import timezone
        from apps.products.models import Banner, CMSBlock, FAQ, Promotion
        today = timezone.localdate()
        self.client.force_authenticate(self.admin)
        banner = self.client.post(reverse('admin-banners'), {'title':'Synthetic QA banner','message':'Synthetic QA only','placement':'qa-only','status':'active'}, format='json')
        self.assertEqual(banner.status_code, 201)
        cms = self.client.post(reverse('admin-cms-blocks'), {'key':'synthetic-qa','title':'Synthetic QA content','placement':'qa-only','is_active':True}, format='json')
        self.assertEqual(cms.status_code, 201)
        self.client.force_authenticate(None)
        for name, pk in [('banners',banner.data['id']), ('cms-blocks',cms.data['id'])]:
            response = self.client.get(reverse(name), {'placement':'qa-only'})
            self.assertEqual([r['id'] for r in response.data['results']], [pk])
        Banner.objects.filter(pk=banner.data['id']).update(status='inactive')
        CMSBlock.objects.filter(pk=cms.data['id']).update(is_active=False)
        self.assertEqual(self.client.get(reverse('banners'), {'placement':'qa-only'}).data['results'], [])
        self.assertEqual(self.client.get(reverse('cms-blocks'), {'placement':'qa-only'}).data['results'], [])
        for code,start,end in [('CURRENT',today,today),('EXPIRED',today-timedelta(days=3),today-timedelta(days=1)),('FUTURE',today+timedelta(days=1),today+timedelta(days=3))]:
            Promotion.objects.create(title=code,code=code,type=Promotion.TYPE_PERCENTAGE,value=10,scope=Promotion.SCOPE_ALL,start_date=start,end_date=end,status=Promotion.STATUS_ACTIVE)
        response = self.client.get(reverse('promotions'))
        self.assertEqual([p['code'] for p in response.data['results']], ['CURRENT'])
