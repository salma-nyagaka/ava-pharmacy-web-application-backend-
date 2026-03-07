"""
Utility helpers for the accounts app.

Includes:
- admin audit logging
- helper functions for professional account provisioning
- activation token + email flow for pharmacist and professional staff
"""
import hashlib
import secrets
from datetime import timedelta
from urllib.parse import urlencode

from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.crypto import get_random_string

from .models import AdminAuditLog, PharmacistActivationToken, User


ACTIVATION_ELIGIBLE_ROLES = {
    User.PHARMACIST,
    User.DOCTOR,
    User.PEDIATRICIAN,
    User.LAB_PARTNER,
    User.LAB_TECHNICIAN,
    User.INVENTORY_STAFF,
}


ROLE_LABELS = {
    User.PHARMACIST: 'Pharmacist',
    User.DOCTOR: 'Doctor',
    User.PEDIATRICIAN: 'Pediatrician',
    User.LAB_PARTNER: 'Lab Partner',
    User.LAB_TECHNICIAN: 'Lab Technician',
    User.INVENTORY_STAFF: 'Inventory Staff',
}


def role_label(role):
    return ROLE_LABELS.get(role, 'Professional')


def dashboard_url_for_role(role):
    frontend_base = getattr(settings, 'FRONTEND_BASE_URL', 'http://localhost:3000').rstrip('/')
    mapping = {
        User.PHARMACIST: getattr(settings, 'FRONTEND_PHARMACIST_DASHBOARD_URL', f'{frontend_base}/pharmacist/dashboard'),
        User.DOCTOR: getattr(settings, 'FRONTEND_DOCTOR_DASHBOARD_URL', f'{frontend_base}/doctor/dashboard'),
        User.PEDIATRICIAN: getattr(settings, 'FRONTEND_PEDIATRICIAN_DASHBOARD_URL', f'{frontend_base}/pediatrician/dashboard'),
        User.LAB_PARTNER: getattr(settings, 'FRONTEND_LAB_PARTNER_DASHBOARD_URL', f'{frontend_base}/laboratory/dashboard'),
        User.LAB_TECHNICIAN: getattr(settings, 'FRONTEND_LAB_TECHNICIAN_DASHBOARD_URL', f'{frontend_base}/labaratory/dashboard'),
        User.INVENTORY_STAFF: getattr(settings, 'FRONTEND_INVENTORY_DASHBOARD_URL', f'{frontend_base}/inventory/dashboard'),
    }
    return mapping.get(role, frontend_base)


def log_admin_action(actor, action, entity_type, entity_id='', message='', metadata=None):
    """Create an AdminAuditLog entry for a given admin action.

    Silently returns ``None`` when called with an unauthenticated actor so that
    audit logging never raises exceptions in view code.

    Args:
        actor: The User performing the action.
        action: Short slug describing the action (e.g. ``'user_suspended'``).
        entity_type: The type of entity acted upon (e.g. ``'user'``).
        entity_id: Primary key or identifier of the entity; stored as string.
        message: Human-readable description of the action.
        metadata: Optional dict of extra context stored as JSON.

    Returns:
        AdminAuditLog | None: The created log entry, or ``None`` if actor is
        unauthenticated.
    """
    if not actor or not getattr(actor, 'is_authenticated', False):
        return None

    return AdminAuditLog.objects.create(
        actor=actor,
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id or ''),
        message=message or action,
        metadata=metadata or {},
    )


def split_full_name(full_name):
    full_name = (full_name or '').strip()
    if not full_name:
        return '', ''
    parts = full_name.split(' ', 1)
    first_name = parts[0]
    last_name = parts[1] if len(parts) > 1 else ''
    return first_name, last_name


def build_temporary_password(length=12):
    alphabet = 'ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789!@#$%'
    return get_random_string(length, allowed_chars=alphabet)


def hash_token(raw_token):
    """Return sha256 hex digest for a token string."""
    return hashlib.sha256(raw_token.encode('utf-8')).hexdigest()


def build_activation_url(raw_token, request=None):
    """Build absolute activation page URL used in invitation emails."""
    if request is not None:
        return request.build_absolute_uri(f"/avapharmacy/api/v1/auth/professional/activate/{raw_token}/")

    backend_base = getattr(settings, 'BACKEND_BASE_URL', 'http://127.0.0.1:8000').rstrip('/')
    return f"{backend_base}/avapharmacy/api/v1/auth/professional/activate/{raw_token}/"


