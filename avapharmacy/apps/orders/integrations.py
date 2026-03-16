import json
import time
from datetime import timedelta
from urllib import error, request

from django.conf import settings
from django.utils import timezone

from .models import OutboundOrderPush


def build_order_push_payload(order, action):
    return {
        'action': action,
        'order': {
            'id': order.id,
            'order_number': order.order_number,
            'status': order.status,
            'payment_method': order.payment_method,
            'payment_status': order.payment_status,
            'payment_reference': order.payment_reference,
            'total': str(order.total),
            'subtotal': str(order.subtotal),
            'discount_total': str(order.discount_total),
            'shipping_fee': str(order.shipping_fee),
            'shipping': {
                'first_name': order.shipping_first_name,
                'last_name': order.shipping_last_name,
                'email': order.shipping_email,
                'phone': order.shipping_phone,
                'street': order.shipping_street,
                'city': order.shipping_city,
                'county': order.shipping_county,
            },
            'items': [
                {
                    'id': item.id,
                    'product_id': item.product_id,
                    'product_sku': item.product_sku,
                    'product_name': item.product_name,
                    'variant_id': item.product_variant_id,
                    'variant_sku': item.variant_sku,
                    'variant_name': item.variant_name,
                    'quantity': item.quantity,
                    'unit_price': str(item.unit_price),
                    'discount_total': str(item.discount_total),
                    'prescription_id': item.prescription_id,
                }
                for item in order.items.all()
            ],
        },
    }


def _should_retry(status_code):
    if status_code is None:
        return True
    return status_code in {408, 429} or status_code >= 500


def _compute_backoff_seconds(attempt_number):
    base = max(0.0, float(settings.POS_ORDER_PUSH_BACKOFF_SECONDS))
    max_backoff = max(base, float(settings.POS_ORDER_PUSH_MAX_BACKOFF_SECONDS))
    return min(base * (2 ** max(0, attempt_number - 1)), max_backoff)


def _upsert_queue_record(order, action, payload, result, queue_record=None):
    total_max_attempts = max(1, int(settings.POS_ORDER_PUSH_QUEUE_MAX_ATTEMPTS))
    record = queue_record
    if record is None:
        record = (
            OutboundOrderPush.objects
            .filter(order=order, action=action, status__in=[OutboundOrderPush.STATUS_PENDING, OutboundOrderPush.STATUS_RETRYING])
            .order_by('-created_at')
            .first()
        )

    if record is None:
        record = OutboundOrderPush(order=order, action=action)

    record.payload = payload
    record.attempt_count = min(total_max_attempts, result.get('attempt_count', 0))
    record.max_attempts = total_max_attempts
    record.last_attempt_at = timezone.now()
    record.response_status_code = result.get('status_code')
    record.response_body = result.get('body', '')[:10000]
    record.last_error = result.get('body', '')[:5000] if not result.get('ok') else ''

    if result.get('ok'):
        record.status = OutboundOrderPush.STATUS_SUCCEEDED
        record.processed_at = timezone.now()
        record.next_attempt_at = timezone.now()
    elif record.attempt_count >= record.max_attempts:
        record.status = OutboundOrderPush.STATUS_EXHAUSTED
        record.processed_at = timezone.now()
        record.next_attempt_at = timezone.now()
    else:
        record.status = (
            OutboundOrderPush.STATUS_RETRYING
            if record.attempt_count > 0
            else OutboundOrderPush.STATUS_PENDING
        )
        record.processed_at = None
        record.next_attempt_at = timezone.now() + timedelta(
            seconds=_compute_backoff_seconds(max(1, record.attempt_count))
        )

    record.save()
    return record


def _push_order_once(endpoint, payload, headers):
    req = request.Request(
        endpoint,
        data=json.dumps(payload).encode('utf-8'),
        headers=headers,
        method='POST',
    )
    try:
        with request.urlopen(req, timeout=settings.POS_ORDER_PUSH_TIMEOUT_SECONDS) as response:
            body = response.read().decode('utf-8') or '{}'
            status_code = getattr(response, 'status', 200)
        return {'ok': True, 'status_code': status_code, 'body': body}
    except error.HTTPError as exc:
        body = exc.read().decode('utf-8')
        return {'ok': False, 'status_code': exc.code, 'body': body}
    except error.URLError as exc:
        return {'ok': False, 'status_code': None, 'body': str(exc)}


def push_order_to_pos(order, action, *, queue_record=None, persist_failure=True, max_attempts=None):
    endpoint = settings.POS_ORDER_PUSH_URL
    if not endpoint:
        return None

    payload = build_order_push_payload(order, action)
    headers = {'Content-Type': 'application/json'}
    if settings.POS_ORDER_PUSH_TOKEN:
        headers['Authorization'] = f'Bearer {settings.POS_ORDER_PUSH_TOKEN}'
    max_attempts = max(1, int(max_attempts or settings.POS_ORDER_PUSH_MAX_ATTEMPTS))
    attempts = []
    last_result = None

    for attempt_number in range(1, max_attempts + 1):
        result = _push_order_once(endpoint, payload, headers)
        result['attempt'] = attempt_number
        attempts.append(result.copy())
        last_result = result

        if result['ok'] or not _should_retry(result['status_code']) or attempt_number >= max_attempts:
            break

        backoff_seconds = _compute_backoff_seconds(attempt_number)
        time.sleep(backoff_seconds)

    final_result = {
        **(last_result or {'ok': False, 'status_code': None, 'body': 'No push attempt was made.'}),
        'attempt_count': len(attempts),
        'attempts': attempts,
    }
    if queue_record is not None or (persist_failure and not final_result['ok']):
        queue = _upsert_queue_record(order, action, payload, final_result, queue_record=queue_record)
        final_result['queue_id'] = queue.id
        final_result['queue_status'] = queue.status
    return final_result
