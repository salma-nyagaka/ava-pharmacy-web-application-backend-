from django.test import TestCase
from rest_framework.test import APIClient
from apps.accounts.models import User
from apps.orders.models import Order, OrderItem
from apps.orders.stock import commit_order_inventory
from apps.products.compliance import supply_error
from apps.products.models import Product, Variant, VariantInventory
from apps.support.models import MedicineRecall


class ProductDeactivationTests(TestCase):
    def setUp(self):
        self.user=User.objects.create_user(email='deactivation@example.test',role='admin')
        self.product=Product.objects.create(name='Stocked test item',price=10)
        self.variant=self.product.variants.get()
        self.variant.regulatory_scope='non_medicine'
        self.variant.save()
        self.stock=VariantInventory.objects.create(variant=self.variant,stock_quantity=20)

    def order(self):
        order=Order.objects.create(customer=self.user,subtotal=20,total=20,status='pending',payment_status='paid',inventory_committed=False)
        OrderItem.objects.create(order=order,product=self.product,variant=self.variant,product_name=self.product.name,product_sku=self.product.sku,quantity=2,unit_price=10)
        return order

    def test_deactivation_blocks_later_stock_commit_without_losing_stock(self):
        order=self.order()
        self.product.is_active=False;self.product.save()
        self.variant.refresh_from_db();self.assertFalse(self.variant.is_active)
        with self.assertRaisesRegex(ValueError,'inactive'):
            commit_order_inventory(order)
        self.stock.refresh_from_db();self.assertEqual(self.stock.stock_quantity,20)
        order.refresh_from_db();self.assertFalse(order.inventory_committed)

    def test_inactive_parent_is_blocked_even_if_legacy_child_still_active(self):
        Product.objects.filter(pk=self.product.pk).update(is_active=False)
        variant=Variant.objects.select_related('product').get(pk=self.variant.pk)
        self.assertTrue(variant.is_active)
        self.assertIn('inactive',supply_error(variant))

    def test_retired_recall_history_no_longer_controls_supply(self):
        historical=MedicineRecall.objects.create(variant=self.variant,reference='RETIRED-HISTORY',reason='Historical record retained',created_by=self.user)
        self.assertIsNone(supply_error(self.variant))
        commit_order_inventory(self.order())
        self.stock.refresh_from_db();self.assertEqual(self.stock.stock_quantity,18)
        historical.refresh_from_db();self.assertEqual(historical.reason,'Historical record retained')

    def test_removed_recall_endpoints_are_not_available(self):
        client=APIClient();client.force_authenticate(self.user)
        for path in ['/api/compliance/recalls/','/api/compliance/recalls/1/','/api/compliance/recalls/1/affected-orders/','/api/compliance/recall-orders/1/']:
            with self.subTest(path=path):
                self.assertEqual(client.get(path).status_code,404)
                self.assertEqual(client.post(path,{},format='json').status_code,404)
