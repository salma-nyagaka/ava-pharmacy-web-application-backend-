from django.test import TestCase
from apps.products.models import Product, Variant
from apps.products.filters import ProductFilter, VariantInventoryFilter

class PrescriptionFilterTests(TestCase):
    def test_filter_includes_active_and_inactive_prescription_items(self):
        rx=Product.objects.create(name='Prescription item',price=10,requires_prescription=True)
        inactive=Product.objects.create(name='Inactive prescription item',price=10,requires_prescription=True,is_active=False)
        otc=Product.objects.create(name='Non-prescription item',price=10,requires_prescription=False)
        self.assertEqual(set(ProductFilter({'requires_prescription':'true'},queryset=Product.objects.all()).qs.values_list('pk',flat=True)),{rx.pk,inactive.pk})
        self.assertEqual(set(ProductFilter({'requires_prescription':'false'},queryset=Product.objects.all()).qs.values_list('pk',flat=True)),{otc.pk})
        self.assertEqual(set(VariantInventoryFilter({'requires_prescription':'true'},queryset=Variant.objects.all()).qs.values_list('product_id',flat=True)),{rx.pk,inactive.pk})
