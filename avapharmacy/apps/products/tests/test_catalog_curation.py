from avapharmacy.test_compliance_fixtures import catalogue_fixture
from decimal import Decimal
from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from apps.products.catalog_curation import infer_brand_name, infer_health_concerns
from apps.products.models import Brand, Category, HealthConcern, Product, Variant
from apps.products.serializers import CategorySerializer
from apps.products.views import CategoryListView


class CatalogCurationRuleTests(TestCase):
    def test_brand_requires_a_recognised_leading_label(self):
        self.assertEqual(infer_brand_name('CeraVe Moisturising Cream 454g'), 'CeraVe')
        self.assertEqual(infer_brand_name('Bath & Body Works Hand Cream'), 'Bath & Body Works')
        self.assertIsNone(infer_brand_name('Replacement heads compatible with Oral-B'))

    def test_health_concerns_can_use_category_and_product_text(self):
        matches = infer_health_concerns(
            name='Gentle baby shampoo',
            description='Daily scalp care',
            category='BABY CARE',
        )
        self.assertIn('Baby & Child Care', matches)
        self.assertIn('Hair & Scalp', matches)


class CatalogCurationCommandTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name='SKIN CARE', slug='skin-care')
        self.product = Product.objects.create(
            sku='LEGACY-P-1',
            slug='cerave-cleanser',
            name='CeraVe Hydrating Cleanser',
        )
        self.variant = Variant.objects.create(
            product=self.product,
            sku='LEGACY-V-1',
            name='CeraVe Hydrating Cleanser 236ml',
            category=self.category,
            price=Decimal('1200.00'),
        **catalogue_fixture(medicine=False, exclude=('product', 'sku', 'name', 'category', 'price')))

    def test_dry_run_does_not_write(self):
        call_command('curate_legacy_catalog', stdout=StringIO())
        self.product.refresh_from_db()

        self.assertIsNone(self.product.brand)
        self.assertEqual(Brand.objects.count(), 0)
        self.assertEqual(HealthConcern.objects.count(), 0)

    def test_apply_is_idempotent_and_records_inference(self):
        call_command('curate_legacy_catalog', apply=True, stdout=StringIO())
        call_command('curate_legacy_catalog', apply=True, stdout=StringIO())
        self.product.refresh_from_db()
        self.variant.refresh_from_db()

        self.assertEqual(self.product.brand.name, 'CeraVe')
        self.assertIn('Brand inferred', self.product.curation_notes)
        self.assertEqual(self.product.curation_notes.count('Brand inferred'), 1)
        self.assertEqual(list(self.variant.health_concerns.values_list('name', flat=True)), ['Skin Health'])
        self.assertEqual(self.variant.curation_notes.count('Health concerns inferred'), 1)


class CategoryNavigationSerializerTests(TestCase):
    def test_category_contains_direct_links_to_stocked_products(self):
        from apps.products.models import Store, StoreVariantListing, VariantInventory

        category = Category.objects.create(name='BODY BUILDING', slug='body-building')
        product = Product.objects.create(sku='P-1', slug='protein-powder', name='Protein Powder')
        variant = Variant.objects.create(
            product=product,
            sku='V-1',
            name='Protein Powder 1kg',
            category=category,
            price=Decimal('2500.00'),
        **catalogue_fixture(medicine=False, exclude=('product', 'sku', 'name', 'category', 'price')))
        store = Store.objects.create(code='test-store', name='Test Store')
        listing = StoreVariantListing.objects.create(
            store=store,
            variant=variant,
            price=Decimal('2500.00'),
            is_active=True,
        )
        VariantInventory.objects.create(
            variant=variant,
            store_listing=listing,
            location=Product.STOCK_BRANCH,
            stock_quantity=5,
        )

        data = CategorySerializer(category).data

        self.assertEqual(data['products'], [{
            'id': product.id,
            'name': 'Protein Powder 1kg',
            'slug': 'protein-powder',
            'requires_prescription': False,
        }])

    def test_category_navigation_prefetch_does_not_query_per_category(self):
        from apps.products.models import Store, StoreVariantListing, VariantInventory

        store = Store.objects.create(code='query-store', name='Query Store')
        for index in range(3):
            category = Category.objects.create(name=f'Category {index}', slug=f'category-{index}')
            product = Product.objects.create(
                sku=f'QUERY-P-{index}', slug=f'query-product-{index}', name=f'Query Product {index}',
            )
            variant = Variant.objects.create(
                product=product,
                sku=f'QUERY-V-{index}',
                name=f'Query Product {index}',
                category=category,
                price=Decimal('100.00'),
            **catalogue_fixture(medicine=False, exclude=('product', 'sku', 'name', 'category', 'price')))
            listing = StoreVariantListing.objects.create(
                store=store, variant=variant, price=Decimal('100.00'), is_active=True,
            )
            VariantInventory.objects.create(
                variant=variant, store_listing=listing, location=Product.STOCK_BRANCH, stock_quantity=1,
            )

        with self.assertNumQueries(3):
            data = CategorySerializer(CategoryListView().get_queryset(), many=True).data

        self.assertEqual(len(data), 3)
