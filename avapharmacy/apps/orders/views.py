from django.conf import settings
from django.db import transaction
from django.db import models
from django.db.models import Count, F, Q, Sum
from django.db.models.functions import TruncDate
from django.http import HttpResponse
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.utils.dateparse import parse_datetime
from django.utils import timezone
from decimal import Decimal, InvalidOperation
from datetime import timedelta
import logging
from urllib.parse import urlencode
from rest_framework import generics, permissions, serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import Address
from apps.accounts.permissions import IsAdminUser
from apps.accounts.utils import log_admin_action
from apps.notifications.utils import create_notification, get_notification_preferences, notify_order_status
from apps.products.models import Product, ProductVariant, annotate_product_inventory

from .models import Cart, CartItem, Coupon, Order, OrderEvent, OrderItem, OrderNote, PaymentIntent, ReturnRequest, ShippingMethod
from .integrations import push_order_to_pos
from .flutterwave import FlutterwaveAPIError, FlutterwaveClient, FlutterwaveConfigurationError
from .mpesa import MpesaAPIError, MpesaClient, MpesaConfigurationError, parse_mpesa_callback
from .payment_helpers import (
    build_paybill_account_reference,
    get_paybill_account_label,
    get_paybill_instructions,
    get_paybill_number,
    resolve_order_number_from_paybill_reference,
)
from .serializers import (
    AdminInvoiceSerializer,
    AdminPaybillReconcileSerializer,
    AdminOrderSerializer,
    AdminOrderUpdateSerializer,
    CartSerializer,
    CheckoutSerializer,
    CouponApplySerializer,
    OrderNoteCreateSerializer,
    OrderSerializer,
    PaybillWebhookSerializer,
    MpesaC2BRegisterSerializer,
    FlutterwaveInitiateSerializer,
    FlutterwaveStatusSerializer,
    PaymentIntentCreateSerializer,
    PaymentIntentSerializer,
    PaymentWebhookSerializer,
    ReturnRequestAdminUpdateSerializer,
    ReturnRequestCreateSerializer,
    ReturnRequestSerializer,
    ShippingMethodSerializer,
)

payments_logger = logging.getLogger('payments')


def _truncate_event_message(message, limit=255):
    text = (message or '').strip()
    if len(text) <= limit:
        return text
    return f'{text[: max(0, limit - 1)].rstrip()}…'


def get_or_create_cart(user):
    cart, _ = Cart.objects.get_or_create(user=user)
    return cart


def create_order_event(order, event_type, message, actor=None, metadata=None):
    return OrderEvent.objects.create(
        order=order,
        actor=actor if getattr(actor, 'is_authenticated', False) else None,
        event_type=event_type,
        message=_truncate_event_message(message),
        metadata=metadata or {},
    )


def _product_availability_error(product, requested_quantity):
    if not product.is_active:
        return f'{product.name} is no longer active.'
    if requested_quantity <= product.stock_quantity:
        return None
    if product.allow_backorder and requested_quantity <= product.available_quantity:
        return None
    if product.stock_quantity == 0 and not product.allow_backorder:
        return f'{product.name} is out of stock.'
    return f'{product.name} only has {product.available_quantity} unit(s) available.'


def _cart_inventory_object(item):
    return item.product_variant or item.product


def _get_prescription_product_match(user, prescription_reference, product, prescription=None, prescription_item=None):
    if not user or not getattr(user, 'is_authenticated', False):
        return None
    from apps.prescriptions.models import PrescriptionItem, Prescription

    queryset = PrescriptionItem.objects.select_related('prescription', 'product').filter(
        prescription__patient=user,
        prescription__status=Prescription.STATUS_APPROVED,
        product=product,
    )
    if prescription_item is not None:
        return queryset.filter(pk=prescription_item.pk).first()
    if prescription is not None:
        return queryset.filter(prescription=prescription).first()
    if not prescription_reference:
        return None
    return queryset.filter(prescription__reference=prescription_reference).first()


def _prescription_cart_error(user, product, prescription_reference, requested_quantity, *, prescription=None, prescription_item=None):
    if not any([prescription_reference, prescription, prescription_item]):
        return f'{product.name} requires an approved prescription before it can be added to cart.'
    match = _get_prescription_product_match(
        user,
        prescription_reference,
        product,
        prescription=prescription,
        prescription_item=prescription_item,
    )
    if not match:
        return f'{product.name} is not linked to an approved prescription for this account.'
    if requested_quantity > match.quantity:
        return (
            f'{product.name} is approved for up to {match.quantity} unit(s) on prescription '
            f'{match.prescription.reference}.'
        )
    return None


def validate_cart_items(items):
    errors = []
    for item in items:
        inventory_object = _cart_inventory_object(item)
        error = _product_availability_error(inventory_object, item.quantity)
        if error:
            errors.append(error)
        if item.product.requires_prescription:
            prescription_error = _prescription_cart_error(
                getattr(item.cart, 'user', None),
                item.product,
                item.prescription_reference,
                item.quantity,
                prescription=item.prescription,
                prescription_item=item.prescription_item,
            )
            if prescription_error:
                errors.append(prescription_error)
    return errors


def build_order_totals(cart, shipping_method=None):
    subtotal = cart.total
    discount_total = cart.discount_total
    discounted_subtotal = subtotal - discount_total
    if shipping_method:
        shipping_fee = shipping_method.calculate_fee(discounted_subtotal)
    else:
        shipping_fee = cart.shipping_fee
    total = discounted_subtotal + shipping_fee
    return subtotal, discount_total, shipping_fee, total


def resolve_mpesa_stk_amount(order_total):
    raw_override = str(getattr(settings, 'MPESA_STK_PUSH_AMOUNT_OVERRIDE', '') or '').strip()
    if not raw_override:
        return order_total
    try:
        override = Decimal(raw_override)
    except (InvalidOperation, TypeError, ValueError):
        return order_total
    return override if override > 0 else order_total


def snapshot_cart_to_order(order, cart_items):
    order.items.all().delete()
    for item in cart_items:
        OrderItem.objects.create(
            order=order,
            product=item.product,
            product_variant=item.product_variant,
            product_name=item.product.name,
            product_sku=item.product.sku,
            quantity=item.quantity,
            variant_name=item.product_variant.name if item.product_variant else '',
            variant_sku=item.product_variant.sku if item.product_variant else '',
            unit_price=item.product_variant.effective_price if item.product_variant else item.product.price,
            prescription_reference=item.prescription_reference,
            prescription=item.prescription,
            prescription_item=item.prescription_item,
        )


def persist_checkout_address(user, data):
    existing_address = data.get('saved_address')
    save_requested = data.get('save_address') or not Address.objects.filter(user=user).exists()
    set_default = data.get('set_default_address') or not Address.objects.filter(user=user).exists()

    if existing_address:
        if set_default and not existing_address.is_default:
            Address.objects.filter(user=user).exclude(pk=existing_address.pk).update(is_default=False)
            existing_address.is_default = True
            existing_address.save(update_fields=['is_default'])
        return existing_address

    if not save_requested:
        return None

    if set_default:
        Address.objects.filter(user=user).update(is_default=False)

    return Address.objects.create(
        user=user,
        label=data.get('address_label') or 'Home',
        street=data['street'],
        city=data['city'],
        county=data['county'],
        is_default=set_default,
    )


def notify_order_update(order, title=None, message=None):
    if not order.customer:
        return
    try:
        preferences = get_notification_preferences(order.customer)
        create_notification(
            recipient=order.customer,
            notification_type='order_status',
            title=title or f'Order {order.order_number} Updated',
            message=message or f'Your order is now {order.status}.',
            data={'url': f'/orders/{order.id}', 'reference': order.order_number, 'status': order.status},
            send_email=bool(preferences and preferences.order_updates_email),
            send_sms=bool(preferences and preferences.order_updates_sms),
        )
    except Exception:
        return


def _save_order_push_result(order, action):
    result = push_order_to_pos(order, action)
    if result is None:
        return
    create_order_event(
        order,
        event_type='order_push_succeeded' if result['ok'] else 'order_push_failed',
        message=f'Order push {action} {"succeeded" if result["ok"] else "failed"}.',
        metadata={'action': action, **result},
    )


def _record_payment_error(intent, stage, message, *, metadata=None, event_type='payment_error'):
    safe_message = (message or 'Payment failed.').strip()
    payload = dict(intent.payload or {})
    error_logs = list(payload.get('error_logs') or [])
    entry = {
        'timestamp': timezone.now().isoformat(),
        'stage': stage,
        'provider': intent.provider,
        'status': intent.status,
        'message': safe_message,
    }
    if metadata:
        entry['metadata'] = metadata

    last_entry = error_logs[-1] if error_logs else None
    is_duplicate = (
        last_entry
        and last_entry.get('stage') == entry['stage']
        and last_entry.get('message') == entry['message']
        and last_entry.get('status') == entry['status']
    )

    if not is_duplicate:
        error_logs.append(entry)
        payload['error_logs'] = error_logs[-20:]
        intent.payload = payload
        intent.last_error = safe_message[:255]
        intent.save(update_fields=['payload', 'last_error', 'updated_at'])
        create_order_event(
            intent.order,
            event_type,
            safe_message,
            metadata={'intent_reference': intent.reference, 'stage': stage, **(metadata or {})},
        )

    payments_logger.error(
        'Payment error [%s] order=%s intent=%s provider=%s status=%s message=%s metadata=%s',
        stage,
        intent.order.order_number,
        intent.reference,
        intent.provider,
        intent.status,
        safe_message,
        metadata or {},
    )


def _record_payment_notice(intent, stage, message, *, metadata=None, event_type='payment_notice'):
    safe_message = (message or '').strip()
    payload = dict(intent.payload or {})
    error_logs = list(payload.get('error_logs') or [])
    entry = {
        'timestamp': timezone.now().isoformat(),
        'stage': stage,
        'provider': intent.provider,
        'status': intent.status,
        'message': safe_message,
        'severity': 'warning',
    }
    if metadata:
        entry['metadata'] = metadata

    last_entry = error_logs[-1] if error_logs else None
    is_duplicate = (
        last_entry
        and last_entry.get('stage') == entry['stage']
        and last_entry.get('message') == entry['message']
        and last_entry.get('status') == entry['status']
    )
    if not is_duplicate:
        error_logs.append(entry)
        payload['error_logs'] = error_logs[-20:]
        intent.payload = payload
        intent.save(update_fields=['payload', 'updated_at'])
        create_order_event(
            intent.order,
            event_type,
            safe_message,
            metadata={'intent_reference': intent.reference, 'stage': stage, **(metadata or {})},
        )

    payments_logger.warning(
        'Payment notice [%s] order=%s intent=%s provider=%s status=%s message=%s metadata=%s',
        stage,
        intent.order.order_number,
        intent.reference,
        intent.provider,
        intent.status,
        safe_message,
        metadata or {},
    )


def _mark_order_paid(order, intent, message, notify_message):
    order.payment_status = Order.PAYMENT_STATUS_PAID
    order.payment_reference = intent.provider_reference or intent.reference
    if order.status == Order.STATUS_DRAFT:
        order.status = Order.STATUS_PAID
    if not order.placed_at:
        order.placed_at = timezone.now()
    order.save(update_fields=['payment_status', 'payment_reference', 'status', 'placed_at', 'updated_at'])
    create_order_event(
        order,
        'payment_succeeded',
        message,
        metadata={'intent_reference': intent.reference, 'provider_reference': intent.provider_reference},
    )
    notify_order_update(
        order,
        title=f'Payment received for {order.order_number}',
        message=notify_message,
    )


def _mark_order_payment_failed(order, intent, message):
    order.payment_status = Order.PAYMENT_STATUS_FAILED
    order.save(update_fields=['payment_status', 'updated_at'])
    _record_payment_error(
        intent,
        'payment_failed',
        message or 'Payment failed.',
        metadata={'provider_reference': intent.provider_reference},
        event_type='payment_failed',
    )


def _build_flutterwave_redirect_url(request, order, intent, fallback=''):
    frontend_target = fallback or getattr(settings, 'FLUTTERWAVE_REDIRECT_URL', '') or f'{settings.FRONTEND_BASE_URL}/checkout'
    callback_url = request.build_absolute_uri(reverse('orders-payment-flutterwave-redirect'))
    query = urlencode({
        'order_id': order.id,
        'intent_id': intent.id,
        'return_url': frontend_target,
    })
    return f'{callback_url}?{query}'


def _append_query_params(base_url, params):
    separator = '&' if '?' in base_url else '?'
    return f'{base_url}{separator}{urlencode(params)}'


def _get_order_for_payment_request(request, order_id):
    try:
        order = Order.objects.select_related('customer').prefetch_related('payment_intents').get(pk=order_id)
    except Order.DoesNotExist:
        return None, Response({'detail': 'Order not found.'}, status=status.HTTP_404_NOT_FOUND)

    if not request.user.is_authenticated:
        return None, Response({'detail': 'Authentication required.'}, status=status.HTTP_401_UNAUTHORIZED)
    if order.customer_id != request.user.id and request.user.role != 'admin':
        return None, Response({'detail': 'You do not have permission to access this order.'}, status=status.HTTP_403_FORBIDDEN)
    return order, None


