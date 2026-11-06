"""Extract printed measurements only; never infer clinical doses or pack counts."""
import re
from dataclasses import dataclass

NUMBER = r'\d+(?:\.\d+)?'
UNIT = r'(?:MCG|ΜG|UG|MG|IU|I\.?U\.?|MEQ|MMOL)'
STRENGTH = re.compile(rf'(?<![\w.]){NUMBER}(?:\s*/\s*{NUMBER})*\s*{UNIT}(?:\s*/\s*(?:{NUMBER}\s*)?(?:ML|L|G))?(?![A-Z])|(?<![\w.]){NUMBER}(?:\s*/\s*{NUMBER})*\s*%', re.I)
SIZE = re.compile(rf'(?<![\w.]){NUMBER}\s*(?:ML|LITRES?|LITERS?|L|KG|G|GRAMS?|OZ|FL\s*OZ)(?![A-Z])', re.I)
COUNT = re.compile(rf"(?<![\w.])({NUMBER})\s*(?:['’]S\b|S\b|TABLETS?\b|TABS?\b|CAPSULES?\b|CAPS?\b|SACHETS?\b|PIECES?\b|PCS\b|PATCHES?\b|STRIPS?\b|PAIRS?\b|AMPOULES?\b|VIALS?\b)", re.I)

@dataclass(frozen=True)
class ItemSpecs:
    strength: str
    pack_size: str
    reasons: tuple[str, ...]


def measurement(value):
    value = re.sub(r'\s+', ' ', value.strip().upper())
    value = re.sub(r'\s*/\s*', '/', value)
    value = re.sub(r'(?<=\d)\s*(?=[A-ZΜ%])', ' ', value)
    for old,new in [('MCG','mcg'),('ΜG','mcg'),('UG','mcg'),('MG','mg'),('ML','mL'),('KG','kg'),('GRAMS','g'),('GRAM','g'),('LITRES','L'),('LITRE','L'),('LITERS','L'),('LITER','L'),('OZ','oz')]:
        value=re.sub(r'\b'+old+r'\b',new,value)
    value=re.sub(r'\bG\b','g',value)
    return value


def extract_specs(name):
    name=str(name or '').upper();reasons=[];strength='';pack=''
    matches=list(STRENGTH.finditer(name))
    capacity_item=bool(re.search(r'SYRINGE|WEIGHING|SCALE|FEEDING BOTTLE|FEEDER|MEASURING CUP|DUMBBELL|DUMBELL|HOT WATER BOTTLE|WATER BOTTLE',name))
    ignored_strengths=[m for m in matches if '%' in m.group() and (m.group().replace(' ','')=='100%' or re.search(r'OFF|DISCOUNT|SAVE',name[max(0,m.start()-12):m.end()+12]))]
    if ignored_strengths:reasons.append('percentage may describe marketing or material composition')
    if capacity_item and matches:reasons.append('measurement may be device capacity rather than strength')
    candidates=[] if capacity_item else [m for m in matches if m not in ignored_strengths]

    if len(candidates)==1:
        strength=measurement(candidates[0].group())
    elif len(candidates)>1:
        # Accept only a contiguous explicit list, without assigning ingredients.
        gaps=[name[a.end():b.start()].strip() for a,b in zip(candidates,candidates[1:])]
        if all(gap in ['/', '+'] for gap in gaps):
            strength=' / '.join(measurement(m.group()) for m in candidates)
        else:reasons.append('multiple strength measurements; review combination or alternatives')
    remaining=list(name)
    for match in matches:
        remaining[match.start():match.end()]=' '*len(match.group())
    remaining=''.join(remaining)
    sizes=list(SIZE.finditer(remaining));counts=list(COUNT.finditer(remaining))
    # Avoid guessing total units from multipacks, dimensions or bundled sizes.
    if capacity_item and sizes:
        reasons.append('volume or weight may be device capacity, not pack size')
    elif re.search(r'\d\s*[*X×]\s*\d',remaining):
        reasons.append('multipack or dimensions require review')
    elif len(sizes)+len(counts)==1:
        if sizes:pack=measurement(sizes[0].group())
        else:
            value=counts[0].group();number=counts[0].group(1)
            if re.search(r"['’]S\b|\d\s*S\b",value):pack=f"{number} {'unit' if number=='1' else 'units'}"
            else:pack=re.sub(r'\s+',' ',value).lower()
    elif len(sizes)+len(counts)>1:
        reasons.append('multiple pack measurements; review bundle or alternatives')
    if not strength:reasons.append('strength not explicit or ambiguous')
    if not pack:reasons.append('pack size not explicit or ambiguous')
    if len(strength)>50:strength='';reasons.append('strength exceeds field length')
    if len(pack)>80:pack='';reasons.append('pack size exceeds field length')
    return ItemSpecs(strength,pack,tuple(dict.fromkeys(reasons)))
