from django.core.management.base import BaseCommand
from django.utils.text import slugify

from apps.products.models import Brand, Product, Variant


FAMILY_FIXES = {
    'RX-AB-001': ('Amoxicillin', 'Amoxicillin 500mg Capsules'),
    'RX-AB-002': ('Co-Amoxiclav', 'Co-Amoxiclav 625mg Tablets'),
    'RX-AB-003': ('Ciprofloxacin', 'Ciprofloxacin 500mg Tablets'),
    'RX-AB-004': ('Metronidazole', 'Metronidazole 400mg Tablets'),
    'RX-CV-001': ('Amlodipine', 'Amlodipine 5mg Tablets'),
    'RX-CV-002': ('Losartan', 'Losartan 50mg Tablets'),
    'RX-CV-003': ('Atorvastatin', 'Atorvastatin 20mg Tablets'),
    'RX-DM-001': ('Metformin', 'Metformin 500mg Tablets'),
    'RX-DM-002': ('Glibenclamide', 'Glibenclamide 5mg Tablets'),
    'RX-RS-001': ('Salbutamol', 'Salbutamol Inhaler 100mcg'),
    'OTC-PR-002': ('Ibuprofen', 'Ibuprofen 400mg Tablets'),
    'OTC-PR-003': ('Aspirin', 'Aspirin 75mg Dispersible Tablets'),
    'OTC-CC-001': ('Strepsils', 'Strepsils Honey & Lemon Lozenges 24s'),
    'OTC-CC-002': ('Vicks VapoRub', 'Vicks VapoRub 50g'),
    'OTC-DG-001': ('ORS Sachets', 'ORS Sachets Oral Rehydration Salts 10s'),
    'OTC-DG-002': ('Omeprazole', 'Omeprazole 20mg Capsules'),
    'OTC-DG-003': ('Loperamide', 'Loperamide 2mg Capsules 12s'),
    'OTC-AL-001': ('Cetirizine', 'Cetirizine 10mg Tablets 10s'),
    'OTC-SK-001': ('Dettol', 'Dettol Antiseptic Liquid 250ml'),
    'OTC-SK-002': ('Clotrimazole', 'Clotrimazole 1% Cream 20g'),
    'VIT-VC-001': ('Vitamin C', 'Vitamin C 1000mg Effervescent Tablets 20s'),
    'VIT-IM-001': ('Ferrous Sulphate + Folic Acid', 'Ferrous Sulphate + Folic Acid 200mg/0.4mg Tablets 30s'),
    'VIT-OM-001': ('Omega-3 Fish Oil', 'Omega-3 Fish Oil 1000mg Softgels 30s'),
    'VIT-PG-001': ('Pregnacare', 'Pregnacare Plus 28+28 Tablets'),
    'VIT-MV-001': ('Complete Multivitamins Adults', 'Complete Multivitamins Adults 30s'),
    'PC-SK-001': ('Cetaphil', 'Cetaphil Gentle Skin Cleanser 250ml'),
    'PC-DC-001': ('Sensodyne', 'Sensodyne Repair & Protect Toothpaste 75ml'),
    'PC-SN-001': ('Eucerin', 'Eucerin Sun Fluid SPF 50+ 50ml'),
    'BM-BN-001': ('SMA Pro', 'SMA Pro Follow-On Milk 900g'),
    'BM-BS-001': ("Johnson's Baby", "Johnson's Baby Lotion 200ml"),
    'BM-BS-002': ('Sudocrem', 'Sudocrem Antiseptic Healing Cream 125g'),
    'MD-BP-001': ('Omron M2', 'Omron M2 Upper Arm Blood Pressure Monitor'),
    'MD-GL-001': ('Accu-Chek Active', 'Accu-Chek Active Glucometer Starter Pack'),
    'MD-TH-001': ('Digital Thermometer', 'Digital Thermometer Oral/Rectal/Axillary'),
    'MD-OX-001': ('Pulse Oximeter', 'Pulse Oximeter Fingertip SpO2 Monitor'),
    'RX-ML-001': ('Artemether/Lumefantrine', 'Artemether/Lumefantrine 20/120mg Tablets (AL)'),
    'RX-ML-002': ('Sulfadoxine/Pyrimethamine', 'Sulfadoxine/Pyrimethamine 500/25mg (SP) Tablets'),
    'RX-HIV-001': (
        'Tenofovir/Lamivudine/Dolutegravir',
        'Tenofovir/Lamivudine/Dolutegravir 300/300/50mg (TLD)',
    ),
    'HB-HR-001': ('Moringa Leaf', 'Moringa Leaf Powder 200g'),
    'OTC-PR-001': ('Panadol', 'Panadol Extra Pain Reliever Tablets'),
    'OTC-PAN-FLU-001': ('Panadol', 'Panadol Flu'),
    'OTC-PAN-COUGH-001': ('Panadol', 'Panadol Cough Syrup'),
    'OTC-PAN-PAIN-001': ('Panadol', 'Panadol Pain Reliever'),
}

