import json
from urllib import error, request

from django.conf import settings
from django.utils import timezone

from .models import Product, ProductInventory, ProductVariant


def _pos_lookup_endpoint():
    return getattr(settings, 'POS_INVENTORY_LOOKUP_URL', '') or ''


def _pos_lookup_token():
    return getattr(settings, 'POS_INVENTORY_LOOKUP_TOKEN', '') or ''


def _pos_lookup_timeout():
    return int(getattr(settings, 'POS_INVENTORY_LOOKUP_TIMEOUT_SECONDS', 8) or 8)


def _pos_lookup_ttl_seconds():
    return int(getattr(settings, 'POS_INVENTORY_LOOKUP_TTL_SECONDS', 300) or 300)


def _pos_link_strategy():
    return str(getattr(settings, 'POS_LINK_STRATEGY', 'sku') or 'sku').strip().lower()


def _build_lookup_item(obj):
    sku = getattr(obj, 'sku', None)
    pos_product_id = getattr(obj, 'pos_product_id', None)
    barcode = getattr(obj, 'barcode', None)
    strategy = _pos_link_strategy()
    if strategy == 'pos_product_id':
        return {'pos_product_id': str(pos_product_id)} if pos_product_id else None
    if strategy == 'barcode':
        return {'barcode': str(barcode)} if barcode else None
    if strategy == 'barcode_and_pos_id':
        if not (barcode and pos_product_id):
            return None
        return {'barcode': str(barcode), 'pos_product_id': str(pos_product_id)}
    if strategy == 'sku_or_pos_id':
        if pos_product_id:
            return {'pos_product_id': str(pos_product_id)}
        return {'sku': str(sku)} if sku else None
    if strategy == 'sku_or_barcode':
        if barcode:
            return {'barcode': str(barcode)}
        return {'sku': str(sku)} if sku else None
    if strategy == 'any':
        item = {}
        if pos_product_id:
            item['pos_product_id'] = str(pos_product_id)
        if barcode:
            item['barcode'] = str(barcode)
        if sku:
            item['sku'] = str(sku)
        return item or None
    return {'sku': str(sku)} if sku else None


def _resolve_pos_item(pos_items, obj):
    for field in ('pos_product_id', 'barcode', 'sku'):
        value = getattr(obj, field, None)
        if value:
            item = pos_items.get(str(value))
            if item is not None:
                return item
    return None


def _identifier_for_object(obj):
    for field in ('pos_product_id', 'barcode', 'sku'):
        value = getattr(obj, field, None)
        if value:
            return str(value)
    return None


def _identifier_for_item(item):
    if not isinstance(item, dict):
        return None
    for key in ('pos_product_id', 'barcode', 'sku', 'product_id'):
        value = item.get(key)
        if value:
            return str(value)
    return None


def _extract_items(payload):
    if not isinstance(payload, dict):
        return []
    for key in ('items', 'availability', 'data'):
        value = payload.get(key)
        if isinstance(value, list):
            return value
    return []


def _extract_quantity(item):
    if not isinstance(item, dict):
        return None
    quantity = item.get('quantity')
    if quantity is None:
        stores = item.get('stores')
        if isinstance(stores, list):
            try:
                return sum(int(store.get('quantity', 0) or 0) for store in stores)
            except (TypeError, ValueError):
                return None
        return None
    try:
        return max(0, int(quantity))
    except (TypeError, ValueError):
        return None


def fetch_pos_inventory(lookup_items):
    endpoint = _pos_lookup_endpoint()
    if not endpoint or not lookup_items:
        return {}

    payload = {'items': lookup_items}
    headers = {'Content-Type': 'application/json'}
    token = _pos_lookup_token()
    if token:
        headers['Authorization'] = f'Bearer {token}'

    req = request.Request(
        endpoint,
        data=json.dumps(payload).encode('utf-8'),
        headers=headers,
        method='POST',
    )
    try:
        with request.urlopen(req, timeout=_pos_lookup_timeout()) as response:
            body = response.read().decode('utf-8') or '{}'
            parsed = json.loads(body)
    except (ValueError, json.JSONDecodeError, UnicodeDecodeError):
        return {}
    except error.HTTPError:
        return {}
    except error.URLError:
        return {}

    items = _extract_items(parsed)
    mapped = {}
    for item in items:
        identifier = _identifier_for_item(item)
        if identifier:
            mapped[identifier] = item
    return mapped


