import io
from decimal import Decimal

from django.core.management import call_command
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from PIL import Image
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.orders.models import Cart, CartItem, Order, OrderItem
from apps.products.models import Brand, Category, Product, ProductInventory, ProductReview, Promotion, Wishlist


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

    def test_admin_brand_create_accepts_image_alias(self):
        self.client.force_authenticate(self.admin)

        response = self.client.post(
            reverse('admin-brands'),
            {
                'name': 'Alias Brand',
                'description': 'Created with image alias',
                'image': make_test_image('brand-alias.png', width=500, height=500),
            },
            format='multipart',
        )

        self.assertEqual(response.status_code, 201)
        brand = Brand.objects.get(name='Alias Brand')
        self.assertIn('brand-alias', brand.logo.name)
        self.assertEqual(response.data['logo'], response.data['image'])

    def test_public_brand_and_product_responses_include_brand_images(self):
        brand = Brand.objects.create(
            name='Image Brand',
            slug='image-brand',
            logo=make_test_image('brand-public.png', width=500, height=500),
            is_active=True,
        )
        Product.objects.create(
            sku='IMG-BRAND-001',
            name='Image Brand Product',
            slug='image-brand-product',
            brand=brand,
            price=Decimal('1200.00'),
            is_active=True,
        )

        brands_response = self.client.get(reverse('brands'))
        self.assertEqual(brands_response.status_code, 200)
        brand_item = next(entry for entry in brands_response.data['results'] if entry['slug'] == brand.slug)
        self.assertEqual(brand_item['logo'], brand_item['image'])
        self.assertIn('brand-public', brand_item['image'])

        products_response = self.client.get(reverse('products'))
        self.assertEqual(products_response.status_code, 200)
        product_item = next(entry for entry in products_response.data['results'] if entry['sku'] == 'IMG-BRAND-001')
        self.assertEqual(product_item['brand_name'], brand.name)
        self.assertIn('brand-public', product_item['brand_image'])

    def test_product_search_brand_facets_include_brand_images(self):
        brand = Brand.objects.create(
            name='Facet Brand',
            slug='facet-brand',
            logo=make_test_image('brand-facet.png', width=500, height=500),
            is_active=True,
        )
        Product.objects.create(
            sku='FACET-BRAND-001',
            name='Facet Brand Syrup',
            slug='facet-brand-syrup',
            brand=brand,
            price=Decimal('700.00'),
            is_active=True,
        )

        response = self.client.get(reverse('product-search'), {'q': 'facet'})
        self.assertEqual(response.status_code, 200)
        facet = next(entry for entry in response.data['results']['facets']['brands'] if entry['slug'] == brand.slug)
        self.assertEqual(facet['logo'], facet['image'])
        self.assertEqual(facet['count'], 1)
        self.assertIn('brand-facet', facet['image'])

    def test_product_image_falls_back_to_brand_logo_when_file_is_missing(self):
        brand = Brand.objects.create(
            name='Fallback Brand',
            slug='fallback-brand',
            logo=make_test_image('brand-fallback.png', width=500, height=500),
            is_active=True,
        )
        product = Product.objects.create(
            sku='FALLBACK-001',
            name='Fallback Product',
            slug='fallback-product',
            brand=brand,
            image='products/missing-packshot.jpg',
            price=Decimal('999.00'),
            is_active=True,
        )

        list_response = self.client.get(reverse('products'))
        self.assertEqual(list_response.status_code, 200)
        list_item = next(entry for entry in list_response.data['results'] if entry['sku'] == product.sku)
        self.assertEqual(list_item['image'], list_item['brand_image'])
        self.assertIn('brand-fallback', list_item['image'])

        detail_response = self.client.get(reverse('product-detail-by-id', args=[product.id]))
        self.assertEqual(detail_response.status_code, 200)
        self.assertEqual(detail_response.data['image'], detail_response.data['brand']['logo'])
        self.assertIn('brand-fallback', detail_response.data['image'])

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

    def test_active_promotion_badge_is_exposed_on_product_list(self):
        product = Product.objects.create(
            sku='BADGE-001',
            name='Badge Product',
            price=Decimal('1000.00'),
            is_active=True,
        )
        Promotion.objects.create(
            title='Badge Promotion',
            type=Promotion.TYPE_PERCENTAGE,
            value=Decimal('20'),
            scope=Promotion.SCOPE_PRODUCT,
            targets=[product.sku],
            start_date='2026-03-01',
            end_date='2026-03-31',
            status=Promotion.STATUS_ACTIVE,
        )

        response = self.client.get(reverse('products'))
        self.assertEqual(response.status_code, 200)
        item = next(entry for entry in response.data['results'] if entry['sku'] == product.sku)
        self.assertEqual(item['badge'], '20% Off')

    def test_no_badge_is_exposed_without_active_promotion(self):
        product = Product.objects.create(
            sku='BADGE-002',
            name='Manual Badge Product',
            price=Decimal('1000.00'),
            is_active=True,
        )

        response = self.client.get(reverse('products'))
        self.assertEqual(response.status_code, 200)
        item = next(entry for entry in response.data['results'] if entry['sku'] == product.sku)
        self.assertEqual(item['badge'], '')

    def test_pricing_has_no_discount_without_active_promotion(self):
        product = Product.objects.create(
            sku='DISC-001',
            name='Legacy Discount Product',
            price=Decimal('1000.00'),
            is_active=True,
        )

        response = self.client.get(reverse('products'))
        self.assertEqual(response.status_code, 200)
        item = next(entry for entry in response.data['results'] if entry['sku'] == product.sku)
        self.assertEqual(Decimal(str(item['final_price'])), Decimal('1000.00'))
        self.assertIsNone(item['original_price'])
        self.assertEqual(Decimal(str(item['discount_total'])), Decimal('0.00'))

    def test_featured_products_prioritize_highly_rated_items(self):
        top_rated = Product.objects.create(
            sku='TOP-001',
            name='Top Rated',
            price=Decimal('1500.00'),
            is_active=True,
        )
        best_seller = Product.objects.create(
            sku='TOP-002',
            name='Best Seller',
            price=Decimal('1200.00'),
            is_active=True,
        )
        unrated = Product.objects.create(
            sku='TOP-003',
            name='No Ratings Yet',
            price=Decimal('900.00'),
            is_active=True,
        )

        ProductReview.objects.create(
            product=top_rated,
            user=self.customer,
            rating=5,
            comment='Excellent',
            is_approved=True,
        )

        paid_order = Order.objects.create(
            customer=self.customer,
            status=Order.STATUS_PAID,
            payment_method=Order.PAYMENT_COD,
            payment_status=Order.PAYMENT_STATUS_PAID,
            shipping_first_name='Customer',
            shipping_last_name='User',
            shipping_email='customer@example.com',
            shipping_phone='+254700000000',
            shipping_street='Moi Avenue',
            shipping_city='Nairobi',
            shipping_county='Nairobi',
            subtotal=Decimal('4200.00'),
            total=Decimal('4200.00'),
        )
        OrderItem.objects.create(
            order=paid_order,
            product=best_seller,
            product_name=best_seller.name,
            product_sku=best_seller.sku,
            quantity=8,
            unit_price=best_seller.price,
        )
        OrderItem.objects.create(
            order=paid_order,
            product=top_rated,
            product_name=top_rated.name,
            product_sku=top_rated.sku,
            quantity=2,
            unit_price=top_rated.price,
        )

        response = self.client.get(reverse('featured-products'))
        self.assertEqual(response.status_code, 200)
        skus = [item['sku'] for item in response.data['results']]
        self.assertIn('TOP-001', skus)
        self.assertNotIn('TOP-002', skus)
        self.assertNotIn('TOP-003', skus)

    def test_featured_products_fall_back_to_paid_sales_when_no_highly_rated_items_exist(self):
        top_product = Product.objects.create(
            sku='FALLBACK-001',
            name='Top Seller',
            price=Decimal('1500.00'),
            is_active=True,
        )
        next_product = Product.objects.create(
            sku='FALLBACK-002',
            name='Next Seller',
            price=Decimal('1200.00'),
            is_active=True,
        )
        low_rated_product = Product.objects.create(
            sku='FALLBACK-003',
            name='Low Rated Product',
            price=Decimal('900.00'),
            is_active=True,
        )

        ProductReview.objects.create(
            product=low_rated_product,
            user=self.customer,
            rating=3,
            comment='Average',
            is_approved=True,
        )

        paid_order = Order.objects.create(
            customer=self.customer,
            status=Order.STATUS_PAID,
            payment_method=Order.PAYMENT_COD,
            payment_status=Order.PAYMENT_STATUS_PAID,
            shipping_first_name='Customer',
            shipping_last_name='User',
            shipping_email='customer@example.com',
            shipping_phone='+254700000000',
            shipping_street='Moi Avenue',
            shipping_city='Nairobi',
            shipping_county='Nairobi',
            subtotal=Decimal('4200.00'),
            total=Decimal('4200.00'),
        )
        OrderItem.objects.create(
            order=paid_order,
            product=top_product,
            product_name=top_product.name,
            product_sku=top_product.sku,
            quantity=5,
            unit_price=top_product.price,
        )
        OrderItem.objects.create(
            order=paid_order,
            product=next_product,
            product_name=next_product.name,
            product_sku=next_product.sku,
            quantity=2,
            unit_price=next_product.price,
        )

        draft_order = Order.objects.create(
            customer=self.customer,
            status=Order.STATUS_DRAFT,
            payment_method=Order.PAYMENT_COD,
            payment_status=Order.PAYMENT_STATUS_PENDING,
            shipping_first_name='Customer',
            shipping_last_name='User',
            shipping_email='customer@example.com',
            shipping_phone='+254700000000',
            shipping_street='Moi Avenue',
            shipping_city='Nairobi',
            shipping_county='Nairobi',
            subtotal=Decimal('1800.00'),
            total=Decimal('1800.00'),
        )
        OrderItem.objects.create(
            order=draft_order,
            product=low_rated_product,
            product_name=low_rated_product.name,
            product_sku=low_rated_product.sku,
            quantity=9,
            unit_price=low_rated_product.price,
        )

        response = self.client.get(reverse('featured-products'))
        self.assertEqual(response.status_code, 200)
        skus = [item['sku'] for item in response.data['results']]
        self.assertLess(skus.index('FALLBACK-001'), skus.index('FALLBACK-002'))
        self.assertLess(skus.index('FALLBACK-002'), skus.index('FALLBACK-003'))

    def test_rebuild_pharmacy_taxonomy_maps_products_to_clean_subcategories(self):
        Product.objects.create(
            sku='RX-AB-001',
            name='Amoxicillin 500mg Capsules',
            price=Decimal('100.00'),
            is_active=True,
        )
        Product.objects.create(
            sku='PC-DC-001',
            name='Sensodyne Repair & Protect Toothpaste 75ml',
            price=Decimal('200.00'),
            is_active=True,
        )
        Product.objects.create(
            sku='BM-BS-002',
            name='Sudocrem Antiseptic Healing Cream 125g',
            price=Decimal('300.00'),
            is_active=True,
        )

        call_command('rebuild_pharmacy_taxonomy')

        antibiotics = Category.objects.get(slug='rx-antibiotics')
        oral_care = Category.objects.get(slug='personal-oral-care')
        rash_care = Category.objects.get(slug='family-nappy-rash-care')

        self.assertEqual(Product.objects.get(sku='RX-AB-001').catalog_subcategory, antibiotics)
        self.assertEqual(Product.objects.get(sku='PC-DC-001').catalog_subcategory, oral_care)
        self.assertEqual(Product.objects.get(sku='BM-BS-002').catalog_subcategory, rash_care)
        self.assertEqual(Category.objects.filter(parent__isnull=True).count(), 7)