UNCOVER_VARIANTS = {
    'UNC-SM-001': 'Uncover Aloe Vera Sheet Mask Bundle',
    'UNC-SM-002': 'Uncover Vitamin C Sheet Mask Bundle',
    'UNC-SM-003': 'Uncover Green Tea Sheet Mask Bundle',
    'UNC-SM-010': 'Uncover 10 Pack Sheet Mask Bundle',
    'UNC-SER-001': 'Uncover Licorice Dark Spot Serum',
    'UNC-SER-002': 'Uncover Green Tea Blemish Serum',
    'UNC-SER-003': 'Uncover Baobab Glow-C Serum',
    'UNC-TON-001': 'Uncover Rooibos Glow Toner',
    'UNC-MOI-001': 'Uncover Argan Moisturiser 30ml',
    'UNC-CLN-001': 'Uncover Green Tea Cleanser 30ml',
    'UNC-SUN-001': 'Uncover Aloe Invisible Sunscreen 40ml',
}


class Command(BaseCommand):
    help = 'Normalize products as parent families and variants as sellable items.'

    def _unique_slug(self, base, product_id=None):
        base_slug = slugify(base) or 'product'
        slug = base_slug
        counter = 2
        queryset = Product.objects.exclude(pk=product_id)
        while queryset.filter(slug=slug).exists():
            slug = f'{base_slug}-{counter}'
            counter += 1
        return slug

    def _rename_product(self, product, family_name):
        product.name = family_name
        product.slug = self._unique_slug(family_name, product.pk)
        product.save(update_fields=['name', 'slug', 'updated_at'])

    def _normalize_standard_variants(self):
        renamed_products = 0
        renamed_variants = 0
        cleaned_strengths = 0
        for sku, (family_name, variant_name) in FAMILY_FIXES.items():
            variant = Variant.objects.select_related('product').filter(sku=sku).first()
            if not variant:
                continue
            if variant.product.name != family_name:
                self._rename_product(variant.product, family_name)
                renamed_products += 1
            if variant.name != variant_name:
                variant.name = variant_name
                variant.save(update_fields=['name', 'updated_at'])
                renamed_variants += 1
            if variant.strength.strip().upper() == 'N/A':
                variant.strength = ''
                variant.save(update_fields=['strength', 'updated_at'])
                cleaned_strengths += 1
        return renamed_products, renamed_variants, cleaned_strengths

    def _normalize_uncover(self):
        brand = Brand.objects.filter(name='Uncover').first()
        if not brand:
            return 0, 0, 0

        first_variant = Variant.objects.select_related('product').filter(sku__in=UNCOVER_VARIANTS).first()
        family, _ = Product.objects.get_or_create(
            sku='UNC-FAMILY-001',
            defaults={
                'name': 'Uncover',
                'slug': self._unique_slug('Uncover'),
                'brand': brand,
                'image': first_variant.product.image if first_variant else '',
                'is_active': True,
            },
        )
        if family.name != 'Uncover':
            self._rename_product(family, 'Uncover')
        if not family.image and first_variant and first_variant.product.image:
            family.image = first_variant.product.image
            family.save(update_fields=['image', 'updated_at'])

        moved = 0
        renamed = 0
        old_product_ids = set()
        for sort_order, (sku, variant_name) in enumerate(UNCOVER_VARIANTS.items()):
            variant = Variant.objects.select_related('product').filter(sku=sku).first()
            if not variant:
                continue
            if variant.product_id != family.id:
                old_product_ids.add(variant.product_id)
                variant.product = family
                moved += 1
            if variant.name != variant_name:
                variant.name = variant_name
                renamed += 1
            variant.sort_order = sort_order
            variant.save(update_fields=['product', 'name', 'sort_order', 'updated_at'])

        removed_empty_products = 0
        for product in Product.objects.filter(pk__in=old_product_ids):
            if not product.variants.exists():
                product.delete()
                removed_empty_products += 1

        return moved, renamed, removed_empty_products

    def handle(self, *args, **options):
        renamed_products, renamed_variants, cleaned_strengths = self._normalize_standard_variants()
        moved_uncover, renamed_uncover, removed_uncover_products = self._normalize_uncover()

        self.stdout.write(self.style.SUCCESS(
            'Product family normalization complete: '
            f'{renamed_products} product rows renamed, '
            f'{renamed_variants} standard variants renamed, '
            f'{cleaned_strengths} placeholder strengths cleaned, '
            f'{moved_uncover} Uncover variants moved, '
            f'{renamed_uncover} Uncover variants renamed, '
            f'{removed_uncover_products} empty Uncover product rows removed.'
        ))
