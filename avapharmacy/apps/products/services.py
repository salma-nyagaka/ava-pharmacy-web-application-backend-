"""
Business-logic services for the products app.

Provides functions for fetching active promotions and calculating per-product
pricing with applied discounts.
"""
from decimal import Decimal

from django.utils import timezone

from .models import Promotion


def get_active_promotions_queryset():
    today = timezone.now().date()
    return Promotion.objects.filter(
        status=Promotion.STATUS_ACTIVE,
        start_date__lte=today,
        end_date__gte=today,
    ).order_by('-priority', '-created_at')


def get_product_promotions(product, promotions=None):
    promotions = promotions or get_active_promotions_queryset()
    return [promotion for promotion in promotions if promotion.applies_to_product(product)]


def calculate_product_pricing(product, promotions=None):
    selling_price = Decimal(product.price)
    discounted_price = getattr(product, 'discount_price', None)
    manual_discount_total = Decimal('0.00')
    starting_price = selling_price

    if discounted_price is not None:
        discounted_price = Decimal(discounted_price)
        if Decimal('0.00') <= discounted_price < selling_price:
            starting_price = discounted_price
            manual_discount_total = selling_price - discounted_price

    applicable_promotions = get_product_promotions(product, promotions=promotions)
    if not applicable_promotions:
        return {
            'base_price': selling_price,
            'discount_total': manual_discount_total,
            'final_price': starting_price,
            'promotions': [],
        }

    applied = []
    promotion_discount_total = Decimal('0.00')
    remaining_amount = starting_price

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

    discount_total = min(selling_price, manual_discount_total + promotion_discount_total)
    return {
        'base_price': selling_price,
        'discount_total': discount_total,
        'final_price': max(Decimal('0.00'), selling_price - discount_total),
        'promotions': applied,
    }
