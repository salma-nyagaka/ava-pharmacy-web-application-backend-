"""
Management command: fetch_catalog_images

Uses DuckDuckGo image search to download specific, high-quality images
for every ProductCategory, HealthConcern, Brand, and Product in the catalog.
Skips records that already have a non-empty image unless --force is passed.
"""

import os
import time
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

from django.conf import settings
from django.core.management.base import BaseCommand


HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
        'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
    ),
    'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
}

# ── Search queries for every entity ────────────────────────────────────────

CATEGORY_QUERIES = {
    'Prescription Medicines':        'prescription medicine pharmacy pill bottles',
    'Over-the-Counter Medicines':    'otc pharmacy medicine tablets shelf',
    'Vitamins & Supplements':        'vitamin supplement capsule bottles health',
    'Personal Care & Beauty':        'personal care skincare cosmetics pharmacy products',
    'Baby, Mother & Family Care':    'baby mother care infant formula family pharmacy products',
    'Medical Devices & Home Diagnostics': 'medical device home diagnostics blood pressure glucometer equipment',
    'Natural & Herbal Remedies':     'herbal medicine natural remedies supplement pharmacy',
}

SUBCATEGORY_QUERIES = {
    'Allergy & Sinus': 'allergy sinus medicine antihistamine pharmacy',
    'Antibiotics': 'antibiotic capsules tablets pharmacy medicine',
    'Antimalarials': 'antimalarial tablets malaria pharmacy medicine',
    'Baby Nutrition': 'baby formula infant nutrition pharmacy products',
    'Baby Skincare': 'baby skincare lotion gentle pharmacy products',
    'Blood Glucose Monitors': 'blood glucose monitor glucometer pharmacy device',
    'Blood Pressure Monitors': 'blood pressure monitor digital pharmacy device',
    'Cardiovascular': 'blood pressure cholesterol prescription medicine pharmacy',
    'Cough, Cold & Flu': 'cough cold flu pharmacy medicine lozenges vaporub',
    'Diabetes Management': 'diabetes tablets pharmacy medicine blood sugar',
    'Digestive Health': 'digestive health pharmacy medicine capsules antacid',
    'Eye & Ear Care': 'eye drops ear care pharmacy medicine',
    'First Aid & Antiseptics': 'first aid antiseptic pharmacy wound care',
    'HIV Care': 'antiretroviral hiv care medicine pharmacy',
    'Hair Care': 'hair care shampoo pharmacy beauty products',
    'Herbal Supplements': 'herbal supplement powder natural remedy pharmacy',
    'Immune Support': 'vitamin c immunity supplements pharmacy',
    'Iron & Minerals': 'iron supplement folic acid pharmacy tablets',
    'Maternity Care': 'maternity care pregnancy essentials pharmacy products',
    'Mental Health': 'mental health prescription medicine pharmacy',
    'Multivitamins': 'multivitamin bottle pharmacy supplements',
    'Nappy & Rash Care': 'nappy rash cream baby pharmacy products',
    'Omega & Heart Health': 'omega 3 supplement heart health pharmacy',
    'Oral Care': 'toothpaste oral care pharmacy products',
    'Pain Relief': 'pain relief tablets pharmacy medicine',
    'Pregnancy Support': 'prenatal vitamins pregnancy support pharmacy',
    'Pulse Oximeters': 'pulse oximeter fingertip pharmacy device',
    'Respiratory': 'asthma inhaler respiratory pharmacy medicine',
    'Skin Treatments': 'antifungal cream skin treatment pharmacy',
    'Skincare': 'skincare cleanser lotion pharmacy beauty',
    'Sun Protection': 'sunscreen sun protection pharmacy skincare',
    'Thermometers': 'digital thermometer pharmacy device',
}

