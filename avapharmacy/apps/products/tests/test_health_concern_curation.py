from io import StringIO
from tempfile import TemporaryDirectory
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase
from apps.products.health_concern_curation import infer_concerns, LEGACY_NOTE
from apps.products.models import Product, HealthConcern


class ConcernRulesTests(SimpleTestCase):
    def test_specific_matches(self):
        self.assertIn('Diabetes & Blood Glucose', infer_concerns('CONTOUR strips', '', 'Blood Glucose Monitoring'))
        self.assertIn('Smoking Cessation', infer_concerns('NICORETTE NICOTINE GUM'))
        self.assertIn('Period Care', infer_concerns('ALWAYS', '', 'Sanitary Pads'))

    def test_avoid_unrelated_medical_inferences(self):
        for name, category, forbidden in [
            ('Vitamin C face serum', 'Skin Care', 'Immune Support'),
            ('VAPE E LIQUID', 'Smoking Alternatives', 'Smoking Cessation'),
            ('HOT COLD PACK', '', 'Cold, Cough & Flu'),
            ('EYE SHADOW', 'Makeup & Nails', 'Eye Care'),
            ('Unknown brand 500mg', 'Pharmacy & Medicines', 'Pain & Fever')]:
            self.assertNotIn(forbidden, infer_concerns(name, category))


class ConcernCommandTests(TestCase):
    def test_replaces_only_attributable_links_and_is_idempotent(self):
        product = Product.objects.create(name='VAPE E LIQUID', price=10)
        v = product.variants.get()
        old = HealthConcern.objects.create(name='Smoking Cessation')
        manual = HealthConcern.objects.create(name='Manual care')
        v.health_concerns.add(old, manual)
        v.curation_notes = LEGACY_NOTE + 'Smoking Cessation.'
        v.save(update_fields=['curation_notes'])
        with TemporaryDirectory() as folder:
            call_command('organize_health_concerns', report_dir=folder, stdout=StringIO())
            self.assertTrue(v.health_concerns.filter(pk=old.pk).exists())
            call_command('organize_health_concerns', apply=True, report_dir=folder, stdout=StringIO())
            self.assertEqual(list(v.health_concerns.values_list('name', flat=True)), ['Manual care'])
            v.refresh_from_db(); notes = v.curation_notes
            call_command('organize_health_concerns', apply=True, report_dir=folder, stdout=StringIO())
            v.refresh_from_db(); self.assertEqual(notes, v.curation_notes)
            self.assertEqual(v.price, 10)

    def test_creates_and_links_new_concern(self):
        product = Product.objects.create(name='BLOOD GLUCOSE METER', price=20)
        with TemporaryDirectory() as folder:
            call_command('organize_health_concerns', apply=True, report_dir=folder, stdout=StringIO())
        self.assertTrue(product.variants.get().health_concerns.filter(name='Diabetes & Blood Glucose').exists())
