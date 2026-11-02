from django.db.models import Sum
from apps.orders.models import Order, OrderItem


def dispensing_error(item, variant, quantity, *, exclude_order=None):
    from .models import Prescription
    if item.prescription.status != Prescription.STATUS_APPROVED:
        return 'An approved prescription is required.'
    if item.is_controlled_substance:
        return 'Controlled drugs cannot be supplied online.'
    approved_variant = item.variant_id
    if not approved_variant and item.product_id:
        candidates = list(item.product.variants.filter(is_active=True).values_list('id', flat=True)[:2])
        approved_variant = candidates[0] if len(candidates) == 1 else None
    if not variant or variant.pk != approved_variant:
        return 'The selected variant does not match the exact approved prescription variant.'
    orders = OrderItem.objects.filter(prescription_item=item).exclude(
        order__status__in=[Order.STATUS_CANCELLED, Order.STATUS_REFUNDED])
    if exclude_order:
        orders = orders.exclude(order_id=exclude_order.pk)
    if orders.filter(order__payment_status=Order.PAYMENT_STATUS_PAID).exists():
        return 'This prescription item has already been paid for and cannot be dispensed again.'
    reserved = orders.aggregate(total=Sum('quantity'))['total'] or 0
    if quantity < 1 or quantity + reserved > item.quantity:
        return f'This prescription is approved for up to {item.quantity} unit(s); {reserved} already reserved in another order.'
    return None
