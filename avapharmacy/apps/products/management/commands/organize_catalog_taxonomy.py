"""Create the catalog hierarchy and assign exact items without touching stock."""
import csv
import json
from collections import Counter
from pathlib import Path
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify
from apps.products.admin_cache import invalidate_admin_catalog
from apps.products.catalog_taxonomy import CATEGORIES, VERSION, classify_item
from apps.products.models import Category, Subcategory, Variant

LEGACY_MERGES = {'ANTISEPTICS AND DISINFECTANTS', 'HEALTH TECH', 'LIP CARE', 'MILK FORMULAR',
                 'NAIL CARE', 'NUTRITION', 'OTC', 'OTC MEDICINE', 'OTC OTHERS', 'TESTS'}


def original_department(variant):
    for line in reversed((variant.curation_notes or '').splitlines()):
        if line.startswith(VERSION + ' '):
            try:
                return json.loads(line[len(VERSION) + 1:])['source_category']
            except (ValueError, KeyError):
                pass
    return variant.category.name if variant.category_id else ''


def unique_slug(model, value):
    base = slugify(value)[:150 if model is Subcategory else 45] or 'catalog'
    candidate = base
    suffix = 2
    while model.objects.filter(slug=candidate).exists():
        candidate = f'{base}-{suffix}'
        suffix += 1
    return candidate


class Command(BaseCommand):
    help = 'Organize every unclassified catalog item into the reviewed merchandising hierarchy (dry run by default).'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true')
        parser.add_argument('--report-dir', required=True)

    def handle(self, *args, **options):
        report_dir = Path(options['report_dir'])
        report_dir.mkdir(parents=True, exist_ok=True)
        apply = options['apply']
        with transaction.atomic():
            variants = Variant.objects.select_related('product__brand', 'category', 'subcategory').order_by('pk')
            if apply:
                variants = variants.select_for_update(of=('self',))
            plan = []
            skipped = 0
            for v in variants:
                if VERSION in (v.curation_notes or '') and v.category_id and v.subcategory_id and v.subcategory.category_id == v.category_id:
                    skipped += 1
                    continue
                source = original_department(v)
                brand = v.product.brand.name if v.product.brand_id else ''
                p = classify_item(v.product.name, source, brand)
                plan.append((v, source, p))
            categories = {}
            subcategories = {}
            created_categories = []
            created_subcategories = []
            renamed = []
            if apply:
                for key in sorted({p.category for _, _, p in plan}):
                    name, legacy, icon = CATEGORIES[key]
                    category = Category.objects.filter(parent=None, name__iexact=name).first()
                    if category is None and legacy:
                        category = Category.objects.filter(parent=None, name__iexact=legacy).first()
                    if category is None:
                        category = Category.objects.create(name=name, slug=unique_slug(Category, name), icon=icon,
                            description=f'Browse {name.lower()} by product type.', is_active=True)
                        created_categories.append(category.pk)
                    else:
                        if category.name != name:
                            renamed.append({'id':category.pk,'old_name':category.name,'name':name,'slug_preserved':category.slug})
                        category.name = name
                        category.is_active = True
                        category.description = category.description or f'Browse {name.lower()} by product type.'
                        category.save(update_fields=['name','is_active','description','updated_at'])
                    categories[key] = category
                for key, subname in sorted({(p.category, p.subcategory) for _, _, p in plan}):
                    category = categories[key]
                    sub = Subcategory.objects.filter(category=category, name__iexact=subname).first()
                    if sub is None:
                        sub = Subcategory.objects.create(category=category, name=subname,
                            slug=unique_slug(Subcategory, category.name + '-' + subname),
                            description=f'{subname} in {category.name}.', is_active=True)
                        created_subcategories.append(sub.pk)
                    elif not sub.is_active:
                        sub.is_active=True
                        sub.save(update_fields=['is_active','updated_at'])
                    subcategories[key,subname] = sub
            assignments = []
            updates = []
            for v, source, p in plan:
                record = {'product_id':v.product_id,'variant_id':v.pk,'sku':v.sku,'name':v.product.name,
                    'old_category_id':v.category_id,'old_subcategory_id':v.subcategory_id,
                    'source_category':source,'category':CATEGORIES[p.category][0],
                    'subcategory':p.subcategory,'reason':p.reason,'review':p.review}
                if apply:
                    category = categories[p.category]
                    sub = subcategories[p.category,p.subcategory]
                    v.category_id=category.pk
                    v.subcategory_id=sub.pk
                    v.updated_at=timezone.now()
                    note=VERSION+' '+json.dumps({'source_category':source,'reason':p.reason,'review':p.review},ensure_ascii=False)
                    v.curation_notes='\n'.join(filter(None,[v.curation_notes,note]))
                    updates.append(v)
                    record.update(category_id=category.pk,subcategory_id=sub.pk)
                assignments.append(record)
            archived=[]
            if apply and updates:
                Variant.objects.bulk_update(updates,['category','subcategory','curation_notes','updated_at'],batch_size=500)
                # Keep legacy IDs/slugs and external references; retire only empty
                # superseded roots. Unrelated administrator-created categories stay.
                for category in Category.objects.filter(name__in=LEGACY_MERGES, is_active=True):
                    if not category.variants.exists() and not category.subcategories.exists():
                        category.is_active=False
                        category.save(update_fields=['is_active','updated_at'])
                        archived.append(category.pk)
                invalidate_admin_catalog()
            summary={'version':VERSION,'mode':'applied' if apply else 'dry-run',
                'assigned':len(assignments),'skipped_classified':skipped,
                'category_count':len({r['category'] for r in assignments}),
                'subcategory_count':len({(r['category'],r['subcategory']) for r in assignments}),
                'review_count':sum(r['review'] for r in assignments),
                'created_category_ids':created_categories,'created_subcategory_ids':created_subcategories,
                'renamed_categories':renamed,'archived_category_ids':archived,
                'by_category':dict(Counter(r['category'] for r in assignments)),
                'by_subcategory':dict(Counter(r['category']+' / '+r['subcategory'] for r in assignments))}
            (report_dir/'assignments.json').write_text(json.dumps(assignments,indent=2,ensure_ascii=False)+'\n')
            (report_dir/'summary.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False)+'\n')
            with (report_dir/'review.csv').open('w',newline='') as f:
                fields=['product_id','variant_id','sku','name','category','subcategory','source_category','reason']
                writer=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');writer.writeheader()
                writer.writerows(r for r in assignments if r['review'])
        self.stdout.write(json.dumps({k:v for k,v in summary.items() if not k.startswith('by_')},ensure_ascii=False))
