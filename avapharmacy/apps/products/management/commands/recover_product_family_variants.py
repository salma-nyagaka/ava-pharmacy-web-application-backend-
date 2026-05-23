from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from apps.products.models import Product, Variant, VariantInventory


PANADOL_VARIANTS = [
    {
        'sku': 'OTC-PR-001',
        'name': 'Panadol Extra Pain Reliever Tablets',
        'strength': '500mg/65mg',
        'price': Decimal('150.00'),
        'cost_price': Decimal('90.00'),
        'stock_qty': 180,
        'image': 'products/panadol-extra-tablets-500mg65mg.jpg',
        'short_description': 'Panadol Extra tablets for pain and fever relief.',
        'description': 'A Panadol pain relief variant with paracetamol and caffeine for headache, fever, and body pain relief.',
        'features': ['Pain relief', 'Fever relief', 'Tablet format'],
    },
    {
        'sku': 'OTC-PAN-FLU-001',
        'name': 'Panadol Flu',
        'strength': '',
        'price': Decimal('250.00'),
        'cost_price': Decimal('155.00'),
        'stock_qty': 90,
        'image': 'products/panadol-extra-tablets-500mg65mg.jpg',
        'short_description': 'Panadol family variant for cold and flu symptom relief.',
        'description': 'Panadol Flu is represented as a variant under the Panadol product family for catalog grouping.',
        'features': ['Cold and flu care', 'Panadol family variant', 'OTC medicine'],
    },
    {
        'sku': 'OTC-PAN-COUGH-001',
        'name': 'Panadol Cough Syrup',
        'strength': '100ml',
        'price': Decimal('350.00'),
        'cost_price': Decimal('220.00'),
        'stock_qty': 70,
        'image': 'products/panadol-extra-tablets-500mg65mg.jpg',
        'short_description': 'Panadol family cough syrup variant.',
        'description': 'Panadol Cough Syrup is represented as a syrup variant under the Panadol product family.',
        'features': ['Cough care', 'Syrup format', 'Panadol family variant'],
    },
    {
        'sku': 'OTC-PAN-PAIN-001',
        'name': 'Panadol Pain Reliever',
        'strength': '500mg',
        'price': Decimal('120.00'),
        'cost_price': Decimal('75.00'),
        'stock_qty': 160,
        'image': 'products/panadol-extra-tablets-500mg65mg.jpg',
        'short_description': 'Core Panadol pain reliever variant.',
        'description': 'Panadol Pain Reliever is grouped under the Panadol parent product as a sellable variant.',
        'features': ['Pain relief', 'Fever relief', 'Panadol family variant'],
    },
]


class Command(BaseCommand):
    help = 'Recover product-family variants such as Panadol -> Panadol Flu, syrup, pain reliever.'

    def handle(self, *args, **options):
        admin = get_user_model().objects.filter(role='admin').first()
        product = Product.objects.filter(name__iexact='Panadol').first()
        if not product:
            self.stdout.write(self.style.ERROR('Panadol product was not found. Run seed_catalog first.'))
            return

        lead = product.get_representative_variant()
        category = lead.category if lead else None
        subcategory = lead.subcategory if lead else None
        health_concerns = list(lead.health_concerns.all()) if lead else []

        created = 0
        updated = 0
        for index, item in enumerate(PANADOL_VARIANTS):
            variant, was_created = Variant.objects.update_or_create(
                sku=item['sku'],
                defaults={
                    'product': product,
                    'name': item['name'],
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
                    'sort_order': index,
                },
            )
            if health_concerns:
                variant.health_concerns.set(health_concerns)

            VariantInventory.objects.update_or_create(
                variant=variant,
                location=Product.STOCK_BRANCH,
                defaults={
                    'stock_quantity': item['stock_qty'],
                    'low_stock_threshold': 10,
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
            created += int(was_created)
            updated += int(not was_created)

        product.created_by = product.created_by or admin
        product.save(update_fields=['created_by'] if product.created_by_id else None)
        self.stdout.write(self.style.SUCCESS(
            f'Panadol product family recovered: {created} variants created, {updated} variants updated.'
        ))
