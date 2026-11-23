from django.urls import reverse
from rest_framework.test import APITestCase
from apps.products.models import Product, Variant, VariantInventory
from avapharmacy.test_compliance_fixtures import catalogue_fixture, inventory_fixture


class PublicPrescriptionVisibilityTests(APITestCase):
    def setUp(self):
        product = Product.objects.create(name='Catalogue fixture')
        self.rx = Variant.objects.create(product=product, name='Prescription fixture', price=100, requires_prescription=True, **catalogue_fixture(medicine=True))
        self.otc = Variant.objects.create(product=Product.objects.create(name='General product'), name='General fixture', price=100, **catalogue_fixture())
        for variant in (self.rx, self.otc):
            VariantInventory.objects.create(variant=variant, stock_quantity=10, **inventory_fixture())

    def rows(self, response):
        data = response.data
        return data if isinstance(data, list) else data.get('results', data.get('data', []))

    def test_browse_excludes_rx_but_search_and_upload_selector_include_rx(self):
        browse = self.rows(self.client.get(reverse('products')))
        self.assertNotIn(self.rx.pk, [row['id'] for row in browse])
        self.assertIn(self.otc.pk, [row['id'] for row in browse])
        for params in ({'search': 'Prescription fixture'}, {'requires_prescription': 'true'}):
            results = self.rows(self.client.get(reverse('products'), params))
            self.assertIn(self.rx.pk, [row['id'] for row in results])


class PublicCatalogQueryTests(APITestCase):
    def test_listing_query_count_stays_constant_with_page_size(self):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        for index in range(12):
            product = Product.objects.create(name=f'Catalog item {index}')
            Variant.objects.create(
                product=product, name=product.name, price=100, **catalogue_fixture(),
            )

        query_counts = []
        for page_size in (1, 12):
            with CaptureQueriesContext(connection) as queries:
                response = self.client.get(reverse('products'), {'page_size': page_size})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(len(response.data['results']), page_size)
            self.assertTrue(all(row['has_variants'] is False for row in response.data['results']))
            query_counts.append(len(queries))

        self.assertEqual(query_counts[0], query_counts[1])
