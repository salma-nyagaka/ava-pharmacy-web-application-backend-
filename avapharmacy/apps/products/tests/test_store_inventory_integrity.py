from avapharmacy.test_compliance_fixtures import catalogue_fixture
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from apps.products.models import (
    Product,
    Store,
    StoreVariantListing,
    Variant,
    VariantInventory,
    annotate_variant_inventory,
)


class StoreInventoryIntegrityTests(TestCase):
    def setUp(self):
        self.product = Product.objects.create(
            sku='INTEGRITY-PRODUCT',
            name='Integrity Product',
        )
        self.first_variant = Variant.objects.create(
            product=self.product,
            sku='INTEGRITY-FIRST',
            name='First Variant',
            price=Decimal('100.00'),
        **catalogue_fixture(medicine=False, exclude=('product', 'sku', 'name', 'price')))
        self.second_variant = Variant.objects.create(
            product=self.product,
            sku='INTEGRITY-SECOND',
            name='Second Variant',
            price=Decimal('120.00'),
        **catalogue_fixture(medicine=False, exclude=('product', 'sku', 'name', 'price')))
        self.store = Store.objects.create(code='integrity-store', name='Integrity Store')
        self.listing = StoreVariantListing.objects.create(
            store=self.store,
            variant=self.first_variant,
            price=Decimal('100.00'),
        )

    def test_inventory_rejects_a_listing_for_a_different_variant(self):
        inventory = VariantInventory(
            variant=self.second_variant,
            store_listing=self.listing,
            stock_quantity=3,
        )

        with self.assertRaises(ValidationError):
            inventory.full_clean()
        with self.assertRaises(ValidationError):
            inventory.save()

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                VariantInventory.objects.bulk_create([inventory])

    def test_inactive_store_listing_stock_is_not_available(self):
        VariantInventory.objects.create(
            variant=self.first_variant,
            store_listing=self.listing,
            stock_quantity=8,
        )
        self.listing.is_active = False
        self.listing.save(update_fields=['is_active'])

        self.first_variant.refresh_from_db()
        annotated = annotate_variant_inventory(
            Variant.objects.filter(pk=self.first_variant.pk)
        ).get()

        self.assertEqual(
            self.first_variant._get_inventory_values()['stock_quantity'],
            0,
        )
        self.assertEqual(annotated.stock_quantity, 0)
