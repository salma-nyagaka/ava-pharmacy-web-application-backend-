"""Whole-catalog counts, independent of table page size and current page."""
from django.core.cache import cache
from django.db.models import Count, Q
from .admin_cache import generation
from .models import Product, Variant, annotate_variant_inventory


def admin_catalog_summary():
    key = 'admin-summary:' + str(generation())
    result = cache.get(key)
    if result is not None:
        return result
    products = Product.objects.aggregate(total=Count('pk'), active=Count('pk', filter=Q(is_active=True)), inactive=Count('pk', filter=Q(is_active=False)))
    inventory = dict(total=0, active=0, inactive=0, in_stock=0, low_stock=0, backorder=0, out_of_stock=0)
    product_stock = {}
    rows = annotate_variant_inventory(Variant.objects.all()).order_by().values_list(
        'product_id', 'is_active', 'stock_quantity', 'low_stock_threshold', 'allow_backorder')
    for product_id, active, quantity, threshold, backorder in rows.iterator():
        inventory['total'] += 1
        inventory['active' if active else 'inactive'] += 1
        if not active:
            continue
        if quantity > 0:
            inventory['in_stock' if quantity > threshold else 'low_stock'] += 1
        else:
            inventory['backorder' if backorder else 'out_of_stock'] += 1
        qty, limit = product_stock.get(product_id, (0, 0))
        product_stock[product_id] = (qty + quantity, limit + threshold)
    products['low_stock'] = sum(1 for qty, threshold in product_stock.values() if 0 < qty <= threshold)
    result = {'products': products, 'inventory': inventory}
    cache.set(key, result, 60)
    return result
