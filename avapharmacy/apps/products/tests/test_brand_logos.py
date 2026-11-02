from io import BytesIO

from django.test import SimpleTestCase
from PIL import Image

from apps.products.management.commands.sync_brand_logos import (
    DISALLOWED_ENTITY_IDS_BY_BRAND,
    Command,
    _entity_score,
)


class BrandLogoCommandTests(SimpleTestCase):
    def test_entity_score_rejects_people_and_unrelated_labels(self):
        self.assertLess(_entity_score("Nivea", {
            "label": "Nivea",
            "description": "American singer, songwriter and actress",
            "match": {"type": "label"},
        }), 0)
        self.assertLess(_entity_score("Nivea", {
            "label": "Nivea Men",
            "description": "personal care brand",
            "match": {"type": "label"},
        }), 0)

    def test_health_and_beauty_entity_outranks_generic_company(self):
        generic = _entity_score("Aquaphor", {
            "label": "Aquaphor",
            "description": "Russian manufacturing company",
            "match": {"type": "label"},
        })
        skincare = _entity_score("Aquaphor", {
            "label": "Aquaphor",
            "description": "skin care brand",
            "match": {"type": "label"},
        })
        self.assertGreater(skincare, generic)

    def test_generated_wordmark_is_valid_square_png(self):
        content = Command()._generate_wordmark("Aunt Jackie's")
        with Image.open(BytesIO(content)) as image:
            self.assertEqual(image.format, "PNG")
            self.assertEqual(image.size, (512, 512))

    def test_known_wrong_entities_are_denied(self):
        self.assertIn("Q3046037", DISALLOWED_ENTITY_IDS_BY_BRAND["eos"])
        self.assertIn("Q5000673", DISALLOWED_ENTITY_IDS_BY_BRAND["burtsbees"])
