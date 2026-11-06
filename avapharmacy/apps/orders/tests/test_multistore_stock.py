from avapharmacy.test_compliance_fixtures import inventory_fixture
from avapharmacy.test_compliance_fixtures import catalogue_fixture
from decimal import Decimal

from django.test import TestCase

from apps.accounts.models import User
from apps.orders.models import Order, OrderItem
from apps.orders.stock import commit_order_inventory, release_order_inventory
from apps.products.models import (
    Product,
    Store,
    StoreVariantListing,
    Variant,
    VariantInventory,
)


class MultiStoreOrderStockTests(TestCase):
    def setUp(self):
        self.customer = User.objects.create_user(
            email='multistore@example.com',
            password='testpass123',
        )
        self.product = Product.objects.create(
            sku='MULTISTORE-PRODUCT',
            name='Multi-store Product',
        )
        self.variant = Variant.objects.create(
            product=self.product,
            sku='MULTISTORE-VARIANT',
            name='Multi-store Variant',
            price=Decimal('500.00'),
        **catalogue_fixture(medicine=False, exclude=('product', 'sku', 'name', 'price')))
        first_store = Store.objects.create(code='first-store', name='First Store')
        second_store = Store.objects.create(code='second-store', name='Second Store')
        first_listing = StoreVariantListing.objects.create(
            store=first_store,
            variant=self.variant,
            price=Decimal('500.00'),
        )
        second_listing = StoreVariantListing.objects.create(
            store=second_store,
            variant=self.variant,
            price=Decimal('510.00'),
        )
        self.first_inventory = VariantInventory.objects.create(
            variant=self.variant,
            store_listing=first_listing,
            stock_quantity=2,
        **inventory_fixture(exclude=('variant', 'store_listing', 'stock_quantity')))
        self.second_inventory = VariantInventory.objects.create(
            variant=self.variant,
            store_listing=second_listing,
            stock_quantity=5,
        **inventory_fixture(exclude=('variant', 'store_listing', 'stock_quantity')))
        self.order = Order.objects.create(
            customer=self.customer,
            status=Order.STATUS_PENDING,
            payment_method=Order.PAYMENT_COD,
            payment_status=Order.PAYMENT_STATUS_PENDING,
            shipping_first_name='Multi',
            shipping_last_name='Store',
            shipping_email='multistore@example.com',
            shipping_phone='+254700000001',
            shipping_street='Test Street',
            shipping_city='Nairobi',
            shipping_county='Nairobi',
        )
        self.item = OrderItem.objects.create(
            order=self.order,
            variant=self.variant,
            product_name=self.product.name,
            product_sku=self.product.sku,
            variant_name=self.variant.name,
            variant_sku=self.variant.sku,
            quantity=3,
            unit_price=self.variant.price,
        )

    def test_release_restores_the_exact_store_rows_consumed(self):
        commit_order_inventory(self.order)

        self.item.refresh_from_db()
        self.first_inventory.refresh_from_db()
        self.second_inventory.refresh_from_db()
        self.assertEqual(self.first_inventory.stock_quantity, 0)
        self.assertEqual(self.second_inventory.stock_quantity, 4)
        self.assertEqual(
            [row['inventory_id'] for row in self.item.inventory_allocations],
            [self.first_inventory.id, self.second_inventory.id],
        )

        release_order_inventory(self.order)

        self.item.refresh_from_db()
        self.first_inventory.refresh_from_db()
        self.second_inventory.refresh_from_db()
        self.assertEqual(self.first_inventory.stock_quantity, 2)
        self.assertEqual(self.second_inventory.stock_quantity, 5)
        self.assertEqual(self.item.inventory_allocations, [])

