import io
from decimal import Decimal

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from PIL import Image
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.orders.models import Cart, CartItem
from apps.products.models import Brand, Category, Product, ProductInventory, Promotion, Wishlist


def make_test_image(name='test.png', *, width=1000, height=1000, color=(220, 20, 60)):
    buffer = io.BytesIO()
    image = Image.new('RGB', (width, height), color=color)
    image.save(buffer, format='PNG')
    buffer.seek(0)
    return SimpleUploadedFile(name, buffer.read(), content_type='image/png')


class AdminCatalogAndWishlistTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_user(
            email='admin@example.com',
            password='testpass123',
            first_name='Admin',
            last_name='User',
            role=User.ADMIN,
            is_staff=True,
        )
        self.customer = User.objects.create_user(
            email='customer@example.com',
            password='testpass123',
            first_name='Customer',
            last_name='User',
            role=User.CUSTOMER,
        )

    def test_admin_can_create_product_category_and_subcategory(self):
        self.client.force_authenticate(self.admin)
        category_response = self.client.post(
            reverse('admin-product-categories'),
            {
                'name': 'Pain Relief',
                'description': 'Pain relief essentials',
                'image': make_test_image('category.png', width=900, height=900),
            },
            format='multipart',
        )
        self.assertEqual(category_response.status_code, 201)
        product_category = Category.objects.get(name='Pain Relief', parent__isnull=True)
        self.assertTrue(product_category.slug)

        subcategory_response = self.client.post(
            reverse('admin-product-subcategories'),
            {
                'name': 'Tablets',
                'category': product_category.id,
                'description': 'Pain relief tablets',
            },
            format='json',
        )
        self.assertEqual(subcategory_response.status_code, 201)
        subcategory = Category.objects.get(name='Tablets', parent=product_category)
        self.assertEqual(subcategory.parent, product_category)

    def test_admin_can_create_brand_product_and_promotion(self):
        self.client.force_authenticate(self.admin)

        brand_response = self.client.post(
            reverse('admin-brands'),
            {
                'name': 'Panadol',
                'description': 'Pain care brand',
                'logo': make_test_image('brand.png', width=500, height=500),
            },
            format='multipart',
        )
        self.assertEqual(brand_response.status_code, 201)
        brand = Brand.objects.get(name='Panadol')

        product_response = self.client.post(
            reverse('admin-products'),
            {
                'sku': 'PANADOL-500',
                'name': 'Panadol 500mg',
                'price': '1000.00',
                'cost_price': '600.00',
                'discount_price': '850.00',
                'brand_id': brand.id,
                'description': 'Pain relief tablet',
                'short_description': 'Fast pain relief',
                'image': make_test_image('product.png', width=1200, height=1200),
                'branch_inventory': '{"stock_quantity": 12, "low_stock_threshold": 3}',
            },
            format='multipart',
        )
        self.assertEqual(product_response.status_code, 201)
        product = Product.objects.get(sku='PANADOL-500')
        self.assertEqual(product.brand, brand)
        branch_inventory = ProductInventory.objects.get(product=product, location=Product.STOCK_BRANCH)
        self.assertEqual(branch_inventory.stock_quantity, 12)

        promotion_response = self.client.post(
            reverse('admin-promotions'),
            {
                'title': 'Panadol Weekend Saver',
                'code': 'PANADOL15',
                'description': '15 percent off Panadol',
                'type': Promotion.TYPE_PERCENTAGE,
                'value': '15',
                'scope': Promotion.SCOPE_PRODUCT,
                'targets': [product.sku],
                'minimum_order_amount': '0',
                'start_date': '2026-03-16',
                'end_date': '2026-03-30',
                'status': Promotion.STATUS_ACTIVE,
            },
            format='json',
        )
        self.assertEqual(promotion_response.status_code, 201)
        promotion = Promotion.objects.get(code='PANADOL15')
        self.assertEqual(promotion.badge, '15% Off')
        self.assertFalse(promotion.is_stackable)

    def test_customer_can_add_to_wishlist_move_to_cart_and_back(self):
        product = Product.objects.create(
            sku='WISH-001',
            name='Vitamin C',
            price=Decimal('500.00'),
            is_active=True,
        )
        ProductInventory.objects.update_or_create(
            product=product,
            location=Product.STOCK_BRANCH,
            defaults={
                'stock_quantity': 10,
                'low_stock_threshold': 2,
            },
        )

        self.client.force_authenticate(self.customer)

        add_wishlist_response = self.client.post(
            reverse('wishlist'),
            {'product_id': product.id},
            format='json',
        )
        self.assertEqual(add_wishlist_response.status_code, 201)
        wishlist_item = Wishlist.objects.get(user=self.customer, product=product)

        move_to_cart_response = self.client.post(
            reverse('wishlist-item-move-to-cart', args=[wishlist_item.id]),
            {'quantity': 2},
            format='json',
        )
        self.assertEqual(move_to_cart_response.status_code, 200)
        self.assertFalse(Wishlist.objects.filter(user=self.customer, product=product).exists())

        cart = Cart.objects.get(user=self.customer)
        cart_item = CartItem.objects.get(cart=cart, product=product)
        self.assertEqual(cart_item.quantity, 2)

        move_back_response = self.client.post(
            reverse('cart-item-move-to-wishlist', args=[cart_item.id]),
            {},
            format='json',
        )
        self.assertEqual(move_back_response.status_code, 200)
        self.assertTrue(Wishlist.objects.filter(user=self.customer, product=product).exists())
        self.assertFalse(CartItem.objects.filter(pk=cart_item.id).exists())

    def test_duplicate_wishlist_entry_is_rejected(self):
        product = Product.objects.create(
            sku='WISH-002',
            name='Zinc',
            price=Decimal('250.00'),
            is_active=True,
        )
        self.client.force_authenticate(self.customer)
        self.client.post(reverse('wishlist'), {'product_id': product.id}, format='json')
        response = self.client.post(reverse('wishlist'), {'product_id': product.id}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Wishlist.objects.filter(user=self.customer, product=product).count(), 1)