HEALTH_CONCERN_QUERIES = {
    'Malaria':                       'malaria medicine treatment mosquito nets africa',
    'Diabetes':                      'diabetes blood glucose monitoring insulin medicine',
    'Hypertension':                  'hypertension blood pressure cuff medicine',
    'HIV/AIDS':                      'hiv aids antiretroviral medicine treatment',
    'Tuberculosis':                  'tuberculosis tb medicine chest xray',
    'Typhoid Fever':                 'typhoid fever treatment antibiotics medicine',
    'Anaemia':                       'anaemia iron deficiency blood cells medicine',
    'Respiratory Infections':        'respiratory infection cough cold medicine inhaler',
    'Heart Disease':                 'heart disease cardiology stethoscope ecg',
    'Cancer Support':                'cancer support chemotherapy oncology medicine',
    'Kidney Disease':                'kidney disease renal medicine dialysis',
    'Mental Health & Depression':    'mental health depression anxiety medicine therapy',
    "Women's Health":                'women health gynecology prenatal vitamins medicine',
    'Child Health':                  'child health paediatric baby medicine immunization',
    'Arthritis & Joint Pain':        'arthritis joint pain inflammation medicine',
    'Skin Conditions':               'skin condition eczema dermatology cream treatment',
    'Digestive Disorders':           'digestive health stomach medicine antacid pills',
    'Eye Health':                    'eye health vision eye drops ophthalmology',
    'Sexual & Reproductive Health':  'reproductive health contraception family planning',
    'Cholesterol Management':        'cholesterol statin heart medicine lipid profile',
    'Malnutrition & Deficiency':     'malnutrition nutritional deficiency supplement food',
}

BRAND_QUERIES = {
    'Pfizer':         'Pfizer pharmaceutical medicine pills laboratory',
    'GSK':            'GlaxoSmithKline GSK pharmacy medicine',
    'Novartis':       'Novartis pharmaceutical medicine research',
    'Sanofi':         'Sanofi pharmaceutical medicine health',
    'Abbott':         'Abbott laboratories medicine health products',
    'Bayer':          'Bayer pharmaceutical aspirin medicine',
    'AstraZeneca':    'AstraZeneca pharmaceutical medicine vaccine',
    'Cipla':          'Cipla generic medicine tablets Africa',
    'Cosmos Limited': 'pharmacy medicine tablets Kenya Africa',
    'Dawa Limited':   'pharmacy medicine oral rehydration Kenya',
    'Beta Healthcare':'healthcare medicine hospital Africa',
    'Strides Pharma': 'pharmaceutical medicine production factory Africa',
}

BRAND_LOGO_URLS = {
    'Abbott': 'https://commons.wikimedia.org/wiki/Special:FilePath/Abbott%20Laboratories%202025%20logo.svg',
    'AstraZeneca': 'https://commons.wikimedia.org/wiki/Special:FilePath/Astrazeneca%20text%20logo.svg',
    'Bayer': 'https://commons.wikimedia.org/wiki/Special:FilePath/Logo%20Bayer.svg',
    'Beta Healthcare': 'https://betacare.co.ke/wp-content/uploads/2025/02/beta-healthcare-international-ltd-logo-sloganWebp.webp',
    'Cipla': 'https://commons.wikimedia.org/wiki/Special:FilePath/Cipla%20logo.svg',
    'Cosmos Limited': 'https://www.cosmos-pharm.com/img/Cosmos-Identity-Col.png',
    'Dawa Limited': 'https://commons.wikimedia.org/wiki/Special:FilePath/Dawa%20LS%20logo%20-%20SVG.svg',
    'GSK': 'https://www.gsk.com/nuxtassets/icons/gsk-logo.svg',
    'Novartis': 'https://commons.wikimedia.org/wiki/Special:FilePath/Novartis-Logo-2023.svg',
    'Pfizer': 'https://www.pfizer.com/profiles/pfecpfizercomus_profile/themes/pfecpfizercomus/public/assets/images/logo-blue.svg',
    'Sanofi': 'https://commons.wikimedia.org/wiki/Special:FilePath/Sanofi_logo.svg',
    'Strides Pharma': 'https://www.strides.com/Upload/Images/thumbnail/Strides-logo-black.svg',
}

