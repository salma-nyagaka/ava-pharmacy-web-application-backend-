"""Login challenges with database-backed retry and replay protection."""
import re
import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import APIException, Throttled

from .models import LoginOTP, User


class OTPError(APIException):
    status_code = 400
    default_detail = 'Invalid or expired login code.'


def send_login_sms(phone, code):
    provider = settings.LOGIN_SMS_PROVIDER
    if provider == 'bongasms':
        send_bongasms_login_sms(phone, code)
    elif provider == 'twilio':
        send_twilio_login_sms(phone, code)
    else:
        raise RuntimeError('Unsupported login SMS provider.')


def send_twilio_login_sms(phone, code):
    import requests

    sid = settings.TWILIO_ACCOUNT_SID
    token = settings.TWILIO_AUTH_TOKEN
    if not re.fullmatch(r'AC[0-9a-fA-F]{32}', sid) or not token:
        raise RuntimeError('Configure Twilio credentials.')
    if settings.TWILIO_MESSAGING_SERVICE_SID:
        sender = {'MessagingServiceSid': settings.TWILIO_MESSAGING_SERVICE_SID}
    elif settings.TWILIO_FROM_NUMBER:
        sender = {'From': settings.TWILIO_FROM_NUMBER}
    else:
        raise RuntimeError('Configure a Twilio SMS sender.')

    with requests.post(
        f'https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json',
        auth=(sid, token),
        data={
            **sender,
            'To': phone,
            'Body': f'Your AVA Pharmacy login code is {code}. It expires in 5 minutes. Do not share it.',
        },
        timeout=10,
        allow_redirects=False,
    ) as response:
        if response.status_code != 201:
            raise RuntimeError('Twilio did not accept the SMS.')
        result = response.json()
        if not result.get('sid') or result.get('error_code') or result.get('status') in {
            'failed', 'undelivered', 'canceled',
        }:
            raise RuntimeError('Twilio did not accept the SMS.')


def send_bongasms_login_sms(phone, code):
    from urllib.parse import urlsplit
    import requests

    endpoint = settings.BONGASMS_SEND_URL
    parsed = urlsplit(endpoint)
    if parsed.scheme != 'https' or not parsed.hostname or parsed.query or parsed.username or parsed.password:
        raise RuntimeError('Configure a BongaSMS HTTPS sending endpoint.')
    if not all((settings.BONGASMS_CLIENT_ID, settings.BONGASMS_API_KEY, settings.BONGASMS_API_SECRET)):
        raise RuntimeError('Configure BongaSMS credentials.')
    msisdn = phone.lstrip('+')
    if not re.fullmatch(r'[1-9][0-9]{7,14}', msisdn):
        raise ValueError('SMS destination must use international format.')
    response = requests.post(endpoint, data={
        'apiClientID': settings.BONGASMS_CLIENT_ID,
        'key': settings.BONGASMS_API_KEY,
        'secret': settings.BONGASMS_API_SECRET,
        'txtMessage': f'Your AVA Pharmacy login code is {code}. It expires in 5 minutes. Do not share it.',
        'MSISDN': msisdn,
        'serviceID': settings.BONGASMS_SERVICE_ID,
    }, timeout=10, allow_redirects=False)
    try:
        result = response.json()
        if not 200 <= response.status_code < 300 or str(result.get('status')) != '222' or result.get('error'):
            raise RuntimeError('BongaSMS did not accept the SMS.')
    finally:
        response.close()


def issue_login_otp(user, *, email_fallback_challenge_id=None):
    with transaction.atomic():
        user = User.objects.select_for_update().get(pk=user.pk)
        previous = LoginOTP.objects.filter(user=user).first()
        if email_fallback_challenge_id is not None and (
            not previous or previous.pk != email_fallback_challenge_id
            or previous.consumed
            or previous.email != user.email
            or (previous.phone and previous.phone != user.phone)
            or previous.credential_hash != user.password
        ):
            raise OTPError('Start signing in again to request a new code.')
        use_sms = settings.LOGIN_OTP_DELIVERY in {'sms', 'both'} and email_fallback_challenge_id is None
        phone = ''
        if use_sms:
            phone = re.sub(r'[\s()-]', '', user.phone)
            if re.fullmatch(r'0[17][0-9]{8}', phone):
                phone = '+254' + phone[1:]
            elif re.fullmatch(r'254[17][0-9]{8}', phone):
                phone = '+' + phone
            if not re.fullmatch(r'\+[1-9][0-9]{7,14}', phone):
                raise OTPError('A valid mobile number is required. Contact support to update your account.')
        now = timezone.now()
        if previous:
            remaining = (previous.sent_at + timedelta(seconds=60) - now).total_seconds()
            if remaining > 0:
                raise Throttled(wait=remaining, detail='Please wait before requesting another code.')
        code = f'{secrets.randbelow(1000000):06d}'
        challenge, _ = LoginOTP.objects.update_or_create(user=user, defaults={
            'code_hash': make_password(code), 'phone': user.phone if use_sms else '', 'email': user.email,
            'credential_hash': user.password, 'expires_at': now + timedelta(minutes=5),
            'sent_at': now, 'attempts': 0, 'consumed': False,
        })
        try:
            if use_sms:
                send_login_sms(phone, code)
            if settings.EMAIL_BACKEND in {
                'django.core.mail.backends.console.EmailBackend',
                'django.core.mail.backends.filebased.EmailBackend',
                'django.core.mail.backends.dummy.EmailBackend',
            }:
                raise RuntimeError('Configure email delivery for login codes.')
            sent = send_mail(
                'Your AVA Pharmacy login code',
                f'Your login code is {code}. It expires in 5 minutes. Do not share it.\n'
                'If you did not request this code, you can ignore this email.',
                settings.DEFAULT_FROM_EMAIL, [user.email], fail_silently=False,
            )
            if sent != 1:
                raise RuntimeError('Email delivery was not accepted.')
        except Exception:
            error = OTPError('Unable to send the login code. Please try again later.')
            error.status_code = 503
            raise error from None
        destination = (
            {'delivery_channel': 'both', 'phone_hint': '••••' + phone[-4:],
             'email_hint': user.email[0] + '***@' + user.email.rsplit('@', 1)[-1]}
            if use_sms else
            {'delivery_channel': 'email', 'email_hint': user.email[0] + '***@' + user.email.rsplit('@', 1)[-1]}
        )
        return {
            **destination,
            'otp_required': True, 'challenge_id': str(challenge.pk),
            'expires_in': 300, 'resend_after': 60,
            'detail': 'Enter the code sent to your account.',
        }


def verify_login_otp(challenge_id, code):
    # Commit failed attempts as well as successful consumption.
    user = None
    with transaction.atomic():
        user_id = LoginOTP.objects.filter(pk=challenge_id).values_list('user_id', flat=True).first()
        if user_id is not None:
            candidate = User.objects.select_for_update().get(pk=user_id)
        challenge = LoginOTP.objects.select_for_update().filter(pk=challenge_id).first()
        if challenge:
            valid = (
                not challenge.consumed and challenge.expires_at > timezone.now()
                and challenge.attempts < 5 and candidate.is_active
                and candidate.status == User.STATUS_ACTIVE
                and candidate.email == challenge.email
                and (not challenge.phone or candidate.phone == challenge.phone)
                and candidate.password == challenge.credential_hash
            )
            if valid:
                challenge.attempts += 1
                if check_password(code, challenge.code_hash):
                    challenge.consumed = True
                    user = candidate
                challenge.save(update_fields=['attempts', 'consumed'])
    if user is None:
        raise OTPError()
    return user
