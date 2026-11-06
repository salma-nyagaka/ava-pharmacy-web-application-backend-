from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APIClient
from apps.accounts.models import User
from apps.products.models import Brand, Category, Product, Variant, VariantInventory


@override_settings(CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}})
class AdminReadViewTests(TestCase):
    def setUp(self):
        cache.clear()
        self.admin = User.objects.create_user(email='reader@example.test', password='testpass123', role='admin')
        self.client = APIClient()
        self.client.force_authenticate(self.admin)

    def test_reference_lists_include_more_than_twenty_and_inactive_records(self):
        Brand.objects.bulk_create([Brand(name=f'Brand {i}', slug=f'brand-{i}', is_active=i % 2 == 0) for i in range(25)])
        Category.objects.bulk_create([Category(name=f'Category {i}', slug=f'category-{i}') for i in range(25)])
        response = self.client.get(reverse('admin-brands'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 25)
        self.assertEqual(sum(b['is_active'] for b in response.data), 13)
        self.assertEqual(len(self.client.get(reverse('admin-categories')).data), 25)

    def test_page_size_is_capped_and_renderer_reports_actual_page_count(self):
        Brand.objects.create(name='Example', slug='example')
        response = self.client.get(reverse('admin-inventory'), {'page_size': 500})
        response.render()
        import json
        self.assertEqual(json.loads(response.content)['meta']['per_page'], 200)

    def test_catalog_summary_spans_every_page_and_updates_on_stock_commit(self):
        product = Product.objects.create(name='Test family', slug='test-family')
        variant = Variant.objects.create(product=product, sku='READ-01', name='Pack', price='20')
        stock = VariantInventory.objects.create(variant=variant, location='branch', stock_quantity=7, low_stock_threshold=2)
        summary = self.client.get(reverse('admin-catalog-stats')).data
        self.assertEqual(summary['inventory']['in_stock'], 1)
        with self.captureOnCommitCallbacks(execute=True):
            stock.stock_quantity = 1
            stock.save()
        summary = self.client.get(reverse('admin-catalog-stats')).data
        self.assertEqual(summary['inventory']['low_stock'], 1)
        self.assertEqual(summary['inventory']['in_stock'], 0)
        with self.captureOnCommitCallbacks(execute=True):
            stock.delete()
        self.assertEqual(self.client.get(reverse('admin-catalog-stats')).data['inventory']['out_of_stock'], 1)

    def test_new_product_invalidates_cached_page_and_compact_list_has_category_ids(self):
        product = Product.objects.create(name='Alpha', slug='alpha')
        category = Category.objects.create(name='Care', slug='care')
        Variant.objects.create(product=product, category=category, sku='READ-02', name='Pack', price='12')
        response = self.client.get(reverse('admin-products'), {'page_size': 1})
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['category'], category.pk)
        self.assertNotIn('variants', response.data['results'][0])
        with self.captureOnCommitCallbacks(execute=True):
            Product.objects.create(name='Beta', slug='beta')
        self.assertEqual(self.client.get(reverse('admin-products'), {'page_size': 1}).data['count'], 2)

    def test_product_filters_use_ids_without_fetching_the_whole_catalog(self):
        category = Category.objects.create(name='Care', slug='care')
        for i in range(3):
            product = Product.objects.create(name=f'Family {i}', slug=f'family-{i}')
            Variant.objects.create(product=product, category=category if i == 0 else None, sku=f'FILTER-{i}', name='Pack', price='12')
        response = self.client.get(reverse('admin-products'), {'category_id': category.pk, 'page_size': 1})
        self.assertEqual(response.data['count'], 1)

    def test_private_summary_and_pages_require_staff(self):
        self.client.force_authenticate(None)
        for route in ['admin-catalog-stats', 'admin-products', 'admin-inventory']:
            self.assertIn(self.client.get(reverse(route)).status_code, [401, 403])

    def test_admin_can_create_unreviewed_stock_but_cannot_make_clinical_decisions(self):
        product = Product.objects.create(name='Unreviewed family', slug='unreviewed-family')
        endpoint = reverse('admin-product-variants', kwargs={'product_pk': product.pk})
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(endpoint, {'name': 'Pack', 'price': '20'}, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        variant = Variant.objects.get(pk=response.data['id'])
        self.assertEqual(variant.regulatory_scope, 'unreviewed')
        for fields in [{'regulatory_scope': 'non_medicine'}, {'warnings': 'Unverified clinical claim'}]:
            response = self.client.post(endpoint, {'name': 'Other pack', 'price': '20', **fields}, format='json')
            self.assertEqual(response.status_code, 400, response.data)

    def test_inventory_totals_cover_all_pages_and_variant_deletion(self):
        products = [Product.objects.create(name=f'Exact item {i}', slug=f'exact-page-{i}') for i in range(25)]
        variants = Variant.objects.bulk_create([
            Variant(product=products[i], sku=f'PAGE-{i}', name=f'Pack {i}', price='10') for i in range(25)
        ])
        VariantInventory.objects.bulk_create([
            VariantInventory(variant=v, location='branch', stock_quantity=7, low_stock_threshold=2) for v in variants
        ])
        page = self.client.get(reverse('admin-inventory'), {'page_size': 10}).data
        summary = self.client.get(reverse('admin-catalog-stats')).data
        self.assertEqual(len(page['results']), 10)
        self.assertEqual(page['count'], 25)
        self.assertEqual(summary['inventory']['total'], 25)
        self.assertEqual(summary['inventory']['in_stock'], 25)
        with self.captureOnCommitCallbacks(execute=True):
            variants[0].delete()
        self.assertEqual(self.client.get(reverse('admin-catalog-stats')).data['inventory']['total'], 24)
        self.assertEqual(self.client.get(reverse('admin-inventory'), {'page_size': 10}).data['count'], 24)

    def test_pos_options_can_be_scoped_to_selected_product(self):
        product = Product.objects.create(name='Selected family', slug='selected-family', pos_product_id='POS-SELECTED')
        Product.objects.create(name='Other family', slug='other-family', pos_product_id='POS-OTHER')
        endpoint = reverse('admin-pos-product-options')
        rows = self.client.get(endpoint, {'product_id': product.pk}).data
        self.assertEqual([r['pos_product_id'] for r in rows], ['POS-SELECTED'])
        self.assertEqual(self.client.get(endpoint, {'product_id': 'invalid'}).status_code, 400)
