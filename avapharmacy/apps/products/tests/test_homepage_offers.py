from django.test import TestCase
from django.utils import timezone
from apps.products.models import Category, Subcategory, Product, Variant, Promotion
from apps.products.filters import VariantInventoryFilter
from apps.products.serializers import PromotionSerializer
from apps.products.services import calculate_variant_pricing


class HomepageOffersTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name='Offer category')
        self.subcategory = Subcategory.objects.create(name='Offer subgroup', category=self.category)
        self.product = Product.objects.create(name='Eligible item', price=100, category=self.category)
        self.variant = self.product.variants.get()
        self.variant.subcategory = self.subcategory
        self.variant.regulatory_scope = 'non_medicine'
        self.variant.save()
        today = timezone.now().date()
        self.promotion = Promotion.objects.create(title='Offer', scope='category', targets=[self.subcategory.slug], type='percentage', value=10, start_date=today, end_date=today, status='active')

    def test_subcategory_offer_is_selected_before_pagination_and_discounted(self):
        queryset = VariantInventoryFilter({'on_offer': 'true'}, queryset=Variant.objects.all()).qs
        self.assertEqual(list(queryset.values_list('pk', flat=True)), [self.variant.pk])
        self.assertEqual(calculate_variant_pricing(self.variant)['discount_total'], 10)

    def test_unreviewed_classification_does_not_block_offers(self):
        self.variant.regulatory_scope = 'unreviewed'
        self.variant.save()
        self.assertTrue(VariantInventoryFilter({'on_offer': 'true'}, queryset=Variant.objects.all()).qs.exists())
        self.assertEqual(calculate_variant_pricing(self.variant)['discount_total'], 10)
        from apps.products.compliance import promotional_product
        self.assertTrue(promotional_product(self.product))

    def test_prescription_items_excluded(self):
        for fields in ({'requires_prescription': True}, {'prescription_classification': 'controlled'}):
            Variant.objects.filter(pk=self.variant.pk).update(**fields)
            self.assertFalse(VariantInventoryFilter({'on_offer': 'true'}, queryset=Variant.objects.all()).qs.exists())
            Variant.objects.filter(pk=self.variant.pk).update(regulatory_scope='non_medicine', requires_prescription=False, prescription_classification='unknown')

    def test_cross_scope_target_rejected(self):
        serializer = PromotionSerializer(self.promotion, data={'scope': 'brand', 'targets': [self.subcategory.slug]}, partial=True)
        self.assertFalse(serializer.is_valid())
        self.assertIn('targets', serializer.errors)
