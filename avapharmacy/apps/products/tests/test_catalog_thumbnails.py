from io import BytesIO, StringIO
from tempfile import TemporaryDirectory

from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase
from PIL import Image

from apps.products.models import Product, Variant
from apps.products.serializers import ProductDetailSerializer, ProductListSerializer, PublicInventoryItemSerializer
from avapharmacy.test_compliance_fixtures import catalogue_fixture


def upload_photo(color):
    data = BytesIO()
    Image.new('RGB', (1200, 600), color).save(data, format='PNG')
    return SimpleUploadedFile('product-photo.png', data.getvalue(), content_type='image/png')


class CatalogThumbnailTests(TestCase):
    def setUp(self):
        media = self.enterContext(TemporaryDirectory())
        self.enterContext(self.settings(MEDIA_ROOT=media, MEDIA_URL='/media/', CATALOG_THUMBNAIL_SPACES_BUCKET=''))

    def test_upload_and_replace_thumbnail_while_detail_keeps_original(self):
        product = Product.objects.create(name='Photo test')
        with self.captureOnCommitCallbacks(execute=True):
            variant = Variant.objects.create(
                product=product, name=product.name, price=100, image=upload_photo('blue'),
                **catalogue_fixture(),
            )
        variant.refresh_from_db()
        first_url = variant.catalog_thumbnail_url
        self.assertTrue(first_url.startswith('/media/products/thumbnails/'))
        with variant.image.storage.open(first_url.removeprefix('/media/')) as source:
            with Image.open(source) as thumbnail:
                self.assertEqual(thumbnail.format, 'WEBP')
                self.assertEqual(thumbnail.size, (480, 240))
        self.assertEqual(PublicInventoryItemSerializer(variant).data['image'], first_url)
        detail = ProductDetailSerializer(product).data
        self.assertEqual(detail['image'], variant.image.url)

        variant.image = upload_photo('green')
        with self.captureOnCommitCallbacks(execute=True):
            variant.save(update_fields=['image'])
        variant.refresh_from_db()
        self.assertNotEqual(variant.catalog_thumbnail_url, first_url)
        self.assertEqual(PublicInventoryItemSerializer(variant).data['image'], variant.catalog_thumbnail_url)

    def test_existing_photo_uses_original_until_backfill(self):
        with self.captureOnCommitCallbacks():
            product = Product.objects.create(name='Existing photo', image=upload_photo('red'))
        self.assertEqual(ProductListSerializer(product).data['image'], product.image.url)

        call_command('backfill_catalog_thumbnails', limit=1, stdout=StringIO())
        product.refresh_from_db()
        self.assertTrue(product.catalog_thumbnail_url.endswith('.webp'))
        self.assertEqual(ProductListSerializer(product).data['image'], product.catalog_thumbnail_url)
