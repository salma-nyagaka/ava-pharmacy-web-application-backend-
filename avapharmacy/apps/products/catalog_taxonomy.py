"""Merchandising hierarchy derived from the local catalogue, not clinical advice.

Names and legacy departments determine browsing placement only. Prescription,
regulatory and clinical classifications are never inferred or modified here.
"""
from dataclasses import dataclass
import re

VERSION = 'catalog-taxonomy-2026-11-05-v1'

# key: (display name, reusable legacy category, icon)
CATEGORIES = {
 'medicines': ('Pharmacy & Medicines', 'DISPENSARY', 'medical'),
 'supplements': ('Vitamins & Supplements', 'SUPPLEMENTS', 'nutrition'),
 'sports': ('Sports Nutrition', 'BODY BUILDING', 'fitness'),
 'skin': ('Skin Care', 'SKIN CARE', 'skin'),
 'body': ('Bath & Body', 'COSMETICS', 'body'),
 'hair': ('Hair Care', 'HAIR CARE', 'hair'),
 'makeup': ('Makeup & Nails', 'MAKE UP', 'beauty'),
 'oral': ('Oral Care', 'ORAL CARE', 'oral'),
 'baby': ('Baby & Maternity', 'BABY CARE', 'baby'),
 'period': ('Period & Continence Care', 'SANITARY PADS AND DIAPERS', 'care'),
 'sexual': ('Sexual Wellness', '', 'wellness'),
 'firstaid': ('First Aid & Medical Supplies', 'MEDICAL SUPPLIES', 'first-aid'),
 'devices': ('Medical Devices & Home Health', 'MACHINES', 'devices'),
 'supports': ('Orthopaedic Supports & Mobility', 'SUPPORTS', 'support'),
 'food': ('Food & Drinks', '', 'food'),
 'aroma': ('Aromatherapy & Home Fragrance', 'ESSENTIAL OILS', 'aroma'),
 'fragrance': ('Fragrance & Deodorants', '', 'fragrance'),
 'grooming': ('Personal Care & Grooming', 'OTC OTHERS', 'care'),
 'smoking': ('Smoking & Vaping', 'STOP SMOKING AIDS', 'wellness'),
 'piercing': ('Ear Piercing & Jewellery', 'EAR PIERCING', 'jewellery'),
 'veterinary': ('Pet & Veterinary Care', 'VETINARY PRODUCTS', 'pets'),
 'services': ('Pharmacy Services', 'SERVICES', 'services'),
 'store': ('Store Supplies & Accessories', 'OTHERS', 'store'),
}


def normalize(value):
    return ' '.join(re.findall(r'[A-Z0-9]+', str(value or '').upper()))


def has(text, pattern):
    return bool(re.search(r'\b(?:' + pattern + r')\b', text))


@dataclass(frozen=True)
class Placement:
    category: str
    subcategory: str
    reason: str
    review: bool = False


def placement(category, subcategory, reason='Explicit product type in name', review=False):
    return Placement(category, subcategory, reason, review)


def medicine(name):
    name = re.sub(r'(\d)(TABLETS?|TABS?|TBS|CAPSULES?|CAPS)(?=\b)', r'\1 \2', name)
    if has(name, r'LIQUID GELS?|SOFTGELS?|SOFT GEL CAPSULES?'):
        return placement('medicines', 'Tablets & Capsules', 'Explicit oral capsule form')
    # Route/form are browsing dimensions, not a claim about indications or Rx.
    rules = [
      ('Eye, Ear & Nasal Combinations', r'EYE EAR|EYE AND EAR'),
      ('Eye Treatments', r'EYES?|OPHTHALMIC|OPTHALMIC|OCULAR|OPTREX|OPTIVE|HYLO'),
      ('Ear Treatments', r'EAR DROPS|EAR SPRAY|OTIC'),
      ('Nasal Treatments', r'NASAL|NASAAL|NASO|NOSE SPRAY'),
      ('Inhalers & Respiratory Treatments', r'INHALER|INHALATION|EVOHALER|DISKUS|TURBUHALER|RESPULES|NEBULES|NEBULISING|NEBULIZING'),
      ('Injections & Infusions', r'INJ|INJECTION|INJECTABLE|VIALS?|AMPOULES?|AMPUL[ES]*|INFUSION|INSULIN|KWIKPEN|MIXTARD|HUMALOG|HUMULIN|IV|I V|IMMUNOGLOBULIN|DEXTROSE|RINGERS'),
      ('Suppositories & Pessaries', r'SUPPOSITORIES|SUPPOSITORY|SUPPOSITORIRES|PESSARIES|PESSARY|VAGINAL TABLETS?|VAGINAL CAPSULES?'),
      ('Topical Treatments', r'CREAMS?|OINTMENTS?|OINT|GELS?|LOTIONS?|TOPICAL|JELLY|LINIMENT|BALM|RUB|MEDICATED SHAMPOO'),
      ('Lozenges & Throat Care', r'LOZENGES?|PASTILLES?|PASTILES|THROAT|RICOLA|FISHERMAN S FRIEND|JAKEMANS'),
      ('Oral Liquids & Powders', r'SYRUPS?|SUSPENSIONS?|SUSP|ORAL LIQUID|ORAL SOLUTION|MIXTURE|LINCTUS|POWDERS?|SACHETS?|SATCHETS|LIQUID|ELIXIR|LAXATIVE|ORS|ORAL REHYDRATION'),
      ('Tablets & Capsules', r'TABLETS?|TAB|TABS|TBS|CAPSULES?|CAPS|CAPLETS?|SOFTGELS?|CHEWABLE|DISPERSIBLE|EFFERVESCENT'),
      ('Other Pharmacy Items', r'.*'),
    ]
    for label, pattern in rules:
        if has(name, pattern):
            return placement('medicines', label, 'Medicine route/form or original pharmacy department', label == 'Other Pharmacy Items')


