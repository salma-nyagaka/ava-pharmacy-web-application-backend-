"""
Management command: seed_catalog

Wipes and re-seeds ProductCategory, ProductSubcategory, HealthConcern,
Brand, and Product tables with realistic pharmacy data (Kenya market).
Downloads high-quality images from picsum.photos CDN.
"""

import os
import urllib.request
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils.text import slugify


HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
        'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    ),
    'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
    'Referer': 'https://unsplash.com/',
    'sec-fetch-dest': 'image',
    'sec-fetch-mode': 'no-cors',
    'sec-fetch-site': 'cross-site',
}


def _download_image(url: str, dest_path: str) -> bool:
    """Download image to dest_path. Returns True on success."""
    try:
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = resp.read()
        with open(dest_path, 'wb') as f:
            f.write(data)
        return True
    except Exception as exc:
        return False


def _media(rel: str) -> str:
    return str(Path(settings.MEDIA_ROOT) / rel)


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------

CATEGORIES = [
    {
        'name': 'Prescription Medicines',
        'icon': '💊',
        'description': 'Dispensed only on presentation of a valid prescription from a licensed practitioner.',
        'img_seed': 'rx-medicine',
        'subcategories': [
            ('Antibiotics', 'Broad- and narrow-spectrum antibacterial agents for treating infections.'),
            ('Cardiovascular', 'Medicines for heart disease, hypertension, and cholesterol management.'),
            ('Diabetes Management', 'Oral hypoglycaemics, insulin formulations, and adjunct therapies.'),
            ('Mental Health', 'Antidepressants, anxiolytics, antipsychotics, and mood stabilisers.'),
            ('Respiratory', 'Bronchodilators, inhaled corticosteroids, and COPD management medicines.'),
            ('Pain Management', 'Opioid and non-opioid analgesics for moderate to severe pain.'),
        ],
    },
    {
        'name': 'Over-the-Counter Medicines',
        'icon': '🏥',
        'description': 'Safe, effective medicines available without a prescription for common ailments.',
        'img_seed': 'otc-pharmacy',
        'subcategories': [
            ('Pain Relief', 'Paracetamol, ibuprofen, and aspirin for headaches, fever, and body pain.'),
            ('Cough & Cold', 'Decongestants, expectorants, antihistamines, and throat lozenges.'),
            ('Digestive Health', 'Antacids, antidiarrhoeals, oral rehydration salts, and laxatives.'),
            ('Allergy & Sinus', 'Antihistamines and nasal sprays for hay fever, urticaria, and allergies.'),
            ('Skin Treatment', 'Antifungals, antiseptics, wound creams, and topical antibiotics.'),
            ('Eye & Ear Care', 'Eye drops, ear drops, and lubricants for infections and dryness.'),
        ],
    },
    {
        'name': 'Vitamins & Supplements',
        'icon': '💪',
        'description': 'Nutritional supplements to support immunity, energy, bone health, and general wellbeing.',
        'img_seed': 'vitamins-supplements',
        'subcategories': [
            ('Multivitamins', 'Complete daily vitamin and mineral formulas for men, women, and children.'),
            ('Vitamin C & D', 'Immune-boosting vitamin C and bone-supporting vitamin D supplements.'),
            ('Iron & Minerals', 'Iron, calcium, magnesium, and zinc supplements for deficiency management.'),
            ('Omega-3 & Fish Oil', 'Omega-3 fatty acids for heart, brain, and joint health.'),
            ('Probiotics', 'Live beneficial bacteria to restore and maintain gut flora balance.'),
            ('Pregnancy Support', 'Prenatal vitamins, folic acid, and supplements for maternal health.'),
        ],
    },
    {
        'name': 'Personal Care',
        'icon': '🧴',
        'description': 'Skincare, haircare, dental hygiene, and body care products for daily wellness.',
        'img_seed': 'personal-care',
        'subcategories': [
            ('Skin Care', 'Cleansers, moisturisers, sunscreens, and treatment creams.'),
            ('Hair Care', 'Medicated shampoos, conditioners, and scalp treatments.'),
            ('Dental Care', 'Toothpastes, mouthwashes, dental floss, and sensitivity treatments.'),
            ('Feminine Hygiene', 'Intimate washes, sanitary pads, and feminine care essentials.'),
            ('Sun Protection', 'SPF sunscreens, after-sun care, and UV-protective moisturisers.'),
        ],
    },
    {
        'name': 'Baby & Mother Care',
        'icon': '👶',
        'description': 'Premium nutrition, skincare, and health products for infants and expectant mothers.',
        'img_seed': 'baby-care',
        'subcategories': [
            ('Baby Nutrition', 'Infant formula, follow-on milk, and weaning cereals.'),
            ('Baby Skincare', 'Gentle lotions, powders, bath products, and nappy creams.'),
            ('Maternity', 'Prenatal vitamins, stretch mark creams, and maternity supports.'),
            ('Immunisation Supplies', 'Syringes, swabs, and cold-chain accessories for vaccination.'),
        ],
    },
    {
        'name': 'Medical Devices & Equipment',
        'icon': '🩺',
        'description': 'Diagnostic devices, monitoring equipment, and wound care supplies for home and clinical use.',
        'img_seed': 'medical-devices',
        'subcategories': [
            ('Blood Pressure Monitors', 'Upper-arm and wrist digital BP monitors for home monitoring.'),
            ('Glucometers & Strips', 'Blood glucose monitors, test strips, and lancets for diabetes care.'),
            ('Thermometers', 'Digital, infrared, and ear thermometers for accurate temperature measurement.'),
            ('Nebulisers', 'Compressor and mesh nebulisers for inhaled medication delivery.'),
            ('Wound Care Supplies', 'Sterile dressings, bandages, adhesive plasters, and surgical tapes.'),
        ],
    },
    {
        'name': 'Herbal & Alternative Medicine',
        'icon': '🌿',
        'description': 'Herbal remedies, homeopathic preparations, and traditional plant-based medicines.',
        'img_seed': 'herbal-medicine',
        'subcategories': [
            ('Herbal Remedies', 'Standardised herbal extracts for common conditions.'),
            ('Homeopathic Medicines', 'Highly diluted preparations used in homeopathic practice.'),
            ('Traditional African Medicine', 'Scientifically assessed traditional plant medicines used across Africa.'),
        ],
    },
]

HEALTH_CONCERNS = [
    ('Malaria', 'mdi-mosquito', 'Prevention and treatment of malaria caused by Plasmodium parasites.'),
    ('Diabetes', 'mdi-diabetes', 'Management of Type 1 and Type 2 diabetes mellitus and pre-diabetes.'),
    ('Hypertension', 'mdi-heart-pulse', 'Control of elevated blood pressure to prevent cardiovascular events.'),
    ('HIV/AIDS', 'mdi-ribbon', 'Antiretroviral therapy, opportunistic infection management, and prevention.'),
    ('Tuberculosis', 'mdi-lungs', 'First-line and second-line TB treatment and prophylaxis.'),
    ('Typhoid Fever', 'mdi-thermometer', 'Antibiotic treatment and supportive care for Salmonella typhi infection.'),
    ('Anaemia', 'mdi-blood-bag', 'Iron, folate, and B12 supplementation for anaemia correction.'),
    ('Respiratory Infections', 'mdi-lungs', 'Antibiotics, bronchodilators, and supportive care for RTIs.'),
    ('Heart Disease', 'mdi-heart', 'Statins, antiplatelets, and antihypertensives for cardiac protection.'),
    ('Cancer Support', 'mdi-ribbon-variant', 'Antiemetics, pain relief, and nutritional support for oncology patients.'),
    ('Kidney Disease', 'mdi-kidney', 'Phosphate binders, erythropoietin stimulants, and renal diet supplements.'),
    ('Mental Health & Depression', 'mdi-brain', 'Antidepressants, anxiolytics, and psychosocial support.'),
    ("Women's Health", 'mdi-gender-female', 'Hormonal therapies, family planning, and gynaecological treatments.'),
    ('Child Health', 'mdi-baby-face', 'Paediatric formulations, growth support, and immunisation.'),
    ('Arthritis & Joint Pain', 'mdi-bone', 'NSAIDs, DMARDs, and supplements for arthritis and joint inflammation.'),
    ('Skin Conditions', 'mdi-skin', 'Topical and systemic treatments for eczema, acne, psoriasis, and fungal infections.'),
    ('Digestive Disorders', 'mdi-stomach', 'Treatments for GERD, IBS, ulcers, constipation, and diarrhoea.'),
    ('Eye Health', 'mdi-eye', 'Eye drops, lubricants, and vitamins for glaucoma, dry eyes, and infections.'),
    ('Sexual & Reproductive Health', 'mdi-heart-plus', 'Contraceptives, STI treatments, and fertility support.'),
    ('Cholesterol Management', 'mdi-chart-line', 'Statins, fibrates, and dietary supplements to reduce LDL cholesterol.'),
]

BRANDS = [
    {
        'name': 'Pfizer',
        'description': 'One of the world\'s largest pharmaceutical companies, known for innovative medicines and vaccines including Lipitor, Zithromax, and COVID-19 vaccines.',
        'img_seed': 'pfizer-pharma',
    },
    {
        'name': 'GSK',
        'description': 'GlaxoSmithKline — a global healthcare company producing medicines, vaccines, and consumer health products including Augmentin, Panadol, and Sensodyne.',
        'img_seed': 'gsk-pharmaceutical',
    },
    {
        'name': 'Novartis',
        'description': 'Swiss multinational pharmaceutical company renowned for innovative medicines in oncology, immunology, and cardiovascular disease.',
        'img_seed': 'novartis-medicine',
    },
    {
        'name': 'Sanofi',
        'description': 'French global healthcare company with a strong presence in diabetes, vaccines, and consumer healthcare across Africa and Europe.',
        'img_seed': 'sanofi-pharma',
    },
    {
        'name': 'Abbott',
        'description': 'Global healthcare company with products ranging from diagnostics, nutritionals (Similac, Ensure), and established pharmaceuticals.',
        'img_seed': 'abbott-laboratories',
    },
    {
        'name': 'Bayer',
        'description': 'German pharmaceutical and life sciences company best known for Aspirin, Ciprobay, and consumer health products.',
        'img_seed': 'bayer-pharma',
    },
    {
        'name': 'AstraZeneca',
        'description': 'British-Swedish multinational specialising in oncology, cardiovascular, and respiratory medicines, with major operations in Africa.',
        'img_seed': 'astrazeneca-medicine',
    },
    {
        'name': 'Cipla',
        'description': 'Indian generics manufacturer and one of the largest suppliers of affordable ARV therapy to sub-Saharan Africa.',
        'img_seed': 'cipla-generic',
    },
    {
        'name': 'Cosmos Limited',
        'description': 'Kenya-based pharmaceutical manufacturer producing quality generic medicines and healthcare products for East African markets.',
        'img_seed': 'cosmos-kenya',
    },
    {
        'name': 'Dawa Limited',
        'description': 'Kenyan manufacturer of affordable essential medicines, ORS, and generic formulations distributed across East Africa.',
        'img_seed': 'dawa-pharma',
    },
    {
        'name': 'Beta Healthcare',
        'description': 'Kenyan pharmaceutical company manufacturing intravenous fluids, antacids, and essential medicines for the local market.',
        'img_seed': 'beta-healthcare',
    },
    {
        'name': 'Strides Pharma',
        'description': 'Indian multinational with a significant African footprint, supplying anti-malarials, ARVs, and sterile injectables.',
        'img_seed': 'strides-pharma',
    },
]

