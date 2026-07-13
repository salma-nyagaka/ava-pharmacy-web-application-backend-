from urllib.parse import urlparse

from django.conf import settings
from django.core import checks
from django.db import DatabaseError, OperationalError, ProgrammingError

from .models import SiteSettings


PENDING_VALUES = {'', 'pending', 'pending update', 'tbd', 'to be updated', 'n/a', 'na', 'none'}

REQUIRED_COMPLIANCE_FIELDS = {
    'postal_address': 'Postal address',
    'health_safety_code': 'Health safety code',
    'premises_registration_number': 'Premises registration number',
    'online_pharmacy_license_number': 'Online pharmacy license number',
    'superintendent_name': 'Superintendent pharmacist / technologist name',
    'superintendent_registration_number': 'Superintendent registration number',
    'pharmacist_consultation_hours': 'Pharmacist consultation hours',
    'ppb_contact_name': 'PPB contact name',
    'ppb_contact_address': 'PPB contact address',
    'ppb_contact_phone': 'PPB contact phone',
    'ppb_contact_email': 'PPB contact email',
    'ppb_website': 'PPB website',
    'complaint_policy_url': 'Complaint policy URL',
    'privacy_policy_url': 'Privacy policy URL',
    'returns_policy_url': 'Returns policy URL',
}


def _is_missing(value):
    return str(value or '').strip().lower() in PENDING_VALUES


def _is_public_https_url(value):
    parsed = urlparse(str(value or '').strip())
    if parsed.scheme != 'https' or not parsed.netloc:
        return False
    host = parsed.hostname or ''
    return host not in {'localhost', '127.0.0.1'} and not host.endswith('.local')


@checks.register(checks.Tags.security, deploy=True)
def check_site_compliance_settings(app_configs, **kwargs):
    try:
        site_settings = SiteSettings.get_solo()
    except (DatabaseError, OperationalError, ProgrammingError) as exc:
        return [
            checks.Warning(
                'Could not read SiteSettings while checking compliance fields.',
                hint=f'Run migrations and verify database connectivity. Error: {exc}',
                id='ava.W001',
            )
        ]

    missing = [
        label
        for field, label in REQUIRED_COMPLIANCE_FIELDS.items()
        if _is_missing(getattr(site_settings, field, ''))
    ]
    if not missing:
        return []

    return [
        checks.Error(
            'Public pharmacy compliance settings are incomplete.',
            hint=(
                'Fill these fields in Admin Settings before audit/release: '
                f'{", ".join(missing)}.'
            ),
            id='ava.E001',
        )
    ]


@checks.register(checks.Tags.security, deploy=True)
def check_bot_challenge_settings(app_configs, **kwargs):
    messages = []
    if getattr(settings, 'BOT_CHALLENGE_PROVIDER', '') != 'turnstile':
        messages.append(
            checks.Error(
                'BOT_CHALLENGE_PROVIDER must be "turnstile" in production.',
                hint='Set BOT_CHALLENGE_PROVIDER=turnstile.',
                id='ava.E010',
            )
        )
    if not str(getattr(settings, 'TURNSTILE_SECRET_KEY', '') or '').strip():
        messages.append(
            checks.Error(
                'TURNSTILE_SECRET_KEY is not configured.',
                hint='Set the Cloudflare Turnstile secret key so login/register/checkout challenges cannot be bypassed.',
                id='ava.E011',
            )
        )
    if not bool(getattr(settings, 'BOT_CHALLENGE_REQUIRED', False)):
        messages.append(
            checks.Error(
                'BOT_CHALLENGE_REQUIRED is disabled.',
                hint='Set BOT_CHALLENGE_REQUIRED=True for production bot checks on login, registration, forgot password, uploads, and checkout.',
                id='ava.E012',
            )
        )
    return messages


@checks.register(checks.Tags.security, deploy=True)
def check_payment_settings(app_configs, **kwargs):
    messages = []
    required_mpesa_values = {
        'MPESA_CONSUMER_KEY': getattr(settings, 'MPESA_CONSUMER_KEY', ''),
        'MPESA_CONSUMER_SECRET': getattr(settings, 'MPESA_CONSUMER_SECRET', ''),
        'MPESA_SHORTCODE': getattr(settings, 'MPESA_SHORTCODE', ''),
        'MPESA_PASSKEY': getattr(settings, 'MPESA_PASSKEY', ''),
        'MPESA_CALLBACK_URL': getattr(settings, 'MPESA_CALLBACK_URL', ''),
        'MPESA_PAYBILL_NUMBER': getattr(settings, 'MPESA_PAYBILL_NUMBER', ''),
        'MPESA_C2B_SHORTCODE': getattr(settings, 'MPESA_C2B_SHORTCODE', ''),
        'MPESA_C2B_VALIDATION_URL': getattr(settings, 'MPESA_C2B_VALIDATION_URL', ''),
        'MPESA_C2B_CONFIRMATION_URL': getattr(settings, 'MPESA_C2B_CONFIRMATION_URL', ''),
    }
    missing = [name for name, value in required_mpesa_values.items() if not str(value or '').strip()]
    if missing:
        messages.append(
            checks.Error(
                'M-Pesa checkout/paybill configuration is incomplete.',
                hint=f'Set these environment variables before release: {", ".join(missing)}.',
                id='ava.E020',
            )
        )

    for name in ('MPESA_CALLBACK_URL', 'MPESA_C2B_VALIDATION_URL', 'MPESA_C2B_CONFIRMATION_URL'):
        value = getattr(settings, name, '')
        if value and not _is_public_https_url(value):
            messages.append(
                checks.Error(
                    f'{name} must be a public HTTPS URL.',
                    hint='Safaricom callbacks cannot use localhost, plain HTTP, or private/local hostnames in production.',
                    id='ava.E021',
                )
            )

    if not bool(getattr(settings, 'MPESA_C2B_URLS_REGISTERED', False)):
        messages.append(
            checks.Error(
                'M-Pesa C2B validation/confirmation URLs are not marked as registered.',
                hint='Register the URLs with Daraja, then set MPESA_C2B_URLS_REGISTERED=True.',
                id='ava.E022',
            )
        )

    override_amount = str(getattr(settings, 'MPESA_STK_PUSH_AMOUNT_OVERRIDE', '') or '').strip()
    if override_amount:
        messages.append(
            checks.Error(
                'MPESA_STK_PUSH_AMOUNT_OVERRIDE is still set.',
                hint='Leave MPESA_STK_PUSH_AMOUNT_OVERRIDE blank in production so customers pay the real order total.',
                id='ava.E023',
            )
        )

    return messages


@checks.register(checks.Tags.security, deploy=True)
def check_frontend_origin_settings(app_configs, **kwargs):
    messages = []
    origins = [origin.strip() for origin in getattr(settings, 'CORS_ALLOWED_ORIGINS', []) if origin.strip()]
    local_origins = [
        origin for origin in origins
        if 'localhost' in origin or '127.0.0.1' in origin
    ]
    if local_origins:
        messages.append(
            checks.Error(
                'CORS_ALLOWED_ORIGINS includes local development origins.',
                hint=f'Remove local origins before production release: {", ".join(local_origins)}.',
                id='ava.E030',
            )
        )

    frontend_url = str(getattr(settings, 'FRONTEND_BASE_URL', '') or '').strip()
    if frontend_url and not _is_public_https_url(frontend_url):
        messages.append(
            checks.Error(
                'FRONTEND_BASE_URL must be a public HTTPS URL in production.',
                hint='Set FRONTEND_BASE_URL to the deployed frontend origin.',
                id='ava.E031',
            )
        )

    return messages
