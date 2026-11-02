from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.products.models import (
    Product,
    Store,
    StoreVariantListing,
    Variant,
    VariantInventory,
)
from apps.products.serializers import VariantInventorySerializer


class StoreCatalogTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        Store.objects.filter(
            code__in=['main-shop', 'pos-store'],
            variant_listings__isnull=True,
        ).delete()
        self.product = Product.objects.create(
            sku='TEST-PRODUCT',
            slug='test-product',
            name='Test Product',
        )
        self.variant = Variant.objects.create(
            product=self.product,
            sku='TEST-VARIANT',
            name='Test Product 100ml',
            price=Decimal('520.00'),
        )
        self.store = Store.objects.create(
            code='gtc-westlands',
            name='GTC Westlands',
            city='Nairobi',
        )
        self.listing = StoreVariantListing.objects.create(
            store=self.store,
            variant=self.variant,
            external_product_id='123',
            price=Decimal('500.00'),
            cost_price=Decimal('300.00'),
            minimum_price=Decimal('480.00'),
            vat_rate=Decimal('16.00'),
            status='ACTIVE',
        )
        self.inventory = VariantInventory.objects.create(
            variant=self.variant,
            store_listing=self.listing,
            location=Product.STOCK_BRANCH,
            stock_quantity=7,
            reorder_level=2,
        )

    def test_inventory_exposes_store_name_and_store_price(self):
        data = VariantInventorySerializer(self.inventory).data

        self.assertEqual(data['store']['code'], 'gtc-westlands')
        self.assertEqual(data['store']['name'], 'GTC Westlands')
        self.assertEqual(data['store_price'], '500.00')
        self.assertEqual(self.inventory.source_name, 'GTC Westlands')

    def test_public_store_list_returns_active_stores(self):
        Store.objects.create(code='closed-store', name='Closed Store', is_active=False)

        response = self.client.get(reverse('stores'))

        self.assertEqual(response.status_code, 200)
        rows = response.data.get('results', response.data)
        self.assertEqual([item['code'] for item in rows], ['gtc-westlands'])

    def test_product_availability_has_store_breakdown(self):
        response = self.client.get(
            reverse('product-availability-detail', args=[self.product.id])
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['quantity'], 7)
        self.assertEqual(response.data['store_stock'], [{
            'id': self.store.id,
            'code': 'gtc-westlands',
            'name': 'GTC Westlands',
            'city': 'Nairobi',
            'quantity': 7,
        }])

    def test_same_variant_can_have_inventory_in_multiple_stores(self):
        karen = Store.objects.create(code='the-hub-karen', name='The Hub Karen')
        karen_listing = StoreVariantListing.objects.create(
            store=karen,
            variant=self.variant,
            external_product_id='987',
            price=Decimal('540.00'),
            status='ACTIVE',
        )

        VariantInventory.objects.create(
            variant=self.variant,
            store_listing=karen_listing,
            location=Product.STOCK_BRANCH,
            stock_quantity=4,
        )

        self.assertEqual(self.variant.inventories.count(), 2)
        self.assertEqual(self.variant._get_inventory_values()['stock_quantity'], 11)

    def _add_karen_inventory(self, quantity=4):
        karen = Store.objects.create(code='the-hub-karen', name='The Hub Karen')
        listing = StoreVariantListing.objects.create(
            store=karen,
            variant=self.variant,
            external_product_id='987',
            price=Decimal('540.00'),
            status='ACTIVE',
        )
        inventory = VariantInventory.objects.create(
            variant=self.variant,
            store_listing=listing,
            location=Product.STOCK_BRANCH,
            stock_quantity=quantity,
        )
        return listing, inventory

    def _authenticate_admin(self):
        admin = User.objects.create_user(
            email='store-admin@example.com',
            password='testpass123',
            role=User.ADMIN,
            is_staff=True,
        )
        self.client.force_authenticate(admin)

    def test_admin_variant_metadata_update_does_not_rewrite_store_inventory(self):
        _, karen_inventory = self._add_karen_inventory()
        self._authenticate_admin()

        response = self.client.patch(
            reverse('admin-product-variant-detail', args=[self.product.id, self.variant.id]),
            {'name': 'Renamed Test Product 100ml'},
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        self.inventory.refresh_from_db()
        karen_inventory.refresh_from_db()
        self.assertEqual(self.inventory.stock_quantity, 7)
        self.assertEqual(karen_inventory.stock_quantity, 4)

    def test_admin_inventory_write_requires_store_when_target_is_ambiguous(self):
        _, karen_inventory = self._add_karen_inventory()
        self._authenticate_admin()
        url = reverse('admin-product-variant-detail', args=[self.product.id, self.variant.id])

        ambiguous = self.client.patch(
            url,
            {'branch_inventory': {'stock_quantity': 12}},
            format='json',
        )
        self.assertEqual(ambiguous.status_code, 400)
        self.assertIn('store_listing_id or store_code', str(ambiguous.data))

        selected = self.client.patch(
            url,
            {'branch_inventory': {'store_code': 'the-hub-karen', 'stock_quantity': 12}},
            format='json',
        )
        self.assertEqual(selected.status_code, 200)
        self.inventory.refresh_from_db()
        karen_inventory.refresh_from_db()
        self.assertEqual(self.inventory.stock_quantity, 7)
        self.assertEqual(karen_inventory.stock_quantity, 12)

    def test_public_availability_excludes_inactive_store_listing(self):
        self.listing.is_active = False
        self.listing.save(update_fields=['is_active'])

        response = self.client.get(
            reverse('product-availability-detail', args=[self.product.id])
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['quantity'], 0)
        self.assertEqual(response.data['store_stock'], [])

    def test_admin_store_listing_rest_crud(self):
        self._authenticate_admin()
        new_store = Store.objects.create(code='nyali', name='Nyali')

        response = self.client.post(
            reverse('admin-store-listings'),
            {
                'store_id': new_store.id,
                'variant_id': self.variant.id,
                'external_product_id': 'NY-123',
                'price': '530.00',
                'is_active': True,
            },
            format='json',
        )

        self.assertEqual(response.status_code, 201)
        listing = StoreVariantListing.objects.get(store=new_store, variant=self.variant)
        self.assertEqual(listing.external_product_id, 'NY-123')