PRODUCT_QUERIES = {
    # Antibiotics
    'Amoxicillin 500mg Capsules':                       'amoxicillin 500mg capsules antibiotic medicine',
    'Co-Amoxiclav 625mg Tablets':                       'co-amoxiclav augmentin 625mg tablets antibiotic',
    'Ciprofloxacin 500mg Tablets':                      'ciprofloxacin 500mg tablets antibiotic medicine',
    'Metronidazole 400mg Tablets':                      'metronidazole 400mg tablets antibiotic pharmacy',
    # Cardiovascular
    'Amlodipine 5mg Tablets':                           'amlodipine 5mg tablets blood pressure medicine',
    'Losartan 50mg Tablets':                            'losartan 50mg tablets hypertension medicine',
    'Atorvastatin 20mg Tablets':                        'atorvastatin lipitor 20mg cholesterol tablets',
    # Diabetes
    'Metformin 500mg Tablets':                          'metformin 500mg tablets diabetes medicine',
    'Glibenclamide 5mg Tablets':                        'glibenclamide 5mg diabetes tablets medicine',
    # Respiratory
    'Salbutamol Inhaler 100mcg':                        'salbutamol ventolin inhaler asthma blue puffer',
    # OTC Pain
    'Panadol Extra Tablets 500mg/65mg':                 'Panadol Extra tablets paracetamol pain relief',
    'Ibuprofen 400mg Tablets':                          'ibuprofen 400mg tablets pain relief anti-inflammatory',
    'Aspirin 75mg Dispersible Tablets':                 'aspirin 75mg dispersible tablets heart medicine',
    # Cough & Cold
    'Strepsils Honey & Lemon Lozenges 24s':             'Strepsils honey lemon lozenges throat sore',
    'Vicks VapoRub 50g':                                'Vicks VapoRub chest rub cold medicine',
    # Digestive
    'ORS Sachets Oral Rehydration Salts 10s':           'oral rehydration salts ORS sachets diarrhoea',
    'Omeprazole 20mg Capsules':                         'omeprazole 20mg capsules stomach acid medicine',
    'Loperamide 2mg Capsules 12s':                      'loperamide 2mg capsules diarrhoea medicine',
    # Allergy
    'Cetirizine 10mg Tablets 10s':                      'cetirizine 10mg antihistamine allergy tablets',
    # Skin
    'Dettol Antiseptic Liquid 250ml':                   'Dettol antiseptic liquid disinfectant bottle',
    'Clotrimazole 1% Cream 20g':                        'clotrimazole antifungal cream tube skin',
    # Vitamins
    'Vitamin C 1000mg Effervescent Tablets 20s':        'vitamin C 1000mg effervescent tablets tube',
    'Ferrous Sulphate + Folic Acid 200mg/0.4mg Tablets 30s': 'ferrous sulphate folic acid iron tablets pregnancy',
    'Omega-3 Fish Oil 1000mg Softgels 30s':             'omega-3 fish oil softgel capsules supplements',
    'Pregnacare Plus 28+28 Tablets':                    'Pregnacare prenatal vitamins pregnancy supplements',
    'Complete Multivitamins Adults 30s':                'multivitamin tablets bottle daily supplements adults',
    # Personal Care
    'Cetaphil Gentle Skin Cleanser 250ml':              'Cetaphil gentle skin cleanser pump bottle',
    'Sensodyne Repair & Protect Toothpaste 75ml':       'Sensodyne toothpaste sensitive teeth tube',
    'Eucerin Sun Fluid SPF 50+ 50ml':                   'Eucerin sunscreen SPF 50 sun protection cream',
    # Baby
    'SMA Pro Follow-On Milk 900g':                      'SMA Pro follow-on infant formula milk tin',
    "Johnson's Baby Lotion 200ml":                      'Johnson baby lotion gentle skin bottle',
    'Sudocrem Antiseptic Healing Cream 125g':           'Sudocrem antiseptic nappy rash cream tub',
    # Medical Devices
    'Omron M2 Upper Arm Blood Pressure Monitor':        'Omron M2 blood pressure monitor upper arm digital',
    'Accu-Chek Active Glucometer Starter Pack':         'Accu-Chek Active glucometer blood glucose monitor',
    'Digital Thermometer Oral/Rectal/Axillary':         'digital thermometer oral temperature medical',
    'Pulse Oximeter Fingertip SpO2 Monitor':            'fingertip pulse oximeter SpO2 blood oxygen monitor',
    # Malaria / HIV
    'Artemether/Lumefantrine 20/120mg Tablets (AL)':    'artemether lumefantrine Coartem malaria tablets',
    'Sulfadoxine/Pyrimethamine 500/25mg (SP) Tablets':  'sulfadoxine pyrimethamine Fansidar malaria tablets',
    'Tenofovir/Lamivudine/Dolutegravir 300/300/50mg (TLD)': 'tenofovir lamivudine dolutegravir HIV ARV tablets',
    # Herbal
    'Moringa Leaf Powder 200g':                         'moringa leaf powder supplement natural health',
}


