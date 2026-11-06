from django.test import TestCase
from rest_framework.test import APIClient
from apps.accounts.models import User
from apps.products.models import Product, Store, VariantInventory, StockMovement

class ProductStockRecordTests(TestCase):
    def setUp(self):
        self.admin=User.objects.create_user(email='stock-record-admin@example.com',role='admin')
        self.client=APIClient();self.client.force_authenticate(self.admin)
        self.product=Product.objects.create(name='Stock record test',price=55)
        self.store=Store.objects.create(code='STOCK-RECORD-TEST',name='Test store')
        self.url=f'/api/admin/products/{self.product.pk}/stock-records/'

    def test_receipts_add_to_same_store_batch_and_keep_other_batches_separate(self):
        payload={'store_id':self.store.pk,'batch_number':'A','expiry_date':'2027-12-31','quantity':74}
        response=self.client.post(self.url,payload,format='json')
        self.assertEqual(response.status_code,201,response.data)
        first=response.data['id']
        payload['quantity']=20
        response=self.client.post(self.url,payload,format='json')
        self.assertEqual(response.status_code,201,response.data)
        self.assertEqual(response.data['id'],first);self.assertEqual(response.data['quantity'],94)
        payload.update(batch_number='B',quantity=10)
        self.assertEqual(self.client.post(self.url,payload,format='json').status_code,201)
        rows=self.client.get(self.url).data
        self.assertEqual(rows['total_quantity'],104);self.assertEqual(len(rows['records']),2)
        self.assertEqual(list(StockMovement.objects.filter(variant_inventory_id=first).order_by('pk').values_list('quantity_change',flat=True)),[74,20])
        response=self.client.patch(f'{self.url}{first}/',{'quantity':90,'low_stock_threshold':5},format='json')
        self.assertEqual(response.status_code,200,response.data)
        self.assertEqual(self.client.get(self.url).data['total_quantity'],100)

    def test_cannot_edit_another_products_stock_or_receive_negative_quantity(self):
        response=self.client.post(self.url,{'store_id':self.store.pk,'quantity':-3},format='json')
        self.assertEqual(response.status_code,400)
        response=self.client.post(self.url,{'store_id':self.store.pk,'quantity':5},format='json')
        other=Product.objects.create(name='Other stock product',price=10)
        response=self.client.patch(f'/api/admin/products/{other.pk}/stock-records/{response.data["id"]}/',{'quantity':100},format='json')
        self.assertEqual(response.status_code,404)
        customer=User.objects.create_user(email='stock-customer@example.com',role='customer')
        self.client.force_authenticate(customer)
        self.assertEqual(self.client.get(self.url).status_code,403)

    def test_general_stock_view_lists_records_and_attribution_and_filters(self):
        for batch in ['FIRST','SECOND']:
            response=self.client.post(self.url,{'store_id':self.store.pk,'batch_number':batch,'quantity':5},format='json')
            self.assertEqual(response.status_code,201,response.data)
        response=self.client.get('/api/admin/stock-records/',{'search':'Stock record test'})
        self.assertEqual(response.status_code,200,response.data)
        self.assertEqual(response.data['total_records'],2)
        self.assertEqual(response.data['stats']['total'],2)
        self.assertEqual(response.data['records'][0]['added_by'],self.admin.email)
        self.assertTrue(response.data['records'][0]['created_at'])
        self.assertEqual(response.data['records'][0]['batch_number'],'SECOND')
        stock_id=response.data['records'][0]['id']
        history=self.client.get('/api/admin/stock-history/',{'variant_inventory':stock_id})
        self.assertEqual(history.status_code,200,history.data)
        self.assertEqual(history.data['count'],1)
        self.assertEqual(history.data['results'][0]['variant_inventory'],stock_id)

    def test_unknown_legacy_creator_is_not_invented(self):
        stock=VariantInventory.objects.create(variant=self.product.variants.get(),stock_quantity=1)
        response=self.client.get(self.url)
        row=next(row for row in response.data['records'] if row['id']==stock.pk)
        self.assertIsNone(row['added_by'])

    def test_two_strengths_and_pack_sizes_are_distinct_items_with_independent_stock(self):
        ids=[]
        for strength,pack in [('250 mg','20 tablets'),('500 mg','30 tablets')]:
            from django.urls import reverse
            response=self.client.post(reverse('admin-flat-item-create'),{
                'name':f'Test product {strength} {pack}',
                'item':{'price':10,'strength':strength,'pack_size':pack,'stock_quantity':3,'store_id':self.store.pk},
            },format='json')
            self.assertEqual(response.status_code,201,response.data)
            product=Product.objects.get(pk=response.data['id']);variant=product.variants.get()
            self.assertEqual((variant.strength,variant.pack_size),(strength,pack));ids.append(product.pk)
            self.assertEqual(product.stock_quantity,3)
        self.assertNotEqual(*ids)
        from django.urls import reverse
        response=self.client.patch(reverse('admin-flat-item-detail',kwargs={'pk':ids[0]}),{'item':{'strength':'300 mg','pack_size':'25 tablets'}},format='json')
        self.assertEqual(response.status_code,200,response.data)
        self.assertEqual(Product.objects.get(pk=ids[0]).variants.get().pack_size,'25 tablets')
        self.assertEqual(Product.objects.get(pk=ids[1]).variants.get().strength,'500 mg')

    def test_specs_are_exposed_in_item_and_stock_table_responses(self):
        from apps.products.serializers import AdminProductTableSerializer
        variant=self.product.variants.get();variant.strength='250 mg';variant.pack_size='20 tablets';variant.save()
        VariantInventory.objects.create(variant=variant,stock_quantity=4)
        item=AdminProductTableSerializer(self.product).data
        self.assertEqual(item['strength'],'250 mg');self.assertEqual(item['pack_size'],'20 tablets')
        response=self.client.get(self.url)
        self.assertEqual(response.data['records'][0]['strength'],'250 mg')
        self.assertEqual(response.data['records'][0]['pack_size'],'20 tablets')

    def test_create_store_and_receive_stock_there(self):
        response=self.client.post('/api/admin/stores/',{'name':'New Pharmacy Store','city':'Nairobi','code':'new-pharmacy-store'},format='json')
        self.assertEqual(response.status_code,201,response.data)
        store_id=response.data['id']
        self.assertEqual(response.data['code'],'new-pharmacy-store')
        self.assertTrue(response.data['is_active'])
        response=self.client.post(self.url,{'store_id':store_id,'quantity':12,'batch_number':'NEW-STORE'},format='json')
        self.assertEqual(response.status_code,201,response.data)
        self.assertEqual(response.data['store'],'New Pharmacy Store')
        duplicate=self.client.post('/api/admin/stores/',{'name':'New Pharmacy Store'},format='json')
        self.assertEqual(duplicate.status_code,400)
        Store.objects.create(name='Other existing store',code='collision-store')
        response=self.client.post('/api/admin/stores/',{'name':'Collision Store','city':'Nairobi','code':'collision-store'},format='json')
        self.assertEqual(response.status_code,400,response.data)
        self.assertIn('code',response.data.get('error',{}).get('details',response.data))

    def test_store_creation_requires_every_field(self):
        for payload in [{}, {'name':'Missing city and code'}, {'name':'Blank fields','city':' ','code':' '}]:
            response=self.client.post('/api/admin/stores/',payload,format='json')
            self.assertEqual(response.status_code,400,response.data)
            self.assertIn('city',response.data.get('error',{}).get('details',response.data))
            self.assertIn('code',response.data.get('error',{}).get('details',response.data))