# Each product: name, sku, strength, brand_name, category_name, subcategory_name,
# price, cost_price, discount_price, stock_qty, requires_prescription, is_featured,
# dosage_quantity, dosage_unit, dosage_frequency, dosage_notes,
# short_description, description, features, health_concern_names, img_seed
PRODUCTS = [
    # ── PRESCRIPTION: Antibiotics ───────────────────────────────────────────
    {
        'name': 'Amoxicillin 500mg Capsules',
        'sku': 'RX-AB-001',
        'strength': '500mg',
        'brand': 'Cipla',
        'category': 'Prescription Medicines',
        'subcategory': 'Antibiotics',
        'price': Decimal('450.00'),
        'cost_price': Decimal('280.00'),
        'discount_price': None,
        'stock_qty': 320,
        'requires_prescription': True,
        'is_featured': False,
        'dosage_quantity': '1',
        'dosage_unit': 'capsule',
        'dosage_frequency': 'three_times_daily',
        'dosage_notes': 'Complete the full course. Take with or without food.',
        'short_description': 'Broad-spectrum penicillin antibiotic for bacterial infections.',
        'description': (
            'Amoxicillin 500mg capsules are a widely used broad-spectrum penicillin antibiotic. '
            'Effective against a wide range of gram-positive and gram-negative bacteria. '
            'Commonly prescribed for respiratory tract infections, urinary tract infections, '
            'skin infections, otitis media, and dental abscesses. It is also used in '
            'combination therapy for H. pylori eradication. Always complete the full course '
            'to prevent antibiotic resistance.'
        ),
        'features': [
            'Broad-spectrum penicillin antibiotic',
            'Effective for respiratory, urinary, and skin infections',
            'Available as easy-to-swallow capsules',
            'WHO Essential Medicine',
        ],
        'health_concerns': ['Respiratory Infections', 'Skin Conditions'],
        'img_seed': 'amoxicillin-capsules',
    },
    {
        'name': 'Co-Amoxiclav 625mg Tablets',
        'sku': 'RX-AB-002',
        'strength': '500mg/125mg',
        'brand': 'GSK',
        'category': 'Prescription Medicines',
        'subcategory': 'Antibiotics',
        'price': Decimal('1850.00'),
        'cost_price': Decimal('1200.00'),
        'discount_price': None,
        'stock_qty': 140,
        'requires_prescription': True,
        'is_featured': False,
        'dosage_quantity': '1',
        'dosage_unit': 'tablet',
        'dosage_frequency': 'twice_daily',
        'dosage_notes': 'Take at the start of a meal to reduce gastrointestinal side effects.',
        'short_description': 'Augmentin — amoxicillin + clavulanate for resistant infections.',
        'description': (
            'Co-Amoxiclav 625mg (brand name Augmentin) combines amoxicillin with the '
            'beta-lactamase inhibitor clavulanic acid to overcome antibiotic resistance. '
            'Used for severe or recurrent infections of the respiratory tract, sinuses, '
            'ear, skin, and soft tissue, as well as urinary tract infections and animal bites. '
            'The addition of clavulanate extends amoxicillin\'s spectrum to cover '
            'beta-lactamase-producing organisms including Staphylococcus aureus and '
            'Klebsiella species.'
        ),
        'features': [
            'Beta-lactamase inhibitor combination',
            'Extends spectrum to resistant organisms',
            'Used for bite wounds, sinusitis, and complicated UTIs',
            'Reduced GI side effects when taken with food',
        ],
        'health_concerns': ['Respiratory Infections'],
        'img_seed': 'coamoxiclav-tablets',
    },
    {
        'name': 'Ciprofloxacin 500mg Tablets',
        'sku': 'RX-AB-003',
        'strength': '500mg',
        'brand': 'Cipla',
        'category': 'Prescription Medicines',
        'subcategory': 'Antibiotics',
        'price': Decimal('680.00'),
        'cost_price': Decimal('400.00'),
        'discount_price': None,
        'stock_qty': 210,
        'requires_prescription': True,
        'is_featured': False,
        'dosage_quantity': '1',
        'dosage_unit': 'tablet',
        'dosage_frequency': 'twice_daily',
        'dosage_notes': 'Drink plenty of fluids. Avoid antacids within 2 hours of dose.',
        'short_description': 'Fluoroquinolone antibiotic for UTIs, typhoid, and enteric infections.',
        'description': (
            'Ciprofloxacin 500mg is a broad-spectrum fluoroquinolone antibiotic highly '
            'effective against gram-negative bacteria. It is the first-line treatment for '
            'uncomplicated typhoid fever, urinary tract infections, traveller\'s diarrhoea, '
            'and certain respiratory infections. Also used for surgical prophylaxis and '
            'treatment of anthrax exposure. Patients should maintain good hydration and '
            'avoid calcium-rich foods and antacids within two hours of dosing.'
        ),
        'features': [
            'First-line for typhoid fever in Kenya',
            'Effective for complicated UTIs and traveller\'s diarrhoea',
            'Broad-spectrum fluoroquinolone',
            'Available as film-coated tablets for easy swallowing',
        ],
        'health_concerns': ['Typhoid Fever', 'Respiratory Infections'],
        'img_seed': 'ciprofloxacin-500',
    },
    {
        'name': 'Metronidazole 400mg Tablets',
        'sku': 'RX-AB-004',
        'strength': '400mg',
        'brand': 'Cosmos Limited',
        'category': 'Prescription Medicines',
        'subcategory': 'Antibiotics',
        'price': Decimal('280.00'),
        'cost_price': Decimal('160.00'),
        'discount_price': None,
        'stock_qty': 280,
        'requires_prescription': True,
        'is_featured': False,
        'dosage_quantity': '1',
        'dosage_unit': 'tablet',
        'dosage_frequency': 'three_times_daily',
        'dosage_notes': 'Avoid alcohol completely during treatment. Take with or after food.',
        'short_description': 'Nitroimidazole antibiotic for anaerobic and protozoal infections.',
        'description': (
            'Metronidazole 400mg is an antimicrobial agent with potent activity against '
            'anaerobic bacteria and protozoa including Trichomonas vaginalis, Giardia lamblia, '
            'and Entamoeba histolytica. Commonly prescribed for amoebic dysentery, dental '
            'infections, pelvic inflammatory disease, and surgical prophylaxis. '
            'Absolute contraindication with alcohol due to disulfiram-like reaction.'
        ),
        'features': [
            'Active against anaerobic bacteria and protozoa',
            'Used for amoebic dysentery and giardiasis',
            'First-line for bacterial vaginosis and trichomoniasis',
            'Essential medicine — affordable and widely available',
        ],
        'health_concerns': ['Digestive Disorders'],
        'img_seed': 'metronidazole-tabs',
    },
    # ── PRESCRIPTION: Cardiovascular ───────────────────────────────────────
    {
        'name': 'Amlodipine 5mg Tablets',
        'sku': 'RX-CV-001',
        'strength': '5mg',
        'brand': 'Pfizer',
        'category': 'Prescription Medicines',
        'subcategory': 'Cardiovascular',
        'price': Decimal('520.00'),
        'cost_price': Decimal('300.00'),
        'discount_price': None,
        'stock_qty': 190,
        'requires_prescription': True,
        'is_featured': False,
        'dosage_quantity': '1',
        'dosage_unit': 'tablet',
        'dosage_frequency': 'once_daily',
        'dosage_notes': 'Can be taken with or without food. Take at the same time each day.',
        'short_description': 'Calcium channel blocker for hypertension and angina.',
        'description': (
            'Amlodipine 5mg is a long-acting calcium channel blocker used as first-line '
            'therapy for hypertension and stable angina pectoris. By relaxing arterial '
            'smooth muscle, it reduces peripheral vascular resistance and cardiac workload. '
            'Its 35–50 hour half-life provides steady 24-hour blood pressure control with '
            'once-daily dosing. Well tolerated in elderly patients and safe in asthma. '
            'Monitor for ankle oedema and flushing during initiation.'
        ),
        'features': [
            'Once-daily dosing for patient compliance',
            '24-hour blood pressure control',
            'Safe in asthma and COPD',
            'Reduces risk of cardiovascular events',
        ],
        'health_concerns': ['Hypertension', 'Heart Disease'],
        'img_seed': 'amlodipine-bp',
    },
    {
        'name': 'Losartan 50mg Tablets',
        'sku': 'RX-CV-002',
        'strength': '50mg',
        'brand': 'Cipla',
        'category': 'Prescription Medicines',
        'subcategory': 'Cardiovascular',
        'price': Decimal('480.00'),
        'cost_price': Decimal('270.00'),
        'discount_price': None,
        'stock_qty': 160,
        'requires_prescription': True,
        'is_featured': False,
        'dosage_quantity': '1',
        'dosage_unit': 'tablet',
        'dosage_frequency': 'once_daily',
        'dosage_notes': 'Monitor potassium levels. Avoid potassium supplements unless prescribed.',
        'short_description': 'ARB antihypertensive with renoprotective properties.',
        'description': (
            'Losartan 50mg is an angiotensin II receptor blocker (ARB) used in the '
            'management of hypertension, diabetic nephropathy, and heart failure. Unlike '
            'ACE inhibitors, it does not cause dry cough. It has demonstrated '
            'renoprotective effects in type 2 diabetic patients with proteinuria and '
            'reduces the risk of stroke in hypertensive patients with left ventricular '
            'hypertrophy. Suitable for patients intolerant to ACE inhibitors.'
        ),
        'features': [
            'No dry cough side effect (vs ACE inhibitors)',
            'Renoprotective in diabetic nephropathy',
            'Reduces stroke risk in LVH patients',
            'Once-daily dosing',
        ],
        'health_concerns': ['Hypertension', 'Kidney Disease', 'Diabetes'],
        'img_seed': 'losartan-arb',
    },
    {
        'name': 'Atorvastatin 20mg Tablets',
        'sku': 'RX-CV-003',
        'strength': '20mg',
        'brand': 'Pfizer',
        'category': 'Prescription Medicines',
        'subcategory': 'Cardiovascular',
        'price': Decimal('890.00'),
        'cost_price': Decimal('560.00'),
        'discount_price': None,
        'stock_qty': 130,
        'requires_prescription': True,
        'is_featured': True,
        'dosage_quantity': '1',
        'dosage_unit': 'tablet',
        'dosage_frequency': 'once_daily',
        'dosage_notes': 'Take at the same time each evening. Report any muscle pain immediately.',
        'short_description': 'Statin for cholesterol reduction and cardiovascular risk prevention.',
        'description': (
            'Atorvastatin 20mg (brand name Lipitor) is the world\'s best-selling statin '
            'and cornerstone of cardiovascular risk management. It lowers LDL cholesterol '
            'by 39–43% and reduces triglycerides by 19–26%. Indicated for primary '
            'hypercholesterolaemia, mixed dyslipidaemia, and prevention of cardiovascular '
            'events in high-risk patients including those with diabetes, hypertension, '
            'or prior myocardial infarction. Take at night for maximum efficacy. '
            'Monitor liver enzymes and creatine kinase periodically.'
        ),
        'features': [
            'Reduces LDL cholesterol by up to 43%',
            'Prevents heart attack and stroke in high-risk patients',
            'Once-daily evening dosing',
            'Evidence-based cardiovascular risk reduction',
        ],
        'health_concerns': ['Cholesterol Management', 'Heart Disease'],
        'img_seed': 'atorvastatin-statin',
    },
    # ── PRESCRIPTION: Diabetes ──────────────────────────────────────────────
    {
        'name': 'Metformin 500mg Tablets',
        'sku': 'RX-DM-001',
        'strength': '500mg',
        'brand': 'Novartis',
        'category': 'Prescription Medicines',
        'subcategory': 'Diabetes Management',
        'price': Decimal('380.00'),
        'cost_price': Decimal('210.00'),
        'discount_price': None,
        'stock_qty': 400,
        'requires_prescription': True,
        'is_featured': True,
        'dosage_quantity': '1-2',
        'dosage_unit': 'tablet',
        'dosage_frequency': 'twice_daily',
        'dosage_notes': 'Always take with meals to reduce gastrointestinal side effects.',
        'short_description': 'First-line oral hypoglycaemic for Type 2 diabetes management.',
        'description': (
            'Metformin 500mg is the globally recommended first-line therapy for Type 2 '
            'diabetes mellitus. It reduces hepatic glucose production and improves insulin '
            'sensitivity without causing hypoglycaemia. Associated with modest weight loss '
            'and cardioprotective benefits in overweight diabetic patients. '
            'Gastrointestinal side effects (nausea, diarrhoea) are common at initiation '
            'but usually resolve after 2–3 weeks. Dose should be titrated gradually. '
            'Contraindicated in significant renal impairment (eGFR <30 mL/min).'
        ),
        'features': [
            'First-line for Type 2 diabetes — WHO Essential Medicine',
            'Does not cause hypoglycaemia when used alone',
            'Associated with cardiovascular protection',
            'Weight-neutral or modest weight loss',
        ],
        'health_concerns': ['Diabetes'],
        'img_seed': 'metformin-diabetes',
    },
    {
        'name': 'Glibenclamide 5mg Tablets',
        'sku': 'RX-DM-002',
        'strength': '5mg',
        'brand': 'Sanofi',
        'category': 'Prescription Medicines',
        'subcategory': 'Diabetes Management',
        'price': Decimal('290.00'),
        'cost_price': Decimal('160.00'),
        'discount_price': None,
        'stock_qty': 280,
        'requires_prescription': True,
        'is_featured': False,
        'dosage_quantity': '1',
        'dosage_unit': 'tablet',
        'dosage_frequency': 'once_daily',
        'dosage_notes': 'Take 30 minutes before breakfast. Monitor blood glucose regularly. Eat on time.',
        'short_description': 'Sulphonylurea oral hypoglycaemic for Type 2 diabetes.',
        'description': (
            'Glibenclamide 5mg (also known as glyburide) is a long-acting sulphonylurea '
            'that stimulates insulin secretion from pancreatic beta cells. It is effective '
            'in lowering fasting and postprandial blood glucose in Type 2 diabetes. '
            'Commonly used in combination with metformin when monotherapy is insufficient. '
            'Risk of hypoglycaemia is significant, particularly in elderly patients and '
            'those with irregular meal schedules. Not recommended in renal or hepatic impairment.'
        ),
        'features': [
            'Stimulates pancreatic insulin secretion',
            'Long-acting — once daily dosing',
            'Often combined with metformin for better control',
            'Affordable sulphonylurea — on Kenya Essential Medicines List',
        ],
        'health_concerns': ['Diabetes'],
        'img_seed': 'glibenclamide-tabs',
    },
    # ── PRESCRIPTION: Respiratory ───────────────────────────────────────────
    {
        'name': 'Salbutamol Inhaler 100mcg',
        'sku': 'RX-RS-001',
        'strength': '100mcg/actuation',
        'brand': 'GSK',
        'category': 'Prescription Medicines',
        'subcategory': 'Respiratory',
        'price': Decimal('750.00'),
        'cost_price': Decimal('480.00'),
        'discount_price': None,
        'stock_qty': 95,
        'requires_prescription': True,
        'is_featured': False,
        'dosage_quantity': '1-2',
        'dosage_unit': 'puffs',
        'dosage_frequency': 'as_needed',
        'dosage_notes': 'For acute bronchospasm. Shake well before use. Max 8 puffs per day.',
        'short_description': 'Short-acting beta-2 agonist (SABA) reliever inhaler for asthma.',
        'description': (
            'Salbutamol (albuterol) 100mcg pressurised metered-dose inhaler (pMDI) is the '
            'most widely used reliever bronchodilator for asthma and COPD-related '
            'bronchospasm. It relaxes airway smooth muscle within 5 minutes, providing '
            'rapid relief of breathlessness, wheezing, and chest tightness. '
            'Use with a spacer device to improve lung deposition. '
            'Patients relying on salbutamol more than twice a week should be reviewed '
            'for escalation of controller therapy. Also used for prevention of '
            'exercise-induced bronchospasm when taken 15 minutes before exertion.'
        ),
        'features': [
            'Rapid onset — relief within 5 minutes',
            'Short-acting reliever for acute bronchospasm',
            'Use with spacer for optimal delivery',
            'Suitable for children and adults with asthma',
        ],
        'health_concerns': ['Respiratory Infections'],
        'img_seed': 'salbutamol-inhaler',
    },
    # ── OTC: Pain Relief ────────────────────────────────────────────────────
    {
        'name': 'Panadol Extra Tablets 500mg/65mg',
        'sku': 'OTC-PR-001',
        'strength': '500mg/65mg',
        'brand': 'GSK',
        'category': 'Over-the-Counter Medicines',
        'subcategory': 'Pain Relief',
        'price': Decimal('150.00'),
        'cost_price': Decimal('80.00'),
        'discount_price': Decimal('130.00'),
        'stock_qty': 580,
        'requires_prescription': False,
        'is_featured': True,
        'dosage_quantity': '1-2',
        'dosage_unit': 'tablet',
        'dosage_frequency': 'every_4_to_6_hours',
        'dosage_notes': 'Do not exceed 8 tablets in 24 hours. Max 4 doses per day.',
        'short_description': 'Paracetamol + caffeine for fast, effective pain and fever relief.',
        'description': (
            'Panadol Extra combines paracetamol 500mg with caffeine 65mg for enhanced '
            'pain relief compared to paracetamol alone. The caffeine acts as an '
            'analgesic adjuvant, increasing paracetamol\'s efficacy by up to 40% for '
            'headaches, dental pain, period pain, and muscular aches. '
            'Safe on the stomach unlike NSAIDs, making it suitable for patients with '
            'gastric sensitivity. Fast-acting formula provides relief within 15–30 minutes. '
            'Do not use with other paracetamol-containing products to avoid overdose.'
        ),
        'features': [
            'Paracetamol + caffeine combination for 40% more pain relief',
            'Gentle on the stomach',
            'Fast-acting — relief within 15–30 minutes',
            'For headaches, dental pain, period pain, fever',
        ],
        'health_concerns': ['Arthritis & Joint Pain'],
        'img_seed': 'panadol-extra',
    },
    {
        'name': 'Ibuprofen 400mg Tablets',
        'sku': 'OTC-PR-002',
        'strength': '400mg',
        'brand': 'Cipla',
        'category': 'Over-the-Counter Medicines',
        'subcategory': 'Pain Relief',
        'price': Decimal('180.00'),
        'cost_price': Decimal('100.00'),
        'discount_price': None,
        'stock_qty': 420,
        'requires_prescription': False,
        'is_featured': False,
        'dosage_quantity': '1',
        'dosage_unit': 'tablet',
        'dosage_frequency': 'three_times_daily',
        'dosage_notes': 'Always take with food or milk. Avoid if you have a stomach ulcer or kidney disease.',
        'short_description': 'NSAID for pain, fever, and inflammation.',
        'description': (
            'Ibuprofen 400mg is a non-steroidal anti-inflammatory drug (NSAID) with '
            'analgesic, antipyretic, and anti-inflammatory properties. Effective for '
            'headaches, toothache, period pain, musculoskeletal pain, soft tissue injuries, '
            'and fever. Works by inhibiting COX-1 and COX-2 enzymes to reduce prostaglandin '
            'synthesis. Always take with food to protect the gastric mucosa. '
            'Avoid in peptic ulcer disease, significant renal impairment, third trimester '
            'of pregnancy, and in patients on anticoagulant therapy.'
        ),
        'features': [
            'Anti-inflammatory, analgesic, and antipyretic',
            'For period pain, dental pain, and sports injuries',
            'Maximum OTC strength available without prescription',
            'Take with food to protect stomach lining',
        ],
        'health_concerns': ['Arthritis & Joint Pain'],
        'img_seed': 'ibuprofen-400',
    },
    {
        'name': 'Aspirin 75mg Dispersible Tablets',
        'sku': 'OTC-PR-003',
        'strength': '75mg',
        'brand': 'Bayer',
        'category': 'Over-the-Counter Medicines',
        'subcategory': 'Pain Relief',
        'price': Decimal('280.00'),
        'cost_price': Decimal('160.00'),
        'discount_price': None,
        'stock_qty': 310,
        'requires_prescription': False,
        'is_featured': False,
        'dosage_quantity': '1',
        'dosage_unit': 'tablet',
        'dosage_frequency': 'once_daily',
        'dosage_notes': 'Dissolve in water before taking. Take with or after food.',
        'short_description': 'Low-dose aspirin for cardiovascular event prevention.',
        'description': (
            'Aspirin 75mg low-dose dispersible tablets are used for antiplatelet therapy '
            'in the secondary prevention of myocardial infarction, stroke, and peripheral '
            'arterial disease. Inhibits thromboxane A2 production in platelets, reducing '
            'platelet aggregation and clot formation. Dissolve in water for faster '
            'absorption and reduced gastric irritation. Commonly prescribed alongside '
            'statins and antihypertensives as part of a cardiovascular prevention strategy. '
            'Not to be used in children under 16 due to Reye\'s syndrome risk.'
        ),
        'features': [
            'Antiplatelet — prevents heart attack and stroke recurrence',
            'Dispersible form — gentle on the stomach',
            'Part of comprehensive CV risk management',
            'Backed by decades of clinical evidence',
        ],
        'health_concerns': ['Heart Disease', 'Cholesterol Management'],
        'img_seed': 'aspirin-75mg',
    },
    # ── OTC: Cough & Cold ───────────────────────────────────────────────────
    {
        'name': 'Strepsils Honey & Lemon Lozenges 24s',
        'sku': 'OTC-CC-001',
        'strength': '1.2mg/0.6mg',
        'brand': 'Cipla',
        'category': 'Over-the-Counter Medicines',
        'subcategory': 'Cough & Cold',
        'price': Decimal('350.00'),
        'cost_price': Decimal('200.00'),
        'discount_price': Decimal('310.00'),
        'stock_qty': 240,
        'requires_prescription': False,
        'is_featured': False,
        'dosage_quantity': '1',
        'dosage_unit': 'lozenge',
        'dosage_frequency': 'every_2_to_3_hours',
        'dosage_notes': 'Allow to dissolve slowly in the mouth. Max 12 lozenges per day. Not for children under 6.',
        'short_description': 'Antibacterial throat lozenges for sore throat relief.',
        'description': (
            'Strepsils Honey & Lemon lozenges contain two antiseptics — '
            'amylmetacresol 0.6mg and 2,4-dichlorobenzyl alcohol 1.2mg — that kill '
            'the bacteria responsible for sore throats and mouth infections. '
            'The soothing honey and lemon flavour provides immediate comfort while '
            'the antiseptic action targets infection. Suitable for sore throats, '
            'mouth ulcers, and throat infections. Effective from the first lozenge. '
            'Do not swallow whole — allow to dissolve slowly for maximum contact time.'
        ),
        'features': [
            'Dual antiseptic formula kills throat bacteria',
            'Soothing honey & lemon flavour',
            'Fast-acting sore throat relief',
            'Sugar-free variant available',
        ],
        'health_concerns': ['Respiratory Infections'],
        'img_seed': 'strepsils-lozenges',
    },
    {
        'name': 'Vicks VapoRub 50g',
        'sku': 'OTC-CC-002',
        'strength': 'Topical',
        'brand': 'Cosmos Limited',
        'category': 'Over-the-Counter Medicines',
        'subcategory': 'Cough & Cold',
        'price': Decimal('420.00'),
        'cost_price': Decimal('240.00'),
        'discount_price': None,
        'stock_qty': 180,
        'requires_prescription': False,
        'is_featured': False,
        'dosage_quantity': 'Small amount',
        'dosage_unit': 'application',
        'dosage_frequency': 'three_times_daily',
        'dosage_notes': 'Apply to chest, throat, and back. Do not apply inside nostrils or to broken skin.',
        'short_description': 'Mentholated topical ointment for cough and cold symptom relief.',
        'description': (
            'Vicks VapoRub is a mentholated topical ointment containing camphor, '
            'eucalyptus oil, and menthol. When applied to the chest, throat, and back, '
            'the vapours are inhaled and provide temporary relief of nasal congestion, '
            'cough, and minor muscle aches associated with colds. Generations of '
            'Kenyan families have relied on Vicks VapoRub as a bedtime remedy for '
            'children and adults alike. Do not apply inside the nose or take by mouth. '
            'Not recommended for children under 2 years.'
        ),
        'features': [
            'Triple action — camphor, eucalyptus, menthol',
            'Relieves nasal congestion and cough',
            'Soothes minor chest and muscle aches',
            'Trusted remedy for over 130 years',
        ],
        'health_concerns': ['Respiratory Infections'],
        'img_seed': 'vicks-vaporub',
    },
    # ── OTC: Digestive Health ───────────────────────────────────────────────
    {
        'name': 'ORS Sachets Oral Rehydration Salts 10s',
        'sku': 'OTC-DG-001',
        'strength': 'WHO formula',
        'brand': 'Dawa Limited',
        'category': 'Over-the-Counter Medicines',
        'subcategory': 'Digestive Health',
        'price': Decimal('120.00'),
        'cost_price': Decimal('60.00'),
        'discount_price': None,
        'stock_qty': 650,
        'requires_prescription': False,
        'is_featured': True,
        'dosage_quantity': '1',
        'dosage_unit': 'sachet',
        'dosage_frequency': 'after_each_loose_stool',
        'dosage_notes': 'Dissolve one sachet in 200ml clean water. Give after each loose stool. Discard after 1 hour.',
        'short_description': 'WHO-formula oral rehydration salts for diarrhoea management.',
        'description': (
            'WHO/UNICEF formulation ORS sachets are the gold standard treatment for '
            'dehydration due to diarrhoea in children and adults. Each sachet contains '
            'sodium chloride 2.6g, trisodium citrate 2.9g, potassium chloride 1.5g, '
            'and glucose 13.5g per litre. This reduced-osmolarity formula reduces '
            'stool output by 20% and vomiting by 30% compared to the older WHO formula. '
            'Zinc supplementation (10–20mg/day for 10–14 days) should be given '
            'alongside ORS in children under 5 for optimal outcomes. '
            'Critical first-line therapy for cholera, acute gastroenteritis, and traveller\'s diarrhoea.'
        ),
        'features': [
            'WHO/UNICEF approved reduced-osmolarity formula',
            'Reduces stool output by 20%',
            'Safe for all ages including infants',
            'Essential for cholera and acute gastroenteritis',
        ],
        'health_concerns': ['Digestive Disorders', 'Child Health'],
        'img_seed': 'ors-sachets',
    },
    {
        'name': 'Omeprazole 20mg Capsules',
        'sku': 'OTC-DG-002',
        'strength': '20mg',
        'brand': 'Cipla',
        'category': 'Over-the-Counter Medicines',
        'subcategory': 'Digestive Health',
        'price': Decimal('480.00'),
        'cost_price': Decimal('280.00'),
        'discount_price': None,
        'stock_qty': 300,
        'requires_prescription': False,
        'is_featured': False,
        'dosage_quantity': '1',
        'dosage_unit': 'capsule',
        'dosage_frequency': 'once_daily',
        'dosage_notes': 'Take 30–60 minutes before breakfast. Swallow whole — do not crush or chew.',
        'short_description': 'Proton pump inhibitor for gastric acid suppression and ulcer healing.',
        'description': (
            'Omeprazole 20mg is a proton pump inhibitor (PPI) that irreversibly inhibits '
            'the gastric H+/K+-ATPase, reducing acid secretion by up to 97%. '
            'Used for gastro-oesophageal reflux disease (GERD), peptic ulcer disease, '
            'H. pylori eradication (triple therapy), NSAID-associated gastropathy, '
            'and Zollinger-Ellison syndrome. Taking before breakfast maximises efficacy '
            'as PPIs are most effective when proton pumps are active. '
            'Long-term use (>1 year) should be reviewed due to risks of B12 deficiency '
            'and hypomagnesaemia.'
        ),
        'features': [
            'Reduces stomach acid by up to 97%',
            'Heals peptic ulcers and relieves GERD',
            'Take 30 minutes before meals for best results',
            'Also available in 40mg strength',
        ],
        'health_concerns': ['Digestive Disorders'],
        'img_seed': 'omeprazole-caps',
    },
    {
        'name': 'Loperamide 2mg Capsules 12s',
        'sku': 'OTC-DG-003',
        'strength': '2mg',
        'brand': 'Cipla',
        'category': 'Over-the-Counter Medicines',
        'subcategory': 'Digestive Health',
        'price': Decimal('220.00'),
        'cost_price': Decimal('120.00'),
        'discount_price': None,
        'stock_qty': 260,
        'requires_prescription': False,
        'is_featured': False,
        'dosage_quantity': '2',
        'dosage_unit': 'capsule',
        'dosage_frequency': 'after_loose_stool',
        'dosage_notes': 'Start with 2 capsules, then 1 after each loose stool. Max 8 capsules per day.',
        'short_description': 'Antidiarrhoeal for acute and traveller\'s diarrhoea.',
        'description': (
            'Loperamide 2mg acts on opioid receptors in the gut wall to slow intestinal '
            'motility, reduce fluid and electrolyte secretion, and increase anal sphincter '
            'tone. Effective for acute non-specific diarrhoea and traveller\'s diarrhoea. '
            'Not to be used when diarrhoea is associated with fever, blood, or mucus '
            'in stools (possible infectious/inflammatory cause). Always use alongside '
            'ORS to maintain hydration. Not for children under 6 years without medical advice.'
        ),
        'features': [
            'Reduces stool frequency and urgency rapidly',
            'Effective for traveller\'s diarrhoea',
            'Use with ORS to maintain hydration',
            'Not for blood-stained or high-fever diarrhoea',
        ],
        'health_concerns': ['Digestive Disorders'],
        'img_seed': 'loperamide-caps',
    },
    # ── OTC: Allergy ────────────────────────────────────────────────────────
    {
        'name': 'Cetirizine 10mg Tablets 10s',
        'sku': 'OTC-AL-001',
        'strength': '10mg',
        'brand': 'Cipla',
        'category': 'Over-the-Counter Medicines',
        'subcategory': 'Allergy & Sinus',
        'price': Decimal('160.00'),
        'cost_price': Decimal('90.00'),
        'discount_price': None,
        'stock_qty': 380,
        'requires_prescription': False,
        'is_featured': False,
        'dosage_quantity': '1',
        'dosage_unit': 'tablet',
        'dosage_frequency': 'once_daily',
        'dosage_notes': 'Take in the evening to minimise drowsiness. Can be taken with or without food.',
        'short_description': 'Non-drowsy second-generation antihistamine for allergies and hay fever.',
        'description': (
            'Cetirizine 10mg is a second-generation antihistamine with selective H1-receptor '
            'antagonism. Provides 24-hour relief from allergic rhinitis (hay fever), '
            'urticaria (hives), angioedema, and allergic conjunctivitis. '
            'Compared to first-generation antihistamines (chlorphenamine), cetirizine '
            'is far less sedating and does not impair psychomotor performance. '
            'Onset of action within 1 hour; lasts 24 hours. Safe for use in adults '
            'and children over 6 years. Caution in renal impairment — dose may need reduction.'
        ),
        'features': [
            'Once-daily 24-hour allergy relief',
            'Minimal drowsiness vs first-generation antihistamines',
            'Effective for hay fever, hives, and skin allergy',
            'Suitable for adults and children over 6',
        ],
        'health_concerns': ['Skin Conditions', 'Respiratory Infections'],
        'img_seed': 'cetirizine-allergy',
    },
    # ── OTC: Skin Treatment ─────────────────────────────────────────────────
    {
        'name': 'Dettol Antiseptic Liquid 250ml',
        'sku': 'OTC-SK-001',
        'strength': '4.8% chloroxylenol',
        'brand': 'Cipla',
        'category': 'Over-the-Counter Medicines',
        'subcategory': 'Skin Treatment',
        'price': Decimal('320.00'),
        'cost_price': Decimal('180.00'),
        'discount_price': Decimal('285.00'),
        'stock_qty': 290,
        'requires_prescription': False,
        'is_featured': False,
        'dosage_quantity': 'Dilute 1:20',
        'dosage_unit': 'application',
        'dosage_frequency': 'as_needed',
        'dosage_notes': 'Always dilute before use. Do not apply undiluted to skin. External use only.',
        'short_description': 'Trusted antiseptic liquid for wound cleaning and skin disinfection.',
        'description': (
            'Dettol Antiseptic Liquid contains chloroxylenol (PCMX) 4.8% as the active '
            'ingredient. It kills bacteria and viruses on contact, making it ideal for '
            'cleaning cuts, wounds, abrasions, and insect bites. '
            'Also used diluted as a disinfectant for personal hygiene, bathing, '
            'first aid, and surface cleaning. The characteristic Dettol smell indicates '
            'active antiseptic properties. Dilute 1:20 in water for wound washing and '
            '1:40 for skin disinfection. Do not use in eyes. '
            'A household staple in Kenyan homes for over 80 years.'
        ),
        'features': [
            'Kills 99.9% of germs on contact',
            'For cuts, wounds, insect bites, and abrasions',
            'Also suitable for laundry disinfection',
            'Trusted antiseptic brand — household staple',
        ],
        'health_concerns': ['Skin Conditions'],
        'img_seed': 'dettol-antiseptic',
    },
    {
        'name': 'Clotrimazole 1% Cream 20g',
        'sku': 'OTC-SK-002',
        'strength': '1%',
        'brand': 'Beta Healthcare',
        'category': 'Over-the-Counter Medicines',
        'subcategory': 'Skin Treatment',
        'price': Decimal('280.00'),
        'cost_price': Decimal('160.00'),
        'discount_price': None,
        'stock_qty': 220,
        'requires_prescription': False,
        'is_featured': False,
        'dosage_quantity': 'Thin layer',
        'dosage_unit': 'application',
        'dosage_frequency': 'twice_daily',
        'dosage_notes': 'Apply to clean dry skin. Continue for 1 week after symptoms clear. For external use only.',
        'short_description': 'Antifungal cream for ringworm, athlete\'s foot, and fungal skin infections.',
        'description': (
            'Clotrimazole 1% cream is a broad-spectrum imidazole antifungal effective '
            'against dermatophytes, Candida, and Malassezia species. '
            'Used to treat ringworm (tinea corporis), athlete\'s foot (tinea pedis), '
            'jock itch (tinea cruris), cutaneous candidiasis, and pityriasis versicolor. '
            'Works by inhibiting ergosterol synthesis in fungal cell membranes. '
            'Treat for a minimum of 4 weeks for dermatophyte infections and continue '
            'for one week after clinical clearance to prevent recurrence. '
            'Safe for use in adults and children over 12 years.'
        ),
        'features': [
            'Broad-spectrum antifungal coverage',
            'Effective for ringworm, athlete\'s foot, and candidiasis',
            'Non-greasy formulation',
            'Complete course to prevent recurrence',
        ],
        'health_concerns': ['Skin Conditions'],
        'img_seed': 'clotrimazole-cream',
    },
    # ── Vitamins & Supplements ──────────────────────────────────────────────
    {
        'name': 'Vitamin C 1000mg Effervescent Tablets 20s',
        'sku': 'VIT-VC-001',
        'strength': '1000mg',
        'brand': 'Bayer',
        'category': 'Vitamins & Supplements',
        'subcategory': 'Vitamin C & D',
        'price': Decimal('420.00'),
        'cost_price': Decimal('240.00'),
        'discount_price': Decimal('370.00'),
        'stock_qty': 350,
        'requires_prescription': False,
        'is_featured': True,
        'dosage_quantity': '1',
        'dosage_unit': 'tablet',
        'dosage_frequency': 'once_daily',
        'dosage_notes': 'Dissolve in 200ml water. Take in the morning. Do not exceed 2000mg vitamin C daily.',
        'short_description': 'High-dose effervescent vitamin C for immune support and antioxidant protection.',
        'description': (
            'Vitamin C 1000mg effervescent tablets provide a high-dose boost of ascorbic '
            'acid in a pleasant, easy-to-absorb effervescent form. '
            'Vitamin C is essential for immune function, collagen synthesis, wound healing, '
            'and acts as a powerful antioxidant protecting cells from oxidative damage. '
            'At 1000mg, it provides more than 10 times the daily recommended amount, '
            'offering therapeutic-level immune support during infections, high-stress '
            'periods, or post-surgery recovery. The effervescent delivery maximises '
            'absorption compared to standard tablets. Orange flavour.'
        ),
        'features': [
            'High-dose 1000mg vitamin C per tablet',
            'Effervescent delivery for superior absorption',
            'Boosts immunity and promotes collagen synthesis',
            'Antioxidant protection against free radicals',
        ],
        'health_concerns': ['Respiratory Infections'],
        'img_seed': 'vitamin-c-effervescent',
    },
    {
        'name': 'Ferrous Sulphate + Folic Acid 200mg/0.4mg Tablets 30s',
        'sku': 'VIT-IM-001',
        'strength': '200mg/0.4mg',
        'brand': 'Cosmos Limited',
        'category': 'Vitamins & Supplements',
        'subcategory': 'Iron & Minerals',
        'price': Decimal('220.00'),
        'cost_price': Decimal('120.00'),
        'discount_price': None,
        'stock_qty': 420,
        'requires_prescription': False,
        'is_featured': False,
        'dosage_quantity': '1',
        'dosage_unit': 'tablet',
        'dosage_frequency': 'once_daily',
        'dosage_notes': 'Take on an empty stomach or with orange juice for better absorption. Stools may turn black.',
        'short_description': 'Iron and folic acid supplement for anaemia prevention and treatment.',
        'description': (
            'Ferrous sulphate 200mg with folic acid 0.4mg is the standard supplement '
            'recommended by the Kenyan Ministry of Health for routine antenatal care '
            'and iron deficiency anaemia. Iron is essential for haemoglobin synthesis '
            'while folic acid prevents neural tube defects in early pregnancy. '
            'Taking with vitamin C-rich juice (e.g. orange juice) dramatically improves '
            'iron absorption. Avoid antacids, tea, and coffee within 2 hours of dosing. '
            'Black or dark stools are normal and expected during iron supplementation.'
        ),
        'features': [
            'Iron + folic acid — standard antenatal supplement',
            'Prevents iron deficiency anaemia in pregnancy',
            'Folic acid reduces neural tube defect risk',
            'Take with vitamin C to maximise absorption',
        ],
        'health_concerns': ['Anaemia', "Women's Health"],
        'img_seed': 'ferrous-folic-acid',
    },
    {
        'name': 'Omega-3 Fish Oil 1000mg Softgels 30s',
        'sku': 'VIT-OM-001',
        'strength': '1000mg',
        'brand': 'Abbott',
        'category': 'Vitamins & Supplements',
        'subcategory': 'Omega-3 & Fish Oil',
        'price': Decimal('680.00'),
        'cost_price': Decimal('400.00'),
        'discount_price': Decimal('620.00'),
        'stock_qty': 180,
        'requires_prescription': False,
        'is_featured': False,
        'dosage_quantity': '2',
        'dosage_unit': 'softgels',
        'dosage_frequency': 'once_daily',
        'dosage_notes': 'Take with meals to reduce fishy aftertaste and improve absorption.',
        'short_description': 'High-purity omega-3 EPA/DHA for heart, brain, and joint health.',
        'description': (
            'Omega-3 Fish Oil 1000mg softgels provide EPA (eicosapentaenoic acid) and '
            'DHA (docosahexaenoic acid) — the two most bioavailable omega-3 fatty acids. '
            'Clinical evidence supports omega-3 supplementation for reducing triglycerides '
            'by 20–50%, lowering blood pressure, reducing inflammation in arthritis, '
            'and supporting cognitive function and foetal brain development in pregnancy. '
            'High-purity molecular distillation process removes heavy metals and PCBs. '
            'Lemon-flavoured softgels minimise fishy aftertaste.'
        ),
        'features': [
            'High EPA + DHA content per softgel',
            'Reduces triglycerides and supports heart health',
            'Supports joint flexibility and brain function',
            'Molecularly distilled — free from heavy metals',
        ],
        'health_concerns': ['Heart Disease', 'Cholesterol Management', 'Arthritis & Joint Pain'],
        'img_seed': 'omega3-fish-oil',
    },
    {
        'name': 'Pregnacare Plus 28+28 Tablets',
        'sku': 'VIT-PG-001',
        'strength': 'Multi-nutrient',
        'brand': 'Abbott',
        'category': 'Vitamins & Supplements',
        'subcategory': 'Pregnancy Support',
        'price': Decimal('2100.00'),
        'cost_price': Decimal('1350.00'),
        'discount_price': Decimal('1890.00'),
        'stock_qty': 90,
        'requires_prescription': False,
        'is_featured': True,
        'dosage_quantity': '1 tab + 1 cap',
        'dosage_unit': 'daily',
        'dosage_frequency': 'once_daily',
        'dosage_notes': 'Take one tablet and one omega-3 capsule daily with the main meal.',
        'short_description': 'Comprehensive prenatal multivitamin + omega-3 for mother and baby.',
        'description': (
            'Pregnacare Plus is a dual-pack prenatal supplement providing a complete '
            'multivitamin tablet plus a DHA omega-3 capsule in a single daily regimen. '
            'Formulated to meet the increased nutritional demands of pregnancy: '
            '400mcg folic acid (neural tube protection), 14mg iron (anaemia prevention), '
            '700mcg vitamin A, calcium, iodine, B vitamins, and zinc. '
            'The accompanying omega-3 DHA capsule supports foetal brain and eye development. '
            'Suitable from conception through to breastfeeding. '
            'The No.1 selling pregnancy supplement in the UK.'
        ),
        'features': [
            'Complete prenatal multivitamin + omega-3 DHA',
            '400mcg folic acid from preconception through pregnancy',
            'Supports foetal brain, eye, and neural development',
            '28 tablets + 28 omega capsules — one month supply',
        ],
        'health_concerns': ["Women's Health", 'Anaemia'],
        'img_seed': 'pregnacare-plus',
    },
    {
        'name': 'Complete Multivitamins Adults 30s',
        'sku': 'VIT-MV-001',
        'strength': '23 vitamins & minerals',
        'brand': 'Abbott',
        'category': 'Vitamins & Supplements',
        'subcategory': 'Multivitamins',
        'price': Decimal('650.00'),
        'cost_price': Decimal('380.00'),
        'discount_price': None,
        'stock_qty': 220,
        'requires_prescription': False,
        'is_featured': False,
        'dosage_quantity': '1',
        'dosage_unit': 'tablet',
        'dosage_frequency': 'once_daily',
        'dosage_notes': 'Take with food in the morning for best absorption.',
        'short_description': 'Daily multivitamin providing 23 essential vitamins and minerals.',
        'description': (
            'Complete Multivitamins for Adults provides 23 essential vitamins and minerals '
            'to fill nutritional gaps in daily diet. Contains the full B-vitamin complex '
            'for energy metabolism, vitamins C, D, and E for immune and antioxidant '
            'support, zinc and selenium for immune defence, and key minerals including '
            'calcium, magnesium, and iodine. One tablet per day supports overall health '
            'and wellbeing, energy levels, and immune function. '
            'Suitable for both men and women. '
            'Food-form nutrients for superior bioavailability.'
        ),
        'features': [
            '23 vitamins and minerals in one daily tablet',
            'Supports energy, immunity, and bone health',
            'Full B-complex for metabolism and nerve function',
            'Suitable for men and women',
        ],
        'health_concerns': [],
        'img_seed': 'multivitamins-adults',
    },
    # ── Personal Care ───────────────────────────────────────────────────────
    {
        'name': 'Cetaphil Gentle Skin Cleanser 250ml',
        'sku': 'PC-SK-001',
        'strength': 'N/A',
        'brand': 'Sanofi',
        'category': 'Personal Care',
        'subcategory': 'Skin Care',
        'price': Decimal('1450.00'),
        'cost_price': Decimal('920.00'),
        'discount_price': Decimal('1290.00'),
        'stock_qty': 110,
        'requires_prescription': False,
        'is_featured': True,
        'dosage_quantity': 'Small amount',
        'dosage_unit': 'application',
        'dosage_frequency': 'twice_daily',
        'dosage_notes': 'Apply to face, lather gently, rinse or wipe off without water. Suitable for sensitive skin.',
        'short_description': 'Dermatologist-recommended gentle cleanser for sensitive and dry skin.',
        'description': (
            'Cetaphil Gentle Skin Cleanser is the No.1 dermatologist-recommended '
            'cleanser for sensitive skin. Its mild, soap-free, non-comedogenic formula '
            'effectively removes dirt, makeup, and excess oil without stripping the skin\'s '
            'natural moisture barrier. Free from alcohol, fragrances, and harsh surfactants. '
            'Safe for eczema-prone and rosacea-affected skin. Can be used as a '
            'no-rinse cleanser — simply apply and wipe off with a soft cloth. '
            'Suitable for newborns through to elderly skin. '
            'Endorsed by dermatologists and paediatricians worldwide.'
        ),
        'features': [
            'Dermatologist recommended for sensitive skin',
            'Soap-free, non-comedogenic, fragrance-free',
            'Can be used as rinse-off or leave-on cleanser',
            'Safe for eczema, rosacea, and dry skin',
        ],
        'health_concerns': ['Skin Conditions'],
        'img_seed': 'cetaphil-cleanser',
    },
    {
        'name': 'Sensodyne Repair & Protect Toothpaste 75ml',
        'sku': 'PC-DC-001',
        'strength': '5% potassium nitrate',
        'brand': 'GSK',
        'category': 'Personal Care',
        'subcategory': 'Dental Care',
        'price': Decimal('680.00'),
        'cost_price': Decimal('420.00'),
        'discount_price': None,
        'stock_qty': 200,
        'requires_prescription': False,
        'is_featured': False,
        'dosage_quantity': 'Pea-sized amount',
        'dosage_unit': 'application',
        'dosage_frequency': 'twice_daily',
        'dosage_notes': 'Brush for 2 minutes. Do not rinse immediately after brushing to allow fluoride contact.',
        'short_description': 'Clinically proven toothpaste for sensitive teeth and enamel repair.',
        'description': (
            'Sensodyne Repair & Protect toothpaste is clinically proven to build a '
            'protective layer over exposed dentine, relieving tooth sensitivity and '
            'repairing vulnerable areas of the teeth. '
            'Contains bio-active NovaMin® technology that forms a mineral layer '
            'over dentine tubules, blocking the pain pathway. '
            'Also contains fluoride for ongoing cavity protection. '
            'Recommended by dentists for patients with dentine hypersensitivity — '
            'a common condition affecting 1 in 8 adults in Kenya. '
            'Use as regular toothpaste twice daily for best results. '
            'Significant relief visible within 2 weeks of regular use.'
        ),
        'features': [
            'Clinically proven sensitivity relief',
            'Builds protective layer over exposed dentine',
            'Fluoride protection against cavities',
            'Dentist recommended — relief within 2 weeks',
        ],
        'health_concerns': [],
        'img_seed': 'sensodyne-toothpaste',
    },
    {
        'name': 'Eucerin Sun Fluid SPF 50+ 50ml',
        'sku': 'PC-SN-001',
        'strength': 'SPF 50+',
        'brand': 'Bayer',
        'category': 'Personal Care',
        'subcategory': 'Sun Protection',
        'price': Decimal('2200.00'),
        'cost_price': Decimal('1400.00'),
        'discount_price': Decimal('1980.00'),
        'stock_qty': 75,
        'requires_prescription': False,
        'is_featured': False,
        'dosage_quantity': '2mg/cm²',
        'dosage_unit': 'application',
        'dosage_frequency': 'every_2_hours',
        'dosage_notes': 'Apply 20 minutes before sun exposure. Reapply every 2 hours and after swimming.',
        'short_description': 'High-protection SPF 50+ sunscreen for daily photoprotection.',
        'description': (
            'Eucerin Sun Fluid SPF 50+ provides very high broad-spectrum UVA/UVB protection '
            'in a lightweight, non-greasy fluid formulation. '
            'Ideal for daily photoprotection in Kenya\'s tropical climate where UV index '
            'regularly exceeds 9 (very high to extreme). '
            'Contains a proprietary UVAPF/UVBPF balanced filter system with antioxidant '
            'protection. Suitable for sensitive and eczema-prone skin. '
            'Non-comedogenic — will not clog pores. '
            'Dermatologically tested. Suitable as a base under makeup. '
            'Daily sunscreen use prevents premature ageing, hyperpigmentation, and skin cancer.'
        ),
        'features': [
            'SPF 50+ — very high UVA/UVB protection',
            'Lightweight, non-greasy fluid finish',
            'Suitable for sensitive and acne-prone skin',
            'Prevents premature ageing and hyperpigmentation',
        ],
        'health_concerns': ['Skin Conditions'],
        'img_seed': 'eucerin-sunscreen',
    },
    # ── Baby & Mother ───────────────────────────────────────────────────────
    {
        'name': 'SMA Pro Follow-On Milk 900g',
        'sku': 'BM-BN-001',
        'strength': 'Stage 2 (6–12 months)',
        'brand': 'Novartis',
        'category': 'Baby & Mother Care',
        'subcategory': 'Baby Nutrition',
        'price': Decimal('3200.00'),
        'cost_price': Decimal('2100.00'),
        'discount_price': Decimal('2890.00'),
        'stock_qty': 60,
        'requires_prescription': False,
        'is_featured': False,
        'dosage_quantity': '5 scoops',
        'dosage_unit': 'per 150ml water',
        'dosage_frequency': 'as_required',
        'dosage_notes': 'Use boiled, cooled water at 70°C or above. Discard unused formula after 2 hours.',
        'short_description': 'Follow-on formula for infants 6–12 months as a breast milk complement.',
        'description': (
            'SMA Pro Follow-On Milk is a nutritionally complete formula for infants from '
            '6 months onwards when used as part of a varied weaning diet. '
            'Enriched with iron to support normal cognitive development during the '
            'critical weaning period when iron stores from birth begin to deplete. '
            'Contains DHA for brain and eye development, and prebiotics GOS/FOS to support '
            'gut health and softening of stools during weaning. '
            'Important: Breast milk is the best food for your baby. '
            'Use only on medical advice or when breastfeeding is not possible.'
        ),
        'features': [
            'Iron-enriched — supports brain development from 6 months',
            'DHA omega-3 for brain and visual development',
            'Prebiotics GOS/FOS for digestive health',
            'Stage 2 formula for 6–12 months',
        ],
        'health_concerns': ['Child Health', 'Malnutrition & Deficiency'],
        'img_seed': 'sma-follow-on',
    },
    {
        'name': "Johnson's Baby Lotion 200ml",
        'sku': 'BM-BS-001',
        'strength': 'Topical',
        'brand': 'Abbott',
        'category': 'Baby & Mother Care',
        'subcategory': 'Baby Skincare',
        'price': Decimal('380.00'),
        'cost_price': Decimal('220.00'),
        'discount_price': None,
        'stock_qty': 240,
        'requires_prescription': False,
        'is_featured': False,
        'dosage_quantity': 'Generous amount',
        'dosage_unit': 'application',
        'dosage_frequency': 'after_each_bath',
        'dosage_notes': 'Apply to damp skin immediately after bathing for best moisturisation.',
        'short_description': 'Gentle, clinically proven daily moisturiser for soft baby skin.',
        'description': (
            'Johnson\'s Baby Lotion is the world\'s most trusted baby moisturiser, '
            'clinically proven to be as gentle as water on newborn skin. '
            'Made with NaturalCalm® milk and soothing scent to help calm and comfort babies. '
            'The mild, hypoallergenic formula is free from parabens, phthalates, sulfates, '
            'and dyes. Absorbs quickly without leaving a greasy residue. '
            'Suitable from birth for daily use. Paediatrician tested and approved. '
            'Keeps baby\'s skin soft and nourished through the day.'
        ),
        'features': [
            'Clinically proven as gentle as water on baby skin',
            'Hypoallergenic — no parabens, sulfates, or phthalates',
            'NaturalCalm® milk formula for soothing comfort',
            'Paediatrician tested and approved from birth',
        ],
        'health_concerns': ['Child Health'],
        'img_seed': 'johnsons-baby-lotion',
    },
    {
        'name': 'Sudocrem Antiseptic Healing Cream 125g',
        'sku': 'BM-BS-002',
        'strength': 'Topical (zinc oxide 15.25%)',
        'brand': 'Cipla',
        'category': 'Baby & Mother Care',
        'subcategory': 'Baby Skincare',
        'price': Decimal('650.00'),
        'cost_price': Decimal('400.00'),
        'discount_price': None,
        'stock_qty': 150,
        'requires_prescription': False,
        'is_featured': False,
        'dosage_quantity': 'Small amount',
        'dosage_unit': 'application',
        'dosage_frequency': 'at_each_nappy_change',
        'dosage_notes': 'Apply a thin layer to clean dry skin at each nappy change. Gentle massage into skin.',
        'short_description': 'Zinc oxide nappy rash cream that heals, soothes, and protects.',
        'description': (
            'Sudocrem Antiseptic Healing Cream is a multi-purpose protective cream '
            'with zinc oxide (15.25%), hypoallergenic lanolin, and benzyl compounds '
            'that soothe, heal, and protect sore skin. '
            'The primary use is nappy rash — it forms a water-resistant barrier '
            'protecting skin from moisture and irritants while promoting natural healing. '
            'Also effective for minor burns, sunburn, eczema, acne, and surface wounds. '
            'The mild anaesthetic and antiseptic components help reduce pain and prevent '
            'secondary infection. Trusted by parents for over 80 years.'
        ),
        'features': [
            'Zinc oxide 15.25% — clinically proven nappy rash treatment',
            'Soothing antiseptic and mild anaesthetic properties',
            'Creates protective water-resistant barrier',
            'Also treats eczema, minor burns, and acne',
        ],
        'health_concerns': ['Child Health', 'Skin Conditions'],
        'img_seed': 'sudocrem-cream',
    },
    # ── Medical Devices ─────────────────────────────────────────────────────
    {
        'name': 'Omron M2 Upper Arm Blood Pressure Monitor',
        'sku': 'MD-BP-001',
        'strength': 'N/A',
        'brand': 'Abbott',
        'category': 'Medical Devices & Equipment',
        'subcategory': 'Blood Pressure Monitors',
        'price': Decimal('5500.00'),
        'cost_price': Decimal('3500.00'),
        'discount_price': Decimal('4990.00'),
        'stock_qty': 35,
        'requires_prescription': False,
        'is_featured': True,
        'dosage_quantity': '1',
        'dosage_unit': 'reading',
        'dosage_frequency': 'twice_daily',
        'dosage_notes': 'Sit quietly for 5 minutes before measuring. Measure at the same time each day.',
        'short_description': 'Clinically validated upper-arm BP monitor for accurate home monitoring.',
        'description': (
            'The Omron M2 is a clinically validated, user-friendly upper-arm blood pressure '
            'monitor designed for reliable home blood pressure monitoring. '
            'Validated by the European Society of Hypertension (ESH) and British Hypertension '
            'Society (BHS). Features Omron\'s IntelliSense technology for automatic inflation '
            'to the correct level, and Easy-Wrap ComFit cuff fitting indicator. '
            'Stores 60 measurements for tracking trends over time. '
            'Regular home BP monitoring has been shown to improve blood pressure control '
            'and reduce cardiovascular event risk in hypertensive patients. '
            'Comes with AC adapter, batteries, and medium adult cuff (22–32cm).'
        ),
        'features': [
            'ESH/BHS clinically validated accuracy',
            'IntelliSense automatic inflation technology',
            'Easy-Wrap ComFit cuff with fitting guide',
            'Stores 60 readings for trend tracking',
        ],
        'health_concerns': ['Hypertension', 'Heart Disease'],
        'img_seed': 'omron-bp-monitor',
    },
    {
        'name': 'Accu-Chek Active Glucometer Starter Pack',
        'sku': 'MD-GL-001',
        'strength': 'N/A',
        'brand': 'Novartis',
        'category': 'Medical Devices & Equipment',
        'subcategory': 'Glucometers & Strips',
        'price': Decimal('3800.00'),
        'cost_price': Decimal('2400.00'),
        'discount_price': Decimal('3490.00'),
        'stock_qty': 28,
        'requires_prescription': False,
        'is_featured': False,
        'dosage_quantity': '1 drop',
        'dosage_unit': 'blood sample',
        'dosage_frequency': 'as_directed_by_doctor',
        'dosage_notes': 'Clean finger with alcohol swab, allow to dry, then lance. Apply drop to test strip.',
        'short_description': 'Reliable glucometer with 10 test strips and lancets for home blood sugar monitoring.',
        'description': (
            'The Accu-Chek Active glucometer provides accurate blood glucose results '
            'in just 5 seconds using a 1µL sample. The starter pack includes the '
            'meter, 10 test strips, 10 lancets, lancing device, and carrying case. '
            'Features a large backlit display, 500-test memory with date and time, '
            'and 7/14/30-day averaging for trend analysis. '
            'Accu-Chek strips are subject to rigorous quality standards with ISO 15197:2013 '
            'compliance. Essential for diabetes self-management in Type 1 and Type 2 patients. '
            'Replacement test strips (Accu-Chek Active Strips) available in packs of 50.'
        ),
        'features': [
            'Results in 5 seconds with 1µL blood sample',
            '500-test memory with averages',
            'ISO 15197:2013 compliant accuracy',
            'Starter kit — everything needed to begin monitoring',
        ],
        'health_concerns': ['Diabetes'],
        'img_seed': 'accuchek-glucometer',
    },
    {
        'name': 'Digital Thermometer Oral/Rectal/Axillary',
        'sku': 'MD-TH-001',
        'strength': 'N/A',
        'brand': 'Cosmos Limited',
        'category': 'Medical Devices & Equipment',
        'subcategory': 'Thermometers',
        'price': Decimal('480.00'),
        'cost_price': Decimal('280.00'),
        'discount_price': None,
        'stock_qty': 120,
        'requires_prescription': False,
        'is_featured': False,
        'dosage_quantity': '1',
        'dosage_unit': 'reading',
        'dosage_frequency': 'as_needed',
        'dosage_notes': 'Measure 30 minutes after eating, drinking, or exercise. Oral: hold under tongue for 60 seconds.',
        'short_description': 'Fast, accurate digital thermometer with fever alarm for all ages.',
        'description': (
            'This clinical-grade digital thermometer provides accurate temperature '
            'measurements in just 60 seconds with ±0.1°C precision. '
            'Suitable for oral, rectal, and axillary (armpit) use. '
            'Large, easy-to-read LCD display with backlight. '
            'Built-in fever alarm beeps when temperature exceeds 37.5°C (oral) or 38°C (rectal). '
            'Memory recall of last reading. Waterproof tip for easy cleaning. '
            'Comes with a protective storage case and replacement battery. '
            'Essential for monitoring temperature in children during malaria and febrile illness episodes.'
        ),
        'features': [
            'Accurate to ±0.1°C in 60 seconds',
            'Oral, rectal, and axillary use',
            'Fever alarm at 37.5°C',
            'Backlit display and waterproof tip',
        ],
        'health_concerns': ['Malaria', 'Child Health'],
        'img_seed': 'digital-thermometer',
    },
    {
        'name': 'Pulse Oximeter Fingertip SpO2 Monitor',
        'sku': 'MD-OX-001',
        'strength': 'N/A',
        'brand': 'Abbott',
        'category': 'Medical Devices & Equipment',
        'subcategory': 'Wound Care Supplies',
        'price': Decimal('1800.00'),
        'cost_price': Decimal('1100.00'),
        'discount_price': Decimal('1600.00'),
        'stock_qty': 45,
        'requires_prescription': False,
        'is_featured': False,
        'dosage_quantity': '1',
        'dosage_unit': 'reading',
        'dosage_frequency': 'as_needed',
        'dosage_notes': 'Remove nail polish before use. Keep finger still during measurement. Normal SpO2 is 95–100%.',
        'short_description': 'Fingertip pulse oximeter for rapid SpO2 and pulse rate measurement.',
        'description': (
            'This fingertip pulse oximeter provides rapid, non-invasive measurement of '
            'peripheral oxygen saturation (SpO2) and pulse rate using photoplethysmography. '
            'SpO2 range: 70–99% (±2%). Pulse rate range: 30–250 bpm (±1 bpm). '
            'Became a household essential during COVID-19 and remains critical for '
            'monitoring asthma, COPD, pneumonia, and altitude-related conditions. '
            'A normal SpO2 reading is 95–100%. Values below 92% require urgent medical attention. '
            'OLED display shows SpO2, pulse rate, and plethysmographic waveform simultaneously. '
            'Runs on 2 AAA batteries; auto-off after 8 seconds of no signal.'
        ),
        'features': [
            'Measures SpO2 ±2% accuracy in seconds',
            'Displays pulse rate and plethysmographic waveform',
            'OLED display — readable in daylight',
            'Auto-off to conserve battery',
        ],
        'health_concerns': ['Respiratory Infections', 'Heart Disease'],
        'img_seed': 'pulse-oximeter',
    },
    # ── Anti-Malarials ──────────────────────────────────────────────────────
    {
        'name': 'Artemether/Lumefantrine 20/120mg Tablets (AL)',
        'sku': 'RX-ML-001',
        'strength': '20mg/120mg',
        'brand': 'Novartis',
        'category': 'Prescription Medicines',
        'subcategory': 'Antibiotics',
        'price': Decimal('780.00'),
        'cost_price': Decimal('480.00'),
        'discount_price': None,
        'stock_qty': 200,
        'requires_prescription': True,
        'is_featured': False,
        'dosage_quantity': '4',
        'dosage_unit': 'tablets',
        'dosage_frequency': 'twice_daily',
        'dosage_notes': 'Take with food (fatty meal improves absorption). Complete all 6 doses over 3 days.',
        'short_description': 'First-line artemisinin-based combination therapy (ACT) for uncomplicated malaria.',
        'description': (
            'Artemether/Lumefantrine (Coartem) is the first-line treatment for '
            'uncomplicated Plasmodium falciparum malaria in Kenya and across sub-Saharan Africa. '
            'The artemisinin component (artemether) rapidly kills parasites while lumefantrine '
            'eliminates residual parasites over a longer period. '
            'A complete 3-day course of 6 doses reduces treatment failure rates to <5%. '
            'Taking with a fatty meal is critical — lumefantrine absorption increases 16-fold '
            'with fat. WHO Model Essential Medicine for malaria. '
            'Do not use for severe or complicated malaria — IV artesunate required.'
        ),
        'features': [
            'WHO first-line treatment for uncomplicated falciparum malaria',
            'Dual mechanism prevents resistance development',
            'Take with food — dramatically improves lumefantrine absorption',
            '3-day course for full parasite clearance',
        ],
        'health_concerns': ['Malaria'],
        'img_seed': 'artemether-lumefantrine',
    },
    {
        'name': 'Sulfadoxine/Pyrimethamine 500/25mg (SP) Tablets',
        'sku': 'RX-ML-002',
        'strength': '500mg/25mg',
        'brand': 'Cosmos Limited',
        'category': 'Prescription Medicines',
        'subcategory': 'Antibiotics',
        'price': Decimal('180.00'),
        'cost_price': Decimal('90.00'),
        'discount_price': None,
        'stock_qty': 280,
        'requires_prescription': True,
        'is_featured': False,
        'dosage_quantity': '3',
        'dosage_unit': 'tablets',
        'dosage_frequency': 'single_dose',
        'dosage_notes': 'Intermittent preventive treatment in pregnancy (IPTp). Given at ANC visits from 16 weeks.',
        'short_description': 'Fansidar — malaria prevention in pregnancy (IPTp) and seasonal malaria chemoprevention.',
        'description': (
            'Sulfadoxine/Pyrimethamine (Fansidar) combines sulphonamide and antifolate '
            'mechanisms to prevent malaria in high-risk groups. '
            'Used as Intermittent Preventive Treatment in Pregnancy (IPTp-SP) — '
            'given at each ANC visit from 16 weeks of pregnancy in malaria-endemic areas. '
            'The Kenya Ministry of Health recommends at least 3 doses in pregnancy. '
            'A single 3-tablet dose is given under direct observation at the clinic. '
            'Also used in Seasonal Malaria Chemoprevention (SMC) in children 3–59 months '
            'in high-transmission seasons. Do not use near term (36+ weeks).'
        ),
        'features': [
            'Kenyan government approved IPTp malaria prevention in pregnancy',
            'Given as single supervised dose at ANC visits',
            'Reduces placental malaria and low birth weight',
            'Also used for SMC in young children',
        ],
        'health_concerns': ['Malaria', "Women's Health"],
        'img_seed': 'sp-fansidar',
    },
    # ── HIV ─────────────────────────────────────────────────────────────────
    {
        'name': 'Tenofovir/Lamivudine/Dolutegravir 300/300/50mg (TLD)',
        'sku': 'RX-HIV-001',
        'strength': '300mg/300mg/50mg',
        'brand': 'Cipla',
        'category': 'Prescription Medicines',
        'subcategory': 'Pain Management',
        'price': Decimal('1200.00'),
        'cost_price': Decimal('750.00'),
        'discount_price': None,
        'stock_qty': 150,
        'requires_prescription': True,
        'is_featured': False,
        'dosage_quantity': '1',
        'dosage_unit': 'tablet',
        'dosage_frequency': 'once_daily',
        'dosage_notes': 'Take at the same time every day. Do not miss doses. Avoid antacids within 2 hours.',
        'short_description': 'Preferred first-line ART regimen (TLD) for HIV-positive adults.',
        'description': (
            'Tenofovir disoproxil fumarate/lamivudine/dolutegravir (TLD) is the '
            'globally recommended preferred first-line antiretroviral therapy for '
            'HIV-1 infection in adults and adolescents. '
            'The dolutegravir integrase strand transfer inhibitor (INSTI) component '
            'has a high genetic barrier to resistance and excellent tolerability. '
            'TLD has superior virological suppression rates (>92% at 48 weeks) compared '
            'to efavirenz-based regimens and fewer central nervous system side effects. '
            'Adopted as first-line by Kenyan MOH in 2019. '
            'Taken once daily as a single pill — maximising adherence.'
        ),
        'features': [
            'Kenya MOH preferred first-line HIV regimen',
            'High barrier to resistance — dolutegravir INSTI',
            '>92% virological suppression at 48 weeks',
            'Single pill once daily — optimal adherence',
        ],
        'health_concerns': ['HIV/AIDS'],
        'img_seed': 'tld-arvs',
    },
    # ── Herbal ──────────────────────────────────────────────────────────────
    {
        'name': 'Moringa Leaf Powder 200g',
        'sku': 'HB-HR-001',
        'strength': 'N/A',
        'brand': 'Dawa Limited',
        'category': 'Herbal & Alternative Medicine',
        'subcategory': 'Herbal Remedies',
        'price': Decimal('580.00'),
        'cost_price': Decimal('320.00'),
        'discount_price': None,
        'stock_qty': 130,
        'requires_prescription': False,
        'is_featured': False,
        'dosage_quantity': '1-2',
        'dosage_unit': 'teaspoons',
        'dosage_frequency': 'once_daily',
        'dosage_notes': 'Mix into food, porridge, or water. Avoid high heat which destroys nutrients.',
        'short_description': 'Nutrient-dense moringa oleifera leaf powder — the African superfood.',
        'description': (
            'Moringa oleifera (drumstick tree) leaf powder is one of Africa\'s most '
            'nutrient-dense superfoods, containing 7× the vitamin C of oranges, '
            '4× the calcium of milk, 4× the vitamin A of carrots, and 2× the protein '
            'of yoghurt. Widely used in Kenya and East Africa as a nutritional supplement '
            'for malnutrition management, maternal health, and general wellness. '
            'Anti-inflammatory, antioxidant, and antimicrobial properties have been '
            'documented in peer-reviewed research. Suitable for adding to uji porridge, '
            'smoothies, or soups. Sustainably sourced from Kenyan farms. '
            'KEBS-registered and quality tested.'
        ),
        'features': [
            'Rich in iron, calcium, vitamin A, C, and protein',
            'Used for malnutrition management and maternal health',
            'Antioxidant and anti-inflammatory properties',
            'Kenyan-grown and KEBS-registered',
        ],
        'health_concerns': ['Malnutrition & Deficiency', 'Anaemia'],
        'img_seed': 'moringa-powder',
    },
]


