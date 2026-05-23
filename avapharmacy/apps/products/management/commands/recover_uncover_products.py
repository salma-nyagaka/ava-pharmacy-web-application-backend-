from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.utils.text import slugify

from apps.products.models import Brand, Category, HealthConcern, Product, Subcategory, Variant, VariantInventory


RECOVERED_PRODUCTS = [
    {
        'sku': 'UNC-SM-001',
        'name': 'Uncover Aloe Vera Sheet Mask Bundle',
        'variant_name': '3 pcs',
        'strength': '3 pcs',
        'price': Decimal('850.00'),
        'cost_price': Decimal('520.00'),
        'stock_qty': 80,
        'subcategory': 'Skin Care',
        'image': 'products/uncover-aloe-vera-sheet-mask-3pcs.jpg',
        'short_description': 'Hydrating aloe vera sheet mask set for calm, refreshed skin.',
        'description': 'Uncover aloe vera sheet masks help hydrate, cool, and soothe skin as part of a weekly skincare routine.',
        'features': ['Aloe vera care', 'Hydrating sheet masks', 'Suitable for routine skincare'],
    },
    {
        'sku': 'UNC-SM-002',
        'name': 'Uncover Vitamin C Sheet Mask Bundle',
        'variant_name': '3 pcs',
        'strength': '3 pcs',
        'price': Decimal('850.00'),
        'cost_price': Decimal('520.00'),
        'stock_qty': 75,
        'subcategory': 'Skin Care',
        'image': 'products/uncover-vitamin-c-sheet-mask-3pcs.webp',
        'short_description': 'Brightening vitamin C sheet mask set for dull-looking skin.',
        'description': 'Uncover vitamin C sheet masks support a brighter-looking, refreshed complexion.',
        'features': ['Vitamin C care', 'Brightening routine support', 'Single-use mask format'],
    },
    {
        'sku': 'UNC-SM-003',
        'name': 'Uncover Green Tea Sheet Mask Bundle',
        'variant_name': '3 pcs',
        'strength': '3 pcs',
        'price': Decimal('850.00'),
        'cost_price': Decimal('520.00'),
        'stock_qty': 75,
        'subcategory': 'Skin Care',
        'image': 'products/uncover-green-tea-sheet-mask-3pcs.webp',
        'short_description': 'Green tea sheet masks for refreshed, balanced-feeling skin.',
        'description': 'Uncover green tea sheet masks are designed for skin that needs a quick calming and refreshing step.',
        'features': ['Green tea care', 'Refreshing sheet mask', 'Good for skincare routines'],
    },
    {
        'sku': 'UNC-SM-010',
        'name': 'Uncover 10 Pack Sheet Mask Bundle',
        'variant_name': '10 pcs',
        'strength': '10 pcs',
        'price': Decimal('2400.00'),
        'cost_price': Decimal('1500.00'),
        'stock_qty': 45,
        'subcategory': 'Skin Care',
        'image': 'products/uncover-10-pack-sheet-mask-bundle.webp',
        'short_description': 'Assorted Uncover sheet mask bundle for a complete mask routine.',
        'description': 'A value bundle of Uncover sheet masks for hydration, brightening, and weekly skincare care.',
        'features': ['Assorted mask bundle', 'Value pack', 'Routine skincare support'],
    },
    {
        'sku': 'UNC-SER-001',
        'name': 'Uncover Licorice Dark Spot Serum',
        'variant_name': 'Serum',
        'strength': '',
        'price': Decimal('2600.00'),
        'cost_price': Decimal('1650.00'),
        'stock_qty': 55,
        'subcategory': 'Skin Care',
        'image': 'products/uncover-licorice-dark-spot-serum.jpg',
        'short_description': 'Licorice serum for uneven tone and dark spot care.',
        'description': 'Uncover licorice dark spot serum supports a more even-looking complexion in a daily skincare routine.',
        'features': ['Dark spot care', 'Licorice extract', 'Daily serum format'],
    },
    {
        'sku': 'UNC-SER-002',
        'name': 'Uncover Green Tea Blemish Serum',
        'variant_name': 'Serum',
        'strength': '',
        'price': Decimal('2500.00'),
        'cost_price': Decimal('1580.00'),
        'stock_qty': 60,
        'subcategory': 'Skin Care',
        'image': 'products/uncover-green-tea-blemish-serum.jpg',
        'short_description': 'Green tea blemish serum for clearer-looking skin.',
        'description': 'Uncover green tea blemish serum is made for oily, combination, and blemish-prone skincare routines.',
        'features': ['Blemish care', 'Green tea extract', 'Light serum texture'],
    },
    {
        'sku': 'UNC-SER-003',
        'name': 'Uncover Baobab Glow-C Serum',
        'variant_name': 'Serum',
        'strength': '',
        'price': Decimal('2800.00'),
        'cost_price': Decimal('1750.00'),
        'stock_qty': 50,
        'subcategory': 'Skin Care',
        'image': 'products/uncover-baobab-glow-c-serum.jpg',
        'short_description': 'Glow serum with baobab and vitamin C routine support.',
        'description': 'Uncover Baobab Glow-C Serum supports radiant-looking skin and antioxidant-focused daily care.',
        'features': ['Glow care', 'Baobab-focused formula', 'Vitamin C routine support'],
    },
    {
        'sku': 'UNC-TON-001',
        'name': 'Uncover Rooibos Glow Toner',
        'variant_name': 'Toner',
        'strength': '',
        'price': Decimal('2200.00'),
        'cost_price': Decimal('1380.00'),
        'stock_qty': 65,
        'subcategory': 'Skin Care',
        'image': 'products/uncover-rooibos-glow-toner.webp',
        'short_description': 'Rooibos toner for refreshed, glow-focused skincare.',
        'description': 'Uncover Rooibos Glow Toner is a daily toner for refreshed skin and glow routine support.',
        'features': ['Rooibos care', 'Daily toner', 'Glow routine support'],
    },
    {
        'sku': 'UNC-MOI-001',
        'name': 'Uncover Argan Moisturiser',
        'variant_name': '30 ml',
        'strength': '30ml',
        'price': Decimal('2200.00'),
        'cost_price': Decimal('1380.00'),
        'stock_qty': 70,
        'subcategory': 'Skin Care',
        'image': 'products/uncover-argan-moisturiser-30ml.png',
        'short_description': 'Argan moisturiser for daily skin hydration.',
        'description': 'Uncover Argan Moisturiser helps keep skin hydrated and comfortable through the day.',
        'features': ['Daily moisturiser', 'Argan care', 'Hydration support'],
    },
    {
        'sku': 'UNC-CLN-001',
        'name': 'Uncover Green Tea Cleanser',
        'variant_name': '30 ml',
        'strength': '30ml',
        'price': Decimal('1800.00'),
        'cost_price': Decimal('1100.00'),
        'stock_qty': 70,
        'subcategory': 'Skin Care',
        'image': 'products/uncover-green-tea-cleanser-30ml.png',
        'short_description': 'Green tea cleanser for a clean, refreshed skin feel.',
        'description': 'Uncover Green Tea Cleanser supports a gentle daily cleanse for oily, combination, and blemish-prone skin.',
        'features': ['Daily cleanser', 'Green tea care', 'Refreshing cleanse'],
    },
    {
        'sku': 'UNC-SUN-001',
        'name': 'Uncover Aloe Invisible Sunscreen',
        'variant_name': '40 ml',
        'strength': '40ml',
        'price': Decimal('2400.00'),
        'cost_price': Decimal('1500.00'),
        'stock_qty': 65,
        'subcategory': 'Sun Protection',
        'image': 'products/uncover-aloe-invisible-sunscreen-40ml.png',
        'short_description': 'Invisible aloe sunscreen for daily sun protection.',
        'description': 'Uncover Aloe Invisible Sunscreen is a lightweight daily sunscreen for face and neck protection.',
        'features': ['Daily sunscreen', 'Invisible finish', 'Aloe care'],
    },
]


