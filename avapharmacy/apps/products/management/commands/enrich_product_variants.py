from decimal import Decimal

from django.core.management.base import BaseCommand

from apps.products.models import Product, Variant, VariantInventory


VARIANT_ENRICHMENTS = {
    'Panadol': [
        ('OTC-PAN-CHILD-001', 'Panadol Children Suspension', '100ml', '420.00', '260.00', 85),
        ('OTC-PAN-NIGHT-001', 'Panadol Night Tablets', '20s', '390.00', '240.00', 70),
        ('OTC-PAN-ACTIFAST-001', 'Panadol Actifast Tablets', '500mg', '320.00', '195.00', 90),
    ],
    'Amoxicillin': [
        ('RX-AMOX-250-SUSP', 'Amoxicillin 250mg/5ml Suspension', '250mg/5ml', '520.00', '330.00', 65),
        ('RX-AMOX-125-SUSP', 'Amoxicillin 125mg/5ml Suspension', '125mg/5ml', '460.00', '290.00', 60),
    ],
    'Co-Amoxiclav': [
        ('RX-COAMOX-457-SUSP', 'Co-Amoxiclav 457mg/5ml Suspension', '457mg/5ml', '2100.00', '1350.00', 40),
        ('RX-COAMOX-1G-TABS', 'Co-Amoxiclav 1g Tablets', '875mg/125mg', '2600.00', '1680.00', 45),
    ],
    'Cetirizine': [
        ('OTC-CET-SYR-001', 'Cetirizine Syrup', '5mg/5ml', '260.00', '160.00', 90),
        ('OTC-CET-30S-001', 'Cetirizine 10mg Tablets 30s', '10mg', '360.00', '220.00', 100),
    ],
    'Ibuprofen': [
        ('OTC-IBU-SUSP-001', 'Ibuprofen Paediatric Suspension', '100mg/5ml', '390.00', '240.00', 70),
        ('OTC-IBU-200-001', 'Ibuprofen 200mg Tablets', '200mg', '140.00', '85.00', 130),
    ],
    'Omeprazole': [
        ('OTC-OME-40-001', 'Omeprazole 40mg Capsules', '40mg', '650.00', '410.00', 75),
        ('OTC-OME-20-28-001', 'Omeprazole 20mg Capsules 28s', '20mg', '920.00', '590.00', 60),
    ],
    'Vitamin C': [
        ('VIT-VC-500-001', 'Vitamin C 500mg Tablets 30s', '500mg', '350.00', '210.00', 95),
        ('VIT-VC-KIDS-001', 'Vitamin C Kids Gummies', '60s', '890.00', '560.00', 55),
    ],
    'Complete Multivitamins Adults': [
        ('VIT-MV-WOMEN-001', 'Complete Multivitamins Women 30s', '30s', '760.00', '480.00', 70),
        ('VIT-MV-MEN-001', 'Complete Multivitamins Men 30s', '30s', '760.00', '480.00', 70),
        ('VIT-MV-KIDS-001', 'Complete Multivitamins Kids Syrup', '100ml', '580.00', '360.00', 65),
    ],
    'Omega-3 Fish Oil': [
        ('VIT-OM-60-001', 'Omega-3 Fish Oil 1000mg Softgels 60s', '1000mg', '1180.00', '760.00', 55),
        ('VIT-OM-1200-001', 'Omega-3 Fish Oil 1200mg Softgels 30s', '1200mg', '820.00', '520.00', 60),
    ],
    'Cetaphil': [
        ('PC-CET-MOIST-001', 'Cetaphil Moisturising Lotion 236ml', '236ml', '1850.00', '1180.00', 50),
        ('PC-CET-CREAM-001', 'Cetaphil Moisturising Cream 250g', '250g', '2100.00', '1360.00', 45),
        ('PC-CET-OILY-001', 'Cetaphil Oily Skin Cleanser 236ml', '236ml', '1950.00', '1260.00', 45),
    ],
    'Sensodyne': [
        ('PC-SEN-FRESH-001', 'Sensodyne Fresh Mint Toothpaste 75ml', '75ml', '620.00', '390.00', 80),
        ('PC-SEN-WHITE-001', 'Sensodyne Gentle Whitening Toothpaste 75ml', '75ml', '720.00', '460.00', 70),
    ],
    'Dettol': [
        ('OTC-DET-500-001', 'Dettol Antiseptic Liquid 500ml', '500ml', '580.00', '360.00', 85),
        ('OTC-DET-HW-001', 'Dettol Handwash Original 200ml', '200ml', '280.00', '170.00', 110),
    ],
    "Johnson's Baby": [
        ('BM-JNJ-OIL-001', "Johnson's Baby Oil 200ml", '200ml', '420.00', '260.00', 70),
        ('BM-JNJ-SHAMPOO-001', "Johnson's Baby Shampoo 200ml", '200ml', '460.00', '285.00', 70),
    ],
    'Sudocrem': [
        ('BM-SUDO-60-001', 'Sudocrem Antiseptic Healing Cream 60g', '60g', '420.00', '260.00', 80),
        ('BM-SUDO-250-001', 'Sudocrem Antiseptic Healing Cream 250g', '250g', '1100.00', '700.00', 40),
    ],
    'Omron M2': [
        ('MD-OMRON-M3-001', 'Omron M3 Upper Arm Blood Pressure Monitor', 'M3', '7200.00', '4700.00', 25),
        ('MD-OMRON-CUFF-001', 'Omron Universal Cuff', '22-42cm', '1800.00', '1150.00', 35),
    ],
    'Accu-Chek Active': [
        ('MD-ACCU-STRIPS-50', 'Accu-Chek Active Test Strips 50s', '50s', '1700.00', '1080.00', 65),
        ('MD-ACCU-LANCETS-100', 'Accu-Chek Softclix Lancets 100s', '100s', '850.00', '540.00', 75),
    ],
    'Uncover': [
        ('UNC-SER-NIA-001', 'Uncover Niacinamide Serum', '30ml', '2600.00', '1650.00', 55),
        ('UNC-MOI-CERA-001', 'Uncover Ceramide Moisturiser', '50ml', '2600.00', '1650.00', 55),
        ('UNC-SUN-SPF50-001', 'Uncover SPF 50 Sunscreen', '50ml', '2800.00', '1780.00', 60),
    ],
    'Strepsils': [
        ('OTC-STR-ORANGE-001', 'Strepsils Orange Lozenges 24s', '24s', '350.00', '215.00', 85),
        ('OTC-STR-REG-001', 'Strepsils Original Lozenges 24s', '24s', '350.00', '215.00', 85),
    ],
    'Vicks VapoRub': [
        ('OTC-VICKS-25-001', 'Vicks VapoRub 25g', '25g', '280.00', '170.00', 90),
        ('OTC-VICKS-100-001', 'Vicks VapoRub 100g', '100g', '720.00', '460.00', 50),
    ],
}


