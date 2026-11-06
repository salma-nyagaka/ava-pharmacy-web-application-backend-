from collections import defaultdict
from datetime import datetime
import json
from urllib import error, request

from django.conf import settings
from django.db import models, transaction
from django.utils import timezone

from .models import (
    Product,
    StockMovement,
    StoreVariantListing,
    Variant,
    VariantInventory,
)


class InventoryTargetError(ValueError):
    """Raised when an inventory write cannot identify one safe target row."""

    code = 'invalid_inventory_target'

    def as_dict(self):
        return {'code': self.code, 'message': str(self)}


class AmbiguousInventoryTarget(InventoryTargetError):
    code = 'ambiguous_inventory_target'


def resolve_variant_inventory_target(
    variant,
    *,
    location,
    store_listing_id=None,
    store_code='',
    batch_number=None,
    for_update=False,
):
    """Resolve one inventory row and its optional listing without guessing.

    A selector is optional for backwards compatibility while a variant has at
    most one matching row. Once multiple stores carry the same variant, callers
    must provide ``store_listing_id`` or ``store_code``.
    """

    normalized_store_code = str(store_code or '').strip()
    normalized_listing_id = store_listing_id
    if normalized_listing_id in ('', None):
        normalized_listing_id = None
    elif isinstance(normalized_listing_id, str):
        try:
            normalized_listing_id = int(normalized_listing_id.strip())
        except (TypeError, ValueError):
            raise InventoryTargetError('store_listing_id must be an integer.')

    listing = None
    if normalized_listing_id is not None or normalized_store_code:
        listings = StoreVariantListing.objects.select_related('store').filter(variant=variant)
        if normalized_listing_id is not None:
            listings = listings.filter(pk=normalized_listing_id)
        if normalized_store_code:
            listings = listings.filter(store__code=normalized_store_code)
        listing = listings.first()
        if listing is None:
            selector = (
                f'store_listing_id={normalized_listing_id}'
                if normalized_listing_id is not None
                else f'store_code={normalized_store_code!r}'
            )
            raise InventoryTargetError(
                f'No store listing for variant {variant.pk} matches {selector}.'
            )

    inventories = VariantInventory.objects.filter(variant=variant, location=location)
    if for_update:
        inventories = inventories.select_for_update()
    else:
        inventories = inventories.select_related('store_listing__store')
    if listing is not None:
        inventories = inventories.filter(store_listing=listing)
    if batch_number is not None:
        inventories = inventories.filter(batch_number=str(batch_number or '').strip())

    matches = list(inventories.order_by('pk')[:2])
    if len(matches) > 1:
        raise AmbiguousInventoryTarget(
            f'Variant {variant.pk} has multiple {location} inventory rows. '
            'Provide store_listing_id or store_code'
            + (' and batch_number.' if listing is not None else '.')
        )

    if not matches and listing is None and variant.store_listings.count() > 1:
        raise AmbiguousInventoryTarget(
            f'Variant {variant.pk} is listed in multiple stores. '
            'Provide store_listing_id or store_code before creating inventory.'
        )

    if not matches and listing is not None and batch_number is not None:
        other_location = VariantInventory.objects.filter(
            variant=variant,
            store_listing=listing,
            batch_number=str(batch_number or '').strip(),
        ).exclude(location=location).values_list('location', flat=True).first()
        if other_location:
            raise InventoryTargetError(
                f'Store listing {listing.pk} already has this batch at location '
                f'{other_location!r}; it cannot also be written as {location!r}.'
            )

    return (matches[0] if matches else None), listing


INVENTORY_LOCATION_ALIASES = {
    'branch': Product.STOCK_BRANCH,
    'main_shop': Product.STOCK_BRANCH,
    'storefront': Product.STOCK_BRANCH,
    'warehouse': Product.STOCK_WAREHOUSE,
    'pos_store': Product.STOCK_WAREHOUSE,
    'pos': Product.STOCK_WAREHOUSE,
}


def _coerce_datetime(value):
    if not value:
        return timezone.now()
    if isinstance(value, datetime):
        return value
    try:
        parsed = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    except ValueError:
        return timezone.now()
    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed, timezone.get_current_timezone())
    return parsed


def _coerce_date(value):
    if not value:
        return None
    if hasattr(value, 'year') and hasattr(value, 'month') and hasattr(value, 'day'):
        return value
    text = str(value).strip()
    for fmt in ('%Y-%m-%d', '%Y/%m/%d'):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(text.replace('Z', '+00:00')).date()
    except ValueError:
        return None


def _coerce_int(value, default=0):
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return default


def _coerce_bool(value):
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {'true', '1', 'yes', 'on'}


def normalize_inventory_payload(payload):
    if isinstance(payload, list):
        items = payload
    else:
        items = None
        for key in ('items', 'data', 'inventory', 'availability'):
            candidate = payload.get(key)
            if isinstance(candidate, list):
                items = candidate
                break
        if items is None:
            items = [payload]
    normalized = []
    for item in items:
        if not isinstance(item, dict):
            continue
        location = INVENTORY_LOCATION_ALIASES.get(
            str(item.get('location') or item.get('source') or Product.STOCK_BRANCH).strip().lower(),
            Product.STOCK_BRANCH,
        )
        normalized.append({
            'sku': str(item.get('sku') or '').strip(),
            'product_id': item.get('product_id'),
            'variant_id': item.get('variant_id'),
            'barcode': str(item.get('barcode') or '').strip(),
            'pos_product_id': str(item.get('pos_product_id') or item.get('pos_id') or '').strip(),
            'location': location,
            'store_listing_id': item.get('store_listing_id'),
            'store_code': str(item.get('store_code') or '').strip(),
            'batch_number': str(item.get('batch_number') or '').strip(),
            'stock_quantity': _coerce_int(item.get('quantity_on_hand', item.get('stock_quantity', item.get('quantity', 0)))),
            'low_stock_threshold': _coerce_int(item.get('low_stock_threshold', 0)),
            'allow_backorder': _coerce_bool(item.get('allow_backorder', False)),
            'max_backorder_quantity': _coerce_int(item.get('max_backorder_quantity', 0)),
            'next_restock_date': _coerce_date(item.get('next_restock_date')),
            'source_name': str(item.get('source_name') or item.get('warehouse_name') or '').strip(),
            'synced_at': _coerce_datetime(item.get('synced_at') or payload.get('synced_at') if isinstance(payload, dict) else None),
            'reference': str(item.get('reference') or item.get('event_id') or '').strip(),
        })
    return normalized


