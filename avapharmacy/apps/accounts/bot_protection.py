"""Bot and abuse risk controls for public account and checkout flows."""

import json
import urllib.parse
import urllib.request
from datetime import timedelta

from django.conf import settings
from django.utils import timezone
from rest_framework.exceptions import APIException, ValidationError

from .models import BotRiskEvent, User


class BotProtectionError(APIException):
    status_code = 403
    default_code = 'bot_protection_failed'
    default_detail = 'Request could not be processed.'


def get_client_ip(request):
    forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR', '')
    if forwarded_for:
        return forwarded_for.split(',', 1)[0].strip() or None
    return request.META.get('REMOTE_ADDR') or None


def get_device_id(request):
    data = getattr(request, 'data', {}) or {}
    return (data.get('device_id') or request.META.get('HTTP_X_AVA_DEVICE_ID') or '').strip()[:120]


def get_honeypot_value(request):
    data = getattr(request, 'data', {}) or {}
    for key in ('website', 'company_website', 'homepage'):
        value = data.get(key)
        if value:
            return str(value).strip()
    return ''


def get_challenge_token(request):
    data = getattr(request, 'data', {}) or {}
    for key in ('bot_challenge_token', 'turnstile_token', 'cf_turnstile_response'):
        value = data.get(key)
        if value:
            return str(value).strip()
    return ''


def log_bot_event(
    request,
    event_type,
    *,
    user=None,
    email='',
    phone='',
    risk_score=0,
    decision=BotRiskEvent.DECISION_ALLOW,
    reasons=None,
    metadata=None,
):
    actor = user if getattr(user, 'is_authenticated', False) else None
    if actor is None and getattr(request, 'user', None) and getattr(request.user, 'is_authenticated', False):
        actor = request.user
    return BotRiskEvent.objects.create(
        user=actor,
        email=(email or getattr(actor, 'email', '') or '').strip().lower(),
        phone=(phone or getattr(actor, 'phone', '') or '').strip(),
        ip_address=get_client_ip(request),
        device_id=get_device_id(request),
        user_agent=(request.META.get('HTTP_USER_AGENT') or '')[:255],
        event_type=event_type,
        risk_score=max(0, min(int(risk_score or 0), 100)),
        decision=decision,
        reasons=list(reasons or []),
        metadata=metadata or {},
    )


def verify_turnstile_token(request, token):
    secret = getattr(settings, 'TURNSTILE_SECRET_KEY', '')
    required = bool(getattr(settings, 'BOT_CHALLENGE_REQUIRED', False))
    if not secret:
        return (not required), 'challenge_not_configured'
    if not token:
        return False, 'missing_challenge_token'

    payload = urllib.parse.urlencode({
        'secret': secret,
        'response': token,
        'remoteip': get_client_ip(request) or '',
    }).encode()
    verify_request = urllib.request.Request(
        'https://challenges.cloudflare.com/turnstile/v0/siteverify',
        data=payload,
        headers={'Content-Type': 'application/x-www-form-urlencoded'},
        method='POST',
    )
    try:
        with urllib.request.urlopen(verify_request, timeout=5) as response:
            result = json.loads(response.read().decode('utf-8'))
    except Exception:
        return False, 'challenge_verification_unavailable'
    return bool(result.get('success')), ','.join(result.get('error-codes') or []) or 'challenge_failed'


def enforce_public_bot_controls(
    request,
    event_type,
    *,
    user=None,
    email='',
    phone='',
    challenge_required=False,
):
    if get_honeypot_value(request):
        log_bot_event(
            request,
            BotRiskEvent.EVENT_HONEYPOT,
            user=user,
            email=email,
            phone=phone,
            risk_score=100,
            decision=BotRiskEvent.DECISION_BLOCK,
            reasons=['honeypot_filled'],
            metadata={'source_event': event_type},
        )
        raise ValidationError({'detail': 'Request could not be processed.'})

    require_challenge = challenge_required or bool(getattr(settings, 'BOT_CHALLENGE_REQUIRED', False))
    if require_challenge:
        ok, reason = verify_turnstile_token(request, get_challenge_token(request))
        if not ok:
            log_bot_event(
                request,
                BotRiskEvent.EVENT_CHALLENGE_FAILED,
                user=user,
                email=email,
                phone=phone,
                risk_score=70,
                decision=BotRiskEvent.DECISION_BLOCK,
                reasons=[reason],
                metadata={'source_event': event_type},
            )
            raise BotProtectionError({
                'code': 'BOT_CHALLENGE_REQUIRED',
                'message': 'Please complete the security check and try again.',
            })

    log_bot_event(
        request,
        event_type,
        user=user,
        email=email,
        phone=phone,
        decision=BotRiskEvent.DECISION_ALLOW,
        reasons=['public_flow_allowed'],
    )


def _recent_events(**filters):
    since = filters.pop('since')
    return BotRiskEvent.objects.filter(created_at__gte=since, **filters).count()


def _is_disposable_email(email):
    domain = (email or '').split('@')[-1].lower()
    return bool(domain and domain in getattr(settings, 'DISPOSABLE_EMAIL_DOMAINS', set()))


def _cart_contains_medicine(items):
    terms = {'medicine', 'medicines', 'pain', 'cough', 'cold', 'flu', 'allergy', 'antacid', 'antibiotic'}
    for item in items:
        variant = getattr(item, 'variant', None)
        if not variant:
            continue
        fields = [
            getattr(getattr(variant, 'category', None), 'name', ''),
            getattr(getattr(variant, 'subcategory', None), 'name', ''),
            getattr(getattr(variant, 'product', None), 'name', ''),
            getattr(variant, 'name', ''),
            getattr(variant, 'dosage_instructions', ''),
            getattr(variant, 'warnings', ''),
        ]
        haystack = ' '.join(str(value or '').lower() for value in fields)
        if getattr(variant, 'requires_prescription', False) or any(term in haystack for term in terms):
            return True
    return False