# ---------------------------------------------------------------------------
# Confirmed-working Unsplash photo IDs (verified accessible from CDN)
# Fallback is LoremFlickr (real Flickr photos tagged by keyword)
# ---------------------------------------------------------------------------

# Primary: Unsplash CDN — confirmed working IDs only
UNSPLASH_PHOTO_IDS = {
    'otc-pharmacy':          '1587854692152-cbe660dbde88',  # pharmacy dispensary
    'vitamins-supplements':  '1471864190281-a93a3070b6de',  # vitamin capsules
    'personal-care':         '1556228578-8c89e6adf883',     # skincare products
    'baby-care':             '1515488042361-ee00e0ddd4e4',  # mother & infant
    'medical-devices':       '1559757148-5c350d0d3c56',     # stethoscope & tools
    'cosmos-kenya':          '1600880292203-757bb62b4baf',  # African pharmacist
    'sanofi-pharma':         '1587854692152-cbe660dbde88',
    'abbott-laboratories':   '1471864190281-a93a3070b6de',
    'beta-healthcare':       '1559757148-5c350d0d3c56',
    'vitamin-c-effervescent':'1471864190281-a93a3070b6de',
    'omega3-fish-oil':       '1471864190281-a93a3070b6de',
    'multivitamins-adults':  '1471864190281-a93a3070b6de',
    'dettol-antiseptic':     '1556228578-8c89e6adf883',
    'cetaphil-cleanser':     '1556228578-8c89e6adf883',
    'sensodyne-toothpaste':  '1559757148-5c350d0d3c56',
    'sma-follow-on':         '1515488042361-ee00e0ddd4e4',
    'johnsons-baby-lotion':  '1515488042361-ee00e0ddd4e4',
    'digital-thermometer':   '1559757148-5c350d0d3c56',
}