def supplements(name):
    for label, pattern in [
      ('Maternity Supplements', r'PREGNACARE|PRENATAL|POSTNATAL|PREGNANCY|STELLAR MAMA'),
      ('Children\'s Supplements', r'KIDS|KIDZ|KIDDZ|CHILDREN|CHILD|JUNIOR|BABY|WELLKID|WELLBABY|ACTIKID|CRECHE GUARD'),
      ('Probiotics & Digestive Support', r'PROBIOTIC|PROBIOTICS|PREBIOTIC|DIGESTIVE|ACIDOPHILUS|FIBRE|FIBER|PSYLLIUM'),
      ('Omega Oils & Essential Fatty Acids', r'OMEGA|FISH OIL|COD LIVER|KRILL|FLAXSEED|EVENING PRIMROSE|EFA'),
      ('Collagen, Hair, Skin & Nails', r'COLLAGEN|BIOTIN|HAIR|SKIN|NAILS|HAIRVIT|HAIR VIT'),
      ('Multivitamins', r'MULTIVIT(?:AMINS?)?|MULTI VITAMIN|DAILY MULTI|A Z|ABC Z|CENTRUM|WELLMAN|WELL MAN|WELLWOMAN|WELL WOMAN'),
      ('Vitamins', r'VITAMIN|VITAMINA|VIT C|VIT D|VIT B|VIT E|B12|B COMPLEX|FOLIC|FOLATE|ASCORBIC'),
      ('Minerals', r'MAGNESIUM|ZINC|CALCIUM|SELENIUM|IRON|POTASSIUM|CHROMIUM|MINERAL|COPPER'),
      ('Herbal & Botanical Supplements', r'ASHWAGANDHA|GINSENG|GINKGO|COHOSH|TURMERIC|CURCUMIN|FENUGREEK|MILK THISTLE|HERBAL|BOTANICAL|TRIBULUS|MACA|MORINGA|BLACK SEED|SAW PALMETTO|GARLIC|SPIRULINA'),
      ('Joint & Bone Supplements', r'JOINT|GLUCOSAMINE|CHONDROITIN|OSTEOCARE|JOINTACE'),
      ('Sleep & Relaxation Supplements', r'MELATONIN|SLEEP|RELAX|VALERIAN'),
      ('Weight & Fitness Supplements', r'WEIGHT|FAT BURNER|DIET|CLA|THERMOGENIC'),
      ('Antioxidants & Specialty Nutrients', r'COQ10|CO Q10|UBIQUINOL|RESVERATROL|ALPHA LIPOIC|LUTEIN|ASTAXANTHIN|QUERCETIN|NAC'),
      ('Other Nutritional Supplements', r'.*'),
    ]:
        if has(name, pattern):return placement('supplements', label, 'Supplement wording or original nutrition department')


def sports(name):
    for label, pattern in [
      ('Protein & Energy Snacks', r'BARS?|SNACKS?|COOKIES'),
      ('Protein Powders & Mass Gainers', r'WHEY|CASEIN|PROTEIN|MASS GAIN|MASS GAINER|SERIOUS MASS'),
      ('Creatine & Amino Acids', r'CREATINE|AMINO|BCAA|EAA|GLUTAMINE'),
      ('Energy, Hydration & Pre-workout', r'PRE WORKOUT|PREWORKOUT|ENERGY|ELECTROLYTE|HYDRATION|ISOTONIC|VOOMA'),
      ('Sports Bottles & Accessories', r'SHAKER|BOTTLE|BELT|GLOVES|ACCESSORIES'),
      ('Other Sports Supplements', r'.*'),
    ]:
        if has(name, pattern):return placement('sports', label, 'Sports nutrition product type or legacy sports department')


def baby(name):
    for label, pattern in [
      ('Infant & Toddler Formula', r'FORMULA|FORMULAR|APTAMIL|SIMILAC|NEOCATE|NUTRAMIGEN|SMA|NAN OPTIPRO|COW GATE|LACTOGEN|LIPTOMIL|KENDAMIL'),
      ('Breastfeeding & Maternity Care', r'BREAST|NIPPLE CREAM|MILK STORAGE|MATERNITY|LANSINOH|MEDELA|PIPPETA PUMP'),
      ('Bottles, Teats & Feeding', r'BOTTLES?|TEATS?|FEEDING|FEEDER|SPOUT|SIPPY|SILICONE CUP|STRAW CUP|BIBS?|WEANING|SPOON|BOWLS?'),
      ('Soothers, Teethers & Toys', r'PACIFIER|SOOTHER|TEETH|TEETHER|TOY|RATTLE'),
      ('Nappies & Baby Wipes', r'DIAPERS?|NAPPIES|NAPPY|WIPES|PAMPERS|HUGGIES'),
      ('Baby Bath, Skin & Sun Care', r'WASH|BATH|SHAMPOO|CREAM|LOTION|OIL|ECZEMA|SUN|SPF|BALM|SOAP|POWDER|CLEAN'),
      ('Baby Safety & Accessories', r'CAR SEAT|SAFETY|MONITOR|THERMOMETER|BRUSH|COMB|CLIPPER|SCISSORS|BAG'),
      ('Other Baby & Maternity Products', r'.*'),
    ]:
        if has(name, pattern):return placement('baby', label, 'Baby product wording or original baby department')


