from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Tuple

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.products.models import Category, Product, ProductCategory, ProductSubcategory


@dataclass(frozen=True)
class SubcategorySpec:
    name: str
    slug: str
    description: str
    legacy_aliases: Tuple[str, ...] = ()


@dataclass(frozen=True)
class CategorySpec:
    name: str
    slug: str
    description: str
    legacy_aliases: Tuple[str, ...]
    subcategories: Tuple[SubcategorySpec, ...]


PHARMACY_TAXONOMY: Tuple[CategorySpec, ...] = (
    CategorySpec(
        name='Prescription Medicines',
        slug='prescription-medicines',
        description='Doctor-prescribed medicines for ongoing treatment, infections, chronic care, and specialist therapy.',
        legacy_aliases=('Prescription Medicines',),
        subcategories=(
            SubcategorySpec('Antibiotics', 'rx-antibiotics', 'Prescription antibiotics for bacterial infections.', ('Antibiotics',)),
            SubcategorySpec('Cardiovascular', 'rx-cardiovascular', 'Prescription medicines for blood pressure, cholesterol, and heart health.', ('Cardiovascular',)),
            SubcategorySpec('Diabetes Management', 'rx-diabetes', 'Prescription products used to manage blood sugar and diabetes.', ('Diabetes Management',)),
            SubcategorySpec('Respiratory', 'rx-respiratory', 'Prescription inhalers and treatments for asthma and breathing conditions.', ('Respiratory',)),
            SubcategorySpec('Antimalarials', 'rx-antimalarials', 'Prescription antimalarial treatments and malaria-support medicines.', ()),
            SubcategorySpec('HIV Care', 'rx-hiv-care', 'Prescription antiretroviral medicines and HIV care essentials.', ()),
            SubcategorySpec('Mental Health', 'rx-mental-health', 'Prescription medicines for anxiety, depression, and mental health support.', ('Mental Health',)),
        ),
    ),
    CategorySpec(
        name='Over-the-Counter Medicines',
        slug='over-the-counter-medicines',
        description='Everyday pharmacy essentials available without a prescription for common symptoms and minor illnesses.',
        legacy_aliases=('Over-the-Counter (OTC)', 'Over-the-Counter Medicines'),
        subcategories=(
            SubcategorySpec('Pain Relief', 'otc-pain-relief', 'Fast relief for headaches, fever, body pain, and inflammation.', ('Pain Relief',)),
            SubcategorySpec('Cough, Cold & Flu', 'otc-cough-cold-flu', 'Remedies for cough, sore throat, congestion, colds, and flu symptoms.', ('Cough & Cold',)),
            SubcategorySpec('Allergy & Sinus', 'otc-allergy-sinus', 'Antihistamines and sinus relief for allergies and nasal congestion.', ('Allergy & Sinus',)),
            SubcategorySpec('Digestive Health', 'otc-digestive-health', 'Support for heartburn, diarrhoea, digestion, and stomach discomfort.', ('Digestive Health',)),
            SubcategorySpec('Skin Treatments', 'otc-skin-treatments', 'Creams and topicals for fungal infections, rashes, and skin irritation.', ('Skin Treatment',)),
            SubcategorySpec('First Aid & Antiseptics', 'otc-first-aid', 'Antiseptics, wound care, and first-aid essentials for home use.', ('First Aid (Bandages, Antiseptics)', 'Wound Care Supplies')),
            SubcategorySpec('Eye & Ear Care', 'otc-eye-ear-care', 'Drops and relief products for eye and ear care.', ('Eye & Ear Care',)),
        ),
    ),
    CategorySpec(
        name='Vitamins & Supplements',
        slug='vitamins-supplements',
        description='Daily supplements for immunity, wellness, pregnancy, heart health, and nutritional support.',
        legacy_aliases=('Vitamins & Supplements',),
        subcategories=(
            SubcategorySpec('Multivitamins', 'supplements-multivitamins', 'Daily multivitamins for routine health and wellbeing.', ('Multivitamins',)),
            SubcategorySpec('Immune Support', 'supplements-immune', 'Vitamin C and other supplements that support immunity.', ('Vitamin C & D',)),
            SubcategorySpec('Iron & Minerals', 'supplements-iron-minerals', 'Iron, folic acid, and essential mineral supplements.', ('Iron & Minerals',)),
            SubcategorySpec('Omega & Heart Health', 'supplements-omega-heart', 'Omega oils and supplements for heart and general wellness.', ('Omega-3 & Fish Oil',)),
            SubcategorySpec('Pregnancy Support', 'supplements-pregnancy', 'Prenatal and pregnancy-focused supplements for mother and baby.', ('Pregnancy Support',)),
        ),
    ),
    CategorySpec(
        name='Personal Care & Beauty',
        slug='personal-care-beauty',
        description='Trusted skincare, oral care, sun care, and everyday personal-care pharmacy products.',
        legacy_aliases=('Personal Care',),
        subcategories=(
            SubcategorySpec('Skincare', 'personal-skincare', 'Cleansers, moisturisers, and skincare treatments for daily care.', ('Skin Care',)),
            SubcategorySpec('Oral Care', 'personal-oral-care', 'Toothpaste and oral-care products for sensitive teeth and hygiene.', ('Dental Care',)),
            SubcategorySpec('Sun Protection', 'personal-sun-protection', 'Sunscreens and skin protection for daily UV exposure.', ('Sun Protection',)),
            SubcategorySpec('Hair Care', 'personal-hair-care', 'Hair-care products for routine cleansing and treatment.', ('Hair Care',)),
        ),
    ),
    CategorySpec(
        name='Baby, Mother & Family Care',
        slug='baby-mother-family-care',
        description='Baby feeding, skincare, maternity, and home essentials for growing families.',
        legacy_aliases=('Baby & Mother Care',),
        subcategories=(
            SubcategorySpec('Baby Nutrition', 'family-baby-nutrition', 'Infant formula and nutrition products for babies and toddlers.', ('Baby Nutrition', 'Baby Food & Formula')),
            SubcategorySpec('Baby Skincare', 'family-baby-skincare', 'Gentle skincare and lotion products for babies.', ('Baby Skincare',)),
            SubcategorySpec('Nappy & Rash Care', 'family-nappy-rash-care', 'Barrier creams and rash-care essentials for babies.', ()),
            SubcategorySpec('Maternity Care', 'family-maternity-care', 'Pregnancy and maternity care support products.', ('Maternity', 'Maternity Care', 'Breastfeeding Essentials')),
        ),
    ),
    CategorySpec(
        name='Medical Devices & Home Diagnostics',
        slug='medical-devices-home-diagnostics',
        description='Home-use health devices and diagnostic tools for self-monitoring and family care.',
        legacy_aliases=('Medical Devices & Equipment',),
        subcategories=(
            SubcategorySpec('Blood Pressure Monitors', 'devices-bp-monitors', 'Home blood pressure monitors for routine cardiovascular checks.', ('Blood Pressure Monitors',)),
            SubcategorySpec('Blood Glucose Monitors', 'devices-glucose-monitors', 'Glucometers and testing kits for blood sugar monitoring.', ('Glucometers & Strips',)),
            SubcategorySpec('Thermometers', 'devices-thermometers', 'Digital thermometers for fast temperature readings.', ('Thermometers',)),
            SubcategorySpec('Pulse Oximeters', 'devices-pulse-oximeters', 'Pulse oximeters for oxygen saturation and pulse checks.', ()),
        ),
    ),
    CategorySpec(
        name='Natural & Herbal Remedies',
        slug='natural-herbal-remedies',
        description='Herbal and natural wellness products used for everyday nutritional and lifestyle support.',
        legacy_aliases=('Herbal & Alternative Medicine',),
        subcategories=(
            SubcategorySpec('Herbal Supplements', 'herbal-supplements', 'Plant-based powders, extracts, and herbal wellness supplements.', ('Herbal Remedies',)),
        ),
    ),
)