def _needs_pos_refresh(product):
    if not _pos_lookup_endpoint():
        return False
    if product.stock_quantity > product.low_stock_threshold:
        return False
    ttl_seconds = _pos_lookup_ttl_seconds()
    inventory = _warehouse_inventory(product)
    if inventory and inventory.last_synced_at:
        age = (timezone.now() - inventory.last_synced_at).total_seconds()
        if age < ttl_seconds:
            return False
    return True


def _warehouse_inventory(product):
    if isinstance(product, Product):
        if hasattr(product, '_prefetched_objects_cache') and 'inventories' in product._prefetched_objects_cache:
            inventories = list(product._prefetched_objects_cache['inventories'])
            for inventory in inventories:
                if inventory.location == Product.STOCK_WAREHOUSE:
                    return inventory
        return ProductInventory.objects.filter(product=product, location=Product.STOCK_WAREHOUSE).first()
    return None


def _needs_pos_refresh_variant(variant):
    if not _pos_lookup_endpoint():
        return False
    if variant.stock_quantity > variant.low_stock_threshold:
        return False
    return True


def _apply_pos_quantity(product, quantity, source_name=None):
    inventory = _warehouse_inventory(product)
    if inventory is None:
        inventory = ProductInventory.objects.create(
            product=product,
            location=Product.STOCK_WAREHOUSE,
            stock_quantity=0,
        )
    inventory.stock_quantity = max(0, int(quantity))
    if source_name:
        inventory.source_name = source_name
    inventory.is_pos_synced = True
    inventory.last_synced_at = timezone.now()
    inventory.save(update_fields=['stock_quantity', 'source_name', 'is_pos_synced', 'last_synced_at', 'updated_at'])
    if hasattr(product, '_clear_inventory_cache'):
        product._clear_inventory_cache()
    return inventory


def refresh_pos_inventory_for_products(products, *, force=False):
    eligible = []
    for product in products:
        if force or _needs_pos_refresh(product):
            item = _build_lookup_item(product)
            if item:
                eligible.append(product)

    if not eligible:
        return {}

    lookup_items = [_build_lookup_item(product) for product in eligible if _build_lookup_item(product)]
    pos_items = fetch_pos_inventory(lookup_items)
    refreshed = {}
    for product in eligible:
        identifier = _identifier_for_object(product)
        if not identifier:
            continue
        pos_item = pos_items.get(identifier) or _resolve_pos_item(pos_items, product)
        if not pos_item:
            continue
        quantity = _extract_quantity(pos_item)
        if quantity is None:
            continue
        source_name = pos_item.get('source_name') if isinstance(pos_item, dict) else None
        _apply_pos_quantity(product, quantity, source_name=source_name)
        refreshed[product.id] = {
            'quantity': quantity,
            'stores': pos_item.get('stores', []) if isinstance(pos_item, dict) else [],
        }
    return refreshed


def refresh_pos_inventory_for_variants(variants, *, force=False):
    eligible = []
    for variant in variants:
        if force or _needs_pos_refresh_variant(variant):
            item = _build_lookup_item(variant)
            if item:
                eligible.append(variant)

    if not eligible:
        return {}

    lookup_items = [_build_lookup_item(variant) for variant in eligible if _build_lookup_item(variant)]
    pos_items = fetch_pos_inventory(lookup_items)
    refreshed = {}
    for variant in eligible:
        identifier = _identifier_for_object(variant)
        if not identifier:
            continue
        pos_item = pos_items.get(identifier) or _resolve_pos_item(pos_items, variant)
        if not pos_item:
            continue
        quantity = _extract_quantity(pos_item)
        if quantity is None:
            continue
        variant.stock_quantity = max(0, int(quantity))
        variant.save(update_fields=['stock_quantity', 'stock_source', 'updated_at'])
        refreshed[variant.id] = {
            'quantity': quantity,
            'stores': pos_item.get('stores', []) if isinstance(pos_item, dict) else [],
        }
    return refreshed