def _upsert_flutterwave_card_intent(request, order, *, return_url=''):
    existing_success = (
        order.payment_intents
        .filter(provider=PaymentIntent.PROVIDER_CARD, status=PaymentIntent.STATUS_SUCCEEDED)
        .order_by('-created_at')
        .first()
    )
    if existing_success:
        return existing_success

    existing_active = (
        order.payment_intents
        .filter(provider=PaymentIntent.PROVIDER_CARD, status__in=[PaymentIntent.STATUS_PENDING, PaymentIntent.STATUS_REQUIRES_ACTION])
        .order_by('-created_at')
        .first()
    )
    intent = existing_active or PaymentIntent.objects.create(
        order=order,
        initiated_by=request.user,
        provider=PaymentIntent.PROVIDER_CARD,
        status=PaymentIntent.STATUS_REQUIRES_ACTION,
        amount=order.total,
        payload={'instructions': 'Redirect customer to hosted card checkout.'},
    )

    redirect_url = _build_flutterwave_redirect_url(request, order, intent, return_url)
    response_payload = FlutterwaveClient().create_card_checkout(
        payment_intent=intent,
        order=order,
        customer=request.user,
        redirect_url=redirect_url,
    )
    response_data = response_payload.get('data') or {}
    tx_ref = str(response_data.get('tx_ref') or intent.reference)

    intent.initiated_by = request.user
    intent.status = PaymentIntent.STATUS_REQUIRES_ACTION
    intent.external_reference = tx_ref
    intent.client_secret = response_data.get('link', '')
    intent.payload = response_payload
    intent.last_error = ''
    intent.processed_at = None
    intent.save(update_fields=[
        'initiated_by', 'status', 'external_reference', 'client_secret',
        'payload', 'last_error', 'processed_at', 'updated_at',
    ])

    order.payment_status = Order.PAYMENT_STATUS_REQUIRES_ACTION
    order.flutterwave_tx_ref = tx_ref
    order.save(update_fields=['payment_status', 'flutterwave_tx_ref', 'updated_at'])
    create_order_event(
        order,
        'payment_intent_created',
        'Card checkout link created.',
        actor=request.user,
        metadata={'intent_reference': intent.reference, 'tx_ref': tx_ref, 'checkout_url': response_data.get('link', '')},
    )
    return intent


def _merge_intent_payload(intent, extra_payload):
    payload = dict(intent.payload or {})
    payload.update(extra_payload or {})
    intent.payload = payload


def _upsert_paybill_intent(intent, *, phone, reference_code, account_reference, metadata=None):
    submitted_at = timezone.now()
    _merge_intent_payload(intent, {
        'channel': 'mpesa_paybill',
        'submitted_reference': reference_code,
        'submitted_phone': phone,
        'submitted_at': submitted_at.isoformat(),
        'paybill_number': get_paybill_number(),
        'paybill_account_label': get_paybill_account_label(),
        'paybill_instructions': get_paybill_instructions(),
        **({'metadata': metadata} if metadata else {}),
    })
    intent.phone_number = phone
    intent.external_reference = account_reference
    intent.provider_reference = reference_code
    intent.status = PaymentIntent.STATUS_REQUIRES_ACTION
    intent.last_error = ''
    intent.processed_at = None
    intent.save(update_fields=[
        'payload', 'initiated_by', 'phone_number', 'external_reference', 'provider_reference',
        'status', 'last_error', 'processed_at', 'updated_at',
    ])
    intent.order.payment_status = Order.PAYMENT_STATUS_REQUIRES_ACTION
    intent.order.save(update_fields=['payment_status', 'updated_at'])
    create_order_event(
        intent.order,
        'paybill_reference_submitted',
        'M-Pesa paybill transaction reference submitted for confirmation.',
        actor=intent.initiated_by,
        metadata={
            'intent_reference': intent.reference,
            'provider_reference': reference_code,
            'account_reference': account_reference,
        },
    )
    return intent


def _parse_payment_amount(value):
    if value in [None, '']:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _amount_matches_order_total(amount, order_total):
    if amount is None:
        return False
    try:
        return amount.quantize(Decimal('0.01')) == Decimal(str(order_total)).quantize(Decimal('0.01'))
    except (InvalidOperation, TypeError, ValueError):
        return False


def _is_mpesa_processing_response(payload):
    result_desc = str((payload or {}).get('ResultDesc', '') or '').strip().lower()
    if not result_desc:
        return False
    processing_markers = (
        'still under processing',
        'being processed',
        'processing',
        'pending',
        'queued',
    )
    return any(marker in result_desc for marker in processing_markers)


def _get_mpesa_sync_meta(intent):
    return dict((intent.payload or {}).get('status_sync') or {})


def _set_mpesa_sync_meta(intent, **extra):
    payload = dict(intent.payload or {})
    sync_meta = dict(payload.get('status_sync') or {})
    sync_meta.update(extra)
    payload['status_sync'] = sync_meta
    intent.payload = payload


def _parse_sync_datetime(value):
    if not value:
        return None
    parsed = parse_datetime(str(value))
    if parsed and timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed, timezone.get_current_timezone())
    return parsed


def _mpesa_sync_retry_after_seconds(message):
    text = str(message or '').lower()
    if 'rate limit' in text or '429' in text or 'spikearrest' in text:
        return max(1, int(getattr(settings, 'MPESA_STATUS_SYNC_RETRY_AFTER_429_SECONDS', 65)))
    if 'blocked by safaricom edge protection' in text or 'incapsula' in text or '403' in text:
        return max(1, int(getattr(settings, 'MPESA_STATUS_SYNC_RETRY_AFTER_403_SECONDS', 180)))
    return 0


def _mpesa_sync_next_allowed_at(intent):
    now = timezone.now()
    min_interval = max(0, int(getattr(settings, 'MPESA_STATUS_SYNC_MIN_INTERVAL_SECONDS', 15)))
    sync_meta = _get_mpesa_sync_meta(intent)
    next_allowed_at = _parse_sync_datetime(sync_meta.get('next_allowed_at'))
    if next_allowed_at and next_allowed_at > now:
        return next_allowed_at

    last_attempt_at = _parse_sync_datetime(sync_meta.get('last_attempt_at'))
    if last_attempt_at and min_interval:
        candidate = last_attempt_at + timedelta(seconds=min_interval)
        if candidate > now:
            return candidate
    return None


def _resolve_paybill_order(*, order_number='', account_reference=''):
    candidates = []
    if order_number:
        candidates.append(str(order_number).strip())
    if account_reference:
        resolved = resolve_order_number_from_paybill_reference(account_reference)
        if resolved and resolved not in candidates:
            candidates.append(resolved)

    for candidate in candidates:
        order = Order.objects.select_for_update().filter(order_number=candidate).first()
        if order is not None:
            return order

    if account_reference:
        intent = PaymentIntent.objects.select_for_update().select_related('order').filter(
            provider=PaymentIntent.PROVIDER_PAYBILL,
            external_reference=str(account_reference).strip(),
        ).order_by('-created_at').first()
        if intent is not None:
            return intent.order
    return None


def _current_paybill_shortcode():
    return str(getattr(settings, 'MPESA_C2B_SHORTCODE', '') or '').strip() or get_paybill_number()


def _validate_paybill_order_for_c2b(order, *, amount=None, business_shortcode=''):
    expected_shortcode = _current_paybill_shortcode()
    if business_shortcode and expected_shortcode and str(business_shortcode).strip() != expected_shortcode:
        return 'Invalid business shortcode.'
    if order.payment_method != Order.PAYMENT_MPESA_PAYBILL:
        return 'This order is not configured for M-Pesa paybill.'
    if order.payment_status == Order.PAYMENT_STATUS_PAID:
        return 'This order is already paid.'
    if order.status not in [Order.STATUS_DRAFT, Order.STATUS_PENDING]:
        return 'This order is not payable in its current state.'
    if amount is None:
        return 'Invalid payment amount.'
    if not _amount_matches_order_total(amount, order.total):
        return f'Expected KES {order.total} for this order.'
    return None


def _build_paybill_callback_metadata(payload, *, source):
    return {
        'source': source,
        'transaction_type': str(payload.get('TransactionType') or '').strip(),
        'transaction_reference': str(payload.get('TransID') or '').strip(),
        'transaction_time': str(payload.get('TransTime') or '').strip(),
        'amount': str(payload.get('TransAmount') or '').strip(),
        'business_shortcode': str(payload.get('BusinessShortCode') or '').strip(),
        'account_reference': str(payload.get('BillRefNumber') or '').strip(),
        'invoice_number': str(payload.get('InvoiceNumber') or '').strip(),
        'third_party_trans_id': str(payload.get('ThirdPartyTransID') or '').strip(),
        'phone_number': str(payload.get('MSISDN') or '').strip(),
        'first_name': str(payload.get('FirstName') or '').strip(),
        'middle_name': str(payload.get('MiddleName') or '').strip(),
        'last_name': str(payload.get('LastName') or '').strip(),
    }


def _apply_paybill_confirmation(order, *, raw_payload, source):
    account_reference = str(raw_payload.get('BillRefNumber') or '').strip()
    provider_reference = str(raw_payload.get('TransID') or '').strip()
    phone_number = str(raw_payload.get('MSISDN') or '').strip()
    amount = _parse_payment_amount(raw_payload.get('TransAmount'))
    callback_metadata = _build_paybill_callback_metadata(raw_payload, source=source)

    intent = PaymentIntent.objects.select_for_update().filter(
        order=order,
        provider=PaymentIntent.PROVIDER_PAYBILL,
    ).order_by('-created_at').first()
    if intent is None:
        intent = PaymentIntent.objects.create(
            order=order,
            provider=PaymentIntent.PROVIDER_PAYBILL,
            status=PaymentIntent.STATUS_PENDING,
            amount=order.total,
            external_reference=account_reference or build_paybill_account_reference(order),
            provider_reference=provider_reference,
            phone_number=phone_number,
            payload={'channel': 'mpesa_paybill', 'source': source},
        )

    intent.callback_payload = raw_payload
    _merge_intent_payload(intent, {
        'channel': 'mpesa_paybill',
        'callback': callback_metadata,
        'paybill_number': get_paybill_number(),
        'paybill_account_label': get_paybill_account_label(),
        'paybill_instructions': get_paybill_instructions(),
    })
    intent.external_reference = account_reference or intent.external_reference or build_paybill_account_reference(order)
    intent.provider_reference = provider_reference or intent.provider_reference
    intent.phone_number = phone_number or intent.phone_number
    intent.processed_at = timezone.now()

    already_paid = order.payment_status == Order.PAYMENT_STATUS_PAID and intent.status == PaymentIntent.STATUS_SUCCEEDED
    mismatch_message = _validate_paybill_order_for_c2b(
        order,
        amount=amount,
        business_shortcode=raw_payload.get('BusinessShortCode', ''),
    )
    if mismatch_message == 'This order is already paid.':
        mismatch_message = ''

    if mismatch_message:
        intent.status = PaymentIntent.STATUS_REQUIRES_ACTION
        intent.last_error = mismatch_message
        intent.save(update_fields=[
            'payload', 'callback_payload', 'external_reference', 'provider_reference',
            'phone_number', 'processed_at', 'status', 'last_error', 'updated_at',
        ])
        if order.payment_status != Order.PAYMENT_STATUS_PAID:
            order.payment_status = Order.PAYMENT_STATUS_REQUIRES_ACTION
            order.save(update_fields=['payment_status', 'updated_at'])
        create_order_event(
            order,
            'paybill_confirmation_review',
            mismatch_message,
            metadata={'intent_reference': intent.reference, **callback_metadata},
        )
        return intent, False

    intent.status = PaymentIntent.STATUS_SUCCEEDED
    intent.last_error = ''
    intent.save(update_fields=[
        'payload', 'callback_payload', 'external_reference', 'provider_reference',
        'phone_number', 'processed_at', 'status', 'last_error', 'updated_at',
    ])
    if not already_paid:
        _mark_order_paid(
            order,
            intent,
            f'M-Pesa paybill payment confirmed automatically via {source}.',
            'Your M-Pesa paybill payment was confirmed successfully.',
        )
    return intent, True


def _sync_flutterwave_intent(intent, transaction_id):
    response = FlutterwaveClient().verify_transaction(transaction_id)
    data = response.get('data') or {}
    status_value = str(data.get('status', '')).lower()
    amount = data.get('amount')
    currency = str(data.get('currency') or intent.currency)
    tx_ref = str(data.get('tx_ref') or intent.external_reference or intent.reference)
    tx_id = str(data.get('id') or transaction_id or '')

    intent.payload = {**intent.payload, 'verification': response}
    intent.callback_payload = data
    intent.processed_at = timezone.now()
    intent.provider_reference = str(data.get('flw_ref') or data.get('id') or intent.provider_reference)
    intent.external_reference = tx_ref

    try:
        verified_amount = Decimal(str(amount))
    except (InvalidOperation, TypeError):
        verified_amount = None

    if (
        str(response.get('status', '')).lower() == 'success'
        and status_value == 'successful'
        and currency.upper() == intent.currency.upper()
        and verified_amount is not None
        and verified_amount == intent.amount
    ):
        intent.status = PaymentIntent.STATUS_SUCCEEDED
        intent.last_error = ''
    else:
        intent.status = PaymentIntent.STATUS_FAILED
        intent.last_error = response.get('message') or data.get('processor_response') or 'Card payment verification failed.'
    intent.save(update_fields=[
        'payload', 'callback_payload', 'processed_at', 'provider_reference',
        'external_reference', 'status', 'last_error', 'updated_at',
    ])
    order = intent.order
    order.flutterwave_tx_ref = tx_ref
    order.flutterwave_tx_id = tx_id
    order.save(update_fields=['flutterwave_tx_ref', 'flutterwave_tx_id', 'updated_at'])
    return response


class CartView(generics.RetrieveAPIView):
    serializer_class = CartSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return get_or_create_cart(self.request.user)


