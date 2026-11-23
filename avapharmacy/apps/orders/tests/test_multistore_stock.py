from avapharmacy.test_compliance_fixtures import inventory_fixture
from avapharmacy.test_compliance_fixtures import catalogue_fixture
from decimal import Decimal

from django.test import TestCase

from apps.accounts.models import User
from apps.orders.models import Order, OrderItem
from apps.orders.stock import commit_order_inventory, release_order_inventory
from apps.products.models import (
    Product,
    Store,
    StoreVariantListing,
    Variant,
    VariantInventory,
)


class MultiStoreOrderStockTests(TestCase):
    def setUp(self):
        self.customer = User.objects.create_user(
            email='multistore@example.com',
            password='testpass123',
        )
        self.product = Product.objects.create(
            sku='MULTISTORE-PRODUCT',
            name='Multi-store Product',
        )
        self.variant = Variant.objects.create(
            product=self.product,
            sku='MULTISTORE-VARIANT',
            name='Multi-store Variant',
            price=Decimal('500.00'),
        **catalogue_fixture(medicine=False, exclude=('product', 'sku', 'name', 'price')))
        first_store = Store.objects.create(code='first-store', name='First Store')
        second_store = Store.objects.create(code='second-store', name='Second Store')
        first_listing = StoreVariantListing.objects.create(
            store=first_store,
            variant=self.variant,
            price=Decimal('500.00'),
        )
        second_listing = StoreVariantListing.objects.create(
            store=second_store,
            variant=self.variant,
            price=Decimal('510.00'),
        )
        self.first_inventory = VariantInventory.objects.create(
            variant=self.variant,
            store_listing=first_listing,
            stock_quantity=2,
        **inventory_fixture(exclude=('variant', 'store_listing', 'stock_quantity')))
        self.second_inventory = VariantInventory.objects.create(
            variant=self.variant,
            store_listing=second_listing,
            stock_quantity=5,
        **inventory_fixture(exclude=('variant', 'store_listing', 'stock_quantity')))
        self.order = Order.objects.create(
            customer=self.customer,
            status=Order.STATUS_PENDING,
            payment_method=Order.PAYMENT_COD,
            payment_status=Order.PAYMENT_STATUS_PENDING,
            shipping_first_name='Multi',
            shipping_last_name='Store',
            shipping_email='multistore@example.com',
            shipping_phone='+254700000001',
            shipping_street='Test Street',
            shipping_city='Nairobi',
            shipping_county='Nairobi',
        )
        self.item = OrderItem.objects.create(
            order=self.order,
            variant=self.variant,
            product_name=self.product.name,
            product_sku=self.product.sku,
            variant_name=self.variant.name,
            variant_sku=self.variant.sku,
            quantity=3,
            unit_price=self.variant.price,
        )

    def test_release_restores_the_exact_store_rows_consumed(self):
        commit_order_inventory(self.order)

        self.item.refresh_from_db()
        self.first_inventory.refresh_from_db()
        self.second_inventory.refresh_from_db()
        self.assertEqual(self.first_inventory.stock_quantity, 0)
        self.assertEqual(self.second_inventory.stock_quantity, 4)
        self.assertEqual(
            [row['inventory_id'] for row in self.item.inventory_allocations],
            [self.first_inventory.id, self.second_inventory.id],
        )

        release_order_inventory(self.order)

        self.item.refresh_from_db()
        self.first_inventory.refresh_from_db()
        self.second_inventory.refresh_from_db()
        self.assertEqual(self.first_inventory.stock_quantity, 2)
        self.assertEqual(self.second_inventory.stock_quantity, 5)
        self.assertEqual(self.item.inventory_allocations, [])


    def test_selected_location_only_is_consumed_and_restored(self):
        self.item.selected_inventory = self.second_inventory
        self.item.save(update_fields=['selected_inventory'])
        commit_order_inventory(self.order)
        self.first_inventory.refresh_from_db()
        self.second_inventory.refresh_from_db()
        self.item.refresh_from_db()
        self.assertEqual(self.first_inventory.stock_quantity, 2)
        self.assertEqual(self.second_inventory.stock_quantity, 2)
        self.assertEqual([row['inventory_id'] for row in self.item.inventory_allocations], [self.second_inventory.pk])
        release_order_inventory(self.order)
        self.second_inventory.refresh_from_db()
        self.assertEqual(self.second_inventory.stock_quantity, 5)

    def test_selected_location_cannot_spill_over_to_another_store(self):
        self.item.selected_inventory = self.first_inventory
        self.item.save(update_fields=['selected_inventory'])
        with self.assertRaisesMessage(ValueError, 'Insufficient stock at the selected medication location'):
            commit_order_inventory(self.order)
        self.first_inventory.refresh_from_db()
        self.second_inventory.refresh_from_db()
        self.order.refresh_from_db()
        self.assertEqual(self.first_inventory.stock_quantity, 2)
        self.assertEqual(self.second_inventory.stock_quantity, 5)
        self.assertFalse(self.order.inventory_committed)

    def test_location_selection_survives_cart_snapshot(self):
        from apps.orders.models import Cart, CartItem
        from apps.orders.views import snapshot_cart_to_order
        cart = Cart.objects.create(user=self.customer)
        item = CartItem.objects.create(cart=cart, variant=self.variant, quantity=1, selected_inventory=self.second_inventory)
        snapshot_cart_to_order(self.order, [item])
        self.assertEqual(self.order.items.get().selected_inventory_id, self.second_inventory.pk)

    def test_catalog_locations_identify_each_store_and_quantity(self):
        from apps.products.medication_locations import location_options, validate_inventory_selection
        options = {row['inventory_id']: row for row in location_options(self.variant)}
        self.assertEqual(options[self.first_inventory.pk]['branch_name'], 'First Store')
        self.assertEqual(options[self.second_inventory.pk]['available_quantity'], 5)
        with self.assertRaisesMessage(ValueError, 'Only 2 unit(s)'):
            validate_inventory_selection(self.variant, self.first_inventory.pk, 3)
        with self.assertRaisesMessage(ValueError, 'does not match this variant'):
            validate_inventory_selection(self.variant, 9999999, 1)

    def test_staff_selection_requires_a_location_when_multiple_are_available(self):
        from apps.prescriptions.serializers import PharmacistPrescriptionReviewItemSerializer
        data = {'name': 'Medication', 'variant_id': self.variant.pk, 'quantity': 1}
        serializer = PharmacistPrescriptionReviewItemSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('selected_inventory_id', serializer.errors)
        data['selected_inventory_id'] = self.second_inventory.pk
        serializer = PharmacistPrescriptionReviewItemSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data['selected_inventory_id'], self.second_inventory.pk)

    def test_review_preserves_the_chosen_location_on_prescription_item(self):
        from apps.prescriptions.models import Prescription
        from apps.prescriptions.views import _replace_prescription_items
        prescription = Prescription.objects.create(patient=self.customer, patient_name='Test patient')
        _replace_prescription_items(prescription, [{'name': 'Medication', 'variant_id': self.variant.pk,
            'selected_inventory_id': self.second_inventory.pk, 'quantity': 1}])
        self.assertEqual(prescription.items.get().selected_inventory_id, self.second_inventory.pk)

    def test_clinician_selection_preserves_location_and_checks_local_stock(self):
        from apps.consultations.serializers import validate_clinician_prescription_items
        from rest_framework.exceptions import ValidationError
        data = {'variant_id': self.variant.pk, 'selected_inventory_id': self.second_inventory.pk, 'quantity': 3}
        result = validate_clinician_prescription_items([data])[0]
        self.assertEqual(result['selected_inventory_id'], self.second_inventory.pk)
        self.assertEqual(result['selected_branch'], 'Second Store')
        data['selected_inventory_id'] = self.first_inventory.pk
        with self.assertRaises(ValidationError):
            validate_clinician_prescription_items([data])
