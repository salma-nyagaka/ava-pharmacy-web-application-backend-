"""Conservative catalogue classification rules for legacy product names.

The legacy SQL exports contain product display names but almost no brand or
clinical metadata.  These rules intentionally favour precision over coverage:
brands must be a recognised leading label, while health concerns use broad,
customer-friendly categories and may have more than one match.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable


def normalized_rule_text(value: str) -> str:
    return ' '.join(re.findall(r'[A-Z0-9]+', str(value or '').upper()))


# Canonical label -> catalogue spellings.  Only leading-name matches are used.
# This prevents incidental mentions such as "compatible with Oral-B" from
# assigning the wrong brand.
BRAND_ALIASES: dict[str, tuple[str, ...]] = {
    "3M": ("3M",),
    "Abena": ("ABENA",),
    "Always": ("ALWAYS",),
    "Anashe": ("ANASHE",),
    "Anua": ("ANUA",),
    "Aptamil": ("APTAMIL",),
    "Aquaphor": ("AQUAPHOR",),
    "Arm & Hammer": ("ARM & HAMMER", "ARM AND HAMMER"),
    "Aunt Jackie's": ("AUNT JACKIES", "AUNT JACKIE'S"),
    "Avent": ("AVENT", "PHILIPS AVENT"),
    "Aveeno": ("AVEENO",),
    "Avène": ("AVENE",),
    "Avon": ("AVON",),
    "Axe": ("AXE",),
    "Batiste": ("BATISTE",),
    "Bath & Body Works": ("BATH AND BODY WORKS", "BATH & BODY WORKS"),
    "Baylis & Harding": ("BAYLIS & HARDING", "BAYLIS AND HARDING"),
    "Benadryl": ("BENADRYL",),
    "Benylin": ("BENYLIN",),
    "Berocca": ("BEROCCA",),
    "Beurer": ("BEURER",),
    "Bigen": ("BIGEN",),
    "Bioderma": ("BIODERMA",),
    "Bioglan": ("BIOGLAN",),
    "BioTechUSA": ("BIOTECH USA", "BIOTECHUSA"),
    "Blistex": ("BLISTEX",),
    "BSN": ("BSN",),
    "Burt's Bees": ("BURTS BEES", "BURT'S BEES"),
    "Calpol": ("CALPOL",),
    "Cantu": ("CANTU",),
    "Careway": ("CAREWAY",),
    "Carmex": ("CARMEX",),
    "Carnation": ("CARNATION",),
    "Cellucor": ("CELLUCOR",),
    "Centrum": ("CENTRUM",),
    "CeraVe": ("CERAVE",),
    "Cetaphil": ("CETAPHIL",),
    "Chicco": ("CHICCO",),
    "Clearblue": ("CLEARBLUE",),
    "Colgate": ("COLGATE",),
    "Contigo": ("CONTIGO",),
    "COSRX": ("COSRX",),
    "Covonia": ("COVONIA",),
    "Denman": ("DENMAN",),
    "Dove": ("DOVE",),
    "Dr. Brown's": ("DR BROWNS", "DR BROWN'S", "DR BROWN"),
    "Dulcolax": ("DULCOLAX",),
    "Durex": ("DUREX",),
    "E45": ("E45",),
    "Elastoplast": ("ELASTOPLAST",),
    "ENO": ("ENO",),
    "Epi-Max": ("EPIMAX", "EPI MAX"),
    "EOS": ("EOS",),
    "Eucerin": ("EUCERIN",),
    "Fillerina": ("FILLERINA",),
    "Fixodent": ("FIXODENT",),
    "Garnier": ("GARNIER",),
    "Gaviscon": ("GAVISCON",),
    "Gillette": ("GILLETTE",),
    "Halls": ("HALLS",),
    "Haliborange": ("HALIBORANGE",),
    "Heliocare": ("HELIOCARE",),
    "Higher Nature": ("HIGHER NATURE",),
    "Huggies": ("HUGGIES",),
    "I'm From": ("I M FROM", "I'M FROM"),
    "Jamieson": ("JAMIESON",),
    "Johnson's": ("JOHNSONS", "JOHN'SONS", "JOHNSON'S"),
    "Kedley": ("KEDLEY",),
    "Kotex": ("KOTEX",),
    "L.A. Girl": ("L A GIRL", "LA GIRL"),
    "La Roche-Posay": ("LA ROCHE POSAY",),
    "Lamberts": ("LAMBERTS",),
    "Lansinoh": ("LANSINOH",),
    "Lemsip": ("LEMSIP",),
    "Life Extension": ("LIFE EXTENSION",),
    "Lil-Lets": ("LIL LETS", "LILLETS"),
    "Listerine": ("LISTERINE",),
    "L'Oréal": ("LOREAL", "L OREAL"),
    "Malibu": ("MALIBU",),
    "Maybelline": ("MAYBELLINE",),
    "Medela": ("MEDELA",),
    "Microlife": ("MICROLIFE",),
    "Mielle": ("MIELLE",),
    "Milton": ("MILTON",),
    "Mitchum": ("MITCHUM",),
    "Mueller": ("MUELLER",),
    "MUA": ("MUA",),
    "Natural Factors": ("NATURAL FACTORS",),
    "Naturium": ("NATURIUM",),
    "Nature's Aid": ("NATURES AID", "NATURE'S AID"),
    "Nature's Plus": ("NATURES PLUS", "NATURE'S PLUS"),
    "NeilMed": ("NEILMED",),
    "NeoStrata": ("NEOSTRATA",),
    "Neutrogena": ("NEUTROGENA",),
    "Nicorette": ("NICORETTE",),
    "Nivea": ("NIVEA",),
    "NOW Foods": ("NOW FOODS", "NOW",),
    "Nuby": ("NUBY",),
    "Nurofen": ("NUROFEN",),
    "Old Spice": ("OLD SPICE",),
    "Olay": ("OLAY",),
    "Olimp": ("OLIMP",),
    "Omron": ("OMRON",),
    "Optimum Nutrition": ("OPTIMUM NUTRITION",),
    "Optrex": ("OPTREX",),
    "Oral-B": ("ORAL B", "ORAL-B"),
    "Otrivine": ("OTRIVINE",),
    "Palmer's": ("PALMERS", "PALMER'S", "PALMER"),
    "Panadol": ("PANADOL",),
    "Pepto-Bismol": ("PEPTO BISMOL",),
    "PhD Nutrition": ("PHD NUTRITION", "PHD",),
    "Profoot": ("PROFOOT",),
    "Revlon": ("REVLON",),
    "Sambucol": ("SAMBUCOL",),
    "Scholl": ("SCHOLL",),
    "Schwarzkopf": ("SCHWARZKOPF",),
    "Sebamed": ("SEBAMED",),
    "Secret": ("SECRET",),
    "Sensodyne": ("SENSODYNE",),
    "Seven Seas": ("SEVEN SEAS",),
    "SheaMoisture": ("SHEA MOISTURE", "SHEAMOISTURE"),
    "Simple": ("SIMPLE",),
    "Sleek": ("SLEEK",),
    "SMOK": ("SMOK",),
    "Solgar": ("SOLGAR",),
    "Stanley": ("STANLEY",),
    "Sterimar": ("STERIMAR",),
    "Strepsils": ("STREPSILS",),
    "Sudafed": ("SUDAFED",),
    "Summer's Eve": ("SUMMERS EVE", "SUMMER'S EVE"),
    "Sundown": ("SUNDOWN",),
    "Sure": ("SURE",),
    "Tampax": ("TAMPAX",),
    "TENA": ("TENA",),
    "TePe": ("TEPE",),
    "The Body Shop": ("THE BODY SHOP",),
    "The Ordinary": ("THE ORDINARY",),
    "Titania": ("TITANIA",),
    "Tynor": ("TYNOR",),
    "Tylenol": ("TYLENOL",),
    "Uriage": ("URIAGE",),
    "USN": ("USN",),
    "Vagisil": ("VAGISIL",),
    "Valupak": ("VALUPAK",),
    "Vaseline": ("VASELINE",),
    "Veet": ("VEET",),
    "Vichy": ("VICHY",),
    "Victoria's Secret": ("VICTORIAS SECRET", "VICTORIA SECRET", "VICTORIA'S SECRET"),
    "Viridian": ("VIRIDIAN",),
    "Visine": ("VISINE",),
    "Vitabiotics": ("VITABIOTICS",),
    "Vicks": ("VICKS",),
    "Waterpik": ("WATERPIK",),
    "Webber Naturals": ("WEBBER NATURALS",),
    "Wella": ("WELLA",),
    "Wet Brush": ("WET BRUSH",),
    "Wisdom": ("WISDOM",),
}


def _compiled_brand_aliases() -> tuple[tuple[str, str], ...]:
    entries = [
        (normalized_rule_text(alias), canonical)
        for canonical, aliases in BRAND_ALIASES.items()
        for alias in aliases
    ]
    return tuple(sorted(entries, key=lambda item: (-len(item[0]), item[1])))


COMPILED_BRAND_ALIASES = _compiled_brand_aliases()


def infer_brand_name(product_name: str) -> str | None:
    name = normalized_rule_text(product_name)
    for alias, canonical in COMPILED_BRAND_ALIASES:
        if name == alias or name.startswith(f'{alias} '):
            return canonical
    return None


@dataclass(frozen=True)
class HealthConcernRule:
    name: str
    description: str
    icon: str
    categories: tuple[str, ...] = ()
    keywords: tuple[str, ...] = ()

    def matches(self, *, name: str, description: str, category: str) -> bool:
        normalized_category = normalized_rule_text(category)
        if normalized_category in {normalized_rule_text(value) for value in self.categories}:
            return True
        haystack = f' {normalized_rule_text(name)} {normalized_rule_text(description)} '
        return any(f' {normalized_rule_text(keyword)} ' in haystack for keyword in self.keywords)


HEALTH_CONCERN_RULES: tuple[HealthConcernRule, ...] = (
    HealthConcernRule('Allergy Relief', 'Products commonly used for allergy symptom relief.', 'allergy', keywords=('ALLERGY', 'ANTIHISTAMINE', 'CETIRIZINE', 'LORATADINE', 'FEXOFENADINE', 'CHLORPHENIRAMINE', 'PIRITON')),
    HealthConcernRule('Baby & Child Care', 'Everyday health and care products for babies and children.', 'baby', categories=('BABY CARE', 'MILK FORMULAR'), keywords=('BABY', 'INFANT', 'PAEDIATRIC', 'PEDIATRIC', 'CHILDREN')),
    HealthConcernRule('Bone, Joint & Muscle', 'Support for bones, joints, muscles and mobility.', 'bone', categories=('SUPPORTS',), keywords=('JOINT', 'ARTHRITIS', 'MUSCLE', 'KNEE', 'ANKLE', 'WRIST', 'BACK SUPPORT', 'CALCIUM')),
    HealthConcernRule('Cold, Cough & Flu', 'Symptom relief for colds, coughs, flu and sore throats.', 'cold', keywords=('COUGH', 'COLD', 'FLU', 'SORE THROAT', 'DECONGEST', 'EXPECTORANT', 'LEMSIP', 'STREPSILS')),
    HealthConcernRule('Digestive Health', 'Support for digestion, reflux, constipation and diarrhoea.', 'digestive', keywords=('ANTACID', 'HEARTBURN', 'REFLUX', 'CONSTIPATION', 'DIARRHOEA', 'DIARRHEA', 'PROBIOTIC', 'GAVISCON', 'DULCOLAX', 'OMEPRAZOLE', 'LANSOPRAZOLE')),
    HealthConcernRule('Eye Care', 'Products for eye comfort, cleansing and vision care.', 'eye', keywords=('EYE DROP', 'DRY EYE', 'EYELID', 'OCULAR', 'OPTREX', 'VISINE', 'CONTACT LENS')),
    HealthConcernRule('First Aid', 'First-aid, wound-care and antiseptic essentials.', 'first-aid', categories=('ANTISEPTICS AND DISINFECTANTS',), keywords=('PLASTER', 'BANDAGE', 'DRESSING', 'WOUND', 'ANTISEPTIC', 'FIRST AID', 'GAUZE')),
    HealthConcernRule('Hair & Scalp', 'Hair and scalp care, including dandruff and hair-loss support.', 'hair', categories=('HAIR CARE',), keywords=('DANDRUFF', 'SCALP', 'HAIR LOSS', 'SHAMPOO', 'CONDITIONER')),
    HealthConcernRule('Heart & Circulation', 'Products associated with cardiovascular and circulation support.', 'heart', keywords=('BLOOD PRESSURE', 'HYPERTENSION', 'CHOLESTEROL', 'AMLODIPINE', 'LOSARTAN', 'ATORVASTATIN', 'HEART')),
    HealthConcernRule('Immune Support', 'Vitamins and supplements commonly used for immune support.', 'immune', keywords=('IMMUNE', 'IMMUNITY', 'VITAMIN C', 'ZINC', 'ECHINACEA', 'SAMBUCOL')),
    HealthConcernRule("Men's Health", "Products associated with men's personal and reproductive health.", 'male', keywords=('PROSTATE', 'ERECTILE', 'MEN S HEALTH', 'MENS HEALTH')),
    HealthConcernRule('Oral Care', 'Dental hygiene, gum care and mouth-care products.', 'oral', categories=('ORAL CARE',), keywords=('TOOTHPASTE', 'TOOTHBRUSH', 'MOUTHWASH', 'DENTAL', 'GUM CARE', 'DENTURE')),
    HealthConcernRule('Pain & Fever', 'Products commonly used for pain or fever relief.', 'pain', keywords=('PAIN', 'FEVER', 'PARACETAMOL', 'IBUPROFEN', 'ASPIRIN', 'DICLOFENAC', 'NAPROXEN', 'PANADOL', 'NUROFEN', 'TYLENOL')),
    HealthConcernRule('Respiratory Health', 'Products associated with breathing and respiratory support.', 'lungs', keywords=('ASTHMA', 'INHALER', 'SALBUTAMOL', 'WHEEZ', 'BRONCH', 'RESPIRATORY')),
    HealthConcernRule('Sexual Health', 'Contraception, intimate care and sexual-wellness products.', 'sexual-health', keywords=('CONDOM', 'LUBRICANT', 'DUREX', 'EMERGENCY CONTRACEPT', 'PREGNANCY TEST')),
    HealthConcernRule('Skin Health', 'Skin care and support for common skin concerns.', 'skin', categories=('SKIN CARE',), keywords=('ACNE', 'ECZEMA', 'DERMATITIS', 'PSORIASIS', 'RASH', 'SUNSCREEN', 'MOISTURISER', 'MOISTURIZER')),
    HealthConcernRule('Sleep & Stress', 'Products associated with sleep, relaxation and stress support.', 'sleep', keywords=('SLEEP', 'MELATONIN', 'RELAX', 'STRESS', 'VALERIAN', 'INSOMNIA')),
    HealthConcernRule('Smoking Cessation', 'Products intended to support stopping smoking.', 'no-smoking', categories=('STOP SMOKING AIDS',), keywords=('NICORETTE', 'NICOTINE PATCH', 'NICOTINE GUM', 'STOP SMOKING')),
    HealthConcernRule('Vitamins & Nutrition', 'Vitamins, minerals, sports nutrition and dietary supplements.', 'nutrition', categories=('NUTRITION', 'SUPPLEMENTS', 'BODY BUILDING'), keywords=('MULTIVITAMIN', 'VITAMIN', 'MINERAL', 'PROTEIN', 'CREATINE', 'OMEGA 3')),
    HealthConcernRule("Women's Health", "Products associated with women's personal and reproductive health.", 'female', categories=('SANITARY PADS AND DIAPERS',), keywords=('MENOPAUSE', 'VAGINAL', 'THRUSH', 'FEMININE', 'SANITARY PAD', 'TAMPON', 'MATERNITY')),
)


def infer_health_concerns(*, name: str, description: str, category: str) -> tuple[str, ...]:
    return tuple(
        rule.name
        for rule in HEALTH_CONCERN_RULES
        if rule.matches(name=name, description=description, category=category)
    )


def iter_health_concern_definitions() -> Iterable[HealthConcernRule]:
    return HEALTH_CONCERN_RULES
