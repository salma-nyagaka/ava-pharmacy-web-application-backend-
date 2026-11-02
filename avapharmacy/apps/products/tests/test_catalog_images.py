from pathlib import Path
from tempfile import TemporaryDirectory

from django.core.management import call_command
from django.test import TestCase, override_settings

from apps.products.management.commands.sync_catalog_images import (
    gtin_check_digit_is_valid,
    image_result_match_score,
    normalized_barcode,
)
from apps.products.models import (
    IMAGE_SOURCE_MANUAL,
    IMAGE_SOURCE_PLACEHOLDER,
    Category,
    Product,
    Variant,
)


class CatalogImageCommandTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name='Oral Care', slug='oral-care')
        self.product = Product.objects.create(sku='PRD-TOOTHPASTE', slug='toothpaste', name='Toothpaste')
        self.variant = Variant.objects.create(
            product=self.product,
            sku='VAR-TOOTHPASTE-75ML',
            name='75ml',
            barcode='12345670',
            category=self.category,
            price='250.00',
        )

    def test_placeholder_mode_covers_products_and_variants(self):
        with TemporaryDirectory() as media_root, override_settings(MEDIA_ROOT=media_root):
            call_command('sync_catalog_images', '--apply', '--mode', 'placeholders')
            self.product.refresh_from_db()
            self.variant.refresh_from_db()

            self.assertEqual(self.product.image_source, IMAGE_SOURCE_PLACEHOLDER)
            self.assertEqual(self.variant.image_source, IMAGE_SOURCE_PLACEHOLDER)
            self.assertTrue(self.product.image.name.endswith('oral-care.png'))
            self.assertEqual(self.product.image.name, self.variant.image.name)
            self.assertTrue((Path(media_root) / self.product.image.name).is_file())

    def test_placeholder_mode_does_not_replace_curated_images(self):
        self.product.image = 'products/manual/product.webp'
        self.product.image_source = IMAGE_SOURCE_MANUAL
        self.product.image_verified = True
        self.product.save(update_fields=('image', 'image_source', 'image_verified', 'updated_at'))

        with TemporaryDirectory() as media_root, override_settings(MEDIA_ROOT=media_root):
            call_command('sync_catalog_images', '--apply', '--mode', 'placeholders')

        self.product.refresh_from_db()
        self.assertEqual(self.product.image.name, 'products/manual/product.webp')
        self.assertEqual(self.product.image_source, IMAGE_SOURCE_MANUAL)
        self.assertTrue(self.product.image_verified)

    def test_barcode_normalization_rejects_internal_codes(self):
        self.assertEqual(normalized_barcode(' 034-285-692-155 '), '034285692155')
        self.assertEqual(normalized_barcode('SKU-123'), '')
        self.assertEqual(normalized_barcode('12345671'), '')
        self.assertEqual(normalized_barcode('00000000'), '')
        self.assertTrue(gtin_check_digit_is_valid('12345670'))

    def test_web_match_score_requires_pack_size_and_close_title(self):
        expected = "Aunt Jackie's Don't Shrink Flaxseed Curling Gel 426g"
        exact = "Aunt Jackie's Don't Shrink Flaxseed Elongating Curling Gel 426g"
        wrong_size = "Aunt Jackie's Don't Shrink Flaxseed Elongating Curling Gel 250g"
        unrelated = 'Cantu Shea Butter Curling Cream 426g'

        self.assertGreaterEqual(image_result_match_score(expected, exact), 0.78)
        self.assertEqual(image_result_match_score(expected, wrong_size), 0.0)
        self.assertLess(image_result_match_score(expected, unrelated), 0.78)