PRODUCT_SUBCATEGORY_MAP: Tuple[Tuple[str, str], ...] = (
    ('RX-AB-', 'rx-antibiotics'),
    ('RX-CV-', 'rx-cardiovascular'),
    ('RX-DM-', 'rx-diabetes'),
    ('RX-RS-', 'rx-respiratory'),
    ('RX-ML-', 'rx-antimalarials'),
    ('RX-HIV-', 'rx-hiv-care'),
    ('OTC-PR-', 'otc-pain-relief'),
    ('OTC-CC-', 'otc-cough-cold-flu'),
    ('OTC-DG-', 'otc-digestive-health'),
    ('OTC-AL-', 'otc-allergy-sinus'),
    ('VIT-MV-', 'supplements-multivitamins'),
    ('VIT-VC-', 'supplements-immune'),
    ('VIT-IM-', 'supplements-iron-minerals'),
    ('VIT-OM-', 'supplements-omega-heart'),
    ('VIT-PG-', 'supplements-pregnancy'),
    ('PC-SK-', 'personal-skincare'),
    ('PC-DC-', 'personal-oral-care'),
    ('PC-SN-', 'personal-sun-protection'),
    ('BM-BN-', 'family-baby-nutrition'),
    ('MD-BP-', 'devices-bp-monitors'),
    ('MD-GL-', 'devices-glucose-monitors'),
    ('MD-TH-', 'devices-thermometers'),
    ('MD-OX-', 'devices-pulse-oximeters'),
    ('HB-HR-', 'herbal-supplements'),
)

