from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.products.models import Product, VariantInventory
from avapharmacy.test_compliance_fixtures import catalogue_fixture, inventory_fixture


class PharmacistCatalogEligibilityTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(User.objects.create_user(email='picker-pharmacist@example.invalid', role='pharmacist'))
        self.product = Product.objects.create(sku='PICKER-TEST', name='Picker medicine', price='100', requires_prescription=True)
        self.variant = self.product.variants.get()
        VariantInventory.objects.update_or_create(variant=self.variant, location=Product.STOCK_BRANCH, defaults={'stock_quantity': 10, **inventory_fixture(exclude=('stock_quantity',))})

    def result(self):
        response = self.client.get('/api/pharmacist/catalog/variants/', {'q': 'Picker medicine'})
        self.assertEqual(response.status_code, 200, response.data)
        return response.data['results'][0]

    def test_unreviewed_status_does_not_block_otherwise_eligible_medicine(self):
        for field, value in catalogue_fixture(medicine=True).items():
            setattr(self.variant, field, value)
        self.variant.regulatory_scope = 'unreviewed'
        self.variant.prescription_review_status = 'inferred'
        self.variant.save()
        result = self.result()
        self.assertGreater(result['available_quantity'], 0)
        self.assertTrue(result['can_select'])
        self.assertEqual(result['unavailable_reason'], '')

    def test_pending_review_status_does_not_block_otherwise_eligible_medicine(self):
        for field, value in catalogue_fixture(medicine=True).items():
            setattr(self.variant, field, value)
        self.variant.regulatory_scope = 'unreviewed'
        self.variant.prescription_review_status = 'pending'
        self.variant.save()
        self.assertTrue(self.result()['can_select'])

    def test_registration_and_supplier_metadata_do_not_block_selection(self):
        for field, value in catalogue_fixture(medicine=True).items():
            setattr(self.variant, field, value)
        self.variant.is_ppb_registered = False
        self.variant.ppb_registration_number = ''
        self.variant.authorized_supplier = ''
        self.variant.regulatory_status = 'unknown'
        self.variant.ppb_license_expiry_date = None
        self.variant.save()
        result = self.result()
        self.assertTrue(result['can_select'])
        self.assertEqual(result['unavailable_reason'], '')

    def test_suspended_and_withdrawn_items_remain_blocked(self):
        for status in ('suspended', 'withdrawn'):
            self.variant.regulatory_status = status
            self.variant.save()
            with self.subTest(status=status):
                result = self.result()
                self.assertFalse(result['can_select'])
                self.assertIn('suspended or withdrawn', result['unavailable_reason'])

    def test_reviewed_in_stock_medicine_is_selectable(self):
        for field, value in catalogue_fixture(medicine=True).items():
            setattr(self.variant, field, value)
        self.variant.save()
        result = self.result()
        self.assertGreater(result['available_quantity'], 0)
        self.assertTrue(result['can_select'])
        self.assertEqual(result['unavailable_reason'], '')

    def test_reviewed_out_of_stock_medicine_has_stock_reason(self):
        for field, value in catalogue_fixture(medicine=True).items():
            setattr(self.variant, field, value)
        self.variant.save()
        self.variant.inventories.update(stock_quantity=0)
        result = self.result()
        self.assertFalse(result['can_select'])
        self.assertEqual(result['unavailable_reason'], 'Out of stock')