def _fetch_ddg_images(query: str, max_results: int = 8):
    """Return a list of image URLs from DuckDuckGo image search."""
    try:
        from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            results = list(ddgs.images(
                query,
                region='wt-wt',
                safesearch='off',
                size='Large',
                type_image='photo',
                max_results=max_results,
            ))
        return [r['image'] for r in results if r.get('image')]
    except Exception:
        return []


def _download(url: str, dest: str) -> bool:
    """Download url to dest. Returns True on success with a real image."""
    try:
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=15) as resp:
            ct = resp.headers.get('Content-Type', '')
            is_svg = 'svg' in ct or url.lower().endswith('.svg')
            if 'image' not in ct and 'octet-stream' not in ct and not is_svg:
                return False
            data = resp.read()
        if len(data) < 1_000 and not is_svg:
            return False
        with open(dest, 'wb') as f:
            f.write(data)
        return True
    except Exception:
        return False


def _preferred_extension_for_url(url: str) -> str:
    path = urlparse(url).path.lower()
    if path.endswith('.svg'):
        return '.svg'
    if path.endswith('.webp'):
        return '.webp'
    if path.endswith('.png'):
        return '.png'
    return '.png'


def _media(rel: str) -> str:
    return str(Path(settings.MEDIA_ROOT) / rel)


def _is_usable_asset(dest_abs: str) -> bool:
    if not os.path.exists(dest_abs):
        return False
    lower_name = dest_abs.lower()
    min_size = 1_000 if lower_name.endswith('.svg') else 5_000
    return os.path.getsize(dest_abs) > min_size