def issue_pharmacist_activation_token(user, *, created_by=None, ttl_hours=None):
    """Create and return a new one-time activation token for eligible staff users."""
    if user.role not in ACTIVATION_ELIGIBLE_ROLES:
        raise ValueError('Activation tokens can only be issued for eligible staff users.')

    now = timezone.now()
    # Invalidate older pending tokens so only the newest link remains active.
    PharmacistActivationToken.objects.filter(
        user=user, used_at__isnull=True, expires_at__gt=now
    ).update(used_at=now)

    raw_token = secrets.token_urlsafe(32)
    ttl = ttl_hours or getattr(
        settings,
        'STAFF_ACTIVATION_TTL_HOURS',
        getattr(settings, 'PHARMACIST_ACTIVATION_TTL_HOURS', 24),
    )
    token = PharmacistActivationToken.objects.create(
        user=user,
        token_hash=hash_token(raw_token),
        sent_to=user.email,
        expires_at=now + timedelta(hours=ttl),
        created_by=created_by if getattr(created_by, 'is_authenticated', False) else None,
    )
    return token, raw_token


def get_valid_pharmacist_activation(raw_token):
    """Return valid activation token row for provided raw token or None."""
    if not raw_token:
        return None

    now = timezone.now()
    token_hash = hash_token(raw_token)
    return (
        PharmacistActivationToken.objects.select_related('user')
        .filter(token_hash=token_hash, used_at__isnull=True, expires_at__gt=now, user__role__in=ACTIVATION_ELIGIBLE_ROLES)
        .first()
    )


def consume_pharmacist_activation(raw_token):
    """Mark a token as used and invalidate all remaining active tokens for that user."""
    token = get_valid_pharmacist_activation(raw_token)
    if token is None:
        return None

    now = timezone.now()
    token.used_at = now
    token.save(update_fields=['used_at'])
    PharmacistActivationToken.objects.filter(
        user=token.user, used_at__isnull=True, expires_at__gt=now
    ).update(used_at=now)
    return token


def send_pharmacist_activation_email(*, user, raw_token, request=None, invited_by=None):
    """Send activation email with themed HTML and text fallback."""
    activation_url = build_activation_url(raw_token, request=request)
    frontend_base = getattr(settings, 'FRONTEND_BASE_URL', 'http://localhost:3000').rstrip('/')
    dashboard_url = dashboard_url_for_role(user.role)
    login_url = getattr(settings, 'FRONTEND_LOGIN_URL', f'{frontend_base}/login')
    expires_hours = getattr(
        settings,
        'STAFF_ACTIVATION_TTL_HOURS',
        getattr(settings, 'PHARMACIST_ACTIVATION_TTL_HOURS', 24),
    )
    role_name = role_label(user.role)

    context = {
        'first_name': user.first_name or 'Professional',
        'full_name': user.full_name or user.email,
        'email': user.email,
        'activation_url': activation_url,
        'dashboard_url': dashboard_url,
        'login_url': login_url,
        'expires_hours': expires_hours,
        'invited_by': invited_by.full_name if getattr(invited_by, 'is_authenticated', False) else 'AVA Pharmacy Admin',
        'support_email': getattr(settings, 'ADMIN_EMAIL', 'admin@avapharmacy.com'),
        'account_role_label': role_name,
        'account_role_lower': role_name.lower(),
    }

    subject = f'Activate your AVA Pharmacy {role_name.lower()} account'
    text_body = render_to_string('accounts/emails/pharmacist_activation.txt', context)
    html_body = render_to_string('accounts/emails/pharmacist_activation.html', context)
    send_mail(
        subject=subject,
        message=text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        html_message=html_body,
        fail_silently=False,
    )


def build_frontend_set_password_url(raw_token):
    """Optional frontend route helper if SPA uses token-based set-password screen."""
    frontend_base = getattr(settings, 'FRONTEND_BASE_URL', 'http://localhost:3000').rstrip('/')
    activation_path = getattr(
        settings,
        'FRONTEND_PROFESSIONAL_ACTIVATION_PATH',
        getattr(settings, 'FRONTEND_PHARMACIST_ACTIVATION_PATH', '/auth/professional/activate'),
    )
    query = urlencode({'token': raw_token})
    return f'{frontend_base}{activation_path}?{query}'
