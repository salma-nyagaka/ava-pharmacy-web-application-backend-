from django.core.management.base import BaseCommand
from django.utils.text import slugify
from decimal import Decimal


class Command(BaseCommand):
    help = 'Seed the database with initial data for all apps'

    def handle(self, *args, **options):
        self.stdout.write('Seeding database...')
        self._seed_users()
        self._seed_categories()
        self._seed_brands()
        self._seed_products()
        self._seed_lab_tests()
        self._seed_doctors()
        self._seed_banners()
        self._seed_promotions()
        self._seed_payout_rules()
        self.stdout.write(self.style.SUCCESS('Database seeded successfully.'))

    def _seed_users(self):
        from apps.accounts.models import Customer, User, Pharmacist
        users = [
            {'email': 'admin@avapharmacy.com', 'first_name': 'Ava', 'last_name': 'Admin', 'role': 'admin', 'is_staff': True, 'is_superuser': True},
            {'email': 'pharmacist@avapharmacy.com', 'first_name': 'Jane', 'last_name': 'Mwangi', 'role': 'pharmacist'},
            {'email': 'doctor@avapharmacy.com', 'first_name': 'Dr. James', 'last_name': 'Kariuki', 'role': 'doctor'},
            {'email': 'pediatrician@avapharmacy.com', 'first_name': 'Dr. Amina', 'last_name': 'Hassan', 'role': 'pediatrician'},
            {'email': 'labtech@avapharmacy.com', 'first_name': 'Kevin', 'last_name': 'Omondi', 'role': 'lab_technician'},
            {'email': 'customer@avapharmacy.com', 'first_name': 'Alice', 'last_name': 'Wanjiru', 'role': 'customer'},
        ]
        for u in users:
            if not User.objects.filter(email=u['email']).exists():
                extra = {k: v for k, v in u.items() if k not in ('email',)}
                user = User.objects.create_user(email=u['email'], password='Test@1234', **extra)
                if user.role == 'pharmacist':
                    Pharmacist.objects.get_or_create(user=user)
                if user.role == 'customer':
                    Customer.objects.get_or_create(user=user)
                self.stdout.write(f'  Created user: {u["email"]}')

    def _seed_categories(self):
        from apps.products.models import Category
        categories = [
            {'name': 'Medicines', 'slug': 'medicines', 'icon': '💊', 'subs': [
                'Prescription Medicines', 'Over the Counter', 'Vitamins & Supplements', 'Antibiotics',
            ]},
            {'name': 'Personal Care', 'slug': 'personal-care', 'icon': '🧴', 'subs': [
                'Skin Care', 'Hair Care', 'Dental Care', 'Eye Care',
            ]},
            {'name': 'Medical Devices', 'slug': 'medical-devices', 'icon': '🩺', 'subs': [
                'Blood Pressure Monitors', 'Glucometers', 'Thermometers',
            ]},
            {'name': 'Baby & Mother', 'slug': 'baby-mother', 'icon': '👶', 'subs': [
                'Baby Care', 'Maternity', 'Baby Nutrition',
            ]},
        ]
        for c in categories:
            parent, _ = Category.objects.get_or_create(
                slug=c['slug'],
                defaults={'name': c['name'], 'icon': c.get('icon', '')}
            )
            for sub_name in c.get('subs', []):
                sub_slug = slugify(sub_name)
                Category.objects.get_or_create(
                    slug=sub_slug,
                    defaults={'name': sub_name, 'parent': parent}
                )
        self.stdout.write('  Categories seeded.')

    def _seed_brands(self):
        from apps.products.models import Brand
        brands = [
            'Panadol', 'Cipla', 'Reckitt', 'GSK', 'Abbott', 'Novartis',
            'Pfizer', 'Johnson & Johnson', 'Bayer', 'Sanofi',
        ]
        for name in brands:
            Brand.objects.get_or_create(name=name, defaults={'slug': slugify(name)})
        self.stdout.write('  Brands seeded.')

    def _seed_products(self):
        from apps.products.models import Product, Category, Brand
        try:
            medicines_cat = Category.objects.get(slug='medicines')
            otc_cat = Category.objects.get(slug='over-the-counter')
            vitamins_cat = Category.objects.get(slug='vitamins-supplements')
            panadol_brand = Brand.objects.get(name='Panadol')
            cipla_brand = Brand.objects.get(name='Cipla')
            reckitt_brand = Brand.objects.get(name='Reckitt')
        except Category.DoesNotExist:
            self.stdout.write(self.style.WARNING('  Categories not found. Run seed_categories first.'))
            return

        products = [
            {
                'sku': 'MED-001', 'slug': 'panadol-500mg-tablets-24',
                'name': 'Panadol 500mg Tablets 24s', 'brand': panadol_brand,
                'category': otc_cat, 'price': Decimal('150.00'), 'discount_price': Decimal('120.00'),
                'stock_source': 'branch', 'stock_quantity': 150,
                'short_description': 'Effective pain and fever relief',
                'description': 'Panadol 500mg tablets provide fast, effective relief from pain and fever.',
                'features': ['Fast-acting formula', 'Gentle on stomach', 'Suitable for adults'],
                'badge': 'Best Seller',
            },
            {
                'sku': 'MED-002', 'slug': 'amoxicillin-500mg-capsules',
                'name': 'Amoxicillin 500mg Capsules 21s', 'brand': cipla_brand,
                'category': medicines_cat, 'price': Decimal('450.00'),
                'stock_source': 'warehouse', 'stock_quantity': 200,
                'requires_prescription': True,
                'short_description': 'Broad-spectrum antibiotic',
                'description': 'Amoxicillin is a penicillin antibiotic used to treat bacterial infections.',
                'features': ['Broad-spectrum coverage', 'Prescription required'],
                'badge': '',
            },
            {
                'sku': 'VIT-001', 'slug': 'vitamin-c-1000mg-effervescent',
                'name': 'Vitamin C 1000mg Effervescent 20s', 'brand': reckitt_brand,
                'category': vitamins_cat, 'price': Decimal('420.00'), 'discount_price': Decimal('350.00'),
                'stock_source': 'branch', 'stock_quantity': 80,
                'short_description': 'Immune system support with vitamin C',
                'description': 'Vitamin C 1000mg effervescent tablets support the immune system and provide antioxidant protection.',
                'features': ['High dose vitamin C', 'Easy to take effervescent form', 'Orange flavour'],
                'badge': 'Sale',
            },
            {
                'sku': 'MED-003', 'slug': 'ibuprofen-400mg-tablets-24',
                'name': 'Ibuprofen 400mg Tablets 24s', 'brand': cipla_brand,
                'category': otc_cat, 'price': Decimal('180.00'),
                'stock_source': 'branch', 'stock_quantity': 120,
                'short_description': 'Anti-inflammatory pain relief',
                'description': 'Ibuprofen 400mg provides relief from pain, fever and inflammation.',
                'features': ['Anti-inflammatory', 'Pain and fever relief', 'Fast-acting'],
                'badge': '',
            },
            {
                'sku': 'VIT-002', 'slug': 'multivitamins-adults-30-tablets',
                'name': 'Complete Multivitamins Adults 30s', 'brand': reckitt_brand,
                'category': vitamins_cat, 'price': Decimal('650.00'),
                'stock_source': 'warehouse', 'stock_quantity': 60,
                'short_description': 'Daily complete nutrition support',
                'description': 'Complete multivitamins for adults providing essential vitamins and minerals for daily health.',
                'features': ['23 vitamins and minerals', 'Once daily', 'Suitable for men and women'],
                'badge': 'New',
            },
        ]

        for p in products:
            if not Product.objects.filter(sku=p['sku']).exists():
                Product.objects.create(**p)
        self.stdout.write('  Products seeded.')

    def _seed_lab_tests(self):
        from apps.lab.models import LabTest
        tests = [
            {'name': 'Complete Blood Count (CBC)', 'category': 'blood', 'price': Decimal('800.00'), 'turnaround': '24 hours', 'sample_type': 'Blood', 'description': 'Comprehensive blood panel measuring red and white blood cells, hemoglobin, and platelets.'},
            {'name': 'Blood Glucose Fasting', 'category': 'metabolic', 'price': Decimal('350.00'), 'turnaround': '4 hours', 'sample_type': 'Blood', 'description': 'Measures blood sugar levels after fasting. Used to diagnose or monitor diabetes.'},
            {'name': 'Lipid Profile', 'category': 'cardiac', 'price': Decimal('1200.00'), 'turnaround': '24 hours', 'sample_type': 'Blood', 'description': 'Measures cholesterol and triglyceride levels to assess cardiovascular risk.'},
            {'name': 'HIV Rapid Test', 'category': 'infectious', 'price': Decimal('500.00'), 'turnaround': '30 minutes', 'sample_type': 'Blood', 'description': 'Rapid screening test for HIV antibodies.'},
            {'name': 'Liver Function Test (LFT)', 'category': 'wellness', 'price': Decimal('1500.00'), 'turnaround': '24 hours', 'sample_type': 'Blood', 'description': 'Evaluates how well the liver is working by measuring enzymes and proteins.'},
            {'name': 'Kidney Function Test (KFT)', 'category': 'wellness', 'price': Decimal('1200.00'), 'turnaround': '24 hours', 'sample_type': 'Blood', 'description': 'Assesses kidney health by measuring creatinine, urea, and electrolytes.'},
            {'name': 'Thyroid Function Test (TFT)', 'category': 'wellness', 'price': Decimal('2000.00'), 'turnaround': '48 hours', 'sample_type': 'Blood', 'description': 'Measures TSH, T3, and T4 to evaluate thyroid function.'},
            {'name': 'Malaria Rapid Test', 'category': 'infectious', 'price': Decimal('400.00'), 'turnaround': '30 minutes', 'sample_type': 'Blood', 'description': 'Rapid diagnostic test for malaria parasites.'},
            {'name': 'Urine Analysis (Urinalysis)', 'category': 'wellness', 'price': Decimal('300.00'), 'turnaround': '2 hours', 'sample_type': 'Urine', 'description': 'Comprehensive urine examination to detect various kidney and metabolic disorders.'},
            {'name': 'Electrocardiogram (ECG)', 'category': 'cardiac', 'price': Decimal('1800.00'), 'turnaround': '1 hour', 'sample_type': 'Non-invasive', 'description': 'Records the electrical activity of the heart to detect cardiac abnormalities.'},
        ]
        for t in tests:
            if not LabTest.objects.filter(name=t['name']).exists():
                LabTest.objects.create(**t)
        self.stdout.write('  Lab tests seeded.')

    def _seed_doctors(self):
        from apps.accounts.models import User
        from apps.consultations.models import ClinicianProfile
        doctors = [
            {
                'name': 'Dr. James Kariuki', 'specialty': 'General Practice',
                'email': 'doctor@avapharmacy.com', 'phone': '0712345678',
                'license_number': 'KMD-12345', 'facility': 'Aga Khan Hospital',
                'availability': 'Mon-Fri 8am-6pm', 'languages': ['English', 'Swahili'],
                'status': 'active', 'consult_fee': Decimal('500.00'), 'rating': Decimal('4.8'),
            },
            {
                'name': 'Dr. Peter Otieno', 'specialty': 'Cardiology',
                'email': 'peter.otieno@avapharmacy.com', 'phone': '0734567890',
                'license_number': 'KMD-11111', 'facility': 'Karen Hospital',
                'availability': 'Tue-Thu 10am-4pm', 'languages': ['English', 'Luo'],
                'status': 'active', 'consult_fee': Decimal('800.00'), 'rating': Decimal('4.7'),
            },
        ]
        pediatricians = [
            {
                'name': 'Dr. Amina Hassan', 'specialty': 'Pediatrics',
                'email': 'pediatrician@avapharmacy.com', 'phone': '0798765432',
                'license_number': 'KMD-67890', 'facility': 'Nairobi Hospital',
                'availability': 'Mon-Sat 9am-5pm', 'languages': ['English', 'Swahili', 'Somali'],
                'status': 'active', 'consult_fee': Decimal('600.00'), 'rating': Decimal('4.9'),
            },
        ]
        for d in doctors:
            if not ClinicianProfile.objects.doctors().filter(email=d['email']).exists():
                user = User.objects.filter(email=d['email']).first()
                profile = ClinicianProfile.objects.create(provider_type=ClinicianProfile.TYPE_DOCTOR, **d)
                if user:
                    profile.user = user
                    profile.save()
        for d in pediatricians:
            if not ClinicianProfile.objects.pediatricians().filter(email=d['email']).exists():
                user = User.objects.filter(email=d['email']).first()
                profile = ClinicianProfile.objects.create(provider_type=ClinicianProfile.TYPE_PEDIATRICIAN, **d)
                if user:
                    profile.user = user
                    profile.save()
        self.stdout.write('  Doctors seeded.')

    def _seed_banners(self):
        from apps.products.models import Banner
        banners = [
            {'message': 'Free delivery on orders above KSh 3,000!', 'link': '/products', 'status': 'active'},
            {'message': 'Get 15% off your first prescription. Use code: FIRSTRX', 'link': '/prescriptions', 'status': 'active'},
            {'message': 'Teleconsultation available 24/7 - Book now', 'link': '/doctor-consultation', 'status': 'active'},
        ]
        for b in banners:
            if not Banner.objects.filter(message=b['message']).exists():
                Banner.objects.create(**b)
        self.stdout.write('  Banners seeded.')

    def _seed_promotions(self):
        from apps.products.models import Promotion
        from django.utils import timezone
        import datetime
        today = timezone.now().date()
        end_date = today + datetime.timedelta(days=30)
        promotions = [
            {
                'title': 'Summer Health Sale', 'type': 'percentage', 'value': Decimal('15.00'),
                'scope': 'all', 'targets': [], 'badge': 'SALE',
                'start_date': today, 'end_date': end_date, 'status': 'active',
            },
            {
                'title': 'Vitamins & Supplements Offer', 'type': 'percentage', 'value': Decimal('20.00'),
                'scope': 'category', 'targets': ['vitamins-supplements'], 'badge': '20% OFF',
                'start_date': today, 'end_date': end_date, 'status': 'active',
            },
        ]
        for p in promotions:
            if not Promotion.objects.filter(title=p['title']).exists():
                Promotion.objects.create(**p)
        self.stdout.write('  Promotions seeded.')

    def _seed_payout_rules(self):
        from apps.payouts.models import PayoutRule
        rules = [
            {'role': 'doctor', 'amount': Decimal('500.00'), 'currency': 'KSh', 'is_active': True},
            {'role': 'pediatrician', 'amount': Decimal('600.00'), 'currency': 'KSh', 'is_active': True},
            {'role': 'pharmacist', 'amount': Decimal('300.00'), 'currency': 'KSh', 'is_active': True},
            {'role': 'lab_partner', 'amount': Decimal('400.00'), 'currency': 'KSh', 'is_active': True},
        ]
        for r in rules:
            PayoutRule.objects.get_or_create(role=r['role'], defaults=r)
        self.stdout.write('  Payout rules seeded.')
