import json
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from django.core.management import call_command
from django.db.models import F
from django.test import SimpleTestCase, TestCase
from apps.products.catalog_taxonomy import CATEGORIES, VERSION, classify_item
from apps.products.models import Brand, Category, Subcategory, Product, Variant, VariantInventory
from apps.products.serializers import AdminProductSerializer, AdminVariantSerializer, SubcategorySerializer


class CatalogPlacementTests(SimpleTestCase):
    def test_representative_catalog_items_and_ambiguous_names(self):
        cases = [
          ('PARACETAMOL 500MG TABLETS','DISPENSARY','medicines','Tablets & Capsules'),
          ('HUMALOG KWIKPEN 100IU','DISPENSARY','medicines','Injections & Infusions'),
          ('CANDID EYE/EAR DROPS','DISPENSARY','medicines','Eye, Ear & Nasal Combinations'),
          ('MUCINEX LIQUID GELS 24S','OTC','medicines','Tablets & Capsules'),
          ('ZYRTEC ORAL SOLUTION','DISPENSARY','medicines','Oral Liquids & Powders'),
          ('THE ORDINARY VITAMIN C SERUM','SKIN CARE','skin','Serums & Targeted Treatments'),
          ('BATH AND BODY WORKS FRAGRANCE MIST','SKIN CARE','fragrance','Body & Fragrance Mists'),
          ('SWANSON VITAMIN C TABLETS','SUPPLEMENTS','supplements','Vitamins'),
          ('WHEY PROTEIN BAR','BODY BUILDING','sports','Protein & Energy Snacks'),
          ('NUBY FEEDING BOTTLE','BABY CARE','baby','Bottles, Teats & Feeding'),
          ('TENA ADULT DIAPERS','SANITARY PADS AND DIAPERS','period','Adult Continence Care'),
          ('CLEARBLUE PREGNANCY TEST','TESTS','devices','Pregnancy & Ovulation Tests'),
          ('CONTOUR TS TEST STRIPS','TESTS','devices','Blood Glucose Monitoring'),
          ('MEDINOX ANKLE SUPPORT','SUPPORTS','supports','Ankle & Foot Supports'),
          ('I-M ES-735 COMPRESSION KNEE SUP XL','','supports','Knee & Leg Supports'),
          ('MOSHI VAPE E-LIQUID','STOP SMOKING AIDS','smoking','Vape Liquids'),
          ('NICORETTE NICOTINE GUM','STOP SMOKING AIDS','smoking','Nicotine Replacement Products'),
          ('OPI NAIL FILE','DISPENSARY','makeup','Manicure & Pedicure Tools'),
          ('URINE SAMPLE CONTAINER','DISPENSARY','firstaid','Catheters, Bags & Clinical Supplies'),
          ('GTC NUTRITION CONSULTATION','SERVICES','services','Nutrition Consultations'),
          ('TELEPHONE EXPENSES','','store','Unspecified Catalog Entries'),
          ('....','DISPENSARY','store','Unspecified Catalog Entries'),
          ('UNSPECIFIED MEDICINE','Pharmacy & Medicines','medicines','Other Pharmacy Items'),
        ]
        for name, source, category, subcategory in cases:
            with self.subTest(name=name):
                result=classify_item(name,source)
                self.assertIn(result.category,CATEGORIES)
                self.assertEqual((result.category,result.subcategory),(category,subcategory))


class CatalogHierarchyCommandTests(TestCase):
    def test_full_assignment_preserves_stock_brand_clinical_flags_and_is_repeat_safe(self):
        old=Category.objects.create(name='DISPENSARY',slug='legacy-dispensary')
        legacy=Category.objects.create(name='OTC MEDICINE')
        brand=Brand.objects.create(name='Test brand',logo='')
        product=Product.objects.create(name='Exact medicine 500mg TABLETS',brand=brand,price=14,category=old)
        variant=product.variants.get()
        stock=VariantInventory.objects.create(variant=variant,stock_quantity=19,batch_number='PRESERVE-TAXONOMY')
        before=list(VariantInventory.objects.values());flags=(variant.price,variant.prescription_classification,variant.regulatory_scope)
        with TemporaryDirectory() as folder:
            call_command('organize_catalog_taxonomy',report_dir=folder,stdout=StringIO())
            variant.refresh_from_db();self.assertIsNone(variant.subcategory_id)
            call_command('organize_catalog_taxonomy',report_dir=folder,apply=True,stdout=StringIO())
            variant.refresh_from_db();old.refresh_from_db();legacy.refresh_from_db();product.refresh_from_db()
            self.assertEqual(old.name,'Pharmacy & Medicines')
            self.assertEqual(old.slug,'legacy-dispensary')
            self.assertEqual(variant.category_id,old.pk)
            self.assertEqual(variant.subcategory.category_id,old.pk)
            self.assertFalse(legacy.is_active)
            self.assertEqual((variant.price,variant.prescription_classification,variant.regulatory_scope),flags)
            self.assertEqual(product.brand_id,brand.pk)
            self.assertEqual(list(VariantInventory.objects.values()),before)
            self.assertEqual(Variant.objects.exclude(category_id=F('subcategory__category_id')).count(),0)
            self.assertIn(VERSION,variant.curation_notes)
            count=Subcategory.objects.count()
            call_command('organize_catalog_taxonomy',report_dir=folder,apply=True,stdout=StringIO())
            summary=json.loads((Path(folder)/'summary.json').read_text())
            self.assertEqual(summary['assigned'],0)
            self.assertEqual(summary['skipped_classified'],1)
            self.assertEqual(Subcategory.objects.count(),count)

    def test_product_and_sku_api_reject_mismatched_subcategory(self):
        a=Category.objects.create(name='Category A');b=Category.objects.create(name='Category B')
        sub=Subcategory.objects.create(name='A subcategory',category=a)
        product=Product.objects.create(name='Item',price=12,category=a,subcategory=sub)
        detail = AdminProductSerializer(product).data
        self.assertEqual(detail['category'], a.pk)
        self.assertEqual(detail['subcategory_id'], sub.pk)
        for serializer in [AdminProductSerializer(product,data={'category_id':b.pk},partial=True),
                           AdminVariantSerializer(product.variants.get(),data={'category_id':b.pk},partial=True)]:
            self.assertFalse(serializer.is_valid())
            self.assertIn('subcategory_id',serializer.errors)

    def test_subcategory_can_supply_parent_and_moves_keep_item_parent_consistent(self):
        a=Category.objects.create(name='Category A');b=Category.objects.create(name='Category B')
        sub=Subcategory.objects.create(name='A subcategory',category=a)
        serializer=AdminProductSerializer(data={'name':'New item','subcategory_id':sub.pk})
        self.assertTrue(serializer.is_valid(),serializer.errors)
        item=serializer.save()
        self.assertEqual(item.category_id,a.pk)
        move=SubcategorySerializer(sub,data={'category':b.pk},partial=True)
        self.assertTrue(move.is_valid(),move.errors);move.save()
        item=item.__class__.objects.get(pk=item.pk)
        self.assertEqual(item.category_id,b.pk)