class Command(BaseCommand):
    help = 'Fetch specific images for every catalog entity using DuckDuckGo image search'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Re-download images even if a file already exists',
        )
        parser.add_argument(
            '--only',
            choices=['categories', 'concerns', 'brands', 'products'],
            help='Fetch images for one entity type only',
        )

    def handle(self, *args, **options):
        force = options['force']
        only = options.get('only')

        if not only or only == 'categories':
            self._fetch_categories(force)
        if not only or only == 'concerns':
            self._fetch_health_concerns(force)
        if not only or only == 'brands':
            self._fetch_brands(force)
        if not only or only == 'products':
            self._fetch_products(force)

        self.stdout.write(self.style.SUCCESS('Image fetch complete.'))

    # ── helpers ──────────────────────────────────────────────────────────────

    def _get_and_save(self, query: str, dest_rel: str, label: str, force: bool) -> bool:
        dest_abs = _media(dest_rel)
        if not force and _is_usable_asset(dest_abs):
            self.stdout.write(f'  SKIP  {label}')
            return True

        self.stdout.write(f'  GET   {label} → "{query}"')
        urls = _fetch_ddg_images(query)
        for url in urls:
            if _download(url, dest_abs):
                size_kb = os.path.getsize(dest_abs) // 1024
                self.stdout.write(self.style.SUCCESS(f'        ✓ {size_kb}KB'))
                time.sleep(0.3)
                return True
        self.stdout.write(self.style.WARNING(f'        ✗ no usable image found'))
        time.sleep(0.5)
        return False

    def _update_image_field(self, instance, field_name: str, rel_path: str):
        dest_abs = _media(rel_path)
        if _is_usable_asset(dest_abs):
            setattr(instance, field_name, rel_path)
            instance.save(update_fields=[field_name])

    # ── entity fetchers ───────────────────────────────────────────────────────

    def _fetch_categories(self, force: bool):
        from apps.products.models import Category, ProductCategory
        self.stdout.write('\n── Product Categories ──')
        for cat in Category.objects.filter(parent__isnull=True).order_by('name'):
            query = CATEGORY_QUERIES.get(cat.name, f'{cat.name} pharmacy medicine')
            rel = f'categories/{cat.slug}.jpg'
            ok = self._get_and_save(query, rel, cat.name, force)
            if ok:
                self._update_image_field(cat, 'image', rel)
                legacy = ProductCategory.objects.filter(slug=cat.slug).first()
                if legacy:
                    self._update_image_field(legacy, 'image', rel)

        self.stdout.write('\n── Product Subcategories ──')
        for subcategory in Category.objects.exclude(parent__isnull=True).select_related('parent').order_by('parent__name', 'name'):
            query = SUBCATEGORY_QUERIES.get(
                subcategory.name,
                f'{subcategory.name} pharmacy medicine health products',
            )
            rel = f'categories/{subcategory.slug}.jpg'
            ok = self._get_and_save(query, rel, f'{subcategory.parent.name} / {subcategory.name}', force)
            if ok:
                self._update_image_field(subcategory, 'image', rel)

    def _fetch_health_concerns(self, force: bool):
        from apps.products.models import HealthConcern
        self.stdout.write('\n── Health Concerns ──')
        for hc in HealthConcern.objects.all():
            query = HEALTH_CONCERN_QUERIES.get(hc.name, f'{hc.name} medicine treatment health')
            rel = f'health_concerns/{hc.slug}.jpg'
            ok = self._get_and_save(query, rel, hc.name, force)
            if ok:
                self._update_image_field(hc, 'image', rel)

    def _fetch_brands(self, force: bool):
        from apps.products.models import Brand
        self.stdout.write('\n── Brands ──')
        for brand in Brand.objects.all():
            curated_url = BRAND_LOGO_URLS.get(brand.name)
            rel = f'brands/{brand.slug}{_preferred_extension_for_url(curated_url)}' if curated_url else f'brands/{brand.slug}.jpg'
            ok = False
            if curated_url:
                self.stdout.write(f'  GET   {brand.name} → curated logo')
                ok = _download(curated_url, _media(rel))
                if ok:
                    size_kb = os.path.getsize(_media(rel)) // 1024
                    self.stdout.write(self.style.SUCCESS(f'        ✓ {size_kb}KB'))
                    time.sleep(0.2)
            if not ok:
                query = BRAND_QUERIES.get(brand.name, f'{brand.name} pharmaceutical medicine')
                rel = f'brands/{brand.slug}.jpg'
                ok = self._get_and_save(query, rel, brand.name, force)
            if ok:
                self._update_image_field(brand, 'logo', rel)

    def _fetch_products(self, force: bool):
        from apps.products.models import Product
        self.stdout.write('\n── Products ──')
        for product in Product.objects.all():
            query = PRODUCT_QUERIES.get(
                product.name,
                f'{product.name} {product.strength} medicine pharmacy'.strip(),
            )
            rel = f'products/{product.slug[:80]}.jpg'
            ok = self._get_and_save(query, rel, product.name, force)
            if ok:
                self._update_image_field(product, 'image', rel)