def supports(name):
    for label, pattern in [
      ('Mobility Aids & Daily Living', r'WHEELCHAIR|CRUTCH|WALKING|WALKER|ROLLATOR|CANE|COMMODE|SHOWER CHAIR|TOILET SEAT|EVACUATION CHAIR'),
      ('Compression Stockings & Hosiery', r'STOCKINGS?|HOSIERY|FLIGHT SOCKS?|COMPRESSION SOCKS|MEDICAL COMPRESSION'),
      ('Knee & Leg Supports', r'KNEE|PATELLA|THIGH|CALF|HAMSTRING|LEG'),
      ('Ankle & Foot Supports', r'ANKLE|ANKLET|HEEL|FOOT|ARCH|ARC|INSOLES?|IN SOLE|ORTHOTIC|TOE|PLANTAR|CAST SHOE'),
      ('Wrist, Hand & Finger Supports', r'WRIST|HAND|FINGER|THUMB|CARPAL'),
      ('Back, Waist & Abdominal Supports', r'BACK|LUMBAR|WAIST|ABDOMINAL|ABDOMEN|MATERNITY BELT|HERNIA|L S BELT'),
      ('Arm, Elbow & Shoulder Supports', r'ARM|ELBOW|SHOULDER|SLING|CLAVICLE'),
      ('Neck Supports & Pillows', r'NECK|CERVICAL|COLLAR|PILLOW|COCCYX|CUSHION'),
      ('Sports Tapes & Tubular Supports', r'TAPE|MWRAP|TUBIGRIP|TUBULAR|BANDAGE|STRAPPING'),
      ('Other Orthopaedic Supports', r'.*'),
    ]:
        if has(name, pattern):return placement('supports',label,'Anatomical support or original orthopaedic department',label=='Other Orthopaedic Supports')


