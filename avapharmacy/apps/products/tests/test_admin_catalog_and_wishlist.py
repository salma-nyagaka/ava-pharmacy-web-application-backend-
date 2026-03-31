import json
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
from apps.products.models import Brand, Category, Product, Promotion, VariantInventory, VariantReview, Wishlist


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
                'name': 'Panadol 500mg',
                'price': '1000.00',
                'cost_price': '600.00',
                'brand_id': brand.id,
                'description': 'Pain relief tablet',
                'short_description': 'Fast pain relief',
                'image': make_test_image('product.png', width=1200, height=1200),
            },
            format='multipart',
        )
        self.assertEqual(product_response.status_code, 201)
        product = Product.objects.get(name='Panadol')
        variant = product.variants.create(
            sku='PANADOL-500',
            name='Standard',
            price=Decimal('1000.00'),
            cost_price=Decimal('600.00'),
            is_active=True,
        )
        self.assertEqual(product.brand, brand)

        promotion_response = self.client.post(
            reverse('admin-promotions'),
            {
                'title': 'Panadol Weekend Saver',
                'code': 'PANADOL15',
                'description': '15 percent off Panadol',
                'image': make_test_image('promotion.png', width=1400, height=900),
                'type': Promotion.TYPE_PERCENTAGE,
                'value': '15',
                'scope': Promotion.SCOPE_PRODUCT,
                'targets': json.dumps([variant.sku]),
                'minimum_order_amount': '0',
                'start_date': '2026-03-16',
                'end_date': '2026-03-30',
                'status': Promotion.STATUS_ACTIVE,
            },
            format='multipart',
        )
        self.assertEqual(promotion_response.status_code, 201)
        promotion = Promotion.objects.get(code='PANADOL15')
        self.assertEqual(promotion.badge, '15% Off')
        self.assertFalse(promotion.is_stackable)
        self.assertTrue(bool(promotion.image))

    def test_admin_can_create_variant_with_medication_fields(self):
        self.client.force_authenticate(self.admin)
        product = Product.objects.create(
            sku='PARENT-001',
            name='Parent Product',
            slug='parent-product',
            price=Decimal('0.00'),
            is_active=True,
        )

        response = self.client.post(
            reverse('admin-product-variants', kwargs={'product_pk': product.id}),
            {
                'name': '500mg - 20 tablets',
                'sku': 'PARENT-001-500',
                'strength': '500mg',
                'dosage_instructions': 'Take 1 tablet twice daily after meals',
                'directions': 'Swallow with water',
                'warnings': 'Keep out of reach of children',
                'pos_product_id': 'POS-500',
                'price': '250.00',
                'branch_inventory': {'stock_quantity': 12, 'low_stock_threshold': 3},
                'is_active': True,
            },
            format='json',
        )

        self.assertEqual(response.status_code, 201)
        variant = product.variants.get(sku='PARENT-001-500')
        self.assertEqual(variant.strength, '500mg')
        self.assertEqual(variant.dosage_instructions, 'Take 1 tablet twice daily after meals')
        self.assertEqual(variant.directions, 'Swallow with water')
        self.assertEqual(variant.warnings, 'Keep out of reach of children')
        self.assertEqual(variant.pos_product_id, 'POS-500')
        branch_inventory = VariantInventory.objects.get(variant=variant, location=Product.STOCK_BRANCH)
        self.assertEqual(branch_inventory.stock_quantity, 12)

    def test_public_inventory_items_list_returns_sellable_variants(self):
        product = Product.objects.create(
            sku='PARENT-INV-001',
            name='Panadol',
            slug='panadol',
            short_description='Pain relief range',
            is_active=True,
        )
        variant_a = product.variants.create(
            sku='PANADOL-EXTRA',
            name='Panadol Extra',
            price=Decimal('150.00'),
            is_active=True,
        )
        variant_b = product.variants.create(
            sku='PANADOL-FLU',
            name='Panadol Flu Gone',
            price=Decimal('175.00'),
            requires_prescription=True,
            is_active=True,
        )
        VariantInventory.objects.filter(variant=variant_a, location=Product.STOCK_BRANCH).update(stock_quantity=8)
        VariantInventory.objects.filter(variant=variant_b, location=Product.STOCK_BRANCH).update(stock_quantity=4)

        response = self.client.get(reverse('inventory-items'))

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        data = payload.get('data', payload) if isinstance(payload, dict) else payload
        rows = data.get('results', data) if isinstance(data, dict) else data
        names = {row['name']: row for row in rows}
        self.assertIn('Panadol Extra', names)
        self.assertIn('Panadol Flu Gone', names)
        self.assertEqual(names['Panadol Extra']['product_id'], product.id)
        self.assertEqual(names['Panadol Extra']['slug'], product.slug)
        self.assertEqual(names['Panadol Extra']['sku'], 'PANADOL-EXTRA')
        self.assertFalse(names['Panadol Extra']['requires_prescription'])
        self.assertTrue(names['Panadol Flu Gone']['requires_prescription'])

    def test_public_products_list_returns_variant_items(self):
        product = Product.objects.create(
            sku='PARENT-PROD-001',
            name='Panadol',
            slug='panadol-public',
            is_active=True,
        )
        product.variants.create(
            sku='PANADOL-NORMAL',
            name='Panadol Normal',
            price=Decimal('120.00'),
            is_active=True,
        )
        product.variants.create(
            sku='PANADOL-EXTRA-2',
            name='Panadol Extra',
            price=Decimal('150.00'),
            is_active=True,
        )

        response = self.client.get(reverse('products'))

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        data = payload.get('data', payload) if isinstance(payload, dict) else payload
        rows = data.get('results', data) if isinstance(data, dict) else data
        names = {row['name']: row for row in rows}
        self.assertIn('Panadol Normal', names)
        self.assertIn('Panadol Extra', names)
        self.assertEqual(names['Panadol Normal']['product_id'], product.id)
        self.assertEqual(names['Panadol Normal']['product_slug'], product.slug)

    def test_admin_inventory_returns_variant_rows(self):
        self.client.force_authenticate(self.admin)
        product = Product.objects.create(
            sku='PARENT-ADMIN-001',
            name='Panadol',
            slug='panadol-admin',
            is_active=True,
        )
        variant = product.variants.create(
            sku='PANADOL-COLD',
            name='Panadol Cold and Flu',
            price=Decimal('180.00'),
            is_active=True,
        )

        response = self.client.get(reverse('admin-inventory'))

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        data = payload.get('data', payload) if isinstance(payload, dict) else payload
        rows = data.get('results', data) if isinstance(data, dict) else data
        match = next((row for row in rows if row['id'] == variant.id), None)
        self.assertIsNotNone(match)
        self.assertEqual(match['product_id'], product.id)
        self.assertEqual(match['product_name'], product.name)
        self.assertEqual(match['name'], variant.name)

    def test_admin_pos_product_options_include_variant_links(self):
        self.client.force_authenticate(self.admin)
        product = Product.objects.create(
            sku='PARENT-002',
            name='Parent Product 2',
            slug='parent-product-2',
            price=Decimal('0.00'),
            is_active=True,
        )
        product.pos_product_id = 'POS-PARENT'
        product.save(update_fields=['pos_product_id'])
        product.variants.create(
            sku='PARENT-002-250',
            name='250mg - 10 tablets',
            strength='250mg',
            pos_product_id='POS-250',
            price=Decimal('150.00'),
            is_active=True,
        )

        response = self.client.get(reverse('admin-pos-product-options'))
        self.assertEqual(response.status_code, 200)
        items = response.data
        variant_item = next(entry for entry in items if entry['pos_product_id'] == 'POS-250')
        product_item = next(entry for entry in items if entry['pos_product_id'] == 'POS-PARENT')

        self.assertEqual(variant_item['source'], 'variant')
        self.assertEqual(variant_item['variant_name'], '250mg - 10 tablets')
        self.assertEqual(product_item['source'], 'product')

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

    def test_wishlist_item_move_to_cart_requires_variant_selection_when_product_has_variants(self):
        product = Product.objects.create(
            sku='WISH-VAR-001',
            name='Variant Managed Product',
            slug='variant-managed-product',
            price=Decimal('0.00'),
            is_active=True,
        )
        product.variants.create(
            sku='WISH-VAR-001-TAB',
            name='Tablets',
            price=Decimal('120.00'),
            stock_quantity=8,
            is_active=True,
        )
        variant = product.variants.get(sku='WISH-VAR-001-TAB')
        wishlist = Wishlist.objects.create(user=self.customer, variant=variant)

        self.client.force_authenticate(self.customer)
        response = self.client.post(reverse('wishlist-item-move-to-cart', args=[wishlist.id]))

        self.assertEqual(response.status_code, 200)

    def test_admin_inventory_adjust_is_blocked_for_variant_managed_product(self):
        self.client.force_authenticate(self.admin)
        product = Product.objects.create(
            sku='INV-VAR-001',
            name='Variant Managed Inventory Product',
            slug='variant-managed-inventory-product',
            price=Decimal('0.00'),
            is_active=True,
        )
        product.variants.create(
            sku='INV-VAR-001-SYR',
            name='Syrup',
            price=Decimal('300.00'),
            stock_quantity=5,
            is_active=True,
        )

        response = self.client.patch(
            reverse('admin-inventory-adjust', args=[product.id]),
            {'stock_quantity': 10, 'reason': 'Manual adjustment'},
            format='json',
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn('Adjust stock on variants instead', response.data['detail'])

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
        variant = product.variants.create(
            sku='WISH-001-TAB',
            name='Tablets',
            price=Decimal('500.00'),
            is_active=True,
        )
        VariantInventory.objects.update_or_create(
            variant=variant,
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
        wishlist_item = Wishlist.objects.get(user=self.customer, variant=variant)

        move_to_cart_response = self.client.post(
            reverse('wishlist-item-move-to-cart', args=[wishlist_item.id]),
            {'quantity': 2},
            format='json',
        )
        self.assertEqual(move_to_cart_response.status_code, 200)
        cart_item = CartItem.objects.get(cart__user=self.customer, variant=variant)
        self.assertEqual(cart_item.quantity, 2)
        self.assertFalse(Wishlist.objects.filter(user=self.customer, variant=variant).exists())

        move_back_response = self.client.post(
            reverse('cart-item-move-to-wishlist', args=[cart_item.id]),
            {},
            format='json',
        )
        self.assertEqual(move_back_response.status_code, 200)
        self.assertTrue(Wishlist.objects.filter(user=self.customer, variant=variant).exists())
        self.assertFalse(CartItem.objects.filter(pk=cart_item.id).exists())

    def test_duplicate_wishlist_entry_is_rejected(self):
        product = Product.objects.create(
            sku='WISH-002',
            name='Zinc',
            price=Decimal('250.00'),
            is_active=True,
        )
        variant = product.variants.create(
            sku='WISH-002-TAB',
            name='Tablets',
            price=Decimal('250.00'),
            is_active=True,
        )
        self.client.force_authenticate(self.customer)
        self.client.post(reverse('wishlist'), {'product_id': product.id}, format='json')
        response = self.client.post(reverse('wishlist'), {'product_id': product.id}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Wishlist.objects.filter(user=self.customer, variant=variant).count(), 1)

    def test_active_promotion_badge_is_exposed_on_product_list(self):
        product = Product.objects.create(
            sku='BADGE-001',
            name='Badge Product',
            is_active=True,
        )
        variant = product.variants.create(
            sku='BADGE-001-V1',
            name='Standard',
            price=Decimal('1000.00'),
            is_active=True,
        )
        Promotion.objects.create(
            title='Badge Promotion',
            type=Promotion.TYPE_PERCENTAGE,
            value=Decimal('20'),
            scope=Promotion.SCOPE_PRODUCT,
            targets=[variant.sku],
            start_date='2026-03-01',
            end_date='2026-03-31',
            status=Promotion.STATUS_ACTIVE,
        )

        response = self.client.get(reverse('products'))
        self.assertEqual(response.status_code, 200)
        item = next(entry for entry in response.data['results'] if entry['sku'] == variant.sku)
        self.assertEqual(item['badge'], '20% Off')

    def test_no_badge_is_exposed_without_active_promotion(self):
        product = Product.objects.create(
            sku='BADGE-002',
            name='Manual Badge Product',
            is_active=True,
        )
        product.variants.create(
            sku='BADGE-002-V1',
            name='Standard',
            price=Decimal('1000.00'),
            is_active=True,
        )

        response = self.client.get(reverse('products'))
        self.assertEqual(response.status_code, 200)
        item = next(entry for entry in response.data['results'] if entry['sku'] == 'BADGE-002-V1')
        self.assertEqual(item['badge'], '')

    def test_pricing_has_no_discount_without_active_promotion(self):
        product = Product.objects.create(
            sku='DISC-001',
            name='Legacy Discount Product',
            is_active=True,
        )
        product.variants.create(
            sku='DISC-001-V1',
            name='Standard',
            price=Decimal('1000.00'),
            is_active=True,
        )

        response = self.client.get(reverse('products'))
        self.assertEqual(response.status_code, 200)
        item = next(entry for entry in response.data['results'] if entry['sku'] == 'DISC-001-V1')
        self.assertEqual(Decimal(str(item['final_price'])), Decimal('1000.00'))
        self.assertIsNone(item['original_price'])
        self.assertEqual(Decimal(str(item['discount_total'])), Decimal('0.00'))

    def test_product_name_is_normalized_to_generic_parent_name(self):
        product = Product.objects.create(
            sku='GENERIC-001',
            name='Panadol 500mg Tablets 20s',
            is_active=True,
        )

        self.assertEqual(product.name, 'Panadol')

    def test_featured_products_prioritize_highly_rated_items(self):
        top_rated = Product.objects.create(
            sku='TOP-001',
            name='Top Rated',
            price=Decimal('1500.00'),
            is_active=True,
        )
        top_rated_variant = top_rated.variants.create(
            sku='TOP-001-V1',
            name='Standard',
            price=Decimal('1500.00'),
            is_active=True,
        )
        best_seller = Product.objects.create(
            sku='TOP-002',
            name='Best Seller',
            price=Decimal('1200.00'),
            is_active=True,
        )
        best_seller_variant = best_seller.variants.create(
            sku='TOP-002-V1',
            name='Standard',
            price=Decimal('1200.00'),
            is_active=True,
        )
        unrated = Product.objects.create(
            sku='TOP-003',
            name='No Ratings Yet',
            price=Decimal('900.00'),
            is_active=True,
        )
        unrated.variants.create(
            sku='TOP-003-V1',
            name='Standard',
            price=Decimal('900.00'),
            is_active=True,
        )

        VariantReview.objects.create(
            variant=top_rated_variant,
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
            variant=best_seller_variant,
            product_name=best_seller.name,
            product_sku=best_seller.sku,
            variant_name=best_seller_variant.name,
            variant_sku=best_seller_variant.sku,
            quantity=8,
            unit_price=best_seller_variant.price,
        )
        OrderItem.objects.create(
            order=paid_order,
            variant=top_rated_variant,
            product_name=top_rated.name,
            product_sku=top_rated.sku,
            variant_name=top_rated_variant.name,
            variant_sku=top_rated_variant.sku,
            quantity=2,
            unit_price=top_rated_variant.price,
        )

        response = self.client.get(reverse('featured-products'))
        self.assertEqual(response.status_code, 200)
        skus = [item['sku'] for item in response.data['results']]
        self.assertEqual(skus[0], 'TOP-001-V1')

    def test_featured_products_fall_back_to_paid_sales_when_no_highly_rated_items_exist(self):
        top_product = Product.objects.create(
            sku='FALLBACK-001',
            name='Top Seller',
            price=Decimal('1500.00'),
            is_active=True,
        )
        top_variant = top_product.variants.create(
            sku='FALLBACK-001-V1',
            name='Standard',
            price=Decimal('1500.00'),
            is_active=True,
        )
        next_product = Product.objects.create(
            sku='FALLBACK-002',
            name='Next Seller',
            price=Decimal('1200.00'),
            is_active=True,
        )
        next_variant = next_product.variants.create(
            sku='FALLBACK-002-V1',
            name='Standard',
            price=Decimal('1200.00'),
            is_active=True,
        )
        low_rated_product = Product.objects.create(
            sku='FALLBACK-003',
            name='Low Rated Product',
            price=Decimal('900.00'),
            is_active=True,
        )
        low_rated_variant = low_rated_product.variants.create(
            sku='FALLBACK-003-V1',
            name='Standard',
            price=Decimal('900.00'),
            is_active=True,
        )

        VariantReview.objects.create(
            variant=low_rated_variant,
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
            variant=top_variant,
            product_name=top_product.name,
            product_sku=top_product.sku,
            variant_name=top_variant.name,
            variant_sku=top_variant.sku,
            quantity=5,
            unit_price=top_variant.price,
        )
        OrderItem.objects.create(
            order=paid_order,
            variant=next_variant,
            product_name=next_product.name,
            product_sku=next_product.sku,
            variant_name=next_variant.name,
            variant_sku=next_variant.sku,
            quantity=2,
            unit_price=next_variant.price,
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
            variant=low_rated_variant,
            product_name=low_rated_product.name,
            product_sku=low_rated_product.sku,
            variant_name=low_rated_variant.name,
            variant_sku=low_rated_variant.sku,
            quantity=9,
            unit_price=low_rated_variant.price,
        )

        response = self.client.get(reverse('featured-products'))
        self.assertEqual(response.status_code, 200)
        skus = [item['sku'] for item in response.data['results']]
        self.assertLess(skus.index('FALLBACK-001-V1'), skus.index('FALLBACK-002-V1'))
        self.assertLess(skus.index('FALLBACK-002-V1'), skus.index('FALLBACK-003-V1'))

    def test_featured_products_exclude_prescription_products(self):
        otc_product = Product.objects.create(
            sku='OTC-001',
            name='Everyday Vitamin',
            price=Decimal('800.00'),
            is_active=True,
        )
        otc_variant = otc_product.variants.create(
            sku='OTC-001-V1',
            name='Standard',
            price=Decimal('800.00'),
            requires_prescription=False,
            is_active=True,
        )
        prescription_product = Product.objects.create(
            sku='RX-001',
            name='Prescription Antibiotic',
            price=Decimal('1500.00'),
            is_active=True,
        )
        prescription_variant = prescription_product.variants.create(
            sku='RX-001-V1',
            name='Standard',
            price=Decimal('1500.00'),
            requires_prescription=True,
            is_active=True,
        )

        VariantReview.objects.create(
            variant=otc_variant,
            user=self.customer,
            rating=5,
            comment='Excellent',
            is_approved=True,
        )
        VariantReview.objects.create(
            variant=prescription_variant,
            user=self.admin,
            rating=5,
            comment='Excellent',
            is_approved=True,
        )

        response = self.client.get(reverse('featured-products'))
        self.assertEqual(response.status_code, 200)
        skus = [item['sku'] for item in response.data['results']]
        self.assertIn('OTC-001-V1', skus)
        self.assertNotIn('RX-001-V1', skus)

    def test_customer_can_create_and_update_review_for_delivered_product(self):
        product = Product.objects.create(
            sku='REVIEW-001',
            name='Reviewable Product',
            price=Decimal('500.00'),
            is_active=True,
        )
        variant = product.variants.create(
            sku='REVIEW-001-V1',
            name='Standard',
            price=Decimal('500.00'),
            is_active=True,
        )
        delivered_order = Order.objects.create(
            customer=self.customer,
            status=Order.STATUS_DELIVERED,
            payment_method=Order.PAYMENT_COD,
            payment_status=Order.PAYMENT_STATUS_PAID,
            shipping_first_name='Customer',
            shipping_last_name='User',
            shipping_email='customer@example.com',
            shipping_phone='+254700000000',
            shipping_street='Moi Avenue',
            shipping_city='Nairobi',
            shipping_county='Nairobi',
            subtotal=Decimal('500.00'),
            total=Decimal('500.00'),
        )
        OrderItem.objects.create(
            order=delivered_order,
            variant=variant,
            product_name=product.name,
            product_sku=product.sku,
            variant_name=variant.name,
            variant_sku=variant.sku,
            quantity=1,
            unit_price=variant.price,
        )

        self.client.force_authenticate(self.customer)
        create_response = self.client.post(
            reverse('product-reviews', args=[product.id]),
            {'rating': 5, 'comment': 'Worked very well.'},
            format='json',
        )
        self.assertEqual(create_response.status_code, 201)
        self.assertEqual(VariantReview.objects.filter(variant=variant, user=self.customer).count(), 1)
        self.assertTrue(create_response.data['is_verified_purchase'])

        update_response = self.client.post(
            reverse('product-reviews', args=[product.id]),
            {'rating': 4, 'comment': 'Updating my rating after a week.'},
            format='json',
        )
        self.assertEqual(update_response.status_code, 200)
        review = VariantReview.objects.get(variant=variant, user=self.customer)
        self.assertEqual(review.rating, 4)
        self.assertEqual(review.comment, 'Updating my rating after a week.')

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
