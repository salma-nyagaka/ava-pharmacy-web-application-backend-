from io import StringIO
from tempfile import TemporaryDirectory
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase
from apps.products.item_spec_extraction import extract_specs
from apps.products.models import Product

class ItemSpecExtractionTests(SimpleTestCase):
    def test_explicit_strengths_and_packs(self):
        cases=[('PENAMOX 250MG/5ML SUSPENSION 100ML','250 mg/5 mL','100 mL'),
          ("CHARCO TABLETS 250MG 100'S",'250 mg','100 units'),
          ('SKIN CREAM 2% 30G','2 %','30 g'),
          ('TABLETS 100/500MG 20S','100/500 mg','20 units'),
          ('MEDICINE 5MG/10MG 30 CAPSULES','5 mg / 10 mg','30 capsules')]
        for name,strength,pack in cases:
            with self.subTest(name=name):
                result=extract_specs(name);self.assertEqual(result.strength,strength);self.assertEqual(result.pack_size,pack)
    def test_ambiguous_and_unprinted_values_are_not_guessed(self):
        for name in ['ZULU MR TABLETS @','CAPSULES 250MG OR 500MG','MIXED PACK 100ML + 50ML','SOAP 3 X 100G','SYRINGE 5ML','WATER BOTTLE 500ML']:
            result=extract_specs(name)
            self.assertTrue(result.reasons)
            if name=='CAPSULES 250MG OR 500MG':self.assertEqual(result.strength,'')
            else:self.assertEqual(result.pack_size,'')

class ItemSpecCommandTests(TestCase):
    def test_preserves_manual_values_and_stock_and_repeat_safe(self):
        product=Product.objects.create(name="Test tablet 250MG 20'S",price=10)
        variant=product.variants.get();variant.sku='LEGACY-V-SPEC-TEST';variant.strength='Manual strength';variant.save()
        with TemporaryDirectory() as folder:
            call_command('extract_item_specs',apply=True,report_dir=folder,stdout=StringIO())
            variant.refresh_from_db();self.assertEqual(variant.strength,'Manual strength');self.assertEqual(variant.pack_size,'20 units')
            before=(variant.price,variant.product_id,variant.sku,variant.pack_size)
            call_command('extract_item_specs',apply=True,report_dir=folder,stdout=StringIO())
            variant.refresh_from_db();self.assertEqual(before,(variant.price,variant.product_id,variant.sku,variant.pack_size))
