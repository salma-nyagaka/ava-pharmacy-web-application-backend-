import csv
import json
from collections import Counter
from pathlib import Path
from django.core.management.base import BaseCommand
from django.db import transaction
from apps.products.models import Variant
from apps.products.admin_cache import invalidate_admin_catalog
from apps.products.item_spec_extraction import extract_specs

class Command(BaseCommand):
    help='Extract explicit strengths/pack sizes for imported items, preserving existing values; preview by default.'

    def add_arguments(self,parser):
        parser.add_argument('--apply',action='store_true')
        parser.add_argument('--report-dir',required=True)

    def handle(self,*args,**options):
        directory=Path(options['report_dir']);directory.mkdir(parents=True,exist_ok=True)
        report=[];updates=[];counts=Counter()
        with transaction.atomic():
            variants=Variant.objects.filter(sku__startswith='LEGACY-V-').select_related('product').order_by('pk')
            if options['apply']:variants=variants.select_for_update(of=('self',))
            for variant in variants:
                result=extract_specs(variant.product.name)
                old_strength=variant.strength;old_pack=variant.pack_size;reasons=list(result.reasons)
                if not variant.strength.strip() and result.strength:
                    variant.strength=result.strength;counts['strengths_filled']+=1
                elif variant.strength.strip() and result.strength and variant.strength.casefold()!=result.strength.casefold():
                    reasons.append('existing strength preserved; differs from extracted text')
                if not variant.pack_size.strip() and result.pack_size:
                    variant.pack_size=result.pack_size;counts['pack_sizes_filled']+=1
                elif variant.pack_size.strip() and result.pack_size and variant.pack_size.casefold()!=result.pack_size.casefold():
                    reasons.append('existing pack size preserved; differs from extracted text')
                if (old_strength,old_pack)!=(variant.strength,variant.pack_size):updates.append(variant)
                if variant.strength.strip():reasons=[r for r in reasons if r!='strength not explicit or ambiguous']
                if variant.pack_size.strip():reasons=[r for r in reasons if r!='pack size not explicit or ambiguous']
                report.append({'product_id':variant.product_id,'variant_id':variant.pk,'sku':variant.sku,'name':variant.product.name,
                    'old_strength':old_strength,'strength':variant.strength,'old_pack_size':old_pack,'pack_size':variant.pack_size,
                    'review_reasons':'; '.join(reasons)})
            if options['apply']:
                Variant.objects.bulk_update(updates,['strength','pack_size'],batch_size=500)
                if updates:invalidate_admin_catalog()
        summary={'mode':'applied' if options['apply'] else 'dry-run','reviewed_items':len(report),'changed_items':len(updates),
            'strengths_filled':counts['strengths_filled'],'pack_sizes_filled':counts['pack_sizes_filled'],
            'items_needing_review':sum(bool(r['review_reasons']) for r in report)}
        (directory/'assignments.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
        (directory/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
        with (directory/'review.csv').open('w',newline='') as file:
            writer=csv.DictWriter(file,fieldnames=list(report[0]) if report else ['name']);writer.writeheader();writer.writerows(r for r in report if r['review_reasons'])
        self.stdout.write(json.dumps(summary))