def classify_item(name, legacy_category='', brand=''):
    n=normalize(name);old=normalize(legacy_category)
    # New imports reuse renamed roots through their stable slugs. Treat a
    # canonical root as its original department when filling missing children.
    canonical_sources = {normalize(display): normalize(legacy) for display, legacy, _ in CATEGORIES.values() if legacy}
    old = canonical_sources.get(old, old)
    if not n:
        return placement('store','Unspecified Catalog Entries','No descriptive product name',True)
    if n in {'TELEPHONE EXPENSES','SURGIPHARM LIMITED','SKIN PREPARATION','INTERNET'}:
        return placement('store','Unspecified Catalog Entries','Internal or insufficiently described legacy entry',True)
    if old=='VETINARY PRODUCTS' or has(n,r'VETERINARY|DEWORMING PET|PET SHAMPOO|DOG SHAMPOO|CAT SHAMPOO|DOGS|ADVANTIX|FRONTLINE'):
        return placement('veterinary','Veterinary Products','Original veterinary department or explicit pet wording')
    if has(n,r'SERVICE|SERVICES|CONSULTATION|MEAL PLAN|INSTALLATION FEE|LOCAL ANAESTHETIC APPLICATION|DRUGS DISPOSAL CHARGES|EXTEMPORANEOUS COMPOUNDING CHARGE|BLOOD PRESSURE WEIGHT BMI CHECK') or n in {'BLOOD GLUCOSE TEST','BLOOD PRESSURE TEST','CHOLESTEROL TEST','BLOOD GROUP TEST'}:
        if has(n,r'PIERCING'):sub='Ear Piercing Services'
        elif has(n,r'NUTRITION|MEAL PLAN'):sub='Nutrition Consultations'
        elif has(n,r'TEST|SCREEN|BLOOD|BMI|WEIGHT'):sub='Health Screening Services'
        elif has(n,r'DRESSING|WOUND'):sub='Wound Care Services'
        else:sub='Other Pharmacy Services'
        return placement('services',sub)
    if old=='STOP SMOKING AIDS' or has(n,r'VAPE|VAPING|E LIQUID|E LIQUIDS|E CIG|E CIGARETTE|NICOTINE|NICORETTE|NICOTINELL|NIQUITIN|OHM|MOSHI|NASTY SALT|DINNER LADY|SMOK|ELEAF|VAPORESSO|WISMEC|JUUL|NAKED 100'):
        if has(n,r'NICORETTE|NICOTINELL|NIQUITIN|NICOTINE PATCH|NICOTINE GUM|NICOTINE LOZENGE'):sub='Nicotine Replacement Products'
        elif has(n,r'COIL|COILS|ATOMIZER|ATOMISER|TANK|POD|PODS|BATTERY|CHARGER|CABLE|DRIP TIP|GLASS TUBE'):sub='Vape Coils, Pods & Accessories'
        elif has(n,r'KIT|DEVICE|VAPORISER|VAPORIZER|E CIG|E CIGARETTE|MOD'):sub='Vape Devices & Kits'
        else:sub='Vape Liquids'
        return placement('smoking',sub,'Explicit smoking/vaping wording or original department')
    if old=='EAR PIERCING' or has(n,r'EARRINGS?|EAR RINGS?|EAR PIERCING|STUDEX|CAFLON|PIERCING GUN|JEWELL?ERY'):
        sub='Piercing Aftercare' if has(n,r'AFTERCARE|CARE SOLUTION|CLEANSER|SWAB') else ('Piercing Instruments & Accessories' if has(n,r'GUN|INSTRUMENT|KIT') else 'Earrings & Studs')
        return placement('piercing',sub)
    if has(n,r'PREGNANCY|PRGNANCY|PREG TEST|OVULATION|CLEARBLUE|PERSONA CONTRACEPTIVE STICKS') and (has(n,r'TEST|TESTS|KIT|KITS|STRIP|STRIPS|CASSETTE|CASSETTES|CASSETTE|DETECTION|STICKS|CLEARBLUE')):
        return placement('devices','Pregnancy & Ovulation Tests')
    if has(n,r'GLUCOMETER|GLUCOMETERS|FREESTYLE LIBRE|ONE TOUCH.*STRIPS|CONTOUR.*STRIPS|GLUCOSE TESTING STRIPS|GLUCOSE TEST|GLUCOSE STRIPS|BLOOD SUGAR TEST|LANCETS?|LANCING|KETONE TEST'):
        return placement('devices','Blood Glucose Monitoring')
    if has(n,r'TEST KIT|TEST KITS|SELF TEST|RAPID TEST|URISCAN|URINALYSIS|HIV TEST|MALARIA TEST'):
        return placement('devices','Other Home & Diagnostic Tests')
    for sub,pat in [
      ('Blood Pressure Monitoring',r'BLOOD PRESSURE MONITOR|BLOOD PESSURE MONITOR|BP MONITOR|B P MONITOR|SPHYGMOMANOMETER|BP CUFF|SOFT CUFF|OMRON.*ADAPT(?:OR|ER|OER)'),
      ('Thermometers & Oximeters',r'THERMOMETER|THERMOSCAN|OXIMETER'),
      ('Respiratory Devices & Accessories',r'NEBULISER|NEBULIZER|NEBULIZATION|NEBULISATION|SPACER|AEROCHAMBER|SINUS INHALER|STEAM INHALER|VAPOPADS|OXYGEN CONCENTRATOR'),
      ('Hearing Aids & Accessories',r'HEARING AID|HEARING AIDS|HEARING AID BATTERY'),
      ('Heat, Cold, Massage & TENS',r'HEATING PAD|HEAT PATCH|HEAT PATCHES|HEATED|OVERBLANKET|UNDERBLANKET|TENS|MASSAGER|HOT WATER BOTTLE|HEAT PAD|HEAT PACK|COLD PACK|HOT COLD GEL PACK|ICE BRICKS|MASSAGE SLIPPER'),
      ('Weighing & Fitness Monitors',r'WEIGHING|COLUMN SCALE|BATHROOM SCALE|BODY SCALE|DIGITAL SCALE|LUGGAGE SCALES|PEDOMETER|FITNESS TRACKER'),
    ]:
        if has(n,pat):return placement('devices',sub)
    if old=='SUPPORTS' or has(n,r'(?:KNEE|ANKLE|WRIST|ELBOW|BACK|LUMBAR|HAND|THUMB|SHOULDER|NECK|ABDOMINAL).*SUPPORT|ORTHOPAEDIC|ORTHOPEDIC|ORTHOCARE|WHEELCHAIR|CRUTCHES|ROLLATOR|COMPRESSION STOCKING|KNEE SUP|FINGER SPLINT|ARM SLING|INSOLES?|ANKLET|EVACUATION CHAIR|ARCH SUPPORT|ARC SUPPORT|ANKLET|COMPRESSION SOCKS|CAST SHOE'):
        return supports(n)
    for sub,pat in [
      ('Gloves, Masks & Protective Wear',r'GLOVES|SURGICAL MASK|FACE MASK.*(?:N95|KN95|KF94|3 PLY)|(?:N95|KN95|KF94|3 PLY).*MASKS?|SURGICAL GOWN|DISPOSABLE APRON|SURGICAL CAP|SHOE COVER'),
      ('Needles, Syringes & IV Supplies',r'SYRINGES?|NEEDLES?|CANNULA|CANULLA|CANNULAE|GIVING SET|INFUSION SET|BUTTERFLY SET|IV SET|I V SET|FLOW REGULATOR'),
      ('Dressings, Bandages & Medical Tape',r'BANDAGES?|GAUZE|PLASTERS?|DRESSINGS?|DRESSING|MEDICAL TAPE|SURGICAL TAPE|LEUKOMED|LEUKOPLAST|LEUKOTAPE|MICROPOROUS TAPE|PRIMAPORE|OPSITE|BACTIGRAS|TUBIGRIP|BAND AID|ADVZORB|STERI STRIP|ELASTOPLAST|HANSAPLAST'),
      ('Antiseptics, Disinfectants & Sanitisers',r'ANTISEPTIC|DISINFECTANT|SANITI[ZS]ER|SANITI[ZS]ING|SURGICAL SPIRIT|METHYLATED SPIRIT|POVIDONE IODINE|HAND GEL.*ALCOHOL'),
      ('Cotton, Swabs & Wound Cleaning',r'STERILE SWAB|ALCOHOL SWAB|COTTON WOOL|SURGICAL COTTON|WOUND CLEAN|STERILE WATER|NORMAL SALINE|IRRIGATION'),
      ('Catheters, Bags & Clinical Supplies',r'CATHETER|URINE BAG|URINAL|STOMA|COLOSTOMY|OSTOMY|BEDPAN|EXAMINATION|SPECULUM|SURGICAL BLADE|SCALPEL|SUTURE|STEINMAN PIN|TOURNIQUET|SAMPLE CONTAINER|SPECIMEN CONTAINER'),
      ('First Aid Kits',r'FIRST AID KIT|FIRST AID BOX'),
    ]:
        if has(n,pat):return placement('firstaid',sub)
    # Correct a few unmistakable non-medicine types even if the imported
    # department was DISPENSARY.
    if has(n,r'OPI|O P I'):
        return placement('makeup','Manicure & Pedicure Tools' if has(n,r'FILE|CUTTER|CLIPPER') else 'Nail Colour & Treatments')
    if has(n,r'LUBE|CONDOMS?|VIBRATOR|VIBRATING|INTIMATE LUBRICANT|LUBRICATING JELLY') and not has(n,r'EYE|OCULAR'):
        return placement('sexual','Condoms' if has(n,r'CONDOMS?') else ('Intimate Lubricants' if has(n,r'LUBE|LUBRICANT|JELLY') else 'Intimate Accessories'))
    if old=='DISPENSARY' or has(n,r'CIFIXIME|CEFIXIME'):
        return medicine(n)
    # The next rules apply to unambiguous consumer product forms. They also fix
    # obvious cosmetics/food misplacements in legacy OTC departments.
    if old=='MILK FORMULAR' or has(n,r'INFANT FORMULA|BABY FORMULA|MILK FORMULA|APTAMIL|NEOCATE|NUTRAMIGEN|COW GATE|SIMILAC'):
        return placement('baby','Infant & Toddler Formula')
    if has(n,r'INCONTINENCE|ADULT DIAPERS?|ADULT NAPPIES|ADULT PANTS|ADULT SLIPS|TENA|ABENA|MOLICARE|MOLIMED|UNDERPADS?|BED PADS?'):
        return placement('period','Adult Continence Care')
    if has(n,r'SANITARY|TAMPOONS?|TAMPONS?|PANTY LINERS?|PANTYLINERS?|MENSTRUAL CUPS?|PERIOD PADS|KOTEX|LIL LETS|ALWAYS|COTTONS.*PADS|MOLIMED|DEPEND.*UNDERWEAR|KEDLEY.*BED PAD'):
        return placement('period','Menstrual Cups' if has(n,r'CUPS?') else ('Tampons' if has(n,r'TAMPOONS?|TAMPONS?') else ('Panty Liners' if has(n,r'LINER|LINERS|PANTYLINER|PANTYLINERS') else 'Sanitary Pads')))
    if old=='BABY CARE' or has(n,r'BREAST PUMP|BREAST MILK|NIPPLE CREAM|PACIFIER|SOOTHER|TEATS?|HUGGIES|PAMPERS|BABY|INFANT|NUBY|JAPLO|AVENT|DR BROWN S|DR BROWNS|NAPPY|NAPPIES|DIAPERS'):
        return baby(n)
    if has(n,r'CONDOMS?|VIBRATOR|VIBRATING|PLEASURE GEL|INTIMATE LUBRICANT|LUBRICATING JELLY|SEX TOY|ADULT TOY|SKINS.*TOY|DUREX|SKYN'):
        sub='Condoms' if has(n,r'CONDOMS?|SKYN|DUREX.*(?:FEEL|SAFE|REAL|EXTRA|THIN)') else ('Intimate Lubricants' if has(n,r'LUBRICANT|LUBRICATING|LUBE|JELLY|PLEASURE GEL') else 'Intimate Accessories')
        return placement('sexual',sub)
    if has(n,r'FEMININE WASH|INTIMATE WASH|VAGINAL WASH|FEMFRESH|LACTACYD|PH CARE|VAGISIL'):
        return placement('sexual','Intimate Hygiene')
    if has(n,r'SCENTED CANDLE|CANDLES?|ROOM SPRAY|ROOM.*FRAGRANCE|LINEN SPRAY|DIFFUSER|HUMIDIFIER|REED DIFFUSER'):
        return placement('aroma','Candles' if has(n,r'CANDLE|CANDLES') else ('Diffusers & Accessories' if has(n,r'DIFFUSER|HUMIDIFIER') else 'Room & Linen Fragrance'))
    if old=='ESSENTIAL OILS' or has(n,r'ESSENTIAL OIL|ESSENTIAL OILS|AROMATHERAPY OIL'):
        return placement('aroma','Essential Oils & Blends')
    if has(n,r'TOOTHPASTE|TOOTHBRUSH|TOOTHBRUSHES|WATER FLOSSER|MOUTHWASH|DENTAL FLOSS|INTERDENTAL|FLOSS N|DENTURE|FIXODENT|POLIGRIP|TEETH WHITEN|TOOTH POWDER|TONGUE CLEANER') or old=='ORAL CARE':
        if has(n,r'WATER FLOSSER'):sub='Electric Toothbrushes & Heads'
        elif has(n,r'DENTURE|FIXODENT|POLIGRIP'):sub='Denture Care'
        elif has(n,r'INTERDENTAL|FLOSS|TOOTHPICK'):sub='Floss & Interdental Cleaning'
        elif has(n,r'MOUTHWASH|MOUTH WASH|RINSE|ORAL GEL|GUM GEL'):sub='Mouthwash & Gum Care'
        elif has(n,r'ELECTRIC|REFILL HEAD|REPLACEMENT HEAD'):sub='Electric Toothbrushes & Heads'
        elif has(n,r'TOOTHBRUSH|TOOTHBRUSHES'):sub='Manual Toothbrushes'
        elif has(n,r'TOOTHPASTE|TOOTH POWDER'):sub='Toothpaste'
        else:sub='Other Oral Care'
        return placement('oral',sub)
    if has(n,r'MAKEUP REMOV|MAKE UP REMOV|MICELLAR'):
        return placement('skin','Cleansers & Makeup Removers')
    if has(n,r'NAIL POLISH|NAIL LACQUER|NAIL VARNISH|NAIL ENVY|CUTICLE|NAIL STRENGTH|NAIL HARDEN|NAIL GLUE|FALSE NAIL|GEL NAIL|OPI|O P I'):
        return placement('makeup','Nail Colour & Treatments')
    if has(n,r'NAIL FILE|NAIL CUTTER|NAIL CLIPPER|MANICURE|PEDICURE|NAIL SCISSORS|NAIL BUFFER') or old=='NAIL CARE':
        return placement('makeup','Manicure & Pedicure Tools')
    for sub,pat in [
      ('Eye & Brow Makeup',r'MASCARA|EYELINER|EYE LINER|EYESHADOW|EYE SHADOW|EYEBROW|BROW PENCIL|BROW GEL|BROW KIT|LIQUID LINER|FALSE LASH|EYELASH'),
      ('Lip Colour',r'LIPSTICK|LIP STICK|LIP GLOSS|LIPGLOSS|LIP SHOT|LIP SHOTS|BALM STAIN|MATTE BALM|LIP LINER|LIP COLOR|LIP COLOUR|LIP TINT'),
      ('Face Makeup',r'FOUNDATION|CONCEALER|BLUSH|BRONZER|SETTING POWDER|SETTING SPRAY|PRESSED POWDER|COMPACT POWDER|FACE POWDER|PRIMER|HIGHLIGHTER|HIGHLIGHTING PALETTE|FACE CONTOUR|FOUNDATION|FOUNATION|BLUSHER|CREME POWDER|CREME TO POWDER|COMPACT|MATTE LIP|PRO PREP|MATTE ME|CONTOUR PALETTE|BB CREAM|CC CREAM'),
      ('Makeup Tools & Accessories',r'MAKEUP BRUSHES?|MAKE UP BRUSHES?|MAKEUP SPONGE|MAKE UP SPONGE|BEAUTY BLENDER|POWDER PUFF|COSMETIC MIRROR|MAKEUP BAG|MAKE UP BAG'),
    ]:
        if has(n,pat):return placement('makeup',sub)
    if has(n,r'PERFUME|FRAGRANCE MIST|BODY MIST|EAU DE|EAU DU|COLOGNE|AFTERSHAVE|AFTER SHAVE|EDT|EDP|FINE FRAGRANCE COLLECTION'):
        return placement('fragrance','Body & Fragrance Mists' if has(n,r'MIST') else 'Perfumes & Colognes')
    if has(n,r'DEODORANT|DEDORANT|DEO|ANTIPERSPIRANT|ANTI PERSPIRANT|BODY SPRAY'):
        return placement('fragrance','Deodorants & Antiperspirants')
    if has(n,r'GILLETTE|RAZORS?|RAZER|SHAVING|SHAVE|AFTERSHAVE BALM|TRIMMER|SHAVER|HAIR CLIPPER|HAIR REMOV|DEPILATORY|WAX STRIP|WAX KIT|WAX BEADS'):
        return placement('grooming','Hair Removal & Waxing' if has(n,r'HAIR REMOV|DEPILATORY|WAX') else 'Shaving & Trimming')
    if has(n,r'EARPLUGS?|EAR PLUGS?|SLEEP MASK|EYE MASK.*SLEEP'):
        return placement('grooming','Earplugs & Sleep Accessories')
    if has(n,r'SUNSCREEN|SUN CREAM|SUN LOTION|SUNBLOCK|SUN BLOCK|SPF|AFTER SUN|UV FILTER'):
        return placement('skin','Sun Protection & After-sun')
    if has(n,r'MOSQUITO|INSECT REPELL|REPELENT|REPELLENT|DEET|ODOMOS|JUNGLE FORMULA|JUNGLE FORMULAR'):
        return placement('body','Insect Repellents & Bite Care')
    if has(n,r'LIP BALM|LIP BUTTER|LIP SCRUB|LIP OIL|LIP CARE|LIP REPAIR') or old=='LIP CARE':
        return placement('skin','Lip Care')
    if has(n,r'BATH SPONGE|BATH BRUSH|LOOFAH|LOOFA|BATH TOWEL|SHOWER CAP|SHOWER PUFF|MASSAGE SPONGE'):
        return placement('body','Bath Accessories')
    if has(n,r'SHOWER GEL|BODY WASH|BATH AND SHOWER|BATH SHOWER|BUBBLE BATH|BATH SALT|BATH BOMB|HAND WASH|HANDWASH|BODY SOAP|SOAP BAR|BEAUTY BAR|HERBAL SOAP|ANTIBACTERIAL SOAP'):
        return placement('body','Hand & Body Cleansing' if not has(n,r'BATH SALT|BATH BOMB') else 'Bath Salts & Bath Bombs')
    if has(n,r'HAND CREAM|FOOT CREAM|HEEL CREAM|HAND AND NAIL|HAND NAIL|CRACKED HEEL|FOOT BALM|FOOT FILE|PUMICE'):
        return placement('body','Hand & Foot Care')
    if has(n,r'BODY LOTION|BODY CREAM|BODY BUTTER|BODY OIL|BODY SCRUB|BODY POLISH|SHEA BUTTER|SUGAR SCRUB|PETROLEUM JELLY'):
        return placement('body','Body Scrubs & Exfoliators' if has(n,r'SCRUB|POLISH') else 'Body Moisturisers & Oils')
    if old=='HAIR CARE' or has(n,r'SHAMPOO|CONDITIONER|HAIR GEL|HAIR OIL|HAIR FOOD|HAIR SPRAY|HAIRSPRAY|HAIR DYE|HAIR COLOUR|HAIR COLOR|HAIR MASK|HAIR SERUM|HAIR COMB|COMBS?|HAIR BRUSH|WOODEN BRUSH|HAIR BANDS|RUBBER BANDS|HAIR CLIPS|BLOW DRY|HAIR DRYER|BEARD OIL|BEARD BALM|BEARD WASH|BEARD BRUSH|POMADE|EDGE CONTROL|SCHWARZKOPF|CANTU|SHEAMOISTURE|WEAVING CAP|HEADBAND|HAIR RINGS|HAIR BEADS|WOODEN BEADS|RUBBER BANDS|BUTTERFLY CLP|HAIR ACCESSORIES|STYING GEL'):
        if has(n,r'BEARD'):sub='Beard Care'
        elif has(n,r'SHAMPOO'):sub='Shampoos'
        elif has(n,r'CONDITIONER|LEAVE IN|HAIR MASK|DEEP TREATMENT'):sub='Conditioners & Hair Masks'
        elif has(n,r'COLOUR|COLOR|DYE|HENNA|RELAXER|BLEACH'):sub='Hair Colour & Relaxers'
        elif has(n,r'COMB|BRUSH|BAND|BANDS|CLIPS|CLIP|DRYER|STRAIGHTENER|CURLER|BONNET|WIG|WEAVING CAP|BEADS'):sub='Hair Tools & Accessories'
        elif has(n,r'OIL|SERUM|FOOD|SCALP|HAIR LOSS|REGROWTH'):sub='Hair & Scalp Treatments'
        else:sub='Styling & Other Hair Care'
        return placement('hair',sub)
    # Consumer skincare forms must be resolved before vitamin wording: a
    # vitamin-C facial serum is skincare, not a dietary vitamin supplement.
    if has(n,r'FACIAL|FACE WASH|FACE CREAM|FACE LOTION|CLEANSER|TONER|SERUM|SERUMS|MOISTURI[ZS]ER|FACE MASK|MASK SHEET|SHEET MASK|ACNE|RETINOL|HYALURONIC|SKIN BRIGHT|SCAR|STRETCH MARK|STRECTH MARK|SCRUB|GARNIER PURE ACTIVE|WITCH HAZEL WATER|GLYCERINE|ROSEHIP SEED OIL') or old=='SKIN CARE' or (old in {'COSMETICS','OTC','OTC OTHERS','MACHINES'} and has(n,r'CREAM|LOTION|BALM|SKIN OIL|SOAP')):
        if has(n,r'CLEANSER|FACE WASH|FACIAL WASH|CLEANSING|SOAP'):sub='Cleansers & Makeup Removers'
        elif has(n,r'TONER|TONIC|ROSE WATER|WITCH HAZEL'):sub='Toners & Facial Mists'
        elif has(n,r'SCRUB|PEEL|EXFOLIAT'):sub='Facial Scrubs & Exfoliators'
        elif has(n,r'MASK'):sub='Face Masks'
        elif has(n,r'EYE'):sub='Eye Care'
        elif has(n,r'SERUM|RETINOL|ACID|VITAMIN C'):sub='Serums & Targeted Treatments'
        elif has(n,r'SCAR|STRETCH MARK|ECZEMA|ACNE|BLEMISH'):sub='Targeted Skin Care'
        else:sub='Moisturisers & Other Skin Care'
        return placement('skin',sub)
    if has(n,r'PROTEIN BAR|PROTEIN BARS|WHEY|MASS GAINER|PRE WORKOUT|PREWORKOUT|CREATINE|BCAA|ISOTONIC|ENERGY GEL') or old=='BODY BUILDING':return sports(n)
    if has(n,r'CHOCOLATE|CHOCOLATERIE|CHEWING GUM|MENTOS|CHUPA CHUPS|SKITTLES|WRIGLEY|WRIGLEYS|WRIGLEY S|TRIDENT|CANDY|CANDIES|SWEETS|LOLLIPOP|ORBIT GUM|M M S|JUICY FRUIT'):
        return placement('food','Confectionery & Chewing Gum')
    if has(n,r'MINERAL WATER|DRINKING WATER|SPARKLING WATER|DASANI|SODA|SOFT DRINK|ENERGY DRINK|FRUIT JUICE|COCONUT WATER'):
        return placement('food','Water & Drinks')
    if has(n,r'HONEY|STEVIA|SWEETENER|SWEETEX|CANDEREL|HERBAL TEA|GREEN TEA BAGS|COCONUT OIL.*(?:COOKING|SPOON A DAY)|TAM TAM SPOON'):
        return placement('food','Honey, Sweeteners & Pantry Foods')
    if has(n,r'VITAMIN|VITAMINA|MULTIVIT(?:AMINS?)?|MULTI VIT|PROBIOTIC|OMEGA|BIOTIN|COLLAGEN|MAGNESIUM|ASHWAGANDHA|GINSENG|COENZYME|COQ10|FOLIC|MINERALS|STELLAR MAMA|WELLBETX') or old in {'SUPPLEMENTS','NUTRITION'} or normalize(brand) in {'SOLGAR','SWANSON','HEALTHAID','QUEST','VITABIOTICS','LIFE EXTENSION','NATURAL FACTORS','NATURE S WAY','NATURE S BOUNTY','NATURE S TRUTH','NOW FOODS','HOLLAND BARRETT','HOLLAND AND BARRETT'}:
        return supplements(n)
    if n.startswith(('NOW ', 'TM ZINC ', 'NATURE S THRUTH ', 'WELLBETX ', 'ACTILIFE ')):
        return supplements(n)
    if old=='OTC MEDICINE' or has(n,r'MUCINEX|GAVISCON|GVISCON|LIQUID GELS|TABLETS?|TABS?|TBS|CAPSULES?|SYRUP|SUSPENSION|NASAL SPRAY|OPHTHALMIC|EYE DROPS?|EAR DROPS?'):
        return medicine(n)
    if has(n,r'WATER BOTTLE|TRAVEL MUG|STANLEY CUP|TUMBLER|CONTIGO|SPORTS BOTTLE|DRINKING BOTTLE'):
        return placement('store','Reusable Bottles & Drinkware')
    if has(n,r'PAPERBAG|PAPER BAG|PAPERBAGS|PACKAGING BAGS?|DISPENSING ENVELOPES?|CARRIER BAGS?|SHOPPING BAGS?'):
        return placement('store','Packaging & Dispensing Supplies')
    if has(n,r'WIPES|WET TISSUE|TISSUES|TOILET PAPER|COTTON BUDS?|COSMETIC BUDS?|COTTON PADS?|COTTON BALLS?'):
        return placement('grooming','Wipes, Tissues & Cotton Accessories')
    if has(n,r'TOILETRY|TOILETER|TRAVEL BOTTLE|WASH BAG|TOILET BAG|SPRAY BOTTLE|SPRAY WATTER BOTTLE|MAKEUP TOOLS|MAKE UP TOOLS|TWEEZERS?|MIRROR|SCISSORS'):
        return placement('grooming','Travel & Grooming Accessories')
    fallback={
      'SEXUAL WELLNESS':('sexual','Intimate Accessories'),
      'FOOD DRINKS':('food','Honey, Sweeteners & Pantry Foods'),
      'FRAGRANCE DEODORANTS':('fragrance','Perfumes & Colognes'),
      'ANTISEPTICS AND DISINFECTANTS':('firstaid','Antiseptics, Disinfectants & Sanitisers'),
      'MEDICAL SUPPLIES':('firstaid','Other Clinical Supplies'),
      'MACHINES':('devices','Other Home Health Devices'),
      'HEALTH TECH':('devices','Other Home Health Devices'),
      'TESTS':('devices','Other Home & Diagnostic Tests'),
      'MAKE UP':('makeup','Other Makeup'),
      'SANITARY PADS AND DIAPERS':('period','Other Period & Continence Products'),
      'COSMETICS':('grooming','Other Personal Care'),
      'OTC':('grooming','Other Personal Care'),
      'OTC OTHERS':('grooming','Other Personal Care'),
      'OTHERS':('store','Other Store Accessories'),
      'SERVICES':('store','Unspecified Catalog Entries'),
    }
    if old in fallback:
        cat,sub=fallback[old]
        return placement(cat,sub,'Broad placement retained from original department; review recommended',True)
    return placement('store','Unspecified Catalog Entries','Insufficient descriptive information; review required',True)
