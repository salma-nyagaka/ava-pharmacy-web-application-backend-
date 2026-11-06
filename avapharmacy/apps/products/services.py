"""
Business-logic services for the products app.

Provides functions for fetching active promotions and calculating per-product
pricing with applied discounts.
"""
from decimal import Decimal

from django.utils import timezone

from .models import Promotion
from .compliance import promotional_product, prescription_required


def get_active_promotions_queryset():
    today = timezone.now().date()
    return Promotion.objects.filter(
        status=Promotion.STATUS_ACTIVE,
        start_date__lte=today,
        end_date__gte=today,
    ).filter(value__gt=0).exclude(type=Promotion.TYPE_PERCENTAGE, value__gt=100).order_by('-priority', '-created_at')


def get_product_promotions(product, promotions=None):
    if not promotional_product(product):
        return []
    promotions = promotions or get_active_promotions_queryset()
    return [promotion for promotion in promotions if promotion.is_currently_active
            and promotion.applies_to_product(product)]


def calculate_product_pricing(product, promotions=None):
    selling_price = Decimal(getattr(product, 'display_price', getattr(product, 'price', Decimal('0.00'))))
    applicable_promotions = get_product_promotions(product, promotions=promotions)
    if not applicable_promotions:
        return {
            'base_price': selling_price,
            'discount_total': Decimal('0.00'),
            'final_price': selling_price,
            'promotions': [],
        }

    applied = []
    promotion_discount_total = Decimal('0.00')
    remaining_amount = selling_price

    for promotion in applicable_promotions:
        if applied and not promotion.is_stackable:
            continue

        discount = promotion.calculate_discount(remaining_amount)
        if discount <= 0:
            continue

        applied.append({
            'id': promotion.id,
            'title': promotion.title,
            'code': promotion.code,
            'badge': promotion.badge,
            'discount': discount,
        })
        promotion_discount_total += discount

        if not promotion.is_stackable:
            break

        remaining_amount = max(Decimal('0.00'), remaining_amount - discount)

    discount_total = min(selling_price, promotion_discount_total)
    return {
        'base_price': selling_price,
        'discount_total': discount_total,
        'final_price': max(Decimal('0.00'), selling_price - discount_total),
        'promotions': applied,
    }


def calculate_variant_pricing(variant, promotions=None, qualifying_subtotal=None):
    """Price the exact sellable SKU; never apply a sibling SKU's promotion."""
    base = Decimal(variant.price)
    qualifying_subtotal = base if qualifying_subtotal is None else Decimal(qualifying_subtotal)
    candidates = [] if prescription_required(variant) else (get_active_promotions_queryset() if promotions is None else promotions)
    product = variant.product
    applied = []
    remaining = base
    for promotion in candidates:
        if not promotion.is_currently_active or qualifying_subtotal < promotion.minimum_order_amount:
            continue
        targets = {str(value) for value in promotion.targets}
        if promotion.scope == Promotion.SCOPE_PRODUCT:
            matches = bool(targets.intersection({str(product.pk), product.slug, product.sku, variant.sku}))
        else:
            matches = promotion.applies_to_product(product)
        if not matches or (applied and not promotion.is_stackable):
            continue
        discount = max(Decimal('0'), promotion.calculate_discount(remaining)).quantize(Decimal('0.01'))
        discount = min(discount, remaining)
        if not discount:
            continue
        applied.append({'id': promotion.pk, 'title': promotion.title, 'code': promotion.code,
                        'badge': promotion.badge, 'discount': discount})
        remaining -= discount
        if not promotion.is_stackable:
            break
    return {'base_price': base, 'discount_total': base - remaining,
            'final_price': remaining, 'promotions': applied}
