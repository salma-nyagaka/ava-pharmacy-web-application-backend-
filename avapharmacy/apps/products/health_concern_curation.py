"""Conservative customer browsing tags from explicit names and product types.

These are merchandising links, not prescribing indications or verification of
clinical suitability. Brand names and unrelated description prose are not used.
"""
from dataclasses import dataclass
import re

VERSION = 'health-concerns-2026-11-05-v2'
LEGACY_NOTE = 'Health concerns inferred from catalogue text (catalogue curation v1): '


def normalize(value):
    return ' '.join(re.findall(r'[A-Z0-9]+',str(value or '').upper()))


@dataclass(frozen=True)
class ConcernRule:
    name: str
    description: str
    keywords: str = ''
    categories: tuple[str,...] = ()
    subcategories: tuple[str,...] = ()
    scope: tuple[str,...] = ()
    exclude: str = ''

    def match(self, name, category, subcategory):
        n=normalize(name);c=normalize(category);s=normalize(subcategory)
        if self.scope and c not in {normalize(x) for x in self.scope}:return False
        if self.exclude and re.search(r'\b(?:'+self.exclude+r')\b',n):return False
        if c in {normalize(x) for x in self.categories}:return True
        if s in {normalize(x) for x in self.subcategories}:return True
        return bool(self.keywords and re.search(r'\b(?:'+self.keywords+r')\b',n))


