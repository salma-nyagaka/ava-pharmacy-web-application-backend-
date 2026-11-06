"""Rebuild attributable automatic browsing tags, preserving manual assignments."""
import json
from collections import Counter
from pathlib import Path
from django.core.management.base import BaseCommand
from django.db import transaction
from apps.products.admin_cache import invalidate_admin_catalog
from apps.products.health_concern_curation import RULES, VERSION, LEGACY_NOTE, infer_concerns
from apps.products.models import HealthConcern, Variant


def managed_names(notes, known_names):
    names = set()
    for line in (notes or '').splitlines():
        if line.startswith(LEGACY_NOTE):
            payload = line[len(LEGACY_NOTE):].rstrip('.')
            # Names themselves contain commas; match complete existing names.
            padded = ', ' + payload + ', '
            names.update(n for n in known_names if ', ' + n + ', ' in padded)
        elif line.startswith(VERSION + ' '):
            try:
                names.update(json.loads(line[len(VERSION) + 1:])['concerns'])
            except (ValueError, KeyError, TypeError):
                pass
    return names


class Command(BaseCommand):
    help = 'Review all sellable items and curate health-concern links (dry run by default).'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true')
        parser.add_argument('--report-dir', required=True)

    def handle(self, *args, **options):
        directory = Path(options['report_dir']); directory.mkdir(parents=True, exist_ok=True)
        apply = options['apply']; rows = []; updates = []; added = removed = 0
        with transaction.atomic():
            concerns = {h.name: h for h in HealthConcern.objects.all()}
            known = set(concerns)
            lookup = {name.casefold(): h for name, h in concerns.items()}
            variants = Variant.objects.select_related('product', 'category', 'subcategory').prefetch_related('health_concerns').order_by('pk')
            if apply:
                variants = variants.select_for_update(of=('self',))
            plan = []
            for v in variants:
                names = infer_concerns(v.product.name, v.category.name if v.category_id else '', v.subcategory.name if v.subcategory_id else '')
                plan.append((v, names))
            needed = {name for _, names in plan for name in names}
            created = []
            for rule in RULES:
                if rule.name not in needed:
                    continue
                existing = lookup.get(rule.name.casefold())
                if existing:
                    concerns[rule.name] = existing
                elif apply:
                    concerns[rule.name] = HealthConcern.objects.create(name=rule.name, description=rule.description)
                    created.append(rule.name)
                else:
                    created.append(rule.name)
            through = Variant.health_concerns.through
            links = []
            for v, names in plan:
                existing = {h.name: h.pk for h in v.health_concerns.all()}
                managed = managed_names(v.curation_notes, known | set(concerns))
                remove_ids = {pk for name, pk in existing.items() if name in managed and name not in names}
                additions = set(names) - set(existing)
                added += len(additions); removed += len(remove_ids)
                if apply:
                    if remove_ids:
                        through.objects.filter(variant_id=v.pk, healthconcern_id__in=remove_ids).delete()
                    links.extend(through(variant_id=v.pk, healthconcern_id=concerns[name].pk) for name in additions)
                    lines = [line for line in (v.curation_notes or '').splitlines() if not line.startswith(VERSION + ' ')]
                    lines.append(VERSION + ' ' + json.dumps({'concerns': names}, ensure_ascii=False))
                    note = '\n'.join(lines)
                    if note != v.curation_notes:
                        v.curation_notes = note; updates.append(v)
                preserved = sorted(name for name in existing if name not in managed and name not in names)
                rows.append({'product_id': v.product_id, 'variant_id': v.pk, 'sku': v.sku, 'name': v.product.name,
                    'concerns': names, 'preserved_manual': preserved,
                    'removed_automatic': sorted(name for name, pk in existing.items() if pk in remove_ids)})
            if apply:
                through.objects.bulk_create(links, ignore_conflicts=True, batch_size=1000)
                Variant.objects.bulk_update(updates, ['curation_notes'], batch_size=500)
                invalidate_admin_catalog()
            summary = {'version': VERSION, 'mode': 'applied' if apply else 'dry-run', 'reviewed_items': len(rows),
                'created_concerns': created, 'added_links': added, 'removed_automatic_links': removed,
                'items_with_concerns': sum(bool(r['concerns'] or r['preserved_manual']) for r in rows),
                'items_without_supported_match': sum(not r['concerns'] and not r['preserved_manual'] for r in rows),
                'by_concern': dict(Counter(name for r in rows for name in set(r['concerns']) | set(r['preserved_manual'])))}
            (directory / 'assignments.json').write_text(json.dumps(rows, indent=2, ensure_ascii=False) + '\n')
            (directory / 'summary.json').write_text(json.dumps(summary, indent=2, ensure_ascii=False) + '\n')
        self.stdout.write(json.dumps(summary, ensure_ascii=False))
