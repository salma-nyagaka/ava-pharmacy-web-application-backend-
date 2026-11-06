"""Evidence-backed, boundary-matched brand assignments for unbranded items."""
import json
from pathlib import Path
from .catalog_curation import BRAND_ALIASES, normalized_rule_text

EVIDENCE_PATH = Path(__file__).with_name('data') / 'researched_brands.json'


def load_brand_rules(path=EVIDENCE_PATH):
    researched = json.loads(Path(path).read_text())
    rules = {}
    for row in researched:
        if not row.get('brand') or not row.get('sources') or not all(url.startswith('https://') for url in row['sources']):
            raise ValueError('Every researched brand requires a name and HTTPS evidence source.')
        for alias in row['aliases']:
            key = normalized_rule_text(alias)
            previous = rules.get(key)
            if previous and normalized_rule_text(previous['brand']) != normalized_rule_text(row['brand']):
                raise ValueError(f'Conflicting brand evidence for {key}')
            rules[key] = row
    # Existing canonical catalogue labels can also be reused, without making
    # any new external attribution or guessing from a generic ingredient.
    for brand, aliases in BRAND_ALIASES.items():
        for alias in aliases:
            rules.setdefault(normalized_rule_text(alias), {
                'brand': brand, 'sources': [], 'note': 'Exact existing catalogue brand label.',
                'researched_on': None,
            })
    return sorted(rules.items(), key=lambda item: (-len(item[0]), item[0]))


def match_brand(name, rules):
    name = normalized_rule_text(name)
    for alias, evidence in rules:
        if name == alias or name.startswith(alias + ' '):
            return evidence
    return None
