"""Import store catalog data from the legacy phpMyAdmin SQL exports."""

from __future__ import annotations

from collections import defaultdict

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q, Sum
from django.utils import timezone

from apps.orders.models import CartItem
from apps.products.legacy_catalog import (
    PRODUCT_SKU_PREFIX,
    VARIANT_SKU_PREFIX,
    CatalogPlan,
    LegacyCatalogPlanError,
    LegacySQLParseError,
    load_catalog_plan,
    legacy_listing_quality_flags,
    normalized_text_key,
)
from apps.products.models import (
    Brand,
    Category,
    HealthConcern,
    Product,
    Promotion,
    StockMovement,
    Store,
    StoreFulfillmentPolicy,
    StoreVariantListing,
    Subcategory,
    Variant,
    VariantInventory,
    normalize_generic_product_name,
)


class Command(BaseCommand):
    help = (
        'Import the gtc.sql, karen.sql, and nyali.sql product dumps into the '
        'canonical product/variant catalog and store-specific listings.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            'sql_files',
            nargs='+',
            help='Paths to known legacy dumps named gtc.sql, karen.sql, or nyali.sql.',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Parse and report the proposed import without changing the database.',
        )
        parser.add_argument(
            '--replace-catalog',
            action='store_true',
            help=(
                'Explicitly delete the current catalog and its dummy taxonomy before '
                'importing. This cascades through carts and other variant relations.'
            ),
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=1000,
            help='Rows per bulk database operation (default: 1000).',
        )

    def handle(self, *args, **options):
        batch_size = options['batch_size']
        if batch_size < 1:
            raise CommandError('--batch-size must be at least 1.')

        try:
            plan = load_catalog_plan(
                options['sql_files'],
                product_name_normalizer=normalize_generic_product_name,
            )
        except (OSError, LegacyCatalogPlanError, LegacySQLParseError) as exc:
            raise CommandError(str(exc)) from exc

        if plan.source_row_count == 0:
            raise CommandError('No products rows were found in the supplied SQL files.')
        if not plan.variants:
            raise CommandError('All parsed products rows had blank p_name values; nothing to import.')

        self._write_plan_summary(plan)
        if plan.skipped_blank_names:
            examples = '; '.join(plan.skipped_blank_names[:10])
            remaining = len(plan.skipped_blank_names) - min(10, len(plan.skipped_blank_names))
            suffix = f'; and {remaining} more' if remaining else ''
            self.stdout.write(self.style.WARNING(
                f'Skipped {len(plan.skipped_blank_names)} row(s) with blank p_name: '
                f'{examples}{suffix}'
            ))

        if options['replace_catalog']:
            replacement_impact = self._replacement_impact()
            self._write_replacement_impact(replacement_impact, dry_run=options['dry_run'])

        if options['dry_run']:
            self.stdout.write(self.style.SUCCESS('Dry run complete; the database was not changed.'))
            return

        with transaction.atomic():
            if options['replace_catalog']:
                self._delete_existing_catalog()
            changes = self._persist_plan(plan, batch_size=batch_size)

        self.stdout.write(self.style.SUCCESS(
            'Legacy catalog import complete: '
            f"{changes['stores_created']} stores created, "
            f"{changes['stores_updated']} stores updated, "
            f"{changes['categories_created']} categories created, "
            f"{changes['products_created']} products created, "
            f"{changes['products_updated']} products updated, "
            f"{changes['variants_created']} variants created, "
            f"{changes['variants_updated']} variants updated, "
            f"{changes['listings_created']} store listings created, "
            f"{changes['listings_updated']} store listings updated, "
            f"{changes['inventories_created']} inventory rows created, and "
            f"{changes['inventories_updated']} inventory rows updated."
        ))

    def _write_plan_summary(self, plan: CatalogPlan):
        inferred_prescription_count = sum(
            1 for variant in plan.variants if variant.requires_prescription
        )
        self.stdout.write(
            f'Parsed {plan.source_row_count} source row(s) for '
            f'{len(plan.stores)} store(s): {len(plan.products)} products, '
            f'{len(plan.variants)} variant slots, {plan.listing_count} '
            f'store listings, and {len(plan.categories)} categories.'
        )
        self.stdout.write(self.style.WARNING(
            f'Prescription inference: {inferred_prescription_count} variant(s) were marked '
            'requires_prescription=True because at least one matched legacy source row is '
            'categorized as DISPENSARY; every other imported variant was marked False.'
        ))

    def _replacement_impact(self):
        cart_queryset = CartItem.objects.filter(variant__product__isnull=False)
        cart_values = cart_queryset.aggregate(quantity=Sum('quantity'))
        return {
            'products': Product.objects.count(),
            'variants': Variant.objects.count(),
            'listings': StoreVariantListing.objects.count(),
            'inventories': VariantInventory.objects.count(),
            'stock_movements': StockMovement.objects.count(),
            'cart_lines': cart_queryset.count(),
            'cart_units': cart_values['quantity'] or 0,
            'categories': Category.objects.count(),
            'subcategories': Subcategory.objects.count(),
            'brands': Brand.objects.count(),
            'health_concerns': HealthConcern.objects.count(),
            'promotions': Promotion.objects.count(),
        }

    def _write_replacement_impact(self, impact, *, dry_run):
        prefix = 'Dry-run replacement would delete' if dry_run else 'Catalog replacement will delete'
        self.stdout.write(self.style.WARNING(
            f"{prefix} {impact['products']} product(s), {impact['variants']} variant(s), "
            f"{impact['listings']} store listing(s), {impact['inventories']} inventory row(s), "
            f"and {impact['stock_movements']} stock movement(s). The cascade will remove "
            f"{impact['cart_lines']} cart line(s) representing {impact['cart_units']} unit(s)."
        ))
        self.stdout.write(self.style.WARNING(
            f"It will also remove {impact['categories']} categories, "
            f"{impact['subcategories']} subcategories, {impact['brands']} brands, and "
            f"{impact['health_concerns']} health concerns and {impact['promotions']} stale "
            'catalog promotion(s) before rebuilding source-backed categories.'
        ))

    def _delete_existing_catalog(self):
        # Deleting products first lets Django apply all variant relation policies:
        # carts/listings/inventory cascade, while historical OrderItem rows retain
        # their denormalized description and receive variant=NULL.
        Product.objects.all().delete()
        Subcategory.objects.all().delete()
        Category.objects.all().delete()
        Brand.objects.all().delete()
        HealthConcern.objects.all().delete()
        Promotion.objects.all().delete()
        # Migration 0064 assigns pre-existing inventory to these temporary
        # stores so the new foreign key can be introduced safely.  Once all
        # old listings have cascaded, they are no longer real catalog data.
        Store.objects.filter(code__in=['main-shop', 'pos-store']).delete()

    def _persist_plan(self, plan: CatalogPlan, *, batch_size: int):
        changes = defaultdict(int)
        stores = self._sync_stores(plan, changes, batch_size=batch_size)
        categories = self._sync_categories(plan, changes, batch_size=batch_size)
        products = self._sync_products(plan, changes, batch_size=batch_size)
        variants = self._sync_variants(
            plan,
            products=products,
            categories=categories,
            changes=changes,
            batch_size=batch_size,
        )
        listings = self._sync_listings(
            plan,
            stores=stores,
            variants=variants,
            changes=changes,
            batch_size=batch_size,
        )
        self._sync_inventory(
            plan,
            variants=variants,
            listings=listings,
            changes=changes,
            batch_size=batch_size,
        )
        return changes

    def _sync_stores(self, plan, changes, *, batch_size):
        codes = [store.code for store in plan.stores]
        names = [store.name for store in plan.stores]
        existing = list(Store.objects.filter(Q(code__in=codes) | Q(name__in=names)))
        by_code = {store.code: store for store in existing}
        by_name = {store.name.casefold(): store for store in existing}
        creates = []
        updates = []
        now = timezone.now()

        for spec in plan.stores:
            store = by_code.get(spec.code) or by_name.get(spec.name.casefold())
            if store is None:
                creates.append(Store(
                    code=spec.code,
                    name=spec.name,
                    city=spec.city,
                    is_active=True,
                ))
                continue
            conflicting_code = by_code.get(spec.code)
            if conflicting_code is not None and conflicting_code.pk != store.pk:
                raise CommandError(
                    f'Store identity conflict: code {spec.code!r} and name {spec.name!r} '
                    'belong to different database rows.'
                )
            store.code = spec.code
            store.name = spec.name
            store.city = spec.city
            store.is_active = True
            store.updated_at = now
            updates.append(store)

        Store.objects.bulk_create(creates, batch_size=batch_size)
        if updates:
            Store.objects.bulk_update(
                updates,
                ['code', 'name', 'city', 'is_active', 'updated_at'],
                batch_size=batch_size,
            )
        stores = list(Store.objects.filter(code__in=codes))
        policy_store_ids = set(
            StoreFulfillmentPolicy.objects.filter(store__code__in=codes).values_list(
                'store_id', flat=True
            )
        )
        StoreFulfillmentPolicy.objects.bulk_create(
            [
                StoreFulfillmentPolicy(store=store)
                for store in stores
                if store.pk not in policy_store_ids
            ],
            batch_size=batch_size,
        )
        changes['stores_created'] += len(creates)
        changes['stores_updated'] += len(updates)
        return {store.code: store for store in stores}

    def _sync_categories(self, plan, changes, *, batch_size):
        existing = list(Category.objects.filter(parent__isnull=True))
        by_key = {normalized_text_key(category.name): category for category in existing}
        by_slug = {category.slug: category for category in existing}
        creates = []
        for category_plan in plan.categories:
            if category_plan.key not in by_key and category_plan.slug not in by_slug:
                creates.append(Category(name=category_plan.name, slug=category_plan.slug, is_active=True))
        Category.objects.bulk_create(creates, batch_size=batch_size)
        changes['categories_created'] += len(creates)
        existing = list(Category.objects.filter(parent__isnull=True))
        by_key = {normalized_text_key(category.name): category for category in existing}
        by_slug = {category.slug: category for category in existing}
        # Curated root names may have changed; their preserved import slug is
        # still the identity of the source category.
        return {spec.key: by_key.get(spec.key) or by_slug[spec.slug] for spec in plan.categories}

    def _sync_products(self, plan, changes, *, batch_size):
        existing = {}
        for product in Product.objects.filter(Q(catalog_family_key__startswith=PRODUCT_SKU_PREFIX) | Q(sku__startswith=PRODUCT_SKU_PREFIX)).order_by('pk'):
            existing.setdefault(product.catalog_family_key or product.sku, product)

        creates = []
        updates = []
        now = timezone.now()
        for product_plan in plan.products:
            product = existing.get(product_plan.sku)
            if product is None:
                creates.append(Product(
                    sku=product_plan.sku,
                    catalog_family_key=product_plan.sku,
                    slug=product_plan.slug,
                    name=product_plan.name,
                    family_review_status=Product.FAMILY_REVIEW_INFERRED,
                    is_active=product_plan.is_active,
                ))
                continue
            product.name = product_plan.name
            product.slug = product_plan.slug
            product.family_review_status = Product.FAMILY_REVIEW_INFERRED
            product.is_active = product_plan.is_active
            product.updated_at = now
            updates.append(product)

        Product.objects.bulk_create(creates, batch_size=batch_size)
        if updates:
            Product.objects.bulk_update(
                updates,
                ['name', 'slug', 'family_review_status', 'is_active', 'updated_at'],
                batch_size=batch_size,
            )
        changes['products_created'] += len(creates)
        changes['products_updated'] += len(updates)
        products = {}
        for product in Product.objects.filter(Q(catalog_family_key__startswith=PRODUCT_SKU_PREFIX) | Q(sku__startswith=PRODUCT_SKU_PREFIX)).order_by('pk'):
            products.setdefault(product.catalog_family_key or product.sku, product)
        self._assert_all_present(
            expected=(product.sku for product in plan.products),
            actual=products,
            label='products',
        )
        return {product_plan.key: products[product_plan.sku] for product_plan in plan.products}

    def _sync_variants(
        self,
        plan,
        *,
        products,
        categories,
        changes,
        batch_size,
    ):
        from apps.products.admin_cache import invalidate_admin_catalog
        invalidate_admin_catalog()
        existing = {
            variant.sku: variant
            for variant in Variant.objects.filter(sku__startswith=VARIANT_SKU_PREFIX).select_related('product', 'category', 'subcategory')
        }
        sort_orders = {}
        for product_plan in plan.products:
            for sort_order, variant_key in enumerate(product_plan.variant_keys):
                sort_orders[variant_key] = sort_order
        creates = []
        updates = []
        now = timezone.now()

        occupied_products = set(Variant.objects.values_list('product_id', flat=True))
        for variant_plan in plan.variants:
            root = products[variant_plan.product_key]
            previous_variant = existing.get(variant_plan.sku)
            if previous_variant is not None:
                owner = previous_variant.product
            elif root.pk not in occupied_products:
                owner = root
                occupied_products.add(owner.pk)
            else:
                owner = Product.objects.create(name=variant_plan.name, slug=f'flat-{variant_plan.sku.lower()}', brand=root.brand, image=root.image, manufacturer=root.manufacturer, marketing_authorization_holder=root.marketing_authorization_holder, family_review_status=root.family_review_status, catalog_family_key=root.catalog_family_key or root.sku, is_active=variant_plan.is_active)
                occupied_products.add(owner.pk)
                changes['products_created'] += 1
            Product.objects.filter(pk=owner.pk).update(name=variant_plan.name, sku=variant_plan.sku, catalog_family_key=root.catalog_family_key or root.sku, is_active=variant_plan.is_active)
            values = {
                'product': owner,
                'name': variant_plan.name,
                'barcode': variant_plan.barcode,
                'pos_product_id': '',
                'strength': previous_variant.strength if previous_variant else '',
                'category': (previous_variant.category if previous_variant and previous_variant.subcategory_id else categories.get(variant_plan.category_key)),
                'subcategory': previous_variant.subcategory if previous_variant and previous_variant.subcategory_id else None,
                'short_description': variant_plan.description[:500],
                'description': variant_plan.description,
                'price': variant_plan.price,
                'cost_price': variant_plan.cost_price,
                'requires_prescription': variant_plan.requires_prescription,
                'prescription_classification': (
                    Variant.PRESCRIPTION_REQUIRED
                    if variant_plan.requires_prescription
                    else Variant.PRESCRIPTION_UNKNOWN
                ),
                'prescription_review_status': (
                    Variant.REVIEW_INFERRED
                    if variant_plan.requires_prescription
                    else Variant.REVIEW_PENDING
                ),
                'is_active': variant_plan.is_active,
                'sort_order': sort_orders[variant_plan.key],
            }
            variant = existing.get(variant_plan.sku)
            if variant is None:
                creates.append(Variant(sku=variant_plan.sku, **values))
                continue
            for field_name, value in values.items():
                setattr(variant, field_name, value)
            variant.updated_at = now
            updates.append(variant)

        Variant.objects.bulk_create(creates, batch_size=batch_size)
        variant_update_fields = [
            'product',
            'name',
            'barcode',
            'pos_product_id',
            'strength',
            'category',
            'subcategory',
            'short_description',
            'description',
            'price',
            'cost_price',
            'requires_prescription',
            'prescription_classification',
            'prescription_review_status',
            'is_active',
            'sort_order',
            'updated_at',
        ]
        if updates:
            Variant.objects.bulk_update(
                updates,
                variant_update_fields,
                batch_size=batch_size,
            )
        changes['variants_created'] += len(creates)
        changes['variants_updated'] += len(updates)
        variants = {
            variant.sku: variant
            for variant in Variant.objects.filter(sku__startswith=VARIANT_SKU_PREFIX)
        }
        self._assert_all_present(
            expected=(variant.sku for variant in plan.variants),
            actual=variants,
            label='variants',
        )
        return {variant_plan.key: variants[variant_plan.sku] for variant_plan in plan.variants}

    def _sync_listings(
        self,
        plan,
        *,
        stores,
        variants,
        changes,
        batch_size,
    ):
        store_codes = list(stores)
        existing = {
            (listing.store.code, listing.variant.sku): listing
            for listing in StoreVariantListing.objects.select_related('store', 'variant').filter(
                store__code__in=store_codes,
                variant__sku__startswith=VARIANT_SKU_PREFIX,
            )
        }
        creates = []
        updates = []
        now = timezone.now()
        for variant_plan in plan.variants:
            variant = variants[variant_plan.key]
            for listing_plan in variant_plan.listings:
                quality_flags = legacy_listing_quality_flags(listing_plan)
                values = {
                    'external_product_id': listing_plan.external_product_id,
                    'price': listing_plan.price,
                    'cost_price': listing_plan.cost_price,
                    'minimum_price': listing_plan.minimum_price,
                    'vat_rate': listing_plan.vat_rate,
                    'status': listing_plan.status[:32],
                    'is_active': listing_plan.is_active,
                    'raw_data': dict(listing_plan.raw_data),
                    'data_quality_flags': quality_flags,
                    'review_status': (
                        StoreVariantListing.REVIEW_NEEDS_REVIEW
                        if quality_flags
                        else StoreVariantListing.REVIEW_UNREVIEWED
                    ),
                }
                key = (listing_plan.store.code, variant.sku)
                listing = existing.get(key)
                if listing is None:
                    creates.append(StoreVariantListing(
                        store=stores[listing_plan.store.code],
                        variant=variant,
                        **values,
                    ))
                    continue
                for field_name, value in values.items():
                    setattr(listing, field_name, value)
                listing.updated_at = now
                updates.append(listing)

        StoreVariantListing.objects.bulk_create(creates, batch_size=batch_size)
        if updates:
            StoreVariantListing.objects.bulk_update(
                updates,
                [
                    'external_product_id',
                    'price',
                    'cost_price',
                    'minimum_price',
                    'vat_rate',
                    'status',
                    'is_active',
                    'raw_data',
                    'data_quality_flags',
                    'review_status',
                    'updated_at',
                ],
                batch_size=batch_size,
            )
        changes['listings_created'] += len(creates)
        changes['listings_updated'] += len(updates)
        listings = {
            (listing.store.code, listing.variant.sku): listing
            for listing in StoreVariantListing.objects.select_related('store', 'variant').filter(
                store__code__in=store_codes,
                variant__sku__startswith=VARIANT_SKU_PREFIX,
            )
        }
        expected_keys = (
            (listing.store.code, variant.sku)
            for variant_plan in plan.variants
            for variant in [variants[variant_plan.key]]
            for listing in variant_plan.listings
        )
        self._assert_all_present(
            expected=expected_keys,
            actual=listings,
            label='store listings',
        )
        return listings

    def _sync_inventory(
        self,
        plan,
        *,
        variants,
        listings,
        changes,
        batch_size,
    ):
        existing = {
            inventory.store_listing_id: inventory
            for inventory in VariantInventory.objects.filter(
                store_listing__variant__sku__startswith=VARIANT_SKU_PREFIX,
                batch_number='',
            )
        }
        creates = []
        updates = []
        now = timezone.now()
        for variant_plan in plan.variants:
            variant = variants[variant_plan.key]
            for listing_plan in variant_plan.listings:
                listing = listings[(listing_plan.store.code, variant.sku)]
                status = self._inventory_status(
                    listing_plan.stock_quantity,
                    listing_plan.reorder_level,
                )
                values = {
                    'variant': variant,
                    'location': Product.STOCK_BRANCH,
                    'batch_number': '',
                    'source_name': listing_plan.store.name,
                    'stock_quantity': listing_plan.stock_quantity,
                    'reorder_level': listing_plan.reorder_level,
                    'low_stock_threshold': listing_plan.reorder_level,
                    'allow_backorder': False,
                    'max_backorder_quantity': 0,
                    'status': status,
                    'is_pos_synced': False,
                }
                inventory = existing.get(listing.pk)
                if inventory is None:
                    creates.append(VariantInventory(store_listing=listing, **values))
                    continue
                for field_name, value in values.items():
                    setattr(inventory, field_name, value)
                inventory.updated_at = now
                updates.append(inventory)

        VariantInventory.objects.bulk_create(creates, batch_size=batch_size)
        if updates:
            VariantInventory.objects.bulk_update(
                updates,
                [
                    'variant',
                    'location',
                    'batch_number',
                    'source_name',
                    'stock_quantity',
                    'reorder_level',
                    'low_stock_threshold',
                    'allow_backorder',
                    'max_backorder_quantity',
                    'status',
                    'is_pos_synced',
                    'updated_at',
                ],
                batch_size=batch_size,
            )
        changes['inventories_created'] += len(creates)
        changes['inventories_updated'] += len(updates)

    @staticmethod
    def _inventory_status(stock_quantity, reorder_level):
        if stock_quantity <= 0:
            return VariantInventory.STATUS_OUT_OF_STOCK
        if reorder_level and stock_quantity <= reorder_level:
            return VariantInventory.STATUS_LOW_STOCK
        return VariantInventory.STATUS_IN_STOCK

    @staticmethod
    def _assert_all_present(*, expected, actual, label):
        missing = [key for key in expected if key not in actual]
        if missing:
            examples = ', '.join(repr(key) for key in missing[:5])
            raise CommandError(
                f'Failed to reload {len(missing)} imported {label}; examples: {examples}'
            )
