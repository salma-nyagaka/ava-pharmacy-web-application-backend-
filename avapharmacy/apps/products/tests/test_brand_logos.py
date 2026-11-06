import io
from PIL import Image
from django.test import SimpleTestCase
from apps.products.management.commands.import_brand_logos import validated_image

class BrandLogoValidationTests(SimpleTestCase):
    def test_raster_and_static_svg(self):
        buffer=io.BytesIO();Image.new('RGB',(10,10),'red').save(buffer,format='PNG')
        self.assertEqual(validated_image(buffer.getvalue())[1], 'png')
        self.assertEqual(validated_image(b'<svg xmlns="http://www.w3.org/2000/svg"><path d="M0 0" /></svg>')[1], 'svg')

    def test_internal_svg_symbol_is_allowed(self):
        self.assertEqual(validated_image(b'<svg xmlns="http://www.w3.org/2000/svg"><defs><path id="logo" d="M0 0"/></defs><use href="#logo"/></svg>')[1], 'svg')

    def test_active_or_remote_svg_rejected(self):
        for markup in [b'<svg><script>alert(1)</script></svg>', b'<svg><image href="https://example.com/a" /></svg>', b'<svg onload="run()"/>', b'<svg><use href="https://example.com/logo"/></svg>']:
            with self.subTest(markup=markup), self.assertRaises(ValueError):validated_image(markup)
