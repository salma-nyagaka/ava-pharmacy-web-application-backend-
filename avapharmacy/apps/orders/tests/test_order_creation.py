from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.orders.models import Cart, CartItem, Order
from apps.prescriptions.models import Prescription, PrescriptionItem
from apps.products.models import Product, ProductInventory


class OrderCreationFlowTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.customer = User.objects.create_user(
            email='buyer@example.com',
            password='testpass123',
            first_name='Buyer',
            last_name='Customer',
            role=User.CUSTOMER,
        )
        self.admin = User.objects.create_user(
            email='admin-orders@example.com',
            password='testpass123',
            first_name='Admin',
            last_name='Orders',
            role=User.ADMIN,
            is_staff=True,
        )
        self.product = Product.objects.create(
            sku='ORDER-001',
            name='Order Test Product',
            price=Decimal('700.00'),
            is_active=True,
        )
        ProductInventory.objects.update_or_create(
            product=self.product,
            location=Product.STOCK_BRANCH,
            defaults={
                'stock_quantity': 20,
                'low_stock_threshold': 3,
            },
        )

    def test_customer_can_create_order_and_admin_can_view_it(self):
        self.client.force_authenticate(self.customer)
        cart = Cart.objects.create(user=self.customer)
        CartItem.objects.create(cart=cart, product=self.product, quantity=2)

        order_response = self.client.post(
            reverse('order-create'),
            {
                'first_name': 'Buyer',
                'last_name': 'Customer',
                'email': 'buyer@example.com',
                'phone': '0727808457',
                'street': 'Moi Avenue',
                'city': 'Nairobi',
                'county': 'Nairobi',
                'payment_method': Order.PAYMENT_COD,
                'delivery_method': 'standard',
            },
            format='json',
        )
        self.assertEqual(order_response.status_code, 201)

        order = Order.objects.get(customer=self.customer)
        self.assertEqual(order.status, Order.STATUS_PENDING)
        self.assertEqual(order.payment_method, Order.PAYMENT_COD)
        self.assertEqual(order.total, Decimal('1400.00') + order.shipping_fee)
        self.assertTrue(order.inventory_committed)
        self.assertEqual(order.items.count(), 1)
        self.assertFalse(CartItem.objects.filter(cart=cart).exists())

        self.client.force_authenticate(self.admin)
        admin_list_response = self.client.get(reverse('admin-orders'))
        self.assertEqual(admin_list_response.status_code, 200)
        admin_detail_response = self.client.get(reverse('admin-order-detail', args=[order.id]))
        self.assertEqual(admin_detail_response.status_code, 200)

    def test_prescription_cart_item_uses_foreign_keys_and_order_snapshot_preserves_them(self):
        self.product.requires_prescription = True
        self.product.save(update_fields=['requires_prescription'])

        prescription = Prescription.objects.create(
            patient=self.customer,
            patient_name=self.customer.full_name,
            status=Prescription.STATUS_APPROVED,
        )
        prescription_item = PrescriptionItem.objects.create(
            prescription=prescription,
            product=self.product,
            name=self.product.name,
            quantity=2,
        )

        self.client.force_authenticate(self.customer)
        add_to_cart_response = self.client.post(
            reverse('cart-items'),
            {
                'product_id': self.product.id,
                'quantity': 2,
                'prescription': prescription.id,
                'prescription_item': prescription_item.id,
            },
            format='json',
        )
        self.assertEqual(add_to_cart_response.status_code, 201)

        cart_item = CartItem.objects.get(cart__user=self.customer, product=self.product)
        self.assertEqual(cart_item.prescription_id, prescription.id)
        self.assertEqual(cart_item.prescription_item_id, prescription_item.id)
        self.assertEqual(cart_item.prescription_reference, prescription.reference)

        order_response = self.client.post(
            reverse('order-create'),
            {
                'first_name': 'Buyer',
                'last_name': 'Customer',
                'email': 'buyer@example.com',
                'phone': '0727808457',
                'street': 'Moi Avenue',
                'city': 'Nairobi',
                'county': 'Nairobi',
                'payment_method': Order.PAYMENT_COD,
                'delivery_method': 'standard',
            },
            format='json',
        )
        self.assertEqual(order_response.status_code, 201)

        order = Order.objects.get(customer=self.customer)
        order_item = order.items.get(product=self.product)
        self.assertEqual(order_item.prescription_id, prescription.id)
        self.assertEqual(order_item.prescription_item_id, prescription_item.id)
        self.assertEqual(order_item.prescription_reference, prescription.reference)
