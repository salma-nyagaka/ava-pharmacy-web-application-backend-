from django.test import SimpleTestCase
from apps.products.management.commands.update_brand_descriptions import describe_brand

class BrandDescriptionTests(SimpleTestCase):
    def test_description_uses_only_linked_product_facts(self):
        text = describe_brand('Example Brand', [{'subcategory__name':'Body Moisturisers & Oils','category__name':'Skin Care','product__name':'EXAMPLE BODY LOTION 200ML'}])
        self.assertIn('Example Brand', text)
        self.assertIn('body moisturisers & oils', text)
        self.assertIn('EXAMPLE BODY LOTION 200ML', text)
        self.assertNotIn('verified', text)

    def test_unlinked_brand_has_no_invented_product_claims(self):
        text = describe_brand('Unlinked Brand', [])
        self.assertIn('Unlinked Brand', text)
        self.assertNotIn('medicine', text)