# Secondary: LoremFlickr — real Flickr photos matched by keyword + lock for consistency
# URL: https://loremflickr.com/{w}/{h}/{keywords}?lock={n}
LOREMFLICKR_QUERIES = {
    # ── Categories ──────────────────────────────────────────────────────────
    'rx-medicine':            ('medicine,pills,prescription', 101),
    'herbal-medicine':        ('herbs,natural,herbal', 107),
    # ── Brands ──────────────────────────────────────────────────────────────
    'pfizer-pharma':          ('pharmaceutical,laboratory', 201),
    'gsk-pharmaceutical':     ('pharmacy,medicine,health', 202),
    'novartis-medicine':      ('medicine,pharmaceutical', 203),
    'bayer-pharma':           ('medicine,research,lab', 206),
    'astrazeneca-medicine':   ('healthcare,research,science', 207),
    'cipla-generic':          ('tablets,capsules,medicine', 208),
    'dawa-pharma':            ('pharmacy,medicine,pills', 210),
    'strides-pharma':         ('pharmaceutical,production', 212),
    # ── Products — Antibiotics ───────────────────────────────────────────────
    'amoxicillin-capsules':   ('capsule,antibiotic,medicine', 301),
    'coamoxiclav-tablets':    ('tablets,medicine,white', 302),
    'ciprofloxacin-500':      ('medicine,prescription,pills', 303),
    'metronidazole-tabs':     ('tablets,pharmacy,medicine', 304),
    # ── Products — Cardiovascular ────────────────────────────────────────────
    'amlodipine-bp':          ('blood-pressure,medicine,heart', 305),
    'losartan-arb':           ('heart,medicine,cardiology', 306),
    'atorvastatin-statin':    ('cholesterol,medicine,tablets', 307),
    # ── Products — Diabetes ──────────────────────────────────────────────────
    'metformin-diabetes':     ('diabetes,medicine,glucose', 308),
    'glibenclamide-tabs':     ('diabetes,pills,blood-sugar', 309),
    # ── Products — Respiratory ───────────────────────────────────────────────
    'salbutamol-inhaler':     ('inhaler,asthma,medicine', 310),
    # ── Products — OTC Pain ──────────────────────────────────────────────────
    'panadol-extra':          ('paracetamol,pain-relief,tablets', 311),
    'ibuprofen-400':          ('ibuprofen,pain,pills', 312),
    'aspirin-75mg':           ('aspirin,heart,medicine', 313),
    # ── Products — Cough & Cold ──────────────────────────────────────────────
    'strepsils-lozenges':     ('lozenges,throat,sore', 314),
    'vicks-vaporub':          ('cold,medicine,menthol', 315),
    # ── Products — Digestive ─────────────────────────────────────────────────
    'ors-sachets':            ('rehydration,health,water', 316),
    'omeprazole-caps':        ('gastric,medicine,capsule', 317),
    'loperamide-caps':        ('medicine,capsules,health', 318),
    # ── Products — Allergy ───────────────────────────────────────────────────
    'cetirizine-allergy':     ('allergy,antihistamine,medicine', 319),
    # ── Products — Skin ──────────────────────────────────────────────────────
    'clotrimazole-cream':     ('cream,skincare,antifungal', 321),
    # ── Products — Vitamins ──────────────────────────────────────────────────
    'ferrous-folic-acid':     ('iron,supplements,pregnancy', 323),
    'pregnacare-plus':        ('pregnancy,vitamins,prenatal', 325),
    # ── Products — Personal Care ─────────────────────────────────────────────
    'eucerin-sunscreen':      ('sunscreen,spf,skincare', 329),
    # ── Products — Baby ──────────────────────────────────────────────────────
    'sudocrem-cream':         ('baby,nappy,cream', 332),
    # ── Products — Medical Devices ───────────────────────────────────────────
    'omron-bp-monitor':       ('blood-pressure,monitor,device', 333),
    'accuchek-glucometer':    ('glucometer,diabetes,monitor', 334),
    'pulse-oximeter':         ('oximeter,pulse,medical', 336),
    # ── Products — Malaria / HIV ─────────────────────────────────────────────
    'artemether-lumefantrine':('malaria,medicine,tropical', 337),
    'sp-fansidar':            ('malaria,prevention,medicine', 338),
    'tld-arvs':               ('hiv,antiretroviral,medicine', 339),
    # ── Products — Herbal ────────────────────────────────────────────────────
    'moringa-powder':         ('moringa,herbal,superfood', 340),
}