class Command(BaseCommand):
    help = 'Recover identifiable Uncover skincare products from local media files.'

    def handle(self, *args, **options):
        admin = get_user_model().objects.filter(role='admin').first()
        brand, _ = Brand.objects.get_or_create(
            name='Uncover',
            defaults={
                'slug': 'uncover',
                'logo': 'brands/brand-fallback.png',
                'description': 'Skincare products for daily cleansing, hydration, brightening, and sun care.',
                'is_active': True,
                'created_by': admin,
            },
        )
        if not brand.logo:
            brand.logo = 'brands/brand-fallback.png'
            brand.save(update_fields=['logo'])

        category = Category.objects.get(slug='personal-care')
        subcategories = {
            sub.name: sub
            for sub in Subcategory.objects.filter(category=category, name__in=['Skin Care', 'Sun Protection'])
        }
        skin_concern = HealthConcern.objects.filter(name='Skin Conditions').first()

        created = 0
        updated = 0
        for item in RECOVERED_PRODUCTS:
            subcategory = subcategories[item['subcategory']]
            product, was_created = Product.objects.update_or_create(
                sku=item['sku'],
                defaults={
                    'name': item['name'],
                    'brand': brand,
                    'image': item['image'],
                    'is_active': True,
                    'created_by': admin,
                },
            )

            variant, _ = Variant.objects.update_or_create(
                product=product,
                sku=item['sku'],
                defaults={
                    'name': item['variant_name'],
                    'strength': item['strength'],
                    'category': category,
                    'subcategory': subcategory,
                    'short_description': item['short_description'],
                    'description': item['description'],
                    'features': item['features'],
                    'price': item['price'],
                    'cost_price': item['cost_price'],
                    'image': item['image'],
                    'requires_prescription': False,
                    'is_active': True,
                },
            )
            if skin_concern:
                variant.health_concerns.set([skin_concern])

            VariantInventory.objects.update_or_create(
                variant=variant,
                location=Product.STOCK_BRANCH,
                defaults={
                    'stock_quantity': item['stock_qty'],
                    'low_stock_threshold': 8,
                    'allow_backorder': False,
                    'max_backorder_quantity': 0,
                },
            )
            VariantInventory.objects.get_or_create(
                variant=variant,
                location=Product.STOCK_WAREHOUSE,
                defaults={
                    'stock_quantity': 0,
                    'low_stock_threshold': 0,
                    'allow_backorder': False,
                    'max_backorder_quantity': 0,
                },
            )

            if was_created:
                created += 1
            else:
                updated += 1

        variant_images = 0
        for variant in Variant.objects.select_related('product').filter(image='').exclude(product__image=''):
            variant.image = variant.product.image.name
            variant.save(update_fields=['image'])
            variant_images += 1

        self.stdout.write(self.style.SUCCESS(
            f'Recovered {created} Uncover products and updated {updated}. '
            f'Backfilled {variant_images} variant images. Total defined: {len(RECOVERED_PRODUCTS)}.'
        ))
        call_command('normalize_product_families')
