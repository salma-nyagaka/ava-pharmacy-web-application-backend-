from django.core.management.base import BaseCommand, CommandError

from apps.products.models import Product, Variant
from apps.products.thumbnails import generate_thumbnail


class Command(BaseCommand):
    help = 'Generate WebP thumbnails for existing product and variant photos.'

    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, help='Maximum number of photos to process across both models.')
        parser.add_argument('--force', action='store_true', help='Regenerate thumbnails, for example after enabling Spaces.')

    def handle(self, *args, limit, force, **options):
        if limit is not None and limit < 1:
            raise CommandError('--limit must be positive.')

        generated = failed = 0
        for model in (Variant, Product):
            rows = model.objects.exclude(image='').order_by('pk')
            if not force:
                rows = rows.filter(catalog_thumbnail_url='')
            if limit is not None:
                rows = rows[:limit - generated - failed]
            for pk, source_name in rows.values_list('pk', 'image').iterator(chunk_size=100):
                if generate_thumbnail(model, pk, source_name, rows.db):
                    generated += 1
                else:
                    failed += 1

        self.stdout.write(f'Generated {generated} catalog thumbnails. Failed or skipped during generation: {failed}.')
        if failed:
            raise CommandError('Review thumbnail warnings and retry failed photos.')
