import json
import io
from datetime import timedelta
from decimal import Decimal

from django.core.management import call_command
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from PIL import Image
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.orders.models import Cart, CartItem, Order, OrderItem
from apps.products.models import Banner, Brand, Category, Product, Promotion, Subcategory, VariantInventory, VariantReview, Wishlist


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
            reverse('admin-categories'),
            {
                'name': 'Pain Relief',
                'description': 'Pain relief essentials',
                'image': make_test_image('category.png', width=900, height=900),
            },
            format='multipart',
        )
        self.assertEqual(category_response.status_code, 201)
        product_category = Category.objects.get(name='Pain Relief')
        self.assertTrue(product_category.slug)

        subcategory_response = self.client.post(
            reverse('admin-sub-categories'),
            {
                'name': 'Tablets',
                'category': product_category.id,
                'description': 'Pain relief tablets',
            },
            format='json',
        )
        self.assertEqual(subcategory_response.status_code, 201)
        subcategory = Subcategory.objects.get(name='Tablets', category=product_category)
        self.assertEqual(subcategory.category, product_category)

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
                'sku': 'ADMIN-KEYED-SKU',
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
        self.assertNotIn('sku', product_response.data)
        self.assertNotIn('cost_price', product_response.data)
        product = Product.objects.get(name='Panadol')
        self.assertTrue(product.sku.startswith('PRD-PANADOL'))
        self.assertNotEqual(product.sku, 'ADMIN-KEYED-SKU')
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

    def test_admin_can_create_multiple_banners_and_public_feed_returns_all_active_banners(self):
        self.client.force_authenticate(self.admin)

        banners = [
            {
                'title': 'Banner 1',
                'message': 'Free delivery on orders above KSh 3,000!',
                'link': 'https://example.com/products',
                'placement': 'home_hero',
                'sort_order': 1,
                'status': 'active',
            },
            {
                'title': 'Banner 2',
                'message': 'Get 15% off your first prescription.',
                'link': 'https://example.com/prescriptions',
                'placement': 'home_hero',
                'sort_order': 2,
                'status': 'active',
            },
            {
                'title': 'Banner 3',
                'message': 'Teleconsultation available 24/7.',
                'link': 'https://example.com/doctor-consultation',
                'placement': 'home_hero',
                'sort_order': 3,
                'status': 'active',
            },
        ]

        for payload in banners:
            response = self.client.post(reverse('admin-banners'), payload, format='json')
            self.assertEqual(response.status_code, 201)

        response = self.client.get(reverse('banners'), {'placement': 'home_hero'})
        self.assertEqual(response.status_code, 200)
        banners_data = response.data.get('results', response.data)
        self.assertGreaterEqual(len(banners_data), 3)
        self.assertEqual([banner['sort_order'] for banner in banners_data[:3]], [1, 2, 3])
        self.assertEqual([banner['title'] for banner in banners_data[:3]], ['Banner 1', 'Banner 2', 'Banner 3'])
        self.assertTrue(
            Banner.objects.filter(
                status='active',
                placement='home_hero',
                title__in=['Banner 1', 'Banner 2', 'Banner 3'],
            ).count() >= 3
        )

    @override_settings(POS_LINK_STRATEGY='barcode')
    def test_admin_product_barcode_is_not_part_of_product_form(self):
        self.client.force_authenticate(self.admin)

        meta_response = self.client.get(reverse('admin-product-form-meta'))
        self.assertEqual(meta_response.status_code, 200)
        self.assertFalse(meta_response.data['accepts_sku'])
        self.assertFalse(meta_response.data['requires_barcode'])
        self.assertFalse(meta_response.data['accepts_barcode'])

        response = self.client.post(
            reverse('admin-products'),
            {
                'name': 'No Product Barcode Product',
                'price': '500.00',
                'cost_price': '250.00',
                'description': 'Created without product barcode',
                'short_description': 'No product barcode',
            },
            format='multipart',
        )

        self.assertEqual(response.status_code, 201)
        self.assertNotIn('barcode', response.data)
        product = Product.objects.get(name='No Product Barcode Product')
        self.assertEqual(product.barcode, '')
        self.assertTrue(product.sku.startswith('PRD-NOPRODUCTBARCODEPRODUCT'))

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

    def test_admin_can_create_variant_without_sku(self):
        self.client.force_authenticate(self.admin)
        product = Product.objects.create(
            sku='AUTO-SKU-PARENT',
            name='Auto SKU Parent',
            slug='auto-sku-parent',
            is_active=True,
        )

        response = self.client.post(
            reverse('admin-product-variants', kwargs={'product_pk': product.id}),
            {
                'name': 'Tablets',
                'price': '150.00',
                'branch_inventory': {'stock_quantity': 6, 'low_stock_threshold': 2},
                'is_active': True,
            },
            format='json',
        )

        self.assertEqual(response.status_code, 201)
        variant = product.variants.get(name='Tablets')
        self.assertEqual(response.data['sku'], variant.sku)
        self.assertTrue(variant.sku.startswith('AUTO-SKU-PARENT-TABLETS'))
        self.assertEqual(variant.inventories.get(location=Product.STOCK_BRANCH).stock_quantity, 6)

    def test_admin_variant_create_saves_opening_stock_fields(self):
        self.client.force_authenticate(self.admin)
        product = Product.objects.create(
            sku='OPENING-STOCK-PARENT',
            name='Opening Stock Parent',
            slug='opening-stock-parent',
            is_active=True,
        )

        response = self.client.post(
            reverse('admin-product-variants', kwargs={'product_pk': product.id}),
            {
                'name': 'Capsules',
                'price': '250.00',
                'stock_quantity': '17',
                'low_stock_threshold': '4',
                'is_active': 'true',
            },
            format='multipart',
        )

        self.assertEqual(response.status_code, 201)
        variant = product.variants.get(name='Capsules')
        branch_inventory = variant.inventories.get(location=Product.STOCK_BRANCH)
        self.assertEqual(branch_inventory.stock_quantity, 17)
        self.assertEqual(branch_inventory.low_stock_threshold, 4)
        self.assertEqual(response.data['stock_quantity'], 17)
        self.assertEqual(response.data['low_stock_threshold'], 4)

    def test_admin_cannot_delete_product(self):
        self.client.force_authenticate(self.admin)
        product = Product.objects.create(
            sku='NO-DELETE-001',
            name='Do Not Delete',
            slug='do-not-delete',
            is_active=True,
        )

        response = self.client.delete(reverse('admin-product-detail', kwargs={'pk': product.id}))

        self.assertEqual(response.status_code, 405)
        self.assertTrue(Product.objects.filter(pk=product.id).exists())

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
        VariantInventory.objects.update_or_create(
            variant=variant_a,
            location=Product.STOCK_BRANCH,
            defaults={'stock_quantity': 8, 'low_stock_threshold': 2},
        )
        VariantInventory.objects.update_or_create(
            variant=variant_b,
            location=Product.STOCK_BRANCH,
            defaults={'stock_quantity': 4, 'low_stock_threshold': 2},
        )

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

    def test_public_product_detail_by_id_accepts_variant_id(self):
        product = Product.objects.create(
            sku='PARENT-DETAIL-001',
            name='Detail Parent',
            slug='detail-parent',
            is_active=True,
        )
        variant = product.variants.create(
            sku='DETAIL-VARIANT-001',
            name='Detail Variant',
            price=Decimal('120.00'),
            is_active=True,
        )

        response = self.client.get(reverse('product-detail-by-id', kwargs={'pk': variant.id}))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['id'], product.id)
        self.assertTrue(any(item['id'] == variant.id for item in response.data['variants']))

    def test_public_products_available_filter_returns_latest_stocked_variants(self):
        product = Product.objects.create(
            sku='PARENT-STOCKED-001',
            name='Stocked Parent',
            slug='stocked-parent',
            is_active=True,
        )
        base_time = timezone.now()
        stocked_variants = []
        for index in range(6):
            variant = product.variants.create(
                sku=f'STOCKED-{index}',
                name=f'Stocked {index}',
                price=Decimal('100.00'),
                is_active=True,
            )
            VariantInventory.objects.create(
                variant=variant,
                location=Product.STOCK_BRANCH,
                stock_quantity=index + 1,
                low_stock_threshold=5,
            )
            product.variants.filter(pk=variant.pk).update(created_at=base_time + timedelta(minutes=index))
            variant.refresh_from_db()
            stocked_variants.append(variant)

        no_stock_variant = product.variants.create(
            sku='NO-STOCK-LATEST',
            name='No Stock Latest',
            price=Decimal('100.00'),
            is_active=True,
        )
        VariantInventory.objects.create(
            variant=no_stock_variant,
            location=Product.STOCK_BRANCH,
            stock_quantity=0,
            low_stock_threshold=5,
        )
        product.variants.filter(pk=no_stock_variant.pk).update(created_at=base_time + timedelta(minutes=10))

        response = self.client.get(reverse('products'), {
            'inventory_status': 'available',
            'ordering': '-created_at',
            'page_size': 5,
        })

        self.assertEqual(response.status_code, 200)
        skus = [item['sku'] for item in response.data['results']]
        self.assertEqual(skus, [variant.sku for variant in reversed(stocked_variants[1:])])
        self.assertNotIn(no_stock_variant.sku, skus)
        self.assertEqual(len(skus), 5)

    def test_public_catalog_hides_products_from_inactive_brands(self):
        active_brand = Brand.objects.create(
            name='Visible Brand',
            slug='visible-brand',
            is_active=True,
        )
        inactive_brand = Brand.objects.create(
            name='Hidden Brand',
            slug='hidden-brand',
            is_active=False,
        )
        visible_product = Product.objects.create(
            sku='VISIBLE-PARENT',
            name='Visible Product',
            slug='visible-product',
            brand=active_brand,
            is_active=True,
        )
        visible_variant = visible_product.variants.create(
            sku='VISIBLE-V1',
            name='Visible Variant',
            price=Decimal('120.00'),
            is_active=True,
        )
        hidden_product = Product.objects.create(
            sku='HIDDEN-PARENT',
            name='Hidden Product',
            slug='hidden-product',
            brand=inactive_brand,
            is_active=True,
        )
        hidden_variant = hidden_product.variants.create(
            sku='HIDDEN-V1',
            name='Hidden Variant',
            price=Decimal('150.00'),
            is_active=True,
        )

        brands_response = self.client.get(reverse('brands'))
        self.assertEqual(brands_response.status_code, 200)
        brand_rows = brands_response.data.get('results', brands_response.data)
        brand_slugs = {brand['slug'] for brand in brand_rows}
        self.assertIn(active_brand.slug, brand_slugs)
        self.assertNotIn(inactive_brand.slug, brand_slugs)

        products_response = self.client.get(reverse('products'))
        self.assertEqual(products_response.status_code, 200)
        product_skus = {item['sku'] for item in products_response.data['results']}
        self.assertIn(visible_variant.sku, product_skus)
        self.assertNotIn('HIDDEN-V1', product_skus)

        inactive_brand_response = self.client.get(reverse('products'), {'brand': inactive_brand.slug})
        self.assertEqual(inactive_brand_response.status_code, 200)
        self.assertEqual(inactive_brand_response.data['results'], [])

        inventory_response = self.client.get(reverse('inventory-items'))
        self.assertEqual(inventory_response.status_code, 200)
        inventory_skus = {item['sku'] for item in inventory_response.data['results']}
        self.assertIn(visible_variant.sku, inventory_skus)
        self.assertNotIn('HIDDEN-V1', inventory_skus)

        featured_response = self.client.get(reverse('featured-products'))
        self.assertEqual(featured_response.status_code, 200)
        featured_skus = {item['sku'] for item in featured_response.data['results']}
        self.assertIn(visible_variant.sku, featured_skus)
        self.assertNotIn('HIDDEN-V1', featured_skus)

        search_response = self.client.get(reverse('product-search'), {'q': 'Hidden'})
        self.assertEqual(search_response.status_code, 200)
        search_payload = search_response.data.get('results', search_response.data)
        search_skus = {item['sku'] for item in search_payload['products']}
        self.assertNotIn('HIDDEN-V1', search_skus)

        suggestions_response = self.client.get(reverse('product-suggestions'), {'q': 'Hidden'})
        self.assertEqual(suggestions_response.status_code, 200)
        self.assertEqual(suggestions_response.data['suggestions'], [])

        detail_response = self.client.get(reverse('product-detail', kwargs={'slug': hidden_product.slug}))
        self.assertEqual(detail_response.status_code, 404)

        detail_by_id_response = self.client.get(reverse('product-detail-by-id', kwargs={'pk': hidden_product.id}))
        self.assertEqual(detail_by_id_response.status_code, 404)

        self.client.force_authenticate(self.customer)
        wishlist_response = self.client.post(reverse('wishlist'), {'variant_id': hidden_variant.id}, format='json')
        self.assertEqual(wishlist_response.status_code, 404)

    def test_public_catalog_hides_deactivated_products(self):
        active_product = Product.objects.create(
            sku='ACTIVE-PARENT',
            name='Active Product',
            slug='active-product',
            is_active=True,
        )
        active_variant = active_product.variants.create(
            sku='ACTIVE-V1',
            name='Active Variant',
            price=Decimal('120.00'),
            is_active=True,
        )
        inactive_product = Product.objects.create(
            sku='INACTIVE-PARENT',
            name='Inactive Product',
            slug='inactive-product',
            is_active=False,
        )
        inactive_variant = inactive_product.variants.create(
            sku='INACTIVE-V1',
            name='Inactive Variant',
            price=Decimal('150.00'),
            is_active=True,
        )

        products_response = self.client.get(reverse('products'))
        self.assertEqual(products_response.status_code, 200)
        product_skus = {item['sku'] for item in products_response.data['results']}
        self.assertIn(active_variant.sku, product_skus)
        self.assertNotIn(inactive_variant.sku, product_skus)

        inventory_response = self.client.get(reverse('inventory-items'))
        self.assertEqual(inventory_response.status_code, 200)
        inventory_skus = {item['sku'] for item in inventory_response.data['results']}
        self.assertIn(active_variant.sku, inventory_skus)
        self.assertNotIn(inactive_variant.sku, inventory_skus)

        featured_response = self.client.get(reverse('featured-products'))
        self.assertEqual(featured_response.status_code, 200)
        featured_skus = {item['sku'] for item in featured_response.data['results']}
        self.assertIn(active_variant.sku, featured_skus)
        self.assertNotIn(inactive_variant.sku, featured_skus)

        search_response = self.client.get(reverse('product-search'), {'q': 'Inactive'})
        self.assertEqual(search_response.status_code, 200)
        search_payload = search_response.data.get('results', search_response.data)
        search_skus = {item['sku'] for item in search_payload['products']}
        self.assertNotIn(inactive_variant.sku, search_skus)

        suggestions_response = self.client.get(reverse('product-suggestions'), {'q': 'Inactive'})
        self.assertEqual(suggestions_response.status_code, 200)
        self.assertEqual(suggestions_response.data['suggestions'], [])

        detail_response = self.client.get(reverse('product-detail', kwargs={'slug': inactive_product.slug}))
        self.assertEqual(detail_response.status_code, 404)

        detail_by_id_response = self.client.get(reverse('product-detail-by-id', kwargs={'pk': inactive_product.id}))
        self.assertEqual(detail_by_id_response.status_code, 404)

        availability_response = self.client.get(reverse('product-availability'), {'product_ids': f'{active_product.id},{inactive_product.id}'})
        self.assertEqual(availability_response.status_code, 200)
        availability_ids = {item['product_id'] for item in availability_response.data['availability']}
        self.assertIn(active_product.id, availability_ids)
        self.assertNotIn(inactive_product.id, availability_ids)

        availability_detail_response = self.client.get(reverse('product-availability-detail', kwargs={'pk': inactive_product.id}))
        self.assertEqual(availability_detail_response.status_code, 404)

        self.client.force_authenticate(self.customer)
        wishlist_response = self.client.post(reverse('wishlist'), {'variant_id': inactive_variant.id}, format='json')
        self.assertEqual(wishlist_response.status_code, 404)

        stale_wishlist = Wishlist.objects.create(user=self.customer, variant=inactive_variant)
        move_to_cart_response = self.client.post(reverse('wishlist-item-move-to-cart', args=[stale_wishlist.id]))
        self.assertEqual(move_to_cart_response.status_code, 400)

        cart, _ = Cart.objects.get_or_create(user=self.customer)
        stale_cart_item = CartItem.objects.create(cart=cart, variant=inactive_variant, quantity=1)
        move_to_wishlist_response = self.client.post(reverse('cart-item-move-to-wishlist', args=[stale_cart_item.id]))
        self.assertEqual(move_to_wishlist_response.status_code, 404)

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
        self.assertEqual(match['inventories'], [])
        self.assertIsNone(match['stock_quantity'])
        self.assertIsNone(match['low_stock_threshold'])
        self.assertIsNone(match['inventory_status'])

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

    def test_public_brand_response_omits_missing_logo_url(self):
        brand = Brand.objects.create(
            name='Missing Logo Brand',
            slug='missing-logo-brand',
            logo='brands/missing-logo.png',
            is_active=True,
        )

        response = self.client.get(reverse('brands'))

        self.assertEqual(response.status_code, 200)
        brand_item = next(entry for entry in response.data['results'] if entry['slug'] == brand.slug)
        self.assertIsNone(brand_item['logo'])
        self.assertIsNone(brand_item['image'])

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
        today = timezone.now().date()
        Promotion.objects.create(
            title='Badge Promotion',
            type=Promotion.TYPE_PERCENTAGE,
            value=Decimal('20'),
            scope=Promotion.SCOPE_PRODUCT,
            targets=[variant.sku],
            start_date=today,
            end_date=today,
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

        antibiotics = Subcategory.objects.get(slug='rx-antibiotics')
        oral_care = Subcategory.objects.get(slug='personal-oral-care')
        rash_care = Subcategory.objects.get(slug='family-nappy-rash-care')

        self.assertEqual(Product.objects.get(sku='RX-AB-001').subcategory, antibiotics)
        self.assertEqual(Product.objects.get(sku='PC-DC-001').subcategory, oral_care)
        self.assertEqual(Product.objects.get(sku='BM-BS-002').subcategory, rash_care)
        self.assertEqual(Category.objects.count(), 7)