class CartItemCreateView(generics.CreateAPIView):
    serializer_class = CartSerializer
    permission_classes = [permissions.IsAuthenticated]

    def create(self, request, *args, **kwargs):
        cart = get_or_create_cart(request.user)
        product_id = request.data.get('product_id')
        variant_id = request.data.get('product_variant_id')
        quantity = request.data.get('quantity', 1)
        prescription_reference = request.data.get('prescription_reference') or request.data.get('prescription_id')
        prescription_pk = request.data.get('prescription')
        prescription_item_pk = request.data.get('prescription_item')

        try:
            quantity = int(quantity)
            if quantity < 1:
                return Response({'quantity': 'Must be at least 1.'}, status=status.HTTP_400_BAD_REQUEST)
        except (TypeError, ValueError):
            return Response({'quantity': 'Invalid quantity.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            product = Product.objects.select_related('brand', 'category').get(pk=product_id, is_active=True)
        except Product.DoesNotExist:
            return Response({'detail': 'Product not found.'}, status=status.HTTP_404_NOT_FOUND)

        variant = None
        if variant_id:
            try:
                variant = ProductVariant.objects.get(pk=variant_id, product=product, is_active=True)
            except ProductVariant.DoesNotExist:
                return Response({'detail': 'Variant not found for this product.'}, status=status.HTTP_404_NOT_FOUND)

        prescription = None
        prescription_item = None
        if prescription_pk or prescription_item_pk:
            from apps.prescriptions.models import Prescription, PrescriptionItem

            if prescription_pk:
                try:
                    prescription = Prescription.objects.get(
                        pk=prescription_pk,
                        patient=request.user,
                        status=Prescription.STATUS_APPROVED,
                    )
                except Prescription.DoesNotExist:
                    return Response({'detail': 'Approved prescription not found.'}, status=status.HTTP_400_BAD_REQUEST)

            if prescription_item_pk:
                prescription_item = (
                    PrescriptionItem.objects.select_related('prescription', 'product')
                    .filter(
                        pk=prescription_item_pk,
                        prescription__patient=request.user,
                        prescription__status=Prescription.STATUS_APPROVED,
                    )
                    .first()
                )
                if not prescription_item:
                    return Response({'detail': 'Approved prescription item not found.'}, status=status.HTTP_400_BAD_REQUEST)
                prescription = prescription_item.prescription
                prescription_reference = prescription.reference
        elif prescription_reference:
            from apps.prescriptions.models import Prescription, PrescriptionItem

            prescription = Prescription.objects.filter(
                reference=prescription_reference,
                patient=request.user,
                status=Prescription.STATUS_APPROVED,
            ).first()
            if prescription:
                prescription_item = PrescriptionItem.objects.select_related('prescription', 'product').filter(
                    prescription=prescription,
                    product=product,
                ).first()

        existing_item_filters = {
            'cart': cart,
            'product': product,
            'product_variant': variant,
        }
        if prescription or prescription_item:
            existing_item_filters.update({
                'prescription': prescription,
                'prescription_item': prescription_item,
            })
        else:
            existing_item_filters['prescription_reference'] = prescription_reference

        existing_item = CartItem.objects.filter(**existing_item_filters).first()
        requested_total = quantity + (existing_item.quantity if existing_item else 0)
        if product.requires_prescription:
            prescription_error = _prescription_cart_error(
                request.user,
                product,
                prescription_reference,
                requested_total,
                prescription=prescription,
                prescription_item=prescription_item,
            )
            if prescription_error:
                return Response({'detail': prescription_error}, status=status.HTTP_400_BAD_REQUEST)
        inventory_object = variant or product
        error = _product_availability_error(inventory_object, requested_total)
        if error:
            return Response({'detail': error}, status=status.HTTP_400_BAD_REQUEST)

        if existing_item:
            existing_item.quantity = requested_total
            existing_item.save(update_fields=['quantity'])
        else:
            CartItem.objects.create(
                cart=cart,
                product=product,
                product_variant=variant,
                quantity=quantity,
                prescription_reference=prescription_reference,
                prescription=prescription,
                prescription_item=prescription_item,
            )

        return Response(CartSerializer(cart).data, status=status.HTTP_201_CREATED)


class CartItemUpdateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def patch(self, request, pk):
        cart = get_or_create_cart(request.user)
        try:
            item = CartItem.objects.select_related('product', 'product_variant').get(pk=pk, cart=cart)
        except CartItem.DoesNotExist:
            return Response({'detail': 'Item not found.'}, status=status.HTTP_404_NOT_FOUND)

        quantity = request.data.get('quantity')
        try:
            quantity = int(quantity)
            if quantity < 1:
                return Response({'quantity': 'Must be at least 1.'}, status=status.HTTP_400_BAD_REQUEST)
        except (TypeError, ValueError):
            return Response({'quantity': 'Invalid quantity.'}, status=status.HTTP_400_BAD_REQUEST)

        if item.product.requires_prescription:
            prescription_error = _prescription_cart_error(
                request.user,
                item.product,
                item.prescription_reference,
                quantity,
                prescription=item.prescription,
                prescription_item=item.prescription_item,
            )
            if prescription_error:
                return Response({'detail': prescription_error}, status=status.HTTP_400_BAD_REQUEST)

        error = _product_availability_error(_cart_inventory_object(item), quantity)
        if error:
            return Response({'detail': error}, status=status.HTTP_400_BAD_REQUEST)

        item.quantity = quantity
        item.save(update_fields=['quantity'])
        return Response(CartSerializer(cart).data)


class CartItemDeleteView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def delete(self, request, pk):
        cart = get_or_create_cart(request.user)
        try:
            item = CartItem.objects.get(pk=pk, cart=cart)
        except CartItem.DoesNotExist:
            return Response({'detail': 'Item not found.'}, status=status.HTTP_404_NOT_FOUND)
        item.delete()
        return Response(CartSerializer(cart).data)


class CartClearView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def delete(self, request):
        cart = get_or_create_cart(request.user)
        cart.items.all().delete()
        cart.coupon = None
        cart.save(update_fields=['coupon', 'updated_at'])
        return Response({'detail': 'Cart cleared.'})


class CartApplyCouponView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = CouponApplySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        cart = get_or_create_cart(request.user)
        try:
            coupon = Coupon.objects.get(code=serializer.validated_data['code'].upper())
        except Coupon.DoesNotExist:
            return Response({'detail': 'Coupon not found.'}, status=status.HTTP_404_NOT_FOUND)

        if not coupon.is_available(request.user):
            return Response({'detail': 'Coupon is not available.'}, status=status.HTTP_400_BAD_REQUEST)
        if cart.total < coupon.minimum_subtotal:
            return Response({'detail': 'Cart does not meet coupon minimum subtotal.'}, status=status.HTTP_400_BAD_REQUEST)

        cart.coupon = coupon
        cart.save(update_fields=['coupon', 'updated_at'])
        return Response(CartSerializer(cart).data)


class CartRemoveCouponView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def delete(self, request):
        cart = get_or_create_cart(request.user)
        cart.coupon = None
        cart.save(update_fields=['coupon', 'updated_at'])
        return Response(CartSerializer(cart).data)


class CheckoutDraftView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        serializer = CheckoutSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        cart = get_or_create_cart(request.user)
        items = list(
            cart.items.select_related('product', 'product__brand', 'product__category', 'product_variant')
            .order_by('id')
        )
        if not items:
            return Response({'detail': 'Cart is empty.'}, status=status.HTTP_400_BAD_REQUEST)

        products = {
            product.id: product
            for product in Product.objects.select_for_update().filter(id__in=[item.product_id for item in items])
        }
        variants = {
            variant.id: variant
            for variant in ProductVariant.objects.select_for_update().filter(
                id__in=[item.product_variant_id for item in items if item.product_variant_id]
            )
        }
        for item in items:
            item.product = products[item.product_id]
            if item.product_variant_id:
                item.product_variant = variants.get(item.product_variant_id)

        errors = validate_cart_items(items)
        if errors:
            return Response({'detail': errors}, status=status.HTTP_400_BAD_REQUEST)

        shipping_method = None
        shipping_method_id = data.get('shipping_method_id')
        if shipping_method_id:
            try:
                shipping_method = ShippingMethod.objects.get(pk=shipping_method_id, is_active=True)
            except ShippingMethod.DoesNotExist:
                return Response({'detail': 'Shipping method not found.'}, status=status.HTTP_404_NOT_FOUND)
        else:
            shipping_method = ShippingMethod.objects.filter(code=data.get('delivery_method', 'standard'), is_active=True).first()

        subtotal, discount_total, shipping_fee, total = build_order_totals(cart, shipping_method=shipping_method)
        order = Order.objects.create(
            customer=request.user,
            coupon=cart.coupon if cart.coupon and cart.coupon.is_available(request.user) else None,
            coupon_code=cart.coupon.code if cart.coupon else '',
            payment_method=data['payment_method'],
            payment_status=Order.PAYMENT_STATUS_PENDING,
            delivery_method=data.get('delivery_method', 'standard'),
            delivery_notes=data.get('delivery_notes', ''),
            shipping_method=shipping_method,
            shipping_first_name=data['first_name'],
            shipping_last_name=data['last_name'],
            shipping_email=data['email'],
            shipping_phone=data['phone'],
            shipping_street=data['street'],
            shipping_city=data['city'],
            shipping_county=data['county'],
            subtotal=subtotal,
            discount_total=discount_total,
            shipping_fee=shipping_fee,
            total=total,
        )
        persist_checkout_address(request.user, data)
        snapshot_cart_to_order(order, items)
        create_order_event(
            order,
            event_type='draft_created',
            message='Checkout draft created.',
            actor=request.user,
            metadata={
                'item_count': len(items),
                'payment_method': order.payment_method,
                'shipping_method': shipping_method.code if shipping_method else order.delivery_method,
            },
        )
        return Response(OrderSerializer(order).data, status=status.HTTP_201_CREATED)


class PaymentIntentCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        serializer = PaymentIntentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            order = Order.objects.select_for_update().get(pk=data['order_id'], customer=request.user)
        except Order.DoesNotExist:
            return Response({'detail': 'Order not found.'}, status=status.HTTP_404_NOT_FOUND)

        if order.status not in [Order.STATUS_DRAFT, Order.STATUS_PENDING]:
            return Response(
                {
                    'detail': (
                        'This order is no longer awaiting payment. '
                        'If you have already paid, refresh the page to see the updated status. '
                        'If this order was completed or cancelled, start a new checkout to make another payment.'
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        existing_success = order.payment_intents.filter(
            provider=data['provider'],
            status=PaymentIntent.STATUS_SUCCEEDED,
        ).order_by('-created_at').first()
        if existing_success:
            return Response(PaymentIntentSerializer(existing_success).data)
        if order.payment_status == Order.PAYMENT_STATUS_PAID:
            return Response({'detail': 'This order has already been paid.'}, status=status.HTTP_400_BAD_REQUEST)

        provider = data['provider']
        existing_active = order.payment_intents.filter(
            provider=provider,
            status__in=[PaymentIntent.STATUS_PENDING, PaymentIntent.STATUS_REQUIRES_ACTION],
        ).order_by('-created_at').first()
        if existing_active and provider != PaymentIntent.PROVIDER_PAYBILL:
            return Response(PaymentIntentSerializer(existing_active).data)

        payload = {}
        client_secret = ''
        status_value = PaymentIntent.STATUS_REQUIRES_ACTION

        if provider == PaymentIntent.PROVIDER_MANUAL:
            status_value = PaymentIntent.STATUS_SUCCEEDED
        elif provider == PaymentIntent.PROVIDER_PAYBILL:
            if not get_paybill_number():
                return Response({'detail': 'M-Pesa paybill is not configured.'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
            if not getattr(settings, 'MPESA_C2B_URLS_REGISTERED', False):
                return Response(
                    {
                        'detail': (
                            'M-Pesa paybill callbacks are not registered yet. '
                            'Register the Daraja validation and confirmation URLs, then set '
                            'MPESA_C2B_URLS_REGISTERED=true in .env.'
                        )
                    },
                    status=status.HTTP_503_SERVICE_UNAVAILABLE,
                )
            try:
                MpesaClient().validate_c2b_configuration()
            except MpesaConfigurationError as exc:
                return Response({'detail': str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
            payload = {
                'channel': 'mpesa_paybill',
                'paybill_number': get_paybill_number(),
                'paybill_account_label': get_paybill_account_label(),
                'paybill_instructions': get_paybill_instructions(),
            }
        elif provider == PaymentIntent.PROVIDER_MPESA:
            payload = {'phone': data.get('phone', ''), 'instructions': 'Await M-Pesa confirmation.'}
        elif provider == PaymentIntent.PROVIDER_CARD:
            payload = {'instructions': 'Redirect customer to hosted card checkout.'}

        intent_amount = resolve_mpesa_stk_amount(order.total) if provider == PaymentIntent.PROVIDER_MPESA else order.total

        intent = existing_active if provider == PaymentIntent.PROVIDER_PAYBILL and existing_active else PaymentIntent.objects.create(
            order=order,
            initiated_by=request.user,
            provider=provider,
            status=status_value,
            amount=intent_amount,
            client_secret=client_secret,
            payload=payload,
            phone_number=data.get('phone', ''),
        )

        if provider == PaymentIntent.PROVIDER_MANUAL:
            order.payment_status = Order.PAYMENT_STATUS_PAID
            order.payment_reference = intent.reference
            order.save(update_fields=['payment_status', 'payment_reference', 'updated_at'])
            create_order_event(order, 'payment_captured', 'Manual payment marked as paid.', actor=request.user)
        elif provider == PaymentIntent.PROVIDER_PAYBILL:
            if order.payment_method != Order.PAYMENT_MPESA_PAYBILL:
                return Response({'detail': 'This order is not configured for M-Pesa paybill.'}, status=status.HTTP_400_BAD_REQUEST)
            intent.initiated_by = request.user
            account_reference = build_paybill_account_reference(order)
            reference_code = data.get('reference_code', '').strip()
            phone_number = data.get('phone', '').strip()
            if reference_code:
                _upsert_paybill_intent(
                    intent,
                    phone=phone_number,
                    reference_code=reference_code,
                    account_reference=account_reference,
                    metadata=data.get('metadata') or {},
                )
            else:
                _merge_intent_payload(intent, {
                    'channel': 'mpesa_paybill',
                    'paybill_number': get_paybill_number(),
                    'paybill_account_label': get_paybill_account_label(),
                    'paybill_instructions': get_paybill_instructions(),
                    **({'metadata': data.get('metadata') or {}} if data.get('metadata') else {}),
                })
                intent.external_reference = account_reference
                intent.phone_number = phone_number
                intent.status = PaymentIntent.STATUS_REQUIRES_ACTION
                intent.last_error = ''
                intent.processed_at = None
                intent.save(update_fields=[
                    'initiated_by', 'payload', 'external_reference', 'phone_number',
                    'status', 'last_error', 'processed_at', 'updated_at',
                ])
                order.payment_status = Order.PAYMENT_STATUS_REQUIRES_ACTION
                order.save(update_fields=['payment_status', 'updated_at'])
                create_order_event(
                    order,
                    'payment_intent_created',
                    'M-Pesa paybill initiated. Awaiting Safaricom confirmation callback.',
                    actor=request.user,
                    metadata={'intent_reference': intent.reference, 'account_reference': account_reference},
                )
        elif provider == PaymentIntent.PROVIDER_MPESA:
            try:
                mpesa_client = MpesaClient()
                normalized_phone, response_payload = mpesa_client.initiate_stk_push(
                    payment_intent=intent,
                    phone=data.get('phone', ''),
                    account_reference=order.order_number,
                    description=f'Pay {order.order_number}',
                )
            except MpesaConfigurationError as exc:
                intent.status = PaymentIntent.STATUS_FAILED
                intent.save(update_fields=['status', 'updated_at'])
                _record_payment_error(intent, 'mpesa_initiate_configuration', str(exc))
                return Response({'detail': str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
            except MpesaAPIError as exc:
                intent.status = PaymentIntent.STATUS_FAILED
                intent.save(update_fields=['status', 'updated_at'])
                _mark_order_payment_failed(order, intent, str(exc))
                return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

            intent.phone_number = normalized_phone
            intent.external_reference = order.order_number
            intent.client_secret = response_payload.get('CustomerMessage', '')
            intent.provider_reference = response_payload.get('ResponseCode', '')
            intent.merchant_request_id = response_payload.get('MerchantRequestID', '')
            intent.checkout_request_id = response_payload.get('CheckoutRequestID', '')
            intent.payload = response_payload
            intent.save(update_fields=[
                'phone_number', 'external_reference', 'client_secret', 'provider_reference',
                'merchant_request_id', 'checkout_request_id', 'payload', 'updated_at'
            ])

            order.payment_status = Order.PAYMENT_STATUS_REQUIRES_ACTION
            order.save(update_fields=['payment_status', 'updated_at'])
            create_order_event(
                order,
                'payment_intent_created',
                'M-Pesa STK push initiated.',
                actor=request.user,
                metadata={'intent_reference': intent.reference, 'phone_number': normalized_phone},
            )
        elif provider == PaymentIntent.PROVIDER_CARD:
            try:
                intent = _upsert_flutterwave_card_intent(
                    request,
                    order,
                    return_url=data.get('return_url', ''),
                )
            except FlutterwaveConfigurationError as exc:
                intent.status = PaymentIntent.STATUS_FAILED
                intent.save(update_fields=['status', 'updated_at'])
                _record_payment_error(intent, 'card_checkout_configuration', str(exc))
                return Response({'detail': str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
            except FlutterwaveAPIError as exc:
                intent.status = PaymentIntent.STATUS_FAILED
                intent.save(update_fields=['status', 'updated_at'])
                _mark_order_payment_failed(order, intent, str(exc))
                return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        else:
            order.payment_status = Order.PAYMENT_STATUS_REQUIRES_ACTION
            order.save(update_fields=['payment_status', 'updated_at'])
            create_order_event(
                order,
                'payment_intent_created',
                f'Payment intent created via {provider}.',
                actor=request.user,
                metadata={'intent_reference': intent.reference},
            )

        return Response(PaymentIntentSerializer(intent).data, status=status.HTTP_201_CREATED)


class FlutterwaveInitiateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        serializer = FlutterwaveInitiateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        order, error_response = _get_order_for_payment_request(request, data['order_id'])
        if error_response:
            return error_response
        order = Order.objects.select_for_update().get(pk=order.pk)

        if order.payment_method != Order.PAYMENT_CARD:
            return Response({'detail': 'This order is not configured for card payment.'}, status=status.HTTP_400_BAD_REQUEST)
        if order.status not in [Order.STATUS_DRAFT, Order.STATUS_PENDING]:
            return Response(
                {'detail': 'This order is no longer awaiting payment. Refresh the order to see its latest payment state.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if order.payment_status == Order.PAYMENT_STATUS_PAID:
            existing_success = order.payment_intents.filter(
                provider=PaymentIntent.PROVIDER_CARD,
                status=PaymentIntent.STATUS_SUCCEEDED,
            ).order_by('-created_at').first()
            if existing_success:
                return Response(PaymentIntentSerializer(existing_success).data)
            return Response({'detail': 'This order has already been paid.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            intent = _upsert_flutterwave_card_intent(request, order, return_url=data.get('return_url', ''))
        except FlutterwaveConfigurationError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except FlutterwaveAPIError as exc:
            _record_payment_error(
                order.payment_intents.filter(provider=PaymentIntent.PROVIDER_CARD).order_by('-created_at').first() or
                PaymentIntent(order=order, provider=PaymentIntent.PROVIDER_CARD, amount=order.total),
                'card_checkout_configuration',
                str(exc),
            )
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(PaymentIntentSerializer(intent).data, status=status.HTTP_201_CREATED)


class FlutterwaveRedirectView(APIView):
    permission_classes = [permissions.AllowAny]

    @transaction.atomic
    def get(self, request):
        tx_ref = str(request.query_params.get('tx_ref') or '').strip()
        transaction_id = str(request.query_params.get('transaction_id') or '').strip()
        return_url = str(
            request.query_params.get('return_url')
            or getattr(settings, 'FLUTTERWAVE_REDIRECT_URL', '')
            or f'{settings.FRONTEND_BASE_URL}/checkout'
        ).strip()

        if not tx_ref:
            return HttpResponseRedirect(_append_query_params(return_url, {'status': 'failed', 'error': 'missing_tx_ref'}))

        try:
            intent = PaymentIntent.objects.select_for_update().select_related('order').get(
                provider=PaymentIntent.PROVIDER_CARD,
                reference=tx_ref,
            )
        except PaymentIntent.DoesNotExist:
            return HttpResponseRedirect(_append_query_params(return_url, {'tx_ref': tx_ref, 'status': 'failed', 'error': 'payment_intent_not_found'}))

        if transaction_id:
            try:
                _sync_flutterwave_intent(intent, transaction_id)
            except (FlutterwaveConfigurationError, FlutterwaveAPIError) as exc:
                _record_payment_error(intent, 'card_redirect_sync', str(exc))
                redirect_status = 'failed'
                redirect_params = {
                    'order_id': intent.order_id,
                    'intent_id': intent.id,
                    'tx_ref': tx_ref,
                    'transaction_id': transaction_id,
                    'status': redirect_status,
                    'error': 'verification_failed',
                }
                return HttpResponseRedirect(_append_query_params(return_url, redirect_params))

            if intent.status == PaymentIntent.STATUS_SUCCEEDED:
                _mark_order_paid(intent.order, intent, 'Card payment confirmed by redirect verification.', 'Your card payment was confirmed successfully.')
                redirect_status = 'successful'
            else:
                _mark_order_payment_failed(intent.order, intent, intent.last_error)
                redirect_status = 'failed'
        else:
            redirect_status = 'cancelled'
            if intent.status not in [PaymentIntent.STATUS_SUCCEEDED, PaymentIntent.STATUS_FAILED, PaymentIntent.STATUS_CANCELLED]:
                intent.status = PaymentIntent.STATUS_CANCELLED
                intent.last_error = 'Card checkout was closed before payment confirmation.'
                intent.processed_at = timezone.now()
                intent.save(update_fields=['status', 'last_error', 'processed_at', 'updated_at'])
                _mark_order_payment_failed(intent.order, intent, intent.last_error)

        redirect_params = {
            'order_id': intent.order_id,
            'intent_id': intent.id,
            'tx_ref': tx_ref,
            'status': redirect_status,
        }
        if transaction_id:
            redirect_params['transaction_id'] = transaction_id
        return HttpResponseRedirect(_append_query_params(return_url, redirect_params))


class FlutterwaveStatusView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @transaction.atomic
    def get(self, request, tx_ref):
        serializer = FlutterwaveStatusSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        transaction_id = serializer.validated_data.get('transaction_id', '').strip()

        try:
            intent = PaymentIntent.objects.select_for_update().select_related('order').get(
                provider=PaymentIntent.PROVIDER_CARD,
                reference=tx_ref,
            )
        except PaymentIntent.DoesNotExist:
            return Response({'detail': 'Payment intent not found.'}, status=status.HTTP_404_NOT_FOUND)

        if intent.order.customer_id != request.user.id and request.user.role != 'admin':
            return Response({'detail': 'You do not have permission to access this payment.'}, status=status.HTTP_403_FORBIDDEN)

        transaction_id = transaction_id or intent.order.flutterwave_tx_id
        if transaction_id and intent.status not in [PaymentIntent.STATUS_SUCCEEDED, PaymentIntent.STATUS_FAILED, PaymentIntent.STATUS_CANCELLED]:
            try:
                _sync_flutterwave_intent(intent, transaction_id)
            except (FlutterwaveConfigurationError, FlutterwaveAPIError) as exc:
                _record_payment_error(intent, 'card_status_poll', str(exc))
                return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
            if intent.status == PaymentIntent.STATUS_SUCCEEDED:
                _mark_order_paid(intent.order, intent, 'Card payment verified successfully.', 'Your card payment was confirmed successfully.')
            elif intent.status == PaymentIntent.STATUS_FAILED:
                _mark_order_payment_failed(intent.order, intent, intent.last_error)

        response_status = status.HTTP_202_ACCEPTED if intent.status == PaymentIntent.STATUS_REQUIRES_ACTION else status.HTTP_200_OK
        return Response(PaymentIntentSerializer(intent).data, status=response_status)


class FlutterwaveCallbackView(APIView):
    permission_classes = [permissions.AllowAny]

    @transaction.atomic
    def post(self, request):
        client = FlutterwaveClient()
        raw_body = request.body or b''
        if not client.verify_signature(raw_body, request.headers):
            return Response({'detail': 'Invalid Flutterwave webhook signature.'}, status=status.HTTP_403_FORBIDDEN)

        event_data = request.data.get('data') or {}
        tx_ref = str(event_data.get('tx_ref') or '').strip()
        transaction_id = str(event_data.get('id') or '').strip()
        if not tx_ref or not transaction_id:
            return Response({'detail': 'Invalid Flutterwave webhook payload.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            intent = PaymentIntent.objects.select_for_update().select_related('order').get(
                provider=PaymentIntent.PROVIDER_CARD,
                reference=tx_ref,
            )
        except PaymentIntent.DoesNotExist:
            return Response({'detail': 'Payment intent not found.'}, status=status.HTTP_404_NOT_FOUND)

        try:
            _sync_flutterwave_intent(intent, transaction_id)
        except (FlutterwaveConfigurationError, FlutterwaveAPIError) as exc:
            _record_payment_error(intent, 'card_webhook_sync', str(exc))
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        if intent.status == PaymentIntent.STATUS_SUCCEEDED:
            _mark_order_paid(intent.order, intent, 'Card payment confirmed by webhook.', 'Your card payment was confirmed successfully.')
        else:
            _mark_order_payment_failed(intent.order, intent, intent.last_error)
        return Response({'detail': 'Flutterwave webhook processed.'})


class MpesaCallbackView(APIView):
    permission_classes = [permissions.AllowAny]

    @transaction.atomic
    def post(self, request):
        callback = parse_mpesa_callback(request.data)
        checkout_request_id = callback['checkout_request_id']
        merchant_request_id = callback['merchant_request_id']

        try:
            intent = PaymentIntent.objects.select_for_update().select_related('order').get(
                provider=PaymentIntent.PROVIDER_MPESA,
                checkout_request_id=checkout_request_id,
                merchant_request_id=merchant_request_id,
            )
        except PaymentIntent.DoesNotExist:
            return Response({'ResultCode': 1, 'ResultDesc': 'Payment intent not found.'})

        intent.callback_payload = request.data
        intent.processed_at = timezone.now()
        intent.provider_reference = callback['metadata'].get('MpesaReceiptNumber', intent.provider_reference)

        order = intent.order
        if callback['result_code'] == '0':
            intent.status = PaymentIntent.STATUS_SUCCEEDED
            intent.last_error = ''
            _mark_order_paid(order, intent, 'M-Pesa payment confirmed.', 'Your M-Pesa payment was confirmed successfully.')
        else:
            intent.status = PaymentIntent.STATUS_FAILED
            intent.last_error = callback['result_desc']
            _mark_order_payment_failed(order, intent, callback['result_desc'] or 'M-Pesa payment failed.')
        intent.save(update_fields=['callback_payload', 'processed_at', 'provider_reference', 'status', 'last_error', 'updated_at'])
        return Response({'ResultCode': 0, 'ResultDesc': 'Accepted'})


class PaymentIntentStatusSyncView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @transaction.atomic
    def post(self, request, pk):
        try:
            intent = PaymentIntent.objects.select_for_update().select_related('order').get(pk=pk, order__customer=request.user)
        except PaymentIntent.DoesNotExist:
            return Response({'detail': 'Payment intent not found.'}, status=status.HTTP_404_NOT_FOUND)

        if (
            intent.provider == PaymentIntent.PROVIDER_MPESA
            and intent.order.payment_status == Order.PAYMENT_STATUS_PAID
            and intent.status != PaymentIntent.STATUS_SUCCEEDED
        ):
            intent.status = PaymentIntent.STATUS_SUCCEEDED
            intent.last_error = ''
            if not intent.processed_at:
                intent.processed_at = timezone.now()
            if not intent.provider_reference:
                intent.provider_reference = intent.order.payment_reference
            intent.save(update_fields=['status', 'last_error', 'processed_at', 'provider_reference', 'updated_at'])
            return Response(PaymentIntentSerializer(intent).data)

        if intent.status in [
            PaymentIntent.STATUS_SUCCEEDED,
            PaymentIntent.STATUS_FAILED,
            PaymentIntent.STATUS_CANCELLED,
        ]:
            return Response(PaymentIntentSerializer(intent).data)

        if intent.provider == PaymentIntent.PROVIDER_MPESA:
            next_allowed_at = _mpesa_sync_next_allowed_at(intent)
            if next_allowed_at:
                _set_mpesa_sync_meta(
                    intent,
                    deferred_until=next_allowed_at.isoformat(),
                )
                intent.save(update_fields=['payload', 'updated_at'])
                return Response(PaymentIntentSerializer(intent).data, status=status.HTTP_202_ACCEPTED)

            _set_mpesa_sync_meta(intent, last_attempt_at=timezone.now().isoformat())
            intent.save(update_fields=['payload', 'updated_at'])
            try:
                mpesa_response = MpesaClient().query_stk_status(intent)
            except MpesaConfigurationError as exc:
                _record_payment_error(intent, 'mpesa_status_sync_configuration', str(exc))
                return Response({'detail': str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
            except MpesaAPIError as exc:
                retry_after_seconds = _mpesa_sync_retry_after_seconds(str(exc))
                if retry_after_seconds:
                    next_allowed_at = timezone.now() + timedelta(seconds=retry_after_seconds)
                    _set_mpesa_sync_meta(
                        intent,
                        next_allowed_at=next_allowed_at.isoformat(),
                        last_transient_error=str(exc),
                    )
                    intent.status = PaymentIntent.STATUS_REQUIRES_ACTION
                    intent.save(update_fields=['payload', 'status', 'updated_at'])
                    _record_payment_notice(
                        intent,
                        'mpesa_status_sync_deferred',
                        str(exc),
                        metadata={'retry_after_seconds': retry_after_seconds},
                    )
                    return Response(PaymentIntentSerializer(intent).data, status=status.HTTP_202_ACCEPTED)
                _record_payment_error(intent, 'mpesa_status_sync', str(exc))
                response_status = (
                    status.HTTP_202_ACCEPTED
                    if intent.status == PaymentIntent.STATUS_REQUIRES_ACTION
                    else status.HTTP_400_BAD_REQUEST
                )
                return Response(PaymentIntentSerializer(intent).data, status=response_status)

            intent.payload = {**intent.payload, 'status_query': mpesa_response}
            result_code = str(mpesa_response.get('ResultCode', ''))
            if result_code == '0':
                intent.status = PaymentIntent.STATUS_SUCCEEDED
                intent.last_error = ''
                _set_mpesa_sync_meta(intent, next_allowed_at='', last_transient_error='')
                intent.provider_reference = mpesa_response.get('MpesaReceiptNumber', intent.provider_reference)
                intent.processed_at = timezone.now()
                intent.save(update_fields=['payload', 'status', 'last_error', 'provider_reference', 'processed_at', 'updated_at'])
                _mark_order_paid(intent.order, intent, 'M-Pesa payment confirmed via status sync.', 'Your M-Pesa payment was confirmed successfully.')
            elif _is_mpesa_processing_response(mpesa_response):
                intent.status = PaymentIntent.STATUS_REQUIRES_ACTION
                intent.last_error = ''
                min_interval = max(1, int(getattr(settings, 'MPESA_STATUS_SYNC_MIN_INTERVAL_SECONDS', 15)))
                _set_mpesa_sync_meta(intent, next_allowed_at=(timezone.now() + timedelta(seconds=min_interval)).isoformat())
                intent.save(update_fields=['payload', 'status', 'last_error', 'updated_at'])
                return Response(PaymentIntentSerializer(intent).data, status=status.HTTP_202_ACCEPTED)
            else:
                intent.status = PaymentIntent.STATUS_FAILED
                intent.last_error = mpesa_response.get('ResultDesc', '')
                intent.processed_at = timezone.now()
                intent.save(update_fields=['payload', 'status', 'last_error', 'processed_at', 'updated_at'])
                _mark_order_payment_failed(intent.order, intent, intent.last_error)
        elif intent.provider == PaymentIntent.PROVIDER_CARD:
            transaction_id = (
                request.data.get('transaction_id')
                or request.query_params.get('transaction_id')
                or intent.order.flutterwave_tx_id
            )
            if not transaction_id:
                return Response({'detail': 'transaction_id is required to verify this card payment.'}, status=status.HTTP_400_BAD_REQUEST)
            try:
                _sync_flutterwave_intent(intent, transaction_id)
            except (FlutterwaveConfigurationError, FlutterwaveAPIError) as exc:
                _record_payment_error(intent, 'card_status_sync', str(exc))
                return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
            if intent.status == PaymentIntent.STATUS_SUCCEEDED:
                _mark_order_paid(intent.order, intent, 'Card payment verified successfully.', 'Your card payment was confirmed successfully.')
            else:
                _mark_order_payment_failed(intent.order, intent, intent.last_error)
        elif intent.provider == PaymentIntent.PROVIDER_PAYBILL:
            response_status = (
                status.HTTP_202_ACCEPTED
                if intent.status in [PaymentIntent.STATUS_PENDING, PaymentIntent.STATUS_REQUIRES_ACTION]
                else status.HTTP_200_OK
            )
            return Response(PaymentIntentSerializer(intent).data, status=response_status)
        else:
            return Response({'detail': 'Unsupported payment provider for sync.'}, status=status.HTTP_400_BAD_REQUEST)

        return Response(PaymentIntentSerializer(intent).data)


class MpesaPaybillValidationView(APIView):
    permission_classes = [permissions.AllowAny]

    @transaction.atomic
    def post(self, request):
        raw_payload = request.data or {}
        account_reference = str(raw_payload.get('BillRefNumber') or '').strip()
        amount = _parse_payment_amount(raw_payload.get('TransAmount'))
        order = _resolve_paybill_order(account_reference=account_reference)

        if order is None:
            payments_logger.warning(
                'Unmatched M-Pesa paybill validation callback account_reference=%s payload=%s',
                account_reference,
                raw_payload,
            )
            return Response({'ResultCode': 1, 'ResultDesc': 'Invalid account reference.'})

        rejection_message = _validate_paybill_order_for_c2b(
            order,
            amount=amount,
            business_shortcode=raw_payload.get('BusinessShortCode', ''),
        )
        if rejection_message:
            create_order_event(
                order,
                'paybill_validation_rejected',
                rejection_message,
                metadata=_build_paybill_callback_metadata(raw_payload, source='daraja_validation'),
            )
            return Response({'ResultCode': 1, 'ResultDesc': rejection_message})

        create_order_event(
            order,
            'paybill_validation_accepted',
            'Safaricom paybill validation accepted.',
            metadata=_build_paybill_callback_metadata(raw_payload, source='daraja_validation'),
        )
        return Response({'ResultCode': 0, 'ResultDesc': 'Accepted'})


class MpesaPaybillConfirmationView(APIView):
    permission_classes = [permissions.AllowAny]

    @transaction.atomic
    def post(self, request):
        raw_payload = request.data or {}
        account_reference = str(raw_payload.get('BillRefNumber') or '').strip()
        provider_reference = str(raw_payload.get('TransID') or '').strip()
        order = _resolve_paybill_order(account_reference=account_reference)

        if order is None:
            payments_logger.error(
                'Unmatched M-Pesa paybill confirmation account_reference=%s provider_reference=%s payload=%s',
                account_reference,
                provider_reference,
                raw_payload,
            )
            return Response({'ResultCode': 0, 'ResultDesc': 'Accepted'})

        intent, confirmed = _apply_paybill_confirmation(
            order,
            raw_payload=raw_payload,
            source='daraja_confirmation',
        )
        if not confirmed:
            payments_logger.warning(
                'M-Pesa paybill confirmation requires review order=%s intent=%s provider_reference=%s last_error=%s',
                order.order_number,
                intent.reference,
                intent.provider_reference,
                intent.last_error,
            )
        return Response({'ResultCode': 0, 'ResultDesc': 'Accepted'})


class PaymentWebhookView(APIView):
    permission_classes = [permissions.AllowAny]

    @transaction.atomic
    def post(self, request):
        flutterwave_signature = request.headers.get('flutterwave-signature') or request.headers.get('verif-hash')
        if flutterwave_signature:
            client = FlutterwaveClient()
            raw_body = request.body or b''
            if not client.verify_signature(raw_body, request.headers):
                return Response({'detail': 'Invalid Flutterwave webhook signature.'}, status=status.HTTP_403_FORBIDDEN)

            event_data = request.data.get('data') or {}
            tx_ref = event_data.get('tx_ref')
            transaction_id = event_data.get('id')
            if not tx_ref or not transaction_id:
                return Response({'detail': 'Invalid Flutterwave webhook payload.'}, status=status.HTTP_400_BAD_REQUEST)

            try:
                intent = PaymentIntent.objects.select_for_update().select_related('order').get(
                    provider=PaymentIntent.PROVIDER_CARD,
                    reference=tx_ref,
                )
            except PaymentIntent.DoesNotExist:
                return Response({'detail': 'Payment intent not found.'}, status=status.HTTP_404_NOT_FOUND)

            try:
                _sync_flutterwave_intent(intent, transaction_id)
            except (FlutterwaveConfigurationError, FlutterwaveAPIError) as exc:
                _record_payment_error(intent, 'card_webhook_sync', str(exc))
                return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

            if intent.status == PaymentIntent.STATUS_SUCCEEDED:
                _mark_order_paid(intent.order, intent, 'Card payment confirmed by webhook.', 'Your card payment was confirmed successfully.')
            else:
                _mark_order_payment_failed(intent.order, intent, intent.last_error)
            return Response({'detail': 'Flutterwave webhook processed.'})

        expected_secret = getattr(settings, 'PAYMENT_WEBHOOK_SECRET', '')
        if expected_secret and request.headers.get('X-Ava-Webhook-Secret') != expected_secret:
            return Response({'detail': 'Invalid webhook signature.'}, status=status.HTTP_403_FORBIDDEN)

        serializer = PaymentWebhookSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            intent = PaymentIntent.objects.select_for_update().select_related('order').get(reference=data['reference'])
        except PaymentIntent.DoesNotExist:
            return Response({'detail': 'Payment intent not found.'}, status=status.HTTP_404_NOT_FOUND)

        intent.status = data['status']
        intent.provider_reference = data.get('provider_reference', '')
        intent.payload = data.get('payload', intent.payload)
        intent.last_error = '' if data['status'] == PaymentIntent.STATUS_SUCCEEDED else data.get('message', '')
        intent.processed_at = timezone.now()
        intent.save()

        order = intent.order
        if intent.status == PaymentIntent.STATUS_SUCCEEDED:
            _mark_order_paid(order, intent, 'Payment confirmed by webhook.', 'Your payment was confirmed successfully.')
        elif intent.status in [PaymentIntent.STATUS_FAILED, PaymentIntent.STATUS_CANCELLED]:
            _mark_order_payment_failed(order, intent, data.get('message') or 'Payment failed.')

        return Response({'detail': 'Webhook processed.'})


class PaybillWebhookView(APIView):
    permission_classes = [permissions.AllowAny]

    @transaction.atomic
    def post(self, request):
        expected_secret = getattr(settings, 'PAYMENT_WEBHOOK_SECRET', '')
        if expected_secret and request.headers.get('X-Ava-Webhook-Secret') != expected_secret:
            return Response({'detail': 'Invalid webhook signature.'}, status=status.HTTP_403_FORBIDDEN)

        serializer = PaybillWebhookSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        transaction_reference = data['transaction_reference'].strip()

        account_reference = (data.get('account_reference') or '').strip()
        order = _resolve_paybill_order(
            order_number=(data.get('order_number') or '').strip(),
            account_reference=account_reference,
        )

        if order is None:
            return Response({'detail': 'Order not found for paybill reconciliation.'}, status=status.HTTP_404_NOT_FOUND)

        status_value = data['status']
        if status_value == PaymentIntent.STATUS_SUCCEEDED:
            intent, _ = _apply_paybill_confirmation(
                order,
                raw_payload={
                    **(data.get('payload') or request.data),
                    'BillRefNumber': account_reference or build_paybill_account_reference(order),
                    'TransID': transaction_reference,
                    'MSISDN': (data.get('phone') or '').strip(),
                    'TransAmount': str(data.get('amount') or order.total),
                },
                source='legacy_paybill_webhook',
            )
        elif status_value in [PaymentIntent.STATUS_FAILED, PaymentIntent.STATUS_CANCELLED]:
            intent = PaymentIntent.objects.select_for_update().filter(
                order=order,
                provider=PaymentIntent.PROVIDER_PAYBILL,
            ).order_by('-created_at').first()
            if intent is None:
                intent = PaymentIntent.objects.create(
                    order=order,
                    provider=PaymentIntent.PROVIDER_PAYBILL,
                    status=PaymentIntent.STATUS_PENDING,
                    amount=order.total,
                    external_reference=account_reference or build_paybill_account_reference(order),
                    provider_reference=transaction_reference,
                    phone_number=(data.get('phone') or '').strip(),
                    payload={'channel': 'mpesa_paybill', 'source': 'legacy_paybill_webhook'},
                )
            intent.callback_payload = data.get('payload') or request.data
            _merge_intent_payload(intent, {
                'channel': 'mpesa_paybill',
                'paybill_number': get_paybill_number(),
                'paybill_account_label': get_paybill_account_label(),
                'paybill_instructions': get_paybill_instructions(),
            })
            intent.external_reference = account_reference or intent.external_reference or build_paybill_account_reference(order)
            intent.provider_reference = transaction_reference
            intent.phone_number = (data.get('phone') or intent.phone_number or '').strip()
            intent.processed_at = timezone.now()
            intent.status = PaymentIntent.STATUS_FAILED
            intent.last_error = data.get('message') or 'Paybill payment was not confirmed.'
            intent.save(update_fields=[
                'payload', 'callback_payload', 'external_reference', 'provider_reference',
                'phone_number', 'processed_at', 'status', 'last_error', 'updated_at',
            ])
            _mark_order_payment_failed(order, intent, intent.last_error)
        else:
            intent = PaymentIntent.objects.select_for_update().filter(
                order=order,
                provider=PaymentIntent.PROVIDER_PAYBILL,
            ).order_by('-created_at').first()
            if intent is None:
                intent = PaymentIntent.objects.create(
                    order=order,
                    provider=PaymentIntent.PROVIDER_PAYBILL,
                    status=PaymentIntent.STATUS_PENDING,
                    amount=order.total,
                    external_reference=account_reference or build_paybill_account_reference(order),
                    provider_reference=transaction_reference,
                    phone_number=(data.get('phone') or '').strip(),
                    payload={'channel': 'mpesa_paybill', 'source': 'legacy_paybill_webhook'},
                )
            intent.callback_payload = data.get('payload') or request.data
            _merge_intent_payload(intent, {
                'channel': 'mpesa_paybill',
                'paybill_number': get_paybill_number(),
                'paybill_account_label': get_paybill_account_label(),
                'paybill_instructions': get_paybill_instructions(),
            })
            intent.external_reference = account_reference or intent.external_reference or build_paybill_account_reference(order)
            intent.provider_reference = transaction_reference
            intent.phone_number = (data.get('phone') or intent.phone_number or '').strip()
            intent.processed_at = timezone.now()
            intent.status = PaymentIntent.STATUS_REQUIRES_ACTION
            intent.last_error = ''
            intent.save(update_fields=[
                'payload', 'callback_payload', 'external_reference', 'provider_reference',
                'phone_number', 'processed_at', 'status', 'last_error', 'updated_at',
            ])
            order.payment_status = Order.PAYMENT_STATUS_REQUIRES_ACTION
            order.save(update_fields=['payment_status', 'updated_at'])
            create_order_event(
                order,
                'paybill_reconciliation_pending',
                'Paybill payment received and is awaiting final reconciliation.',
                metadata={'intent_reference': intent.reference, 'provider_reference': transaction_reference},
            )

        return Response(PaymentIntentSerializer(intent).data)


class AdminPaybillReconcileView(APIView):
    permission_classes = [IsAdminUser]

    @transaction.atomic
    def post(self, request, pk):
        try:
            intent = PaymentIntent.objects.select_for_update().select_related('order').get(
                pk=pk,
                provider=PaymentIntent.PROVIDER_PAYBILL,
            )
        except PaymentIntent.DoesNotExist:
            return Response({'detail': 'Paybill payment intent not found.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = AdminPaybillReconcileSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        provider_reference = data.get('provider_reference', '').strip() or intent.provider_reference
        message = data.get('message', '').strip()
        intent.provider_reference = provider_reference
        _merge_intent_payload(intent, {
            'admin_reconciliation': {
                'actor_id': request.user.id,
                'actor_name': getattr(request.user, 'full_name', '') or getattr(request.user, 'email', ''),
                'status': data['status'],
                'message': message,
                'timestamp': timezone.now().isoformat(),
                'payload': data.get('payload') or {},
            },
        })
        intent.processed_at = timezone.now()

        if data['status'] == PaymentIntent.STATUS_SUCCEEDED:
            intent.status = PaymentIntent.STATUS_SUCCEEDED
            intent.last_error = ''
            intent.save(update_fields=['provider_reference', 'payload', 'processed_at', 'status', 'last_error', 'updated_at'])
            _mark_order_paid(
                intent.order,
                intent,
                message or 'M-Pesa paybill payment confirmed by admin.',
                'Your M-Pesa paybill payment was confirmed successfully.',
            )
        else:
            intent.status = PaymentIntent.STATUS_FAILED
            intent.last_error = message or 'Paybill payment was not confirmed.'
            intent.save(update_fields=['provider_reference', 'payload', 'processed_at', 'status', 'last_error', 'updated_at'])
            _mark_order_payment_failed(intent.order, intent, intent.last_error)

        log_admin_action(
            request.user,
            action='paybill_payment_reconciled',
            entity_type='payment_intent',
            entity_id=intent.id,
            message=f'Paybill intent {intent.reference} reconciled as {intent.status}',
            metadata={'order_number': intent.order.order_number, 'provider_reference': provider_reference},
        )
        return Response(PaymentIntentSerializer(intent).data)


class AdminMpesaPaybillRegisterUrlsView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request):
        serializer = MpesaC2BRegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            client = MpesaClient()
            if serializer.validated_data.get('response_type'):
                client.c2b_response_type = serializer.validated_data['response_type']
            response_payload = client.register_c2b_urls()
        except MpesaConfigurationError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except MpesaAPIError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        log_admin_action(
            request.user,
            action='mpesa_paybill_urls_registered',
            entity_type='payment_gateway',
            entity_id=0,
            message='Registered M-Pesa paybill validation and confirmation URLs.',
            metadata={
                'response_type': client.c2b_response_type,
                'shortcode': client.c2b_shortcode,
                'validation_url': client.c2b_validation_url,
                'confirmation_url': client.c2b_confirmation_url,
                'provider_response': response_payload,
            },
        )
        return Response({
            'detail': 'M-Pesa paybill callback URLs registered successfully.',
            'next_step': 'Set MPESA_C2B_URLS_REGISTERED=true in .env and restart Django.',
            'shortcode': client.c2b_shortcode,
            'response_type': client.c2b_response_type,
            'validation_url': client.c2b_validation_url,
            'confirmation_url': client.c2b_confirmation_url,
            'provider_response': response_payload,
        })


class CheckoutFinalizeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @transaction.atomic
    def post(self, request, pk):
        try:
            order = Order.objects.select_for_update().prefetch_related('items').get(pk=pk, customer=request.user)
        except Order.DoesNotExist:
            return Response({'detail': 'Order not found.'}, status=status.HTTP_404_NOT_FOUND)

        if order.status not in [Order.STATUS_DRAFT, Order.STATUS_PENDING, Order.STATUS_PAID]:
            return Response({'detail': 'Order cannot be finalized in its current state.'}, status=status.HTTP_400_BAD_REQUEST)

        if order.payment_method != Order.PAYMENT_COD and order.payment_status != Order.PAYMENT_STATUS_PAID:
            return Response({'detail': 'Payment must be confirmed before finalizing this order.'}, status=status.HTTP_400_BAD_REQUEST)

        product_ids = [item.product_id for item in order.items.all() if item.product_id]
        variant_ids = [item.product_variant_id for item in order.items.all() if item.product_variant_id]
        locked_products = {
            product.id: product
            for product in Product.objects.select_for_update().filter(id__in=product_ids)
        }
        locked_variants = {
            variant.id: variant
            for variant in ProductVariant.objects.select_for_update().filter(id__in=variant_ids)
        }

        errors = []
        for item in order.items.all():
            inventory_object = locked_variants.get(item.product_variant_id) if item.product_variant_id else locked_products.get(item.product_id)
            if not inventory_object:
                errors.append(f'{item.product_name} is no longer available.')
                continue
            error = _product_availability_error(inventory_object, item.quantity)
            if error:
                errors.append(error)
        if errors:
            return Response({'detail': errors}, status=status.HTTP_400_BAD_REQUEST)

        for item in order.items.all():
            inventory_object = locked_variants.get(item.product_variant_id) if item.product_variant_id else locked_products.get(item.product_id)
            if not inventory_object:
                continue
            inventory_object.stock_quantity = max(0, inventory_object.stock_quantity - item.quantity)
            inventory_object.save()

        order.status = Order.STATUS_PENDING if order.payment_method == Order.PAYMENT_COD else Order.STATUS_PAID
        if order.payment_method == Order.PAYMENT_COD:
            order.payment_status = Order.PAYMENT_STATUS_PENDING
        order.inventory_committed = True
        if not order.placed_at:
            order.placed_at = timezone.now()
        order.save(update_fields=['status', 'payment_status', 'inventory_committed', 'placed_at', 'updated_at'])

        cart = get_or_create_cart(request.user)
        cart.items.all().delete()
        if cart.coupon_id == order.coupon_id:
            cart.coupon = None
            cart.save(update_fields=['coupon', 'updated_at'])

        create_order_event(order, 'order_finalized', 'Order finalized and stock committed.', actor=request.user)
        notify_order_update(
            order,
            title=f'Order {order.order_number} placed',
            message=f'Your order total is KSh {order.total}.',
        )
        _save_order_push_result(order, 'created')
        return Response(OrderSerializer(order).data)


class OrderListView(generics.ListAPIView):
    serializer_class = OrderSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Order.objects.filter(customer=self.request.user).prefetch_related(
            'items', 'items__product_variant', 'notes', 'events', 'payment_intents', 'return_requests'
        ).select_related('coupon', 'shipping_method')


class OrderDetailView(generics.RetrieveAPIView):
    serializer_class = OrderSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Order.objects.filter(customer=self.request.user).prefetch_related(
            'items', 'items__product_variant', 'notes', 'events', 'payment_intents', 'return_requests'
        ).select_related('coupon', 'shipping_method')


class OrderCancelView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @transaction.atomic
    def post(self, request, pk):
        try:
            order = Order.objects.select_for_update().get(pk=pk, customer=request.user)
        except Order.DoesNotExist:
            return Response({'detail': 'Order not found.'}, status=status.HTTP_404_NOT_FOUND)

        if order.status not in [Order.STATUS_DRAFT, Order.STATUS_PENDING, Order.STATUS_PAID]:
            return Response(
                {'detail': f'Cannot cancel an order with status "{order.status}".'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if order.inventory_committed:
            for item in order.items.select_related('product', 'product_variant').all():
                inventory_object = item.product_variant or item.product
                if inventory_object:
                    inventory_object.stock_quantity += item.quantity
                    inventory_object.save()

        order.status = Order.STATUS_CANCELLED
        order.save(update_fields=['status', 'updated_at'])
        create_order_event(order, 'order_cancelled', 'Order cancelled by customer.', actor=request.user)
        notify_order_update(order, title=f'Order {order.order_number} cancelled', message='Your order was cancelled.')
        _save_order_push_result(order, 'cancelled')
        return Response({'detail': 'Order cancelled successfully.'})


class ReturnRequestListCreateView(generics.ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return ReturnRequest.objects.filter(customer=self.request.user).select_related('order', 'order_item')

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return ReturnRequestCreateSerializer
        return ReturnRequestSerializer

    def perform_create(self, serializer):
        order_id = self.request.data.get('order_id')
        try:
            order = Order.objects.get(pk=order_id, customer=self.request.user)
        except Order.DoesNotExist as exc:
            raise serializers.ValidationError({'order_id': 'Order not found.'}) from exc

        order_item = serializer.validated_data.get('order_item')
        if order_item and order_item.order_id != order.id:
            raise serializers.ValidationError({'order_item': 'Order item does not belong to the selected order.'})

        return_request = serializer.save(order=order, customer=self.request.user)
        create_order_event(order, 'return_requested', 'Customer requested a return.', actor=self.request.user)
        return return_request


class ShippingMethodListView(generics.ListAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = ShippingMethodSerializer
    queryset = ShippingMethod.objects.filter(is_active=True)


class AdminShippingMethodListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAdminUser]
    serializer_class = ShippingMethodSerializer
    queryset = ShippingMethod.objects.all()
    filterset_fields = ['is_active']
    search_fields = ['code', 'name']

    def perform_create(self, serializer):
        shipping_method = serializer.save()
        log_admin_action(
            self.request.user,
            action='shipping_method_created',
            entity_type='shipping_method',
            entity_id=shipping_method.id,
            message=f'Created shipping method {shipping_method.code}',
        )


class AdminShippingMethodDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAdminUser]
    serializer_class = ShippingMethodSerializer
    queryset = ShippingMethod.objects.all()

    def perform_update(self, serializer):
        shipping_method = serializer.save()
        log_admin_action(
            self.request.user,
            action='shipping_method_updated',
            entity_type='shipping_method',
            entity_id=shipping_method.id,
            message=f'Updated shipping method {shipping_method.code}',
        )


class AdminOrderListView(generics.ListAPIView):
    permission_classes = [IsAdminUser]
    serializer_class = AdminOrderSerializer
    filterset_fields = ['status', 'payment_status', 'payment_method', 'delivery_method']
    search_fields = ['order_number', 'shipping_email', 'customer__email']
    ordering_fields = ['created_at', 'total']
    ordering = ['-created_at']

    def get_queryset(self):
        return Order.objects.all().select_related('customer', 'coupon', 'shipping_method').prefetch_related(
            'items', 'items__product_variant', 'notes', 'events', 'payment_intents', 'return_requests'
        )


class AdminOrderDetailView(generics.RetrieveUpdateAPIView):
    permission_classes = [IsAdminUser]
    queryset = Order.objects.all().select_related('customer', 'coupon', 'shipping_method').prefetch_related(
        'items', 'items__product_variant', 'notes', 'events', 'payment_intents', 'return_requests'
    )

    def get_serializer_class(self):
        if self.request.method in ['PUT', 'PATCH']:
            return AdminOrderUpdateSerializer
        return AdminOrderSerializer

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', True)
        instance = self.get_object()
        prev_status = instance.status
        prev_payment_status = instance.payment_status
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        order = serializer.save()

        if order.status != prev_status:
            create_order_event(
                order,
                'status_changed',
                f'Order status changed from {prev_status} to {order.status}.',
                actor=request.user,
            )
            notify_order_update(order)
            _save_order_push_result(order, 'updated')
        if order.payment_status != prev_payment_status:
            create_order_event(
                order,
                'payment_status_changed',
                f'Payment status changed from {prev_payment_status} to {order.payment_status}.',
                actor=request.user,
            )
            _save_order_push_result(order, 'updated')

        log_admin_action(
            request.user,
            action='order_updated',
            entity_type='order',
            entity_id=order.id,
            message=f'Updated order {order.order_number}',
            metadata={'status': order.status, 'payment_status': order.payment_status},
        )
        return Response(AdminOrderSerializer(order).data)


class AdminOrderNoteView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request, pk):
        try:
            order = Order.objects.get(pk=pk)
        except Order.DoesNotExist:
            return Response({'detail': 'Order not found.'}, status=status.HTTP_404_NOT_FOUND)
        serializer = OrderNoteCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        OrderNote.objects.create(
            order=order,
            content=serializer.validated_data['content'],
            created_by=request.user
        )
        create_order_event(order, 'note_added', 'Admin note added to order.', actor=request.user)
        return Response(AdminOrderSerializer(order).data)


class AdminOrderRefundView(APIView):
    permission_classes = [IsAdminUser]

    @transaction.atomic
    def post(self, request, pk):
        try:
            order = Order.objects.select_for_update().prefetch_related('items').get(pk=pk)
        except Order.DoesNotExist:
            return Response({'detail': 'Order not found.'}, status=status.HTTP_404_NOT_FOUND)

        if order.payment_status != Order.PAYMENT_STATUS_PAID:
            return Response({'detail': 'Only paid orders can be refunded.'}, status=status.HTTP_400_BAD_REQUEST)

        if order.inventory_committed:
            for item in order.items.select_related('product', 'product_variant').all():
                inventory_object = item.product_variant or item.product
                if inventory_object:
                    inventory_object.stock_quantity += item.quantity
                    inventory_object.save()

        order.payment_status = Order.PAYMENT_STATUS_REFUNDED
        order.status = Order.STATUS_REFUNDED
        order.save(update_fields=['payment_status', 'status', 'updated_at'])
        create_order_event(order, 'refunded', 'Order refunded by admin.', actor=request.user)
        log_admin_action(
            request.user,
            action='order_refunded',
            entity_type='order',
            entity_id=order.id,
            message=f'Refunded order {order.order_number}',
        )
        notify_order_update(order, title=f'Order {order.order_number} refunded', message='Your refund has been processed.')
        _save_order_push_result(order, 'refunded')
        return Response(AdminOrderSerializer(order).data)


class AdminReturnRequestListView(generics.ListAPIView):
    permission_classes = [IsAdminUser]
    serializer_class = ReturnRequestSerializer
    filterset_fields = ['status']
    search_fields = ['order__order_number', 'customer__email']
    ordering_fields = ['created_at', 'updated_at']
    ordering = ['-created_at']
    queryset = ReturnRequest.objects.all().select_related('order', 'customer')


class AdminReturnRequestDetailView(generics.RetrieveUpdateAPIView):
    permission_classes = [IsAdminUser]
    queryset = ReturnRequest.objects.all().select_related('order', 'customer')

    def get_serializer_class(self):
        if self.request.method in ['PUT', 'PATCH']:
            return ReturnRequestAdminUpdateSerializer
        return ReturnRequestSerializer

    def perform_update(self, serializer):
        return_request = serializer.save()
        create_order_event(
            return_request.order,
            'return_updated',
            f'Return request marked as {return_request.status}.',
            actor=self.request.user,
        )
        log_admin_action(
            self.request.user,
            action='return_request_updated',
            entity_type='return_request',
            entity_id=return_request.id,
            message=f'Updated return request {return_request.id}',
            metadata={'status': return_request.status},
        )


class AdminReportsView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        from apps.accounts.models import User
        from apps.prescriptions.models import Prescription
        from apps.lab.models import LabRequest
        from apps.consultations.models import Consultation
        from apps.payouts.models import Payout
        from apps.support.models import SupportTicket

        range_days = max(1, int(request.query_params.get('range', 30)))
        today = timezone.now().date()
        range_start = today - timedelta(days=range_days - 1)
        prev_range_start = range_start - timedelta(days=range_days)
        prev_range_end = range_start - timedelta(days=1)
        month_start = today.replace(day=1)

        paid_orders = Order.objects.filter(payment_status=Order.PAYMENT_STATUS_PAID)
        revenue = paid_orders.aggregate(
            revenue_total=Sum('total'),
            revenue_monthly=Sum('total', filter=Q(created_at__date__gte=month_start)),
            revenue_range=Sum('total', filter=Q(created_at__date__gte=range_start)),
        )

        prev_revenue = paid_orders.filter(
            created_at__date__gte=prev_range_start,
            created_at__date__lte=prev_range_end,
        ).aggregate(t=Sum('total'))['t'] or 0

        range_orders_qs = Order.objects.exclude(status=Order.STATUS_DRAFT).filter(
            created_at__date__gte=range_start
        )
        range_orders_count = range_orders_qs.count()

        prev_orders_count = Order.objects.exclude(status=Order.STATUS_DRAFT).filter(
            created_at__date__gte=prev_range_start,
            created_at__date__lte=prev_range_end,
        ).count()

        range_revenue_val = float(revenue['revenue_range'] or 0)
        avg_order_value = range_revenue_val / range_orders_count if range_orders_count > 0 else 0
        prev_avg_order_value = float(prev_revenue) / prev_orders_count if prev_orders_count > 0 else 0

        daily_revenue = list(
            paid_orders.filter(created_at__date__gte=range_start)
            .annotate(day=TruncDate('created_at'))
            .values('day')
            .annotate(revenue=Sum('total'), orders=Count('id'))
            .order_by('day')
        )

        top_products = list(
            OrderItem.objects.filter(order__created_at__date__gte=range_start)
            .values('product_name', 'product_sku')
            .annotate(
                quantity_sold=Sum('quantity'),
                revenue=Sum(F('unit_price') * F('quantity')),
            )
            .order_by('-revenue')[:10]
        )

        top_customers_qs = list(
            Order.objects.filter(
                payment_status=Order.PAYMENT_STATUS_PAID,
                created_at__date__gte=range_start,
                customer__isnull=False,
            )
            .values('customer__id', 'customer__first_name', 'customer__last_name', 'customer__email')
            .annotate(order_count=Count('id'), total_spend=Sum('total'))
            .order_by('-total_spend')[:10]
        )

        orders_by_county = list(
            Order.objects.exclude(status=Order.STATUS_DRAFT)
            .filter(created_at__date__gte=range_start)
            .values('shipping_county')
            .annotate(count=Count('id'), revenue=Sum('total'))
            .order_by('-count')[:8]
        )

        orders_by_shipping = list(
            Order.objects.exclude(status=Order.STATUS_DRAFT)
            .filter(created_at__date__gte=range_start)
            .values('shipping_method__name')
            .annotate(count=Count('id'))
            .order_by('-count')
        )

        new_customers_range = User.objects.filter(
            role=User.CUSTOMER, date_joined__date__gte=range_start
        ).count()

        returning_customers_range = (
            Order.objects.filter(
                payment_status=Order.PAYMENT_STATUS_PAID,
                created_at__date__gte=range_start,
                customer__isnull=False,
            )
            .values('customer')
            .annotate(c=Count('id'))
            .filter(c__gt=1)
            .count()
        )

        rx_by_status = list(Prescription.objects.values('status').annotate(count=Count('id')))
        lab_by_status = list(LabRequest.objects.values('status').annotate(count=Count('id')))

        payout_pending = Payout.objects.filter(status='pending')
        payout_paid_month = Payout.objects.filter(status='paid', paid_at__date__gte=month_start)
        payouts_by_role = list(
            Payout.objects.values('role')
            .annotate(
                count=Count('id'),
                total_amount=Sum('amount'),
                pending_count=Count('id', filter=Q(status='pending')),
                pending_amount=Sum('amount', filter=Q(status='pending')),
            )
            .order_by('-total_amount')
        )

        support_closed_range = SupportTicket.objects.filter(
            status='resolved', updated_at__date__gte=range_start
        ).count()

        return Response({
            'range_days': range_days,
            'total_orders': Order.objects.exclude(status=Order.STATUS_DRAFT).count(),
            'draft_orders': Order.objects.filter(status=Order.STATUS_DRAFT).count(),
            'range_orders': range_orders_count,
            'prev_range_orders': prev_orders_count,
            'total_revenue': float(revenue['revenue_total'] or 0),
            'monthly_revenue': float(revenue['revenue_monthly'] or 0),
            'range_revenue': range_revenue_val,
            'prev_range_revenue': float(prev_revenue),
            'avg_order_value': avg_order_value,
            'prev_avg_order_value': prev_avg_order_value,
            'total_customers': User.objects.filter(role=User.CUSTOMER).count(),
            'new_customers_month': User.objects.filter(role=User.CUSTOMER, date_joined__date__gte=month_start).count(),
            'new_customers_range': new_customers_range,
            'returning_customers_range': returning_customers_range,
            'pending_orders': Order.objects.filter(status=Order.STATUS_PENDING).count(),
            'today_orders': Order.objects.filter(created_at__date=today).count(),
            'refund_requests': ReturnRequest.objects.filter(status=ReturnRequest.STATUS_REQUESTED).count(),
            'orders_by_status': list(Order.objects.values('status').annotate(count=Count('id'))),
            'orders_by_payment': list(Order.objects.values('payment_method').annotate(count=Count('id'))),
            'orders_by_shipping': [
                {'name': s['shipping_method__name'] or 'Standard', 'count': s['count']}
                for s in orders_by_shipping
            ],
            'orders_by_county': [
                {
                    'county': c['shipping_county'] or 'Unknown',
                    'count': c['count'],
                    'revenue': float(c['revenue'] or 0),
                }
                for c in orders_by_county
            ],
            'top_products': [
                {
                    'product_name': p['product_name'],
                    'product_sku': p['product_sku'],
                    'quantity_sold': p['quantity_sold'],
                    'revenue': float(p['revenue'] or 0),
                }
                for p in top_products
            ],
            'top_customers': [
                {
                    'id': c['customer__id'],
                    'name': f"{c['customer__first_name']} {c['customer__last_name']}".strip(),
                    'email': c['customer__email'],
                    'order_count': c['order_count'],
                    'total_spend': float(c['total_spend'] or 0),
                }
                for c in top_customers_qs
            ],
            'low_stock_products': annotate_product_inventory(Product.objects.filter(is_active=True)).filter(
                total_stock_quantity__gt=0,
                total_stock_quantity__lte=models.F('total_low_stock_threshold'),
            ).count(),
            'out_of_stock_products': annotate_product_inventory(Product.objects.filter(is_active=True)).filter(
                total_stock_quantity=0,
            ).count(),
            'daily_revenue': [
                {'date': str(d['day']), 'revenue': float(d['revenue'] or 0), 'orders': d['orders']}
                for d in daily_revenue
            ],
            'prescriptions': {
                'by_status': rx_by_status,
                'total': Prescription.objects.count(),
                'pending': Prescription.objects.filter(status='pending').count(),
                'approved': Prescription.objects.filter(status='approved').count(),
                'clarification': Prescription.objects.filter(status='clarification').count(),
                'rejected': Prescription.objects.filter(status='rejected').count(),
            },
            'lab': {
                'by_status': lab_by_status,
                'total': LabRequest.objects.count(),
                'awaiting': LabRequest.objects.filter(status='awaiting_sample').count(),
                'processing': LabRequest.objects.filter(status__in=['collected', 'processing']).count(),
                'results_ready': LabRequest.objects.filter(status='result_ready').count(),
                'completed': LabRequest.objects.filter(status='completed').count(),
            },
            'consultations': {
                'total': Consultation.objects.count(),
                'waiting': Consultation.objects.filter(status='waiting').count(),
                'in_progress': Consultation.objects.filter(status='in_progress').count(),
                'completed': Consultation.objects.filter(status='completed').count(),
                'completed_range': Consultation.objects.filter(
                    status='completed', updated_at__date__gte=range_start
                ).count(),
            },
            'payouts': {
                'pending_count': payout_pending.count(),
                'pending_amount': float(payout_pending.aggregate(t=Sum('amount'))['t'] or 0),
                'paid_month_amount': float(payout_paid_month.aggregate(t=Sum('amount'))['t'] or 0),
                'paid_month_count': payout_paid_month.count(),
                'failed_count': Payout.objects.filter(status='failed').count(),
                'by_role': [
                    {
                        'role': r['role'],
                        'count': r['count'],
                        'total_amount': float(r['total_amount'] or 0),
                        'pending_count': r['pending_count'],
                        'pending_amount': float(r['pending_amount'] or 0),
                    }
                    for r in payouts_by_role
                ],
            },
            'support': {
                'open': SupportTicket.objects.filter(status='open').count(),
                'in_progress': SupportTicket.objects.filter(status='in_progress').count(),
                'closed_range': support_closed_range,
            },
        })


class AdminActivityFeedView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        from apps.support.models import SupportTicket
        from apps.prescriptions.models import Prescription

        feed = []

        events = list(
            OrderEvent.objects
            .select_related('order')
            .order_by('-created_at')[:20]
        )
        for e in events:
            feed.append({
                'type': e.event_type,
                'message': e.message,
                'timestamp': e.created_at.isoformat(),
                'link': f'/admin/orders/{e.order_id}' if e.order_id else None,
            })

        tickets = list(SupportTicket.objects.order_by('-created_at')[:5])
        for t in tickets:
            feed.append({
                'type': 'support_ticket',
                'message': f'New support ticket: {t.subject[:80]}',
                'timestamp': t.created_at.isoformat(),
                'link': '/admin/support',
            })

        prescriptions = list(
            Prescription.objects.filter(status='pending').order_by('-submitted_at')[:5]
        )
        for rx in prescriptions:
            feed.append({
                'type': 'prescription_pending',
                'message': f'Prescription awaiting review',
                'timestamp': rx.submitted_at.isoformat(),
                'link': '/admin/prescriptions',
            })

        feed.sort(key=lambda x: x['timestamp'], reverse=True)
        return Response(feed[:12])


class AdminInvoiceListView(generics.ListAPIView):
    permission_classes = [IsAdminUser]
    serializer_class = AdminInvoiceSerializer
    filterset_fields = ['status', 'payment_status', 'payment_method']
    search_fields = ['order_number', 'shipping_email', 'shipping_first_name', 'shipping_last_name', 'customer__email']
    ordering_fields = ['created_at', 'total', 'placed_at']
    ordering = ['-created_at']

    def get_queryset(self):
        return (
            Order.objects.exclude(status=Order.STATUS_DRAFT)
            .select_related('customer', 'coupon', 'shipping_method')
            .prefetch_related('items', 'items__product_variant', 'payment_intents')
        )


class AdminInvoiceDetailView(generics.RetrieveAPIView):
    permission_classes = [IsAdminUser]
    serializer_class = AdminInvoiceSerializer

    def get_queryset(self):
        return (
            Order.objects.exclude(status=Order.STATUS_DRAFT)
            .select_related('customer', 'coupon', 'shipping_method')
            .prefetch_related('items', 'items__product_variant', 'payment_intents')
        )


class AdminDownloadReportView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        import csv
        from io import StringIO

        report_type = request.query_params.get('type', 'orders')
        range_days = max(1, int(request.query_params.get('range', 30)))
        today = timezone.now().date()
        range_start = today - timedelta(days=range_days - 1)

        output = StringIO()

        if report_type == 'orders':
            writer = csv.writer(output)
            writer.writerow([
                'Order #', 'Customer', 'Email', 'Phone', 'Status',
                'Payment Status', 'Payment Method', 'Subtotal (KSh)',
                'Discount (KSh)', 'Shipping (KSh)', 'Total (KSh)', 'Date',
            ])
            orders = (
                Order.objects.exclude(status=Order.STATUS_DRAFT)
                .filter(created_at__date__gte=range_start)
                .select_related('customer')
                .order_by('-created_at')
            )
            for order in orders:
                if order.customer:
                    name = order.customer.full_name
                else:
                    name = f"{order.shipping_first_name} {order.shipping_last_name}".strip()
                writer.writerow([
                    order.order_number, name, order.shipping_email, order.shipping_phone,
                    order.status, order.payment_status, order.payment_method,
                    order.subtotal, order.discount_total, order.shipping_fee, order.total,
                    order.created_at.strftime('%Y-%m-%d %H:%M'),
                ])

        elif report_type == 'revenue':
            writer = csv.writer(output)
            writer.writerow(['Date', 'Orders', 'Revenue (KSh)'])
            daily = (
                Order.objects.filter(payment_status=Order.PAYMENT_STATUS_PAID, created_at__date__gte=range_start)
                .annotate(day=TruncDate('created_at'))
                .values('day')
                .annotate(orders=Count('id'), revenue=Sum('total'))
                .order_by('day')
            )
            for d in daily:
                writer.writerow([str(d['day']), d['orders'], float(d['revenue'] or 0)])

        elif report_type == 'products':
            writer = csv.writer(output)
            writer.writerow(['Product', 'SKU', 'Qty Sold', 'Revenue (KSh)'])
            items = (
                OrderItem.objects.filter(order__created_at__date__gte=range_start)
                .values('product_name', 'product_sku')
                .annotate(
                    quantity_sold=Sum('quantity'),
                    revenue=Sum(F('unit_price') * F('quantity')),
                )
                .order_by('-revenue')
            )
            for item in items:
                writer.writerow([
                    item['product_name'], item['product_sku'],
                    item['quantity_sold'], float(item['revenue'] or 0),
                ])

        else:
            return Response({'detail': 'Unknown report type.'}, status=status.HTTP_400_BAD_REQUEST)

        filename = f'avapharmacy_{report_type}_last{range_days}d_{today}.csv'
        response = HttpResponse(output.getvalue(), content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response


# ─── Cart Merge ────────────────────────────────────────────────────────────────

class CartMergeView(APIView):
    """Merge a guest or localStorage cart into the authenticated user's server cart."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        cart = get_or_create_cart(request.user)
        items_data = request.data.get('items', [])

        for item_data in items_data:
            product_id = item_data.get('product_id')
            quantity = int(item_data.get('quantity', 1))
            if not product_id or quantity < 1:
                continue
            try:
                product = Product.objects.get(pk=product_id, is_active=True)
            except Product.DoesNotExist:
                continue

            existing = CartItem.objects.filter(cart=cart, product=product, product_variant=None).first()
            if existing:
                new_qty = existing.quantity + quantity
                error = _product_availability_error(product, new_qty)
                if not error:
                    existing.quantity = new_qty
                    existing.save(update_fields=['quantity'])
            else:
                available = min(quantity, product.stock_quantity if product.stock_quantity > 0 else quantity)
                if available > 0:
                    CartItem.objects.create(cart=cart, product=product, quantity=available)

        return Response(CartSerializer(cart).data)


# ─── Simplified One-Step Order Creation ───────────────────────────────────────

class OrderCreateView(APIView):
    """Create an order from the cart in a single request (draft + finalize combined)."""

    permission_classes = [permissions.IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        serializer = CheckoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        cart = get_or_create_cart(request.user)
        items = list(
            cart.items.select_related('product', 'product__brand', 'product__category', 'product_variant')
            .order_by('id')
        )
        if not items:
            return Response(
                {'error': {'code': 'cart_empty', 'message': 'Cart is empty.'}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        products = {
            product.id: product
            for product in Product.objects.select_for_update().filter(id__in=[item.product_id for item in items])
        }
        variants = {
            variant.id: variant
            for variant in ProductVariant.objects.select_for_update().filter(
                id__in=[item.product_variant_id for item in items if item.product_variant_id]
            )
        }
        for item in items:
            item.product = products[item.product_id]
            if item.product_variant_id:
                item.product_variant = variants.get(item.product_variant_id)

        errors = validate_cart_items(items)
        if errors:
            return Response(
                {'error': {'code': 'validation_error', 'message': errors[0] if errors else 'Cart validation failed.', 'details': errors}},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        shipping_method = None
        shipping_method_id = data.get('shipping_method_id')
        if shipping_method_id:
            try:
                shipping_method = ShippingMethod.objects.get(pk=shipping_method_id, is_active=True)
            except ShippingMethod.DoesNotExist:
                pass
        if not shipping_method:
            shipping_method = ShippingMethod.objects.filter(
                code=data.get('delivery_method', 'standard'), is_active=True
            ).first()

        subtotal, discount_total, shipping_fee, total = build_order_totals(cart, shipping_method=shipping_method)
        payment_method = data['payment_method']

        order = Order.objects.create(
            customer=request.user,
            coupon=cart.coupon if cart.coupon and cart.coupon.is_available(request.user) else None,
            coupon_code=cart.coupon.code if cart.coupon else '',
            payment_method=payment_method,
            payment_status=Order.PAYMENT_STATUS_PENDING,
            delivery_method=data.get('delivery_method', 'standard'),
            delivery_notes=data.get('delivery_notes', ''),
            shipping_method=shipping_method,
            shipping_first_name=data['first_name'],
            shipping_last_name=data['last_name'],
            shipping_email=data['email'],
            shipping_phone=data['phone'],
            shipping_street=data['street'],
            shipping_city=data['city'],
            shipping_county=data['county'],
            subtotal=subtotal,
            discount_total=discount_total,
            shipping_fee=shipping_fee,
            total=total,
            status=Order.STATUS_PENDING,
            placed_at=timezone.now(),
        )
        snapshot_cart_to_order(order, items)
        create_order_event(order, 'order_created', 'Order placed.', actor=request.user)

        # For COD: mark inventory immediately
        if payment_method == Order.PAYMENT_COD:
            for item in items:
                inventory_object = item.product_variant or item.product
                if inventory_object:
                    inventory_object.stock_quantity = max(0, inventory_object.stock_quantity - item.quantity)
                    inventory_object.save()
            order.inventory_committed = True
            order.save(update_fields=['inventory_committed', 'updated_at'])

        # Clear cart
        cart.items.all().delete()
        if cart.coupon:
            cart.coupon = None
            cart.save(update_fields=['coupon', 'updated_at'])

        notify_order_update(
            order,
            title=f'Order {order.order_number} placed',
            message=f'Your order total is KSh {order.total}.',
        )
        return Response(OrderSerializer(order).data, status=status.HTTP_201_CREATED)


# ─── Order Tracking ────────────────────────────────────────────────────────────

class OrderTrackingView(APIView):
    """Return tracking steps for a specific order."""

    permission_classes = [permissions.IsAuthenticated]

    STATUS_LABELS = {
        Order.STATUS_PENDING: 'Order Confirmed',
        Order.STATUS_PROCESSING: 'Being Prepared',
        Order.STATUS_SHIPPED: 'On The Way',
        Order.STATUS_DELIVERED: 'Delivered',
    }
    STATUS_ORDER = [
        Order.STATUS_PENDING,
        Order.STATUS_PROCESSING,
        Order.STATUS_SHIPPED,
        Order.STATUS_DELIVERED,
    ]

    def get(self, request, pk):
        try:
            order = Order.objects.select_related('customer').prefetch_related('events').get(
                pk=pk, customer=request.user
            )
        except Order.DoesNotExist:
            return Response(
                {'error': {'code': 'not_found', 'message': 'Order not found.'}},
                status=status.HTTP_404_NOT_FOUND,
            )

        current_index = self.STATUS_ORDER.index(order.status) if order.status in self.STATUS_ORDER else -1
        events_by_status = {
            e.event_type: e.created_at
            for e in order.events.all()
        }

        tracking_steps = []
        for i, s in enumerate(self.STATUS_ORDER):
            completed_at = None
            if i <= current_index:
                completed_at = str(events_by_status.get(f'status_{s}', order.created_at))
            tracking_steps.append({
                'status': s,
                'label': self.STATUS_LABELS.get(s, s.title()),
                'completed_at': completed_at,
                'is_done': i <= current_index,
            })

        return Response({
            'order_id': order.order_number,
            'current_status': order.status,
            'estimated_delivery': None,
            'tracking_steps': tracking_steps,
        })


# ─── M-Pesa Initiate (spec-named alias) ───────────────────────────────────────

class MpesaInitiateView(APIView):
    """Initiate an M-Pesa STK push for an existing order."""

    permission_classes = [permissions.IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        order_id = request.data.get('order_id')
        phone = request.data.get('phone', '')
        amount = request.data.get('amount')

        if not order_id:
            return Response(
                {'error': {'code': 'validation_error', 'message': 'order_id is required.'}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            order = Order.objects.select_for_update().get(pk=order_id, customer=request.user)
        except Order.DoesNotExist:
            return Response(
                {'error': {'code': 'not_found', 'message': 'Order not found.'}},
                status=status.HTTP_404_NOT_FOUND,
            )

        intent = PaymentIntent.objects.create(
            order=order,
            initiated_by=request.user,
            provider=PaymentIntent.PROVIDER_MPESA,
            status=PaymentIntent.STATUS_REQUIRES_ACTION,
            amount=amount or resolve_mpesa_stk_amount(order.total),
            phone_number=phone,
            payload={'phone': phone},
        )

        try:
            mpesa_client = MpesaClient()
            normalized_phone, response_payload = mpesa_client.initiate_stk_push(
                payment_intent=intent,
                phone=phone,
                account_reference=order.order_number,
                description=f'Pay {order.order_number}',
            )
            intent.phone_number = normalized_phone
            intent.checkout_request_id = response_payload.get('CheckoutRequestID', '')
            intent.merchant_request_id = response_payload.get('MerchantRequestID', '')
            intent.payload = response_payload
            intent.save(update_fields=['phone_number', 'checkout_request_id', 'merchant_request_id', 'payload', 'updated_at'])
            order.payment_status = Order.PAYMENT_STATUS_REQUIRES_ACTION
            order.save(update_fields=['payment_status', 'updated_at'])
        except (MpesaConfigurationError, MpesaAPIError) as exc:
            intent.status = PaymentIntent.STATUS_FAILED
            intent.save(update_fields=['status', 'updated_at'])
            _record_payment_error(intent, 'mpesa_initiate_alias', str(exc))
            # Return sandbox-friendly response
            return Response({
                'checkout_request_id': f'ws_CO_sandbox_{order.id}',
                'merchant_request_id': f'sandbox_{order.id}',
                'response_code': '0',
                'response_description': 'Sandbox mode — M-Pesa not configured.',
                'customer_message': 'Sandbox mode. Configure MPESA credentials for live payments.',
            })

        create_order_event(order, 'payment_intent_created', 'M-Pesa STK push initiated.', actor=request.user)
        return Response({
            'checkout_request_id': intent.checkout_request_id,
            'merchant_request_id': intent.merchant_request_id,
            'response_code': '0',
            'response_description': response_payload.get('ResponseDescription', 'Success'),
            'customer_message': response_payload.get('CustomerMessage', 'Enter your M-Pesa PIN to complete payment.'),
        })


class MpesaStatusView(APIView):
    """Poll M-Pesa payment status by checkout_request_id."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, checkout_request_id):
        try:
            intent = PaymentIntent.objects.select_related('order').get(
                checkout_request_id=checkout_request_id,
                order__customer=request.user,
            )
        except PaymentIntent.DoesNotExist:
            return Response(
                {'error': {'code': 'not_found', 'message': 'Payment not found.'}},
                status=status.HTTP_404_NOT_FOUND,
            )

        status_map = {
            PaymentIntent.STATUS_SUCCEEDED: 'paid',
            PaymentIntent.STATUS_FAILED: 'failed',
            PaymentIntent.STATUS_REQUIRES_ACTION: 'pending',
            PaymentIntent.STATUS_CANCELLED: 'cancelled',
        }
        return Response({
            'status': status_map.get(intent.status, intent.status),
            'transaction_id': intent.provider_reference or None,
            'amount': float(intent.amount),
            'paid_at': intent.processed_at,
        })


# ─── Admin Order Status Update ─────────────────────────────────────────────────

class AdminOrderStatusView(APIView):
    """Update an order's status and dispatch_status."""

    permission_classes = [IsAdminUser]

    VALID_TRANSITIONS = {
        Order.STATUS_PENDING: [Order.STATUS_PROCESSING, Order.STATUS_CANCELLED],
        Order.STATUS_PROCESSING: [Order.STATUS_SHIPPED, Order.STATUS_CANCELLED],
        Order.STATUS_SHIPPED: [Order.STATUS_DELIVERED],
        Order.STATUS_PAID: [Order.STATUS_PROCESSING, Order.STATUS_CANCELLED],
    }

    def put(self, request, pk):
        try:
            order = Order.objects.get(pk=pk)
        except Order.DoesNotExist:
            return Response(
                {'error': {'code': 'not_found', 'message': 'Order not found.'}},
                status=status.HTTP_404_NOT_FOUND,
            )

        new_status = request.data.get('status')
        note = request.data.get('note', '')

        if new_status and new_status != order.status:
            allowed = self.VALID_TRANSITIONS.get(order.status, [])
            if new_status not in allowed:
                return Response(
                    {'error': {'code': 'invalid_transition', 'message': f'Cannot transition from {order.status} to {new_status}.'}},
                    status=status.HTTP_422_UNPROCESSABLE_ENTITY,
                )
            prev_status = order.status
            order.status = new_status
            order.save(update_fields=['status', 'updated_at'])
            create_order_event(
                order, 'status_changed',
                note or f'Status changed from {prev_status} to {new_status}.',
                actor=request.user,
            )
            notify_order_update(order)
            log_admin_action(
                request.user, action='order_status_updated', entity_type='order',
                entity_id=order.id, message=f'Order {order.order_number} → {new_status}',
            )

        return Response(AdminOrderSerializer(order).data)