def _has_prescription_items(items):
    return any(
        getattr(getattr(item, 'variant', None), 'requires_prescription', False)
        or bool(getattr(item, 'prescription_reference', ''))
        or bool(getattr(item, 'prescription_id', None))
        for item in items
    )


def _payment_failure_count(user):
    try:
        from apps.orders.models import PaymentIntent
    except Exception:
        return 0
    return PaymentIntent.objects.filter(
        order__customer=user,
        status=PaymentIntent.STATUS_FAILED,
        created_at__gte=timezone.now() - timedelta(hours=24),
    ).count()


def score_checkout_risk(request, items, checkout_phone=''):
    user = request.user
    score = 0
    reasons = []
    now = timezone.now()
    account_age = now - user.date_joined
    new_account_window = timedelta(hours=int(getattr(settings, 'NEW_ACCOUNT_RISK_WINDOW_HOURS', 24)))

    if account_age < new_account_window:
        score += 30
        reasons.append('new_account')
    if user.status != User.STATUS_ACTIVE or not user.is_active:
        score += 30
        reasons.append('account_not_active')
    if not (user.phone or '').strip():
        score += 15
        reasons.append('missing_phone')
    if checkout_phone and user.phone and checkout_phone.strip() != user.phone.strip():
        score += 20
        reasons.append('checkout_phone_mismatch')
    if _is_disposable_email(user.email):
        score += 25
        reasons.append('disposable_email_domain')
    if _cart_contains_medicine(items):
        score += 20
        reasons.append('medicine_cart')
    if _has_prescription_items(items):
        score += 30
        reasons.append('prescription_cart')

    total_quantity = sum(getattr(item, 'quantity', 0) or 0 for item in items)
    if total_quantity >= 8:
        score += 15
        reasons.append('high_quantity')

    recent_checkout_count = _recent_events(
        event_type=BotRiskEvent.EVENT_CHECKOUT,
        user=user,
        since=now - timedelta(minutes=30),
    )
    if recent_checkout_count >= 3:
        score += 20
        reasons.append('rapid_checkout_attempts')

    ip_address = get_client_ip(request)
    if ip_address:
        recent_registers = _recent_events(
            event_type=BotRiskEvent.EVENT_REGISTER,
            ip_address=ip_address,
            since=now - timedelta(hours=24),
        )
        if recent_registers >= 3:
            score += 30
            reasons.append('many_registrations_from_ip')

    payment_failures = _payment_failure_count(user)
    if payment_failures >= 2:
        score += 20
        reasons.append('recent_payment_failures')

    return min(score, 100), reasons


def enforce_checkout_risk(request, items, *, checkout_phone=''):
    if get_honeypot_value(request):
        log_bot_event(
            request,
            BotRiskEvent.EVENT_HONEYPOT,
            risk_score=100,
            decision=BotRiskEvent.DECISION_BLOCK,
            reasons=['honeypot_filled'],
            metadata={'source_event': BotRiskEvent.EVENT_CHECKOUT},
        )
        raise BotProtectionError({
            'code': 'CHECKOUT_BLOCKED',
            'message': 'Checkout could not be completed.',
        })

    score, reasons = score_checkout_risk(request, items, checkout_phone=checkout_phone)
    challenge_threshold = int(getattr(settings, 'CHECKOUT_RISK_CHALLENGE_THRESHOLD', 40))
    verify_threshold = int(getattr(settings, 'CHECKOUT_RISK_VERIFY_THRESHOLD', 60))
    review_threshold = int(getattr(settings, 'CHECKOUT_RISK_REVIEW_THRESHOLD', 80))
    hard_stop_reasons = {
        'account_not_active',
        'disposable_email_domain',
        'many_registrations_from_ip',
        'rapid_checkout_attempts',
        'recent_payment_failures',
    }
    has_hard_stop_reason = bool(hard_stop_reasons.intersection(reasons))

    if score >= review_threshold and has_hard_stop_reason:
        log_bot_event(
            request,
            BotRiskEvent.EVENT_CHECKOUT,
            risk_score=score,
            decision=BotRiskEvent.DECISION_REVIEW,
            reasons=reasons,
        )
        raise BotProtectionError({
            'code': 'CHECKOUT_REVIEW_REQUIRED',
            'message': 'This checkout requires staff review before it can proceed.',
            'reasons': reasons,
        })

    if score >= verify_threshold and has_hard_stop_reason:
        log_bot_event(
            request,
            BotRiskEvent.EVENT_CHECKOUT,
            risk_score=score,
            decision=BotRiskEvent.DECISION_VERIFY,
            reasons=reasons,
        )
        raise BotProtectionError({
            'code': 'ACCOUNT_VERIFICATION_REQUIRED',
            'message': 'Please verify your account details before checking out.',
            'reasons': reasons,
        })

    if score >= challenge_threshold:
        ok, reason = verify_turnstile_token(request, get_challenge_token(request))
        if not ok:
            log_bot_event(
                request,
                BotRiskEvent.EVENT_CHECKOUT,
                risk_score=score,
                decision=BotRiskEvent.DECISION_CHALLENGE,
                reasons=[*reasons, reason],
            )
            raise BotProtectionError({
                'code': 'BOT_CHALLENGE_REQUIRED',
                'message': 'Please complete the security check before checking out.',
                'reasons': reasons,
            })

    log_bot_event(
        request,
        BotRiskEvent.EVENT_CHECKOUT,
        risk_score=score,
        decision=BotRiskEvent.DECISION_ALLOW,
        reasons=reasons or ['checkout_allowed'],
    )
