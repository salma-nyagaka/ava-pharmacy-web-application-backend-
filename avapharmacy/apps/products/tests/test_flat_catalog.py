from django.test import TestCase, TransactionTestCase
from django.db import connection, IntegrityError, transaction
from django.db.migrations.executor import MigrationExecutor
from apps.products.models import Product, Variant, VariantInventory


class FlatCatalogModelTests(TestCase):
    def test_one_exact_sku_per_product_is_enforced(self):
        item=Product.objects.create(name='Exact 500mg 20 tablets')
        self.assertEqual(item.name,'Exact 500mg 20 tablets')
        Variant.objects.create(product=item,name='20 tablets',sku='FLAT-01',price=20)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Variant.objects.create(product=item,name='Other pack',sku='FLAT-02',price=30)
        self.assertEqual(item.variants.count(),1)

    def test_multiple_batches_still_belong_to_one_exact_item(self):
        product=Product.objects.create(name='Exact item',price=10)
        variant=product.variants.get()
        VariantInventory.objects.create(variant=variant,batch_number='A',stock_quantity=7)
        VariantInventory.objects.create(variant=variant,batch_number='B',stock_quantity=5)
        self.assertEqual(product.stock_records.count(),2)
        self.assertEqual(product.stock_quantity,12)


class FlatCatalogMigrationTests(TransactionTestCase):
    old=[('products','0070_unified_products_stock')]
    new=[('products','0071_flat_sellable_items')]
    def setUp(self):
        executor=MigrationExecutor(connection);executor.migrate(self.old)
        self.apps=executor.loader.project_state(self.old).apps
    def tearDown(self):
        executor=MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())
        super().tearDown()
    def test_shared_family_is_split_without_replacing_any_stock_or_sku(self):
        P=self.apps.get_model('products','Product');V=self.apps.get_model('products','Variant');I=self.apps.get_model('products','VariantInventory')
        parent=P.objects.create(name='Shared family',sku='FAMILY-FLAT',slug='family-flat')
        first=V.objects.create(product=parent,sku='EXACT-01',name='500mg 20 tablets',price=10)
        second=V.objects.create(product=parent,sku='EXACT-02',name='250mg 100ml syrup',price=20)
        stock=I.objects.create(variant=second,stock_quantity=13,batch_number='KEEP-01')
        executor=MigrationExecutor(connection);executor.migrate(self.new)
        migrated=executor.loader.project_state(self.new).apps
        V=migrated.get_model('products','Variant');I=migrated.get_model('products','VariantInventory');P=migrated.get_model('products','Product')
        first=V.objects.get(pk=first.pk);second=V.objects.get(pk=second.pk);stock=I.objects.get(pk=stock.pk)
        self.assertNotEqual(first.product_id,second.product_id)
        self.assertEqual(first.product_id,parent.pk)
        self.assertEqual((first.sku,second.sku),('EXACT-01','EXACT-02'))
        self.assertEqual((stock.variant_id,stock.stock_quantity,stock.batch_number),(second.pk,13,'KEEP-01'))
        self.assertEqual(second.product.name,'250mg 100ml syrup')
        self.assertEqual(first.product.catalog_family_key,second.product.catalog_family_key)
        self.assertEqual(P.objects.count(),V.objects.count())


class FlatItemApiTests(TestCase):
    def setUp(self):
        from apps.accounts.models import User
        from rest_framework.test import APIClient
        self.admin=User.objects.create_user(email='flat-api@example.test',role='admin')
        self.client=APIClient();self.client.force_authenticate(self.admin)

    def test_create_exact_item_and_store_stock_in_one_request(self):
        from apps.products.models import Store
        from django.urls import reverse
        store=Store.objects.create(name='Synthetic exact store',code='flat-store')
        response=self.client.post(reverse('admin-flat-item-create'), {'name':'Exact 500mg 20 tablets','item':{'sku':'FLAT-NEW','price':'20.50','stock_quantity':12,'low_stock_threshold':3,'store_id':store.pk,'batch_number':'KEEP-BATCH'}},format='json')
        self.assertEqual(response.status_code,201,response.data)
        product=Product.objects.get(pk=response.data['id']);exact=product.variants.get()
        self.assertEqual(product.sku, exact.sku)
        self.assertEqual((product.name,exact.sku,exact.price),('Exact 500mg 20 tablets','FLAT-NEW',20.50))
        stock=exact.inventories.get()
        self.assertEqual(stock.created_by_id,self.admin.pk)
        self.assertEqual((stock.stock_quantity,stock.store.pk,stock.batch_number),(12,store.pk,'KEEP-BATCH'))

    def test_admin_detail_category_is_the_id_used_by_the_item_form(self):
        from apps.products.models import Category
        from apps.products.serializers import AdminProductSerializer
        category = Category.objects.create(name='Exact category')
        product = Product.objects.create(name='Categorized item', price=10, category=category)
        self.assertEqual(AdminProductSerializer(product).data['category'], category.pk)

    def test_invalid_stock_does_not_leave_a_partial_product(self):
        from django.urls import reverse
        response=self.client.post(reverse('admin-flat-item-create'), {'name':'Should roll back','item':{'price':20,'stock_quantity':2}},format='json')
        self.assertEqual(response.status_code,400)
        self.assertFalse(Product.objects.filter(name='Should roll back').exists())

    def test_item_edit_price_is_atomic_and_store_stock_is_preserved(self):
        from django.urls import reverse
        product=Product.objects.create(name='Original exact item',price=10)
        exact=product.variants.get();VariantInventory.objects.create(variant=exact,stock_quantity=7)
        endpoint=reverse('admin-flat-item-detail',kwargs={'pk':product.pk})
        response=self.client.patch(endpoint,{'name':'Changed item','item':{'price':-1}},format='json')
        self.assertEqual(response.status_code,400,response.data)
        product.refresh_from_db();self.assertEqual(product.name,'Original exact item')
        response=self.client.patch(endpoint,{'name':'Changed item','item':{'price':'22.00'}},format='json')
        self.assertEqual(response.status_code,200,response.data)
        exact.refresh_from_db();self.assertEqual(exact.price,22)
        self.assertEqual(exact.inventories.get().stock_quantity,7)


class FlatItemStatusTests(TestCase):
    def test_inactive_item_keeps_its_exact_identity_and_physical_stock(self):
        product=Product.objects.create(name='Exact disabled item',price=12)
        exact=product.variants.get();exact.sku='EXACT-DISABLED';exact.save()
        VariantInventory.objects.create(variant=exact,stock_quantity=7)
        product.is_active=False;product.save()
        exact.refresh_from_db()
        self.assertFalse(exact.is_active)
        self.assertEqual(product.get_display_sku(),'EXACT-DISABLED')
        self.assertEqual(product.display_price,12)
        self.assertEqual(product.stock_quantity,7)
        self.assertEqual(product.available_quantity,0)
        product.is_active=True;product.save()
        exact.refresh_from_db();self.assertTrue(exact.is_active)
        self.assertEqual(exact._get_inventory_values()['stock_quantity'],7)