def _find_variants_for_payload(rows):
    sku_values = {row['sku'] for row in rows if row['sku']}
    barcode_values = {row['barcode'] for row in rows if row['barcode']}
    pos_values = {row['pos_product_id'] for row in rows if row['pos_product_id']}
    product_ids = {row['product_id'] for row in rows if row['product_id']}
    variant_ids = {row['variant_id'] for row in rows if row['variant_id']}

    variants = Variant.objects.filter(
        models.Q(sku__in=sku_values) | models.Q(barcode__in=barcode_values) | models.Q(pos_product_id__in=pos_values) | models.Q(id__in=variant_ids)
    ).select_related('product').prefetch_related('inventories')
    by_sku = {variant.sku: variant for variant in variants if variant.sku}
    by_barcode = {variant.barcode: variant for variant in variants if variant.barcode}
    by_pos_id = {variant.pos_product_id: variant for variant in variants if variant.pos_product_id}
    by_id = {variant.id: variant for variant in variants}

    variants_by_product_id = {}
    if product_ids:
        for variant in Variant.objects.filter(product_id__in=product_ids, is_active=True).select_related('product').prefetch_related('inventories').order_by('product_id', 'sort_order', 'name', 'pk'):
            variants_by_product_id.setdefault(variant.product_id, variant)
    return by_sku, by_barcode, by_pos_id, by_id, variants_by_product_id


@transaction.atomic
def apply_inventory_sync(rows, *, source=StockMovement.SOURCE_POS_SYNC):
    if not rows:
        return []

    by_sku, by_barcode, by_pos_id, by_id, variants_by_product_id = _find_variants_for_payload(rows)
    results = []

    for row in rows:
        variant = (
            by_sku.get(row['sku'])
            or by_barcode.get(row['barcode'])
            or by_pos_id.get(row['pos_product_id'])
            or by_id.get(row['variant_id'])
            or variants_by_product_id.get(row['product_id'])
        )
        if variant is None:
            results.append({'matched': False, 'sku': row['sku'], 'product_id': row['product_id'], 'variant_id': row['variant_id']})
            continue

        try:
            inventory, listing = resolve_variant_inventory_target(
                variant,
                location=row['location'],
                store_listing_id=row['store_listing_id'],
                store_code=row['store_code'],
                batch_number=row['batch_number'],
                for_update=True,
            )
        except InventoryTargetError as exc:
            results.append({
                'matched': True,
                'updated': False,
                'product_id': variant.product_id,
                'variant_id': variant.id,
                'sku': variant.sku,
                'location': row['location'],
                'error': exc.as_dict(),
            })
            continue

        if inventory is None:
            inventory = VariantInventory.objects.create(
                variant=variant,
                store_listing=listing,
                location=row['location'],
                batch_number=row['batch_number'],
                source_name=row['source_name'],
                stock_quantity=0,
                low_stock_threshold=row['low_stock_threshold'],
                allow_backorder=row['allow_backorder'],
                max_backorder_quantity=row['max_backorder_quantity'],
                next_restock_date=row['next_restock_date'],
            )
        before_quantity = inventory.stock_quantity
        if before_quantity != row['stock_quantity']:
            StockMovement.objects.create(
                variant_inventory=inventory,
                movement_type=StockMovement.TYPE_ADJUSTMENT,
                source=source,
                quantity_change=row['stock_quantity'] - before_quantity,
                quantity_before=before_quantity,
                quantity_after=row['stock_quantity'],
                reason=f'Inventory sync for {inventory.location}',
                reference=row['reference'],
            )

        inventory.stock_quantity = row['stock_quantity']
        inventory.low_stock_threshold = row['low_stock_threshold']
        inventory.allow_backorder = row['allow_backorder']
        inventory.max_backorder_quantity = row['max_backorder_quantity']
        inventory.next_restock_date = row['next_restock_date']
        inventory.source_name = row['source_name']
        inventory.is_pos_synced = True
        inventory.last_synced_at = row['synced_at']
        inventory.save()
        variant._clear_inventory_cache()
        variant.save()

        results.append({
            'matched': True,
            'updated': True,
            'product_id': variant.product_id,
            'variant_id': variant.id,
            'sku': variant.sku,
            'location': inventory.location,
            'store_listing_id': inventory.store_listing_id,
            'quantity': inventory.stock_quantity,
        })
    return results


def fetch_remote_inventory_payload():
    if not settings.INVENTORY_SYNC_URL:
        return []
    headers = {'Content-Type': 'application/json'}
    req = request.Request(settings.INVENTORY_SYNC_URL, headers=headers, method='GET')
    with request.urlopen(req, timeout=settings.INVENTORY_SYNC_TIMEOUT_SECONDS) as response:
        body = response.read().decode('utf-8') or '{}'
    payload = json.loads(body)
    return normalize_inventory_payload(payload)


def sync_inventory_from_remote():
    rows = fetch_remote_inventory_payload()
    return apply_inventory_sync(rows, source=StockMovement.SOURCE_POS_SYNC)
