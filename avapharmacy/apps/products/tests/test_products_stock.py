from django.test import TestCase, TransactionTestCase
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.urls import reverse
from rest_framework.test import APIClient
from apps.accounts.models import User
from apps.products.models import Product, Variant, VariantInventory, StockMovement


class ProductsStockTests(TestCase):
    def test_identifiers_are_stored_once_on_exact_variant(self):
        product = Product.objects.create(name='Unified family', barcode='BAR-01', pos_product_id='POS-01')
        variant = product.variants.get()
        self.assertEqual((variant.barcode, variant.pos_product_id), ('BAR-01', 'POS-01'))
        self.assertNotIn('barcode', {field.name for field in Product._meta.fields})
        self.assertNotIn('pos_product_id', {field.name for field in Product._meta.fields})
        product.pos_product_id = 'POS-02'
        product.save(update_fields=['pos_product_id'])
        variant.refresh_from_db()
        product.refresh_from_db()
        self.assertEqual((variant.pos_product_id, product.pos_product_id), ('POS-02', 'POS-02'))
        self.assertEqual(product.variants.count(), 1)

    def test_blank_legacy_identifiers_do_not_create_an_extra_variant(self):
        product = Product.objects.create(name='Draft family', barcode='', pos_product_id='')
        self.assertEqual(product.variants.count(), 0)
        self.assertEqual(Product(name='Unsaved').barcode, '')

    def test_store_batch_records_remain_independent_under_same_product(self):
        product = Product.objects.create(name='Unified family')
        first = Variant.objects.create(product=product, name='Small pack', sku='UNIFY-S', price=10)
        other_product = Product.objects.create(name='Other exact item')
        second = Variant.objects.create(product=other_product, name='Large pack', sku='UNIFY-L', price=20)
        a = VariantInventory.objects.create(variant=first, batch_number='A', stock_quantity=7)
        b = VariantInventory.objects.create(variant=first, batch_number='B', stock_quantity=3)
        other = VariantInventory.objects.create(variant=second, batch_number='A', stock_quantity=9)
        self.assertEqual(set(product.stock_records.values_list('pk', flat=True)), {a.pk,b.pk})
        self.assertEqual(a.product_id, product.pk)
        self.assertEqual(a.product, product)
        a.stock_quantity = 5; a.save()
        b.refresh_from_db(); other.refresh_from_db()
        self.assertEqual((b.stock_quantity, other.stock_quantity), (3,9))

    def test_stock_history_is_paginated_and_scoped_to_product(self):
        admin=User.objects.create_user(email='unified-admin@example.test', role='admin')
        product=Product.objects.create(name='Family with history')
        variant=Variant.objects.create(product=product, name='Pack', sku='UNIFY-H', price=10)
        inventory=VariantInventory.objects.create(variant=variant)
        StockMovement.objects.bulk_create([StockMovement(variant_inventory=inventory, movement_type='adjustment', quantity_change=1, quantity_before=0, quantity_after=1, reference=f'SYNTHETIC-{i}') for i in range(101)])
        client=APIClient();client.force_authenticate(admin)
        response=client.get(reverse('admin-stock-history'), {'product_id':product.pk,'page_size':20})
        self.assertEqual(response.status_code,200,response.data)
        self.assertEqual(response.data['count'],101)
        self.assertEqual(len(response.data['results']),20)
        self.assertEqual(response.data['results'][0]['product_id'],product.pk)
        self.assertEqual(response.data['results'][0]['variant_sku'],variant.sku)
        other=Product.objects.create(name='Other family')
        self.assertEqual(client.get(reverse('admin-stock-history'),{'product_id':other.pk}).data['count'],0)
        self.assertEqual(client.get(reverse('admin-stock-history'),{'product_id':'invalid'}).status_code,400)
        client.force_authenticate(None)
        self.assertIn(client.get(reverse('admin-stock-history')).status_code,[401,403])


class ProductsStockMigrationTests(TransactionTestCase):
    old = [('products','0069_variant_pil_reviewed_at_variant_pil_reviewed_by_and_more')]
    new = [('products','0070_unified_products_stock')]

    def setUp(self):
        executor=MigrationExecutor(connection);executor.migrate(self.old)
        self.old_apps=executor.loader.project_state(self.old).apps

    def tearDown(self):
        # Always restore the schema, even when testing a refused ambiguous merge.
        ProductOld=self.old_apps.get_model('products','Product')
        ProductOld.objects.update(barcode='',pos_product_id='')
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())
        super().tearDown()

    def test_migration_preserves_nonempty_legacy_identifiers_and_quantities(self):
        P=self.old_apps.get_model('products','Product');V=self.old_apps.get_model('products','Variant');I=self.old_apps.get_model('products','VariantInventory')
        p=P.objects.create(name='Legacy family',sku='MIG-FAM',slug='mig-family',barcode='LEGACY-BAR',pos_product_id='LEGACY-POS')
        v=V.objects.create(product_id=p.pk,name='Pack',sku='MIG-PACK',price=10)
        inventory=I.objects.create(variant_id=v.pk,stock_quantity=17,batch_number='BATCH-KEEP')
        MigrationExecutor(connection).migrate(self.new)
        v=Variant.objects.get(pk=v.pk);inventory=VariantInventory.objects.get(pk=inventory.pk)
        self.assertEqual((v.barcode,v.pos_product_id),('LEGACY-BAR','LEGACY-POS'))
        self.assertEqual((inventory.stock_quantity,inventory.batch_number,inventory.variant_id),(17,'BATCH-KEEP',v.pk))
        # tearDown needs the old columns, so restore schema here before clearing fixtures.
        MigrationExecutor(connection).migrate(self.old)

    def test_migration_refuses_to_guess_between_sibling_variants(self):
        P=self.old_apps.get_model('products','Product');V=self.old_apps.get_model('products','Variant')
        p=P.objects.create(name='Ambiguous family',sku='MIG-AMBIG',slug='mig-ambig',barcode='UNASSIGNED')
        for i in range(2):V.objects.create(product_id=p.pk,name=f'Pack {i}',sku=f'MIG-AMB-{i}',price=10)
        with self.assertRaisesRegex(RuntimeError,'exact-variant identifier review'):
            MigrationExecutor(connection).migrate(self.new)
        self.assertEqual(P.objects.get(pk=p.pk).barcode,'UNASSIGNED')