class Command(BaseCommand):
    help = 'Add sensible extra sellable variants under existing product families.'

    def handle(self, *args, **options):
        created = 0
        updated = 0
        skipped_products = []

        for product_name, variants in VARIANT_ENRICHMENTS.items():
            product = Product.objects.filter(name=product_name).prefetch_related('variants').first()
            if not product:
                skipped_products.append(product_name)
                continue

            lead = product.get_representative_variant()
            category = lead.category if lead else None
            subcategory = lead.subcategory if lead else None
            health_concerns = list(lead.health_concerns.all()) if lead else []
            image = lead.image or product.image
            next_order = product.variants.count()

            for offset, (sku, name, strength, price, cost_price, stock_qty) in enumerate(variants):
                variant, was_created = Variant.objects.update_or_create(
                    sku=sku,
                    defaults={
                        'product': product,
                        'name': name,
                        'strength': strength,
                        'category': category,
                        'subcategory': subcategory,
                        'short_description': f'{name} under the {product.name} product family.',
                        'description': f'{name} is a sellable variant grouped under {product.name}.',
                        'features': ['Product family variant', 'In-store and online sale', 'Tracked stock'],
                        'price': Decimal(price),
                        'cost_price': Decimal(cost_price),
                        'image': image,
                        'requires_prescription': bool(lead.requires_prescription) if lead else False,
                        'is_active': True,
                        'sort_order': next_order + offset,
                    },
                )
                if health_concerns:
                    variant.health_concerns.set(health_concerns)

                VariantInventory.objects.update_or_create(
                    variant=variant,
                    location=Product.STOCK_BRANCH,
                    defaults={
                        'stock_quantity': stock_qty,
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

        message = f'Variant enrichment complete: {created} created, {updated} updated.'
        if skipped_products:
            message += f' Skipped missing products: {", ".join(skipped_products)}.'
        self.stdout.write(self.style.SUCCESS(message))