PRODUCT_EXACT_SUBCATEGORY_MAP: Dict[str, str] = {
    'OTC-SK-001': 'otc-first-aid',
    'OTC-SK-002': 'otc-skin-treatments',
    'BM-BS-001': 'family-baby-skincare',
    'BM-BS-002': 'family-nappy-rash-care',
}


class Command(BaseCommand):
    help = 'Rebuild the storefront pharmacy taxonomy and attach products to clean category/subcategory nodes.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--no-prune',
            action='store_true',
            help='Keep obsolete categories and subcategories instead of deleting them.',
        )

    def handle(self, *args, **options):
        prune = not options['no_prune']
        with transaction.atomic():
            created_roots, created_children, root_nodes, child_nodes = self._upsert_taxonomy()
            mapped_products = self._map_products(child_nodes)
            self._sync_category_images(root_nodes, child_nodes)
            if prune:
                self._prune_obsolete(root_nodes, child_nodes)

        self.stdout.write(self.style.SUCCESS(
            f'Rebuilt taxonomy: {created_roots} root categories, {created_children} subcategories, {mapped_products} mapped products.'
        ))

    def _find_existing_root(self, spec: CategorySpec) -> Optional[Category]:
        queryset = Category.objects.filter(parent__isnull=True)
        exact = queryset.filter(slug=spec.slug).first() or queryset.filter(name=spec.name).first()
        if exact:
            return exact
        for alias in spec.legacy_aliases:
            candidate = queryset.filter(name=alias).first()
            if candidate:
                return candidate
        return None

    def _find_existing_legacy_root(self, spec: CategorySpec) -> Optional[ProductCategory]:
        queryset = ProductCategory.objects.all()
        exact = queryset.filter(slug=spec.slug).first() or queryset.filter(name=spec.name).first()
        if exact:
            return exact
        for alias in spec.legacy_aliases:
            candidate = queryset.filter(name=alias).first()
            if candidate:
                return candidate
        return None

    def _find_existing_child(self, parent: Category, spec: SubcategorySpec) -> Optional[Category]:
        queryset = Category.objects.filter(parent=parent)
        exact = queryset.filter(slug=spec.slug).first() or queryset.filter(name=spec.name).first()
        if exact:
            return exact
        for alias in spec.legacy_aliases:
            candidate = queryset.filter(name=alias).first()
            if candidate:
                return candidate
        return None

    def _find_existing_legacy_child(self, root: ProductCategory, spec: SubcategorySpec) -> Optional[ProductSubcategory]:
        queryset = ProductSubcategory.objects.filter(category=root)
        exact = queryset.filter(slug=spec.slug).first() or queryset.filter(name=spec.name).first()
        if exact:
            return exact
        for alias in spec.legacy_aliases:
            candidate = queryset.filter(name=alias).first()
            if candidate:
                return candidate
        return None

    def _upsert_taxonomy(self):
        root_nodes: Dict[str, Category] = {}
        child_nodes: Dict[str, Category] = {}
        created_roots = 0
        created_children = 0

        for spec in PHARMACY_TAXONOMY:
            root = self._find_existing_root(spec)
            if root is None:
                root = Category(parent=None)
                created_roots += 1
            root.name = spec.name
            root.slug = spec.slug
            root.description = spec.description
            root.is_active = True
            root.save()
            root_nodes[spec.slug] = root

            legacy_root = self._find_existing_legacy_root(spec)
            if legacy_root is None:
                legacy_root = ProductCategory()
            legacy_root.name = spec.name
            legacy_root.slug = spec.slug
            legacy_root.description = spec.description
            legacy_root.is_active = True
            if not legacy_root.image:
                legacy_root.image = ''
            legacy_root.save()

            for child_spec in spec.subcategories:
                child = self._find_existing_child(root, child_spec)
                if child is None:
                    child = Category(parent=root)
                    created_children += 1
                child.parent = root
                child.name = child_spec.name
                child.slug = child_spec.slug
                child.description = child_spec.description
                child.is_active = True
                child.save()
                child_nodes[child.slug] = child

                legacy_child = self._find_existing_legacy_child(legacy_root, child_spec)
                if legacy_child is None:
                    legacy_child = ProductSubcategory(category=legacy_root)
                legacy_child.category = legacy_root
                legacy_child.category_node = child
                legacy_child.name = child_spec.name
                legacy_child.slug = child_spec.slug
                legacy_child.description = child_spec.description
                legacy_child.is_active = True
                legacy_child.save()

        return created_roots, created_children, root_nodes, child_nodes

    def _subcategory_slug_for_product(self, product: Product) -> Optional[str]:
        if product.sku in PRODUCT_EXACT_SUBCATEGORY_MAP:
            return PRODUCT_EXACT_SUBCATEGORY_MAP[product.sku]
        for prefix, slug in PRODUCT_SUBCATEGORY_MAP:
            if product.sku.startswith(prefix):
                return slug
        return None

    def _map_products(self, child_nodes: Dict[str, Category]) -> int:
        mapped_products = 0
        for product in Product.objects.all().select_related('catalog_subcategory', 'category'):
            subcategory_slug = self._subcategory_slug_for_product(product)
            if not subcategory_slug:
                continue
            subcategory = child_nodes[subcategory_slug]
            root = subcategory.parent
            update_fields: List[str] = []
            if product.catalog_subcategory_id != subcategory.id:
                product.catalog_subcategory = subcategory
                update_fields.append('catalog_subcategory')
            if product.category_id != root.id:
                product.category = root
                update_fields.append('category')
            if update_fields:
                product.save(update_fields=update_fields)
                mapped_products += 1
        return mapped_products

    def _sync_category_images(self, root_nodes: Dict[str, Category], child_nodes: Dict[str, Category]):
        for spec in PHARMACY_TAXONOMY:
            root = root_nodes[spec.slug]
            legacy_root = ProductCategory.objects.filter(slug=spec.slug).first()
            if legacy_root and legacy_root.image and not root.image:
                root.image = legacy_root.image
                root.save(update_fields=['image'])

        for child in child_nodes.values():
            if child.image:
                continue
            product = Product.objects.filter(catalog_subcategory=child).exclude(image='').exclude(image__isnull=True).first()
            if product and product.image:
                child.image = product.image
                child.save(update_fields=['image'])

    def _prune_obsolete(self, root_nodes: Dict[str, Category], child_nodes: Dict[str, Category]):
        desired_root_slugs = set(root_nodes.keys())
        desired_child_slugs = set(child_nodes.keys())

        ProductSubcategory.objects.exclude(slug__in=desired_child_slugs).delete()
        ProductCategory.objects.exclude(slug__in=desired_root_slugs).delete()

        Category.objects.filter(parent__isnull=False).exclude(slug__in=desired_child_slugs).delete()
        Category.objects.filter(parent__isnull=True).exclude(slug__in=desired_root_slugs).delete()
