import json
from pathlib import Path
from tempfile import TemporaryDirectory

from django.core.management import call_command
from django.test import TestCase, SimpleTestCase
from apps.products.brand_research import load_brand_rules, match_brand
from apps.products.models import Brand, Product, VariantInventory


class BrandEvidenceTests(SimpleTestCase):
    def test_evidence_is_consistent_and_matches_exact_trade_labels(self):
        rules = load_brand_rules()
        self.assertEqual(match_brand('ZYRTEC 10MG TABS', rules)['brand'], 'Zyrtec')
        self.assertIsNone(match_brand('CETIRIZINE 10MG TABS', rules))
        self.assertIsNone(match_brand('Compatible with Oral-B toothbrush', rules))
        self.assertIsNone(match_brand('ZYRTECX 10MG', rules))
        self.assertIsNone(match_brand('PAPERBAG NUMBER 2', rules))
        self.assertEqual(match_brand('NATURE\\\'S WAY GUMMIES', rules)['brand'], "Nature's Way")


class BrandLinkCommandTests(TestCase):
    def test_dry_run_apply_reuse_and_repeat_do_not_touch_stock_or_existing_brands(self):
        existing = Brand.objects.create(name='Zyrtec', logo='')
        keep = Brand.objects.create(name='Keep label', logo='')
        exact = Product.objects.create(name='ZYRTEC 10MG TABS', price=20)
        tagged = Product.objects.create(name='ZYRTEC tagged already', brand=keep, price=25)
        new = Product.objects.create(name='ZZZQUIL NIGHTTIME 177ML', price=30)
        unknown = Product.objects.create(name='CETIRIZINE GENERIC', price=10)
        stock = VariantInventory.objects.create(variant=exact.variants.get(), stock_quantity=12, batch_number='BRAND-KEEP')
        before_stock = list(VariantInventory.objects.filter(pk=stock.pk).values())
        before_variants = list(exact.variants.values())
        with TemporaryDirectory() as folder:
            call_command('link_researched_brands', report_dir=folder, verbosity=0)
            exact.refresh_from_db()
            self.assertIsNone(exact.brand_id)
            call_command('link_researched_brands', report_dir=folder, apply=True, verbosity=0)
            exact.refresh_from_db(); tagged.refresh_from_db(); new.refresh_from_db(); unknown.refresh_from_db()
            self.assertEqual(exact.brand_id, existing.pk)
            self.assertEqual(tagged.brand_id, keep.pk)
            self.assertEqual(new.brand.name, 'ZzzQuil')
            self.assertIsNone(unknown.brand_id)
            self.assertEqual(list(exact.variants.values()), before_variants)
            self.assertEqual(list(VariantInventory.objects.filter(pk=stock.pk).values()), before_stock)
            self.assertIn('https://www.zyrtec.com/', exact.curation_notes)
            report = json.loads((Path(folder) / 'summary.json').read_text())
            self.assertEqual(report['assigned'], 2)
            count = Brand.objects.count()
            call_command('link_researched_brands', report_dir=folder, apply=True, verbosity=0)
            self.assertEqual(Brand.objects.count(), count)
            self.assertEqual(json.loads((Path(folder) / 'summary.json').read_text())['assigned'], 0)