class Command(BaseCommand):
    help = 'Wipe and re-seed catalog: ProductCategory, ProductSubcategory, HealthConcern, Brand, Product'

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING('Wiping existing catalog data...'))
        self._wipe()
        self.stdout.write('Seeding health concerns...')
        self._seed_health_concerns()
        self.stdout.write('Seeding brands...')
        self._seed_brands()
        self.stdout.write('Seeding product categories & subcategories...')
        self._seed_categories()
        self.stdout.write('Seeding products...')
        self._seed_products()
        self.stdout.write(self.style.SUCCESS('Catalog seeded successfully.'))

    # ── helpers ──────────────────────────────────────────────────────────────

    def _wipe(self):
        from apps.products.models import Product, ProductSubcategory, ProductCategory, HealthConcern, Brand
        Product.objects.all().delete()
        ProductSubcategory.objects.all().delete()
        ProductCategory.objects.all().delete()
        HealthConcern.objects.all().delete()
        Brand.objects.all().delete()
        self.stdout.write('  Existing catalog data deleted.')

    def _get_admin(self):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        return User.objects.filter(role='admin').first()

    def _img_field(self, rel_path: str, seed: str, width: int = 800, height: int = 600) -> str:
        """
        Download a real photo and save to MEDIA_ROOT/<rel_path>.

        Priority:
          1. Confirmed-working Unsplash CDN photo ID
          2. LoremFlickr (real Flickr photos by keyword + lock)
          3. Picsum (always works, beautiful but generic)
        Skips download when a non-empty file already exists.
        """
        dest_abs = _media(rel_path)
        if os.path.exists(dest_abs) and os.path.getsize(dest_abs) > 0:
            return rel_path

        candidates = []

        photo_id = UNSPLASH_PHOTO_IDS.get(seed)
        if photo_id:
            candidates.append(
                f'https://images.unsplash.com/photo-{photo_id}'
                f'?w={width}&h={height}&fit=crop&crop=center&q=85&auto=format'
            )

        lf = LOREMFLICKR_QUERIES.get(seed)
        if lf:
            terms, lock = lf
            candidates.append(
                f'https://loremflickr.com/{width}/{height}/{terms}?lock={lock}'
            )

        seed_num = abs(hash(seed)) % 1000
        candidates.append(f'https://picsum.photos/seed/{seed_num}/{width}/{height}')

        self.stdout.write(f'    Downloading {os.path.basename(rel_path)} ...')
        for url in candidates:
            ok = _download_image(url, dest_abs)
            if ok and os.path.getsize(dest_abs) > 0:
                return rel_path

        self.stdout.write(self.style.WARNING(f'    All sources failed for {seed}'))
        os.makedirs(os.path.dirname(dest_abs), exist_ok=True)
        open(dest_abs, 'wb').close()
        return rel_path

    # ── seed methods ─────────────────────────────────────────────────────────

    def _seed_health_concerns(self):
        from apps.products.models import HealthConcern
        admin = self._get_admin()
        for name, icon, desc in HEALTH_CONCERNS:
            HealthConcern.objects.create(
                name=name,
                icon=icon,
                description=desc,
                is_active=True,
                created_by=admin,
            )
        self.stdout.write(f'  Created {len(HEALTH_CONCERNS)} health concerns.')

    def _seed_brands(self):
        from apps.products.models import Brand
        admin = self._get_admin()
        for b in BRANDS:
            img_rel = f'brands/{slugify(b["name"])}.jpg'
            img_field = self._img_field(img_rel, b['img_seed'], 400, 400)
            Brand.objects.create(
                name=b['name'],
                description=b['description'],
                logo=img_field,
                is_active=True,
                created_by=admin,
            )
        self.stdout.write(f'  Created {len(BRANDS)} brands.')

    def _seed_categories(self):
        from apps.products.models import ProductCategory, ProductSubcategory
        admin = self._get_admin()
        for c in CATEGORIES:
            img_rel = f'categories/{slugify(c["name"])}.jpg'
            img_field = self._img_field(img_rel, c['img_seed'], 800, 600)
            cat = ProductCategory.objects.create(
                name=c['name'],
                icon=c.get('icon', ''),
                description=c['description'],
                image=img_field,
                is_active=True,
                created_by=admin,
            )
            for sub_name, sub_desc in c['subcategories']:
                ProductSubcategory.objects.create(
                    category=cat,
                    name=sub_name,
                    description=sub_desc,
                    is_active=True,
                    created_by=admin,
                )
        total_subs = sum(len(c['subcategories']) for c in CATEGORIES)
        self.stdout.write(f'  Created {len(CATEGORIES)} categories, {total_subs} subcategories.')

    def _seed_products(self):
        from apps.products.models import Product, ProductCategory, ProductSubcategory, Brand, HealthConcern

        brand_map = {b.name: b for b in Brand.objects.all()}
        cat_map = {c.name: c for c in ProductCategory.objects.all()}
        sub_map = {}
        for sub in ProductSubcategory.objects.select_related('category').all():
            sub_map[(sub.category.name, sub.name)] = sub
        hc_map = {hc.name: hc for hc in HealthConcern.objects.all()}

        admin = self._get_admin()
        created = 0
        for p in PRODUCTS:
            brand = brand_map.get(p['brand'])
            subcategory = sub_map.get((p['category'], p['subcategory']))
            img_rel = f'products/{slugify(p["name"])[:60]}.jpg'
            img_field = self._img_field(img_rel, p['img_seed'], 800, 800)

            product = Product.objects.create(
                name=p['name'],
                strength=p.get('strength', ''),
                brand=brand,
                subcategory=subcategory,
                price=p['price'],
                cost_price=p.get('cost_price'),
                image=img_field,
                short_description=p.get('short_description', ''),
                description=p.get('description', ''),
                features=p.get('features', []),
                requires_prescription=p.get('requires_prescription', False),
                is_active=True,
                dosage_quantity=p.get('dosage_quantity', ''),
                dosage_unit=p.get('dosage_unit', ''),
                dosage_frequency=p.get('dosage_frequency', ''),
                dosage_notes=p.get('dosage_notes', ''),
                sku=p['sku'],
                stock_source='branch',
                stock_quantity=p.get('stock_qty', 100),
                created_by=admin,
            )
            for hc_name in p.get('health_concerns', []):
                hc = hc_map.get(hc_name)
                if hc:
                    product.health_concerns.add(hc)
            created += 1

        self.stdout.write(f'  Created {created} products.')