RULES = (
 ConcernRule('Allergy Relief','Browse products explicitly labelled for allergy care.',r'ALLERG(?:Y|IES|IC)|ANTIHISTAMINE|HAY FEVER'),
 ConcernRule('Baby & Child Care','Everyday baby and child care products.',r'BABY|INFANT|PAEDIATRIC|PEDIATRIC|CHILDREN|KIDS',subcategories=('Infant & Toddler Formula','Bottles, Teats & Feeding','Soothers, Teethers & Toys','Nappies & Baby Wipes','Baby Bath, Skin & Sun Care','Baby Safety & Accessories','Children\'s Supplements')),
 ConcernRule('Bone, Joint & Muscle','Browse musculoskeletal supports and products explicitly labelled for joint or muscle care.',r'JOINT|JOINTS|MUSCLE|MUSCULAR|ARTHRITIS|BONE HEALTH',categories=('Orthopaedic Supports & Mobility',)),
 ConcernRule('Cold, Cough & Flu','Products explicitly labelled for cold, cough, flu and throat care.',r'COUGH|COUGHS|COLD FLU|COLDS|FLU|SORE THROAT|EXPECTORANT|DECONGESTANT',subcategories=('Lozenges & Throat Care',),exclude=r'COLD PACK|COLD WATER|HOT COLD|COLD PRESSED|COLD PRESS|ICE PACK'),
 ConcernRule('Digestive Health','Browse digestive products and explicitly labelled digestive support.',r'DIGESTIVE|DIGESTION|ANTACID|HEARTBURN|ACID REFLUX|CONSTIPATION|DIARRHOEA|DIARRHEA|PROBIOTICS?|PREBIOTICS?',subcategories=('Probiotics & Digestive Support',)),
 ConcernRule('Eye Care','Eye comfort, eye treatments and contact-lens care.',r'DRY EYES?|EYE DROPS?|EYE WASH|EYELID|CONTACT LENS|LENS SOLUTION|OPHTHALMIC|OCULAR',subcategories=('Eye Treatments','Eye, Ear & Nasal Combinations'),exclude=r'MASCARA|EYELINER|EYE LINER|EYE SHADOW|EYESHADOW|EYEBROW|FALSE LASH'),
 ConcernRule('First Aid','First-aid, wound care and clinical supplies.',r'WOUND|FIRST AID|BANDAGES?|GAUZE|PLASTERS?|ANTISEPTIC',categories=('First Aid & Medical Supplies',)),
 ConcernRule('Hair & Scalp','Hair and scalp care products.',r'SCALP|DANDRUFF|HAIR LOSS|SHAMPOO|CONDITIONER',categories=('Hair Care',)),
 ConcernRule('Heart & Circulation','Monitoring and explicitly labelled heart or circulation support.',r'BLOOD PRESSURE|CIRCULATION|CARDIOVASCULAR|HEART HEALTH|CHOLESTEROL',subcategories=('Blood Pressure Monitoring','Compression Stockings & Hosiery')),
 ConcernRule('Immune Support','Products explicitly labelled for immune support.',r'IMMUNE|IMMUNITY|IMMUNO'),
 ConcernRule("Men's Health",'Products explicitly labelled for male health needs.',r'PROSTATE|ERECTILE|MEN S HEALTH|MENS HEALTH|MALE FERTILITY'),
 ConcernRule('Oral Care','Dental hygiene and mouth care.',r'TOOTHPASTE|TOOTHBRUSH(?:ES)?|MOUTHWASH|DENTAL|DENTURE|GUM CARE',categories=('Oral Care',)),
 ConcernRule('Pain & Fever','Products explicitly labelled for pain or fever relief.',r'PAIN|PAINKILLER|PAINKILLERS|FEVER|ANALGESIC',exclude=r'PAINLESS|PAIN FREE PIERCING'),
 ConcernRule('Respiratory Health','Breathing devices and explicitly labelled respiratory products.',r'ASTHMA|RESPIRATORY|WHEEZING|BRONCHIAL|INHALERS?|NEBULI[ZS]ER',subcategories=('Inhalers & Respiratory Treatments','Respiratory Devices & Accessories')),
 ConcernRule('Sexual Health','Contraception, intimate hygiene and sexual wellness.',r'CONDOMS?|CONTRACEPTION|CONTRACEPTIVE|INTIMATE LUBRICANT',categories=('Sexual Wellness',)),
 ConcernRule('Skin Health','Skin care and explicitly labelled skin concerns.',r'ACNE|ECZEMA|DERMATITIS|PSORIASIS|RASH|SUNSCREEN|SKIN CARE',categories=('Skin Care',),subcategories=('Baby Bath, Skin & Sun Care','Body Moisturisers & Oils','Hand & Foot Care')),
 ConcernRule('Sleep & Stress','Products explicitly labelled for sleep, relaxation or stress support.',r'SLEEP|RELAXATION|STRESS|INSOMNIA',subcategories=('Sleep & Relaxation Supplements','Earplugs & Sleep Accessories'),exclude=r'STRESS BALL'),
 ConcernRule('Smoking Cessation','Nicotine replacement and explicitly labelled stop-smoking products.',r'STOP SMOKING|SMOKING CESSATION|NICOTINE PATCH|NICOTINE GUM|NICOTINE LOZENGE',subcategories=('Nicotine Replacement Products',),exclude=r'VAPE|E LIQUID|NICOTINE SALT|E CIG'),
 ConcernRule('Vitamins & Nutrition','Vitamins, minerals and nutritional supplements.',categories=('Vitamins & Supplements','Sports Nutrition')),
 ConcernRule("Women's Health",'Female reproductive, menstrual and maternity care.',r'MENOPAUSE|VAGINAL|FEMININE|WOMEN S HEALTH|WOMENS HEALTH',subcategories=('Maternity Supplements','Breastfeeding & Maternity Care','Sanitary Pads','Panty Liners','Tampons','Menstrual Cups')),
 ConcernRule('Acne & Blemishes','Products explicitly labelled for acne, blemishes or blackheads.',r'ACNE|BLEMISH(?:ES)?|BLACKHEADS?|PIMPLES?'),
 ConcernRule('Dry Skin & Hydration','Skin moisturising and hydration care.',r'DRY SKIN|DEHYDRATED SKIN|SKIN HYDRATION|HYDRATING|MOISTURI[ZS](?:ER|ERS|ING)',scope=('Skin Care','Bath & Body','Baby & Maternity'),subcategories=('Body Moisturisers & Oils',)),
 ConcernRule('Eczema & Dermatitis Care','Products explicitly labelled for eczema or dermatitis care.',r'ECZEMA|DERMATITIS'),
 ConcernRule('Sensitive Skin','Products explicitly labelled for sensitive skin.',r'SENSITIVE SKIN|SKIN SENSITIVE|ULTRA SENSITIVE',scope=('Skin Care','Bath & Body','Baby & Maternity')),
 ConcernRule('Sun Protection','Sunscreen, sun protection and after-sun products.',r'SUNSCREEN|SUNBLOCK|SUN BLOCK|SUN PROTECTION|AFTER SUN|SPF',subcategories=('Sun Protection & After-sun',)),
 ConcernRule('Scars & Stretch Marks','Products explicitly labelled for scars or stretch marks.',r'SCARS?|STRETCH MARKS?|STRECTH MARKS?'),
 ConcernRule('Anti-ageing Skin Care','Skincare explicitly labelled for ageing, wrinkles or firming.',r'ANTI AGEING|ANTI AGING|ANTIAGEING|ANTIAGING|WRINKLES?|FIRMING|LIFTING',scope=('Skin Care','Bath & Body')),
 ConcernRule('Dandruff Care','Hair products explicitly labelled for dandruff care.',r'DANDRUFF'),
 ConcernRule('Hair Thinning & Hair Loss','Products explicitly labelled for hair thinning or hair-loss care.',r'HAIR LOSS|HAIR THINNING|THINNING HAIR|HAIR REGROWTH|ANTI HAIR LOSS'),
 ConcernRule('Diabetes & Blood Glucose','Blood glucose monitoring and explicitly labelled diabetes care.',r'DIABETES|DIABETIC|BLOOD GLUCOSE|BLOOD SUGAR',subcategories=('Blood Glucose Monitoring',)),
 ConcernRule('Pregnancy & Breastfeeding','Maternity, prenatal and breastfeeding products.',r'PREGNANCY|PRENATAL|POSTNATAL|BREASTFEEDING|BREAST PUMP|MILK STORAGE|MATERNITY',subcategories=('Maternity Supplements','Breastfeeding & Maternity Care'),exclude=r'PREGNANCY TEST'),
 ConcernRule('Fertility & Ovulation','Fertility, ovulation and pregnancy testing products.',r'FERTILITY|OVULATION|PREGNANCY TEST',subcategories=('Pregnancy & Ovulation Tests',)),
 ConcernRule('Period Care','Sanitary pads, tampons, menstrual cups and period care.',r'MENSTRUAL|PERIOD PAIN|PERIOD CARE',subcategories=('Sanitary Pads','Panty Liners','Tampons','Menstrual Cups')),
 ConcernRule('Incontinence Care','Adult continence and absorbent care products.',r'INCONTINENCE|CONTINENCE|ADULT DIAPERS?|ADULT NAPPIES|BED WETTING',subcategories=('Adult Continence Care',)),
 ConcernRule('Foot Care','Foot care, insoles and ankle or foot supports.',r'FOOT CARE|FOOT CREAM|HEEL|INSOLES?|CALLUS|CALLOUS|CORN PADS?|PLANTAR',subcategories=('Ankle & Foot Supports',)),
 ConcernRule('Ear Care','Ear treatments, hearing aids and hearing protection.',r'EAR DROPS?|EAR WAX|EARWAX|EARPLUGS?|EAR PLUGS?|HEARING AID',subcategories=('Ear Treatments','Eye, Ear & Nasal Combinations','Hearing Aids & Accessories')),
 ConcernRule('Nasal & Sinus Care','Nasal and sinus care products.',r'NASAL|SINUS|NOSE SPRAY|NASOGEL',subcategories=('Nasal Treatments',)),
 ConcernRule('Heartburn & Acid Reflux','Products explicitly labelled for heartburn, acid reflux or antacid use.',r'HEARTBURN|ACID REFLUX|ANTACID'),
 ConcernRule('Constipation Care','Products explicitly labelled for constipation or laxative use.',r'CONSTIPATION|LAXATIVE'),
 ConcernRule('Diarrhoea & Rehydration','Products explicitly labelled for diarrhoea or oral rehydration.',r'DIARRHOEA|DIARRHEA|ORAL REHYDRATION'),
 ConcernRule('Energy & Sports Performance','Sports nutrition and explicitly labelled energy or performance products.',categories=('Sports Nutrition',),keywords=r'ENERGY|PERFORMANCE',scope=('Sports Nutrition','Vitamins & Supplements')),
 ConcernRule('Weight Management','Products explicitly labelled for weight management.',r'WEIGHT MANAGEMENT|WEIGHT LOSS|FAT BURNER|SLIMMING',subcategories=('Weight & Fitness Supplements',)),
 ConcernRule('Memory & Focus','Supplements explicitly labelled for memory, focus or concentration.',r'MEMORY|FOCUS|CONCENTRATION|BRAIN SUPPORT',scope=('Vitamins & Supplements','Sports Nutrition')),
 ConcernRule('Menopause Care','Products explicitly labelled for menopause care.',r'MENOPAUSE|MENOPAUSAL'),
)


def infer_concerns(name, category='', subcategory=''):
    return tuple(rule.name for rule in RULES if rule.match(name,category,subcategory))
