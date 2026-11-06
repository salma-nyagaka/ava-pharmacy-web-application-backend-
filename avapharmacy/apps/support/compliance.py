import hashlib
import json
from datetime import timedelta
from django.db.models import Sum
from django.utils import timezone
from .models import MedicineAssessment
from apps.products.compliance import is_medicine


def screening_digest(screening):
    return hashlib.sha256(json.dumps(screening or {}, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def matching_assessment(item):
    query = MedicineAssessment.objects.filter(customer_id=item.cart.user_id, variant=item.variant,
        quantity=item.quantity, screening_digest=screening_digest(item.otc_screening), cart_item_id=item.pk)
    return query.order_by('-created_at', '-pk').first()


def assessment_error(item):
    variant = item.variant
    if not variant or variant.prescription_classification != 'otc':
        return None
    if hasattr(item, 'cart_id'):
        latest = matching_assessment(item)
        if latest and hasattr(latest, 'order_item'):
            return 'This pharmacist assessment is already reserved for an order.'
    else:
        latest = item.medicine_assessment
        if latest and (latest.customer_id != item.order.customer_id or latest.variant_id != item.variant_id or
                       latest.quantity != item.quantity or latest.screening_digest != screening_digest(item.otc_screening)):
            return 'Medicine assessment does not match the order.'
        if latest and MedicineAssessment.objects.filter(cart_item_id=latest.cart_item_id, created_at__gt=latest.created_at).exists() and latest.cart_item_id:
            return 'The pharmacist decision has changed; reassessment is required.'
    from apps.prescriptions.access import can_review
    if latest and not can_review(latest.reviewed_by):
        return 'The assessing pharmacist credentials require reverification.'
    if not latest or latest.decision != 'approved' or latest.expires_at <= timezone.now():
        return 'A current pharmacist suitability assessment and counselling record are required.'
    return None


def medicine_frequency_risk(item):
    """Triage thresholds require professional validation; no automated clinical clearance."""
    from django.conf import settings
    from apps.orders.models import OrderItem
    if not is_medicine(item.variant):
        return None
    recent = OrderItem.objects.filter(order__customer_id=item.cart.user_id, variant=item.variant,
        order__created_at__gte=timezone.now()-timedelta(days=30)).exclude(order__status__in=['cancelled', 'refunded'])
    count = recent.values('order_id').distinct().count()
    qty = recent.aggregate(total=Sum('quantity'))['total'] or 0
    if count >= getattr(settings, 'MEDICINE_REVIEW_ORDERS_30D', 3) or qty + item.quantity > getattr(settings, 'MEDICINE_REVIEW_UNITS_30D', 30):
        latest = MedicineAssessment.objects.filter(customer_id=item.cart.user_id, variant=item.variant,
            screening_digest=screening_digest(item.otc_screening), quantity=item.quantity,
            intervention__gt='', decision='approved', created_at__gte=timezone.now()-timedelta(hours=24)).first()
        if not latest:
            from apps.accounts.models import BotRiskEvent
            if not BotRiskEvent.objects.filter(user_id=item.cart.user_id, reasons__contains=['medicine_frequency_review'], created_at__gte=timezone.now()-timedelta(hours=24)).exists():
                BotRiskEvent.objects.create(user_id=item.cart.user_id, event_type='checkout', decision='review', reasons=['medicine_frequency_review'], metadata={'variant_id': item.variant_id, 'orders_30d': count, 'units_30d': qty})
            return 'Repeated or excessive medicine requests require an accountable pharmacist intervention.'
    return None


def delivery_error(order):
    audit = order.delivery_audits.order_by('-recorded_at', '-pk').first()
    if not audit or audit.event_type != 'delivered':
        return 'Record a successful recipient-verified delivery audit before completing the order.'
    if not audit.recipient_verified or not audit.recipient_name.strip():
        return 'Recipient verification is required.'
    sensitive = list(order.items.filter(variant__is_temperature_sensitive=True).select_related('variant'))
    if sensitive:
        if audit.cold_chain_intact is not True or audit.temperature_reading_c is None:
            return 'Cold-chain evidence is required; failed or missing evidence must be held for review.'
        for item in sensitive:
            v = item.variant
            if v.storage_temperature_min_c is None or v.storage_temperature_max_c is None:
                return 'Configure the approved medicine temperature limits before completing delivery.'
            if not v.storage_temperature_min_c <= audit.temperature_reading_c <= v.storage_temperature_max_c:
                return 'Temperature excursion: hold this delivery for professional review.'
    return None
