"""Write brand descriptions grounded in their linked catalog items."""
import json
from collections import Counter
from pathlib import Path
from django.core.management.base import BaseCommand
from django.db import transaction
from apps.products.admin_cache import invalidate_admin_catalog
from apps.products.models import Brand, Variant


def join_words(values):
    return values[0] if len(values) == 1 else ', '.join(values[:-1]) + ' and ' + values[-1]


def describe_brand(name, items):
    if not items:
        return f'Browse {name} at Ava Pharmacy. Product details and availability are provided on individual listings as the range becomes available.'
    types = Counter(item['subcategory__name'] or item['category__name'] for item in items if item['subcategory__name'] or item['category__name'])
    # These descriptions describe the stocked range, not unverified company
    # history, ownership, clinical claims or the brand's entire global range.
    labels = [label.lower() for label, _ in types.most_common(3)]
    examples = list(dict.fromkeys(item['product__name'].strip() for item in items if item['product__name'].strip()))[:2]
    opening = f'{name} at Ava Pharmacy includes {join_words(labels)}.' if labels else f'Discover the {name} range at Ava Pharmacy.'
    if examples:
        opening += ' Explore ' + join_words(examples) + ', with pack sizes and product information on each listing.'
    return opening


class Command(BaseCommand):
    help = 'Replace brand description placeholders with catalog-grounded copy (dry-run by default).'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true')
        parser.add_argument('--report-dir', required=True)

    def handle(self, *args, **options):
        grouped = {}
        for item in Variant.objects.order_by('product__name', 'pk').values('product__brand_id', 'product__name', 'category__name', 'subcategory__name'):
            grouped.setdefault(item['product__brand_id'], []).append(item)
        directory = Path(options['report_dir']); directory.mkdir(parents=True, exist_ok=True)
        report = []; updates = []
        with transaction.atomic():
            for brand in Brand.objects.order_by('pk'):
                items = grouped.get(brand.pk, [])
                description = describe_brand(brand.name, items)
                if brand.description == description:
                    continue
                report.append({'id':brand.pk,'name':brand.name,'old_description':brand.description,'description':description,
                    'linked_items':len(items),'basis':'linked catalog product types and names' if items else 'no linked items; availability wording only'})
                brand.description = description; updates.append(brand)
            if options['apply']:
                Brand.objects.bulk_update(updates, ['description'], batch_size=500)
                invalidate_admin_catalog()
        summary = {'mode':'applied' if options['apply'] else 'dry-run', 'updated':len(report), 'with_linked_items':sum(bool(row['linked_items']) for row in report),'without_linked_items':sum(not row['linked_items'] for row in report)}
        (directory/'descriptions.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
        (directory/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
        self.stdout.write(json.dumps(summary))
