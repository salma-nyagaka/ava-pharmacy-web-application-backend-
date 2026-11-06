from collections import Counter

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.text import slugify

from apps.products.catalog_curation import (
    infer_brand_name,
    infer_health_concerns,
    iter_health_concern_definitions,
)
from apps.products.models import Brand, HealthConcern, Product, Variant


BRAND_NOTE = 'Brand inferred from the leading label in the imported catalogue (catalogue curation v1).'
CONCERN_NOTE_PREFIX = 'Health concerns inferred from catalogue text (catalogue curation v1): '


def append_note(existing, note):
    existing = (existing or '').strip()
    if note in existing:
        return existing
    return f'{existing}\n{note}'.strip()


class Command(BaseCommand):
    help = 'Infer conservative brand and health-concern metadata for the imported legacy catalogue.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--apply',
            action='store_true',
            help='Write inferred data. Without this flag the command is a dry run.',
        )

    def handle(self, *args, **options):
        apply_changes = options['apply']
        brand_matches, concern_matches = self._classify()

        self.stdout.write(
            f'Catalogue curation {"apply" if apply_changes else "dry run"}: '
            f'{len(brand_matches)} products have a recognised leading brand; '
            f'{len(concern_matches)} variants have at least one health-concern match.'
        )
        self._write_summary('Brands', Counter(brand for _, brand in brand_matches))
        self._write_summary(
            'Health concerns',
            Counter(concern for _, concerns in concern_matches for concern in concerns),
        )

        if not apply_changes:
            self.stdout.write(self.style.WARNING('Dry run only. Re-run with --apply to save these assignments.'))
            return

        with transaction.atomic():
            brand_count = self._apply_brands(brand_matches)
            concern_count, relation_count = self._apply_health_concerns(concern_matches)

        self.stdout.write(self.style.SUCCESS(
            f'Applied catalogue curation: {brand_count} product brand assignments, '
            f'{concern_count} active health concerns, and {relation_count} variant-concern relationships.'
        ))

    def _classify(self):
        brand_matches = []
        products = Product.objects.filter(is_active=True, brand__isnull=True).only(
            'pk', 'name', 'curation_notes'
        )
        for product in products.iterator(chunk_size=1000):
            brand_name = infer_brand_name(product.name)
            if brand_name:
                brand_matches.append((product, brand_name))

        concern_matches = []
        variants = (
            Variant.objects.filter(is_active=True, product__is_active=True)
            .select_related('product', 'category')
            .only(
                'pk', 'name', 'short_description', 'description', 'curation_notes',
                'product__name', 'category__name',
            )
        )
        for variant in variants.iterator(chunk_size=1000):
            concerns = infer_health_concerns(
                name=f'{variant.product.name} {variant.name}',
                description=f'{variant.short_description} {variant.description}',
                category=variant.category.name if variant.category else '',
            )
            if concerns:
                concern_matches.append((variant, concerns))
        return brand_matches, concern_matches

    def _apply_brands(self, matches):
        brand_cache = {brand.name.casefold(): brand for brand in Brand.objects.all()}
        products_to_update = []
        for product, name in matches:
            brand = brand_cache.get(name.casefold())
            if brand is None:
                brand = Brand.objects.create(
                    name=name,
                    slug=self._unique_slug(Brand, name, 'brand'),
                    logo='',
                    description=(
                        'Created from a recognised leading label in the imported product catalogue. '
                        'The assignment is inferred and should be reviewed by merchandising.'
                    ),
                    is_active=True,
                )
                brand_cache[name.casefold()] = brand
            elif not brand.is_active:
                brand.is_active = True
                brand.save(update_fields=['is_active', 'updated_at'])

            product.brand_id = brand.pk
            product.curation_notes = append_note(product.curation_notes, BRAND_NOTE)
            products_to_update.append(product)

        if products_to_update:
            Product.objects.bulk_update(products_to_update, ['brand', 'curation_notes'], batch_size=1000)
        return len(products_to_update)

    def _apply_health_concerns(self, matches):
        concern_cache = {concern.name.casefold(): concern for concern in HealthConcern.objects.all()}
        for definition in iter_health_concern_definitions():
            concern = concern_cache.get(definition.name.casefold())
            if concern is None:
                concern = HealthConcern.objects.create(
                    name=definition.name,
                    slug=self._unique_slug(HealthConcern, definition.name, 'concern'),
                    description=definition.description,
                    icon=definition.icon,
                    is_active=True,
                )
                concern_cache[definition.name.casefold()] = concern
            else:
                changed = []
                if concern.description != definition.description:
                    concern.description = definition.description
                    changed.append('description')
                if concern.icon != definition.icon:
                    concern.icon = definition.icon
                    changed.append('icon')
                if not concern.is_active:
                    concern.is_active = True
                    changed.append('is_active')
                if changed:
                    concern.save(update_fields=[*changed, 'updated_at'])

        through_model = Variant.health_concerns.through
        relations = []
        variants_to_update = []
        for variant, names in matches:
            concern_ids = [concern_cache[name.casefold()].pk for name in names]
            relations.extend(
                through_model(variant_id=variant.pk, healthconcern_id=concern_id)
                for concern_id in concern_ids
            )
            note = f'{CONCERN_NOTE_PREFIX}{", ".join(names)}.'
            updated_notes = append_note(variant.curation_notes, note)
            if updated_notes != variant.curation_notes:
                variant.curation_notes = updated_notes
                variants_to_update.append(variant)

        if relations:
            through_model.objects.bulk_create(relations, ignore_conflicts=True, batch_size=2000)
        if variants_to_update:
            Variant.objects.bulk_update(variants_to_update, ['curation_notes'], batch_size=1000)
        return len(concern_cache), len(relations)

    @staticmethod
    def _unique_slug(model, name, fallback):
        base = slugify(name) or fallback
        candidate = base
        suffix = 2
        while model.objects.filter(slug=candidate).exists():
            candidate = f'{base}-{suffix}'
            suffix += 1
        return candidate

    def _write_summary(self, title, counts):
        if not counts:
            self.stdout.write(f'{title}: none')
            return
        preview = ', '.join(f'{name} ({count})' for name, count in counts.most_common(15))
        self.stdout.write(f'{title}: {preview}')
