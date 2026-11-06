import csv
import json
from collections import Counter
from pathlib import Path

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify

from apps.products.admin_cache import invalidate_admin_catalog
from apps.products.brand_research import load_brand_rules, match_brand
from apps.products.catalog_curation import normalized_rule_text
from apps.products.models import Brand, Product


class Command(BaseCommand):
    help = 'Link missing product brands using reviewed source evidence; dry run by default.'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true')
        parser.add_argument('--report-dir', required=True)

    def handle(self, *args, **options):
        rules = load_brand_rules()
        report_dir = Path(options['report_dir'])
        report_dir.mkdir(parents=True, exist_ok=True)
        with transaction.atomic():
            products = Product.objects.filter(brand__isnull=True).order_by('pk')
            if options['apply']:
                products = products.select_for_update()
            matches = []
            unresolved = []
            for product in products.only('pk', 'name', 'sku', 'brand_id', 'curation_notes'):
                evidence = match_brand(product.name, rules)
                if evidence:
                    matches.append((product, evidence))
                else:
                    unresolved.append({'id': product.pk, 'sku': product.sku, 'name': product.name,
                                       'reason': 'No verified unambiguous brand label; requires pack/supplier evidence.'})
            records = []
            created = []
            cache = {normalized_rule_text(b.name): b for b in Brand.objects.all()}
            for product, evidence in matches:
                key = normalized_rule_text(evidence['brand'])
                brand = cache.get(key)
                if options['apply'] and brand is None:
                    base = slugify(evidence['brand'])[:90] or 'brand'
                    slug = base
                    suffix = 2
                    while Brand.objects.filter(slug=slug).exists():
                        slug = f'{base}-{suffix}'
                        suffix += 1
                    brand = Brand.objects.create(name=evidence['brand'], slug=slug, logo='',
                        description='Brand label verified during catalogue research on 2026-11-05. Sources: ' + '; '.join(evidence['sources']))
                    cache[key] = brand
                    created.append({'id': brand.pk, 'name': brand.name})
                records.append({'product_id': product.pk, 'sku': product.sku, 'name': product.name,
                                'old_brand_id': None, 'brand_id': brand.pk if brand else None,
                                'brand': brand.name if brand else evidence['brand'],
                                'sources': evidence['sources'], 'evidence_note': evidence['note']})
                if options['apply']:
                    product.brand_id = brand.pk
                    note = 'Brand label verified 2026-11-05: ' + brand.name + '. Evidence: ' + ('; '.join(evidence['sources']) or 'exact existing catalogue brand label')
                    product.curation_notes = '\n'.join(filter(None, [product.curation_notes, note]))
                    product.updated_at = timezone.now()
            if options['apply'] and matches:
                Product.objects.bulk_update([product for product, _ in matches], ['brand', 'curation_notes', 'updated_at'], batch_size=500)
                invalidate_admin_catalog()
            summary = {'mode': 'applied' if options['apply'] else 'dry-run', 'at': timezone.now().isoformat(),
                       'assigned': len(matches), 'unresolved': len(unresolved), 'created_brands': created,
                       'assignments_by_brand': dict(Counter(r['brand'] for r in records))}
            # Report failures roll the database transaction back as well.
            (report_dir / 'assignments.json').write_text(json.dumps(records, indent=2, ensure_ascii=False) + '\n')
            (report_dir / 'summary.json').write_text(json.dumps(summary, indent=2, ensure_ascii=False) + '\n')
            with (report_dir / 'unresolved.csv').open('w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=['id', 'sku', 'name', 'reason'])
                writer.writeheader()
                writer.writerows(unresolved)
        self.stdout.write(json.dumps(summary, ensure_ascii=False))
