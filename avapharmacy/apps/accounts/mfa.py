"""Mandatory staff TOTP, with database-serialized verification and recovery."""
import base64
import hashlib
import secrets
from datetime import timedelta

import pyotp
from cryptography.fernet import Fernet
from django.conf import settings
from django.utils import timezone
from django.utils.crypto import constant_time_compare, salted_hmac
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.tokens import RefreshToken

from .models import MFAChallenge, MFACredential, User


def required(user):
    return user.role in {User.ADMIN, User.PHARMACIST, User.DOCTOR, User.PEDIATRICIAN} or user.is_staff or user.is_superuser


def cipher():
    # Separate encryption domain, always encrypted even without an explicit key.
    key = getattr(settings, 'MFA_ENCRYPTION_KEY', '')
    if not key:
        key = base64.urlsafe_b64encode(hashlib.sha256(('ava-mfa:' + settings.SECRET_KEY).encode()).digest())
    return Fernet(key)


def fingerprint(user):
    return salted_hmac('mfa-credentials', f'{user.pk}:{user.password}:{user.email}:{user.role}', algorithm='sha256').hexdigest()


def recovery_hash(code):
    return salted_hmac('mfa-recovery', code.replace('-', '').strip().lower(), algorithm='sha256').hexdigest()


def issue_challenge(user):
    """Caller must hold the user row lock."""
    credential, _ = MFACredential.objects.get_or_create(user=user)
    raw = secrets.token_urlsafe(32)
    now = timezone.now()
    # Keep only one active password-authenticated flow per user.
    MFAChallenge.objects.filter(user=user, consumed=False).update(consumed=True, pending_secret='')
    MFAChallenge.objects.filter(user=user, expires_at__lt=now).delete()
    challenge = MFAChallenge.objects.create(
        user=user, token_hash=hashlib.sha256(raw.encode()).hexdigest(),
        credential_fingerprint=fingerprint(user), enrollment=not credential.enabled,
        expires_at=now + timedelta(minutes=5),
    )
    return {
        'mfa_required': True, 'mfa_setup_required': challenge.enrollment,
        'challenge_token': raw, 'expires_at': challenge.expires_at,
    }


def locked(credential):
    return credential.locked_until and credential.locked_until > timezone.now()


def verify_code(credential, code, *, secret=None, allow_recovery=True):
    """Caller holds user row lock; persist failed attempts outside rollback paths."""
    if locked(credential):
        return False
    if credential.locked_until:
        credential.failed_attempts = 0
        credential.locked_until = None
    valid = False
    if len(code) == 6 and code.isascii() and code.isdigit():
        totp = pyotp.TOTP(secret or cipher().decrypt(credential.secret.encode()).decode())
        current = int(timezone.now().timestamp()) // 30
        for counter in (current - 1, current, current + 1):
            if counter > credential.last_counter and constant_time_compare(totp.at(counter * 30), code):
                credential.last_counter = counter
                valid = True
                break
    elif allow_recovery:
        digest = recovery_hash(code)
        for stored in credential.recovery_hashes:
            if constant_time_compare(stored, digest):
                credential.recovery_hashes = [value for value in credential.recovery_hashes if value != stored]
                valid = True
                break
    if valid:
        credential.failed_attempts = 0
        credential.locked_until = None
    else:
        credential.failed_attempts += 1
        if credential.failed_attempts >= 5:
            credential.locked_until = timezone.now() + timedelta(minutes=15)
    credential.save()
    return valid


def token_payload(user, credential):
    from .serializers import UserSerializer
    refresh = RefreshToken.for_user(user)
    refresh['mfa_version'] = credential.version
    refresh['amr'] = ['pwd', 'otp']
    return {'user': UserSerializer(user).data, 'tokens': {'refresh': str(refresh), 'access': str(refresh.access_token)}}


def require_verified_token(user, token):
    if required(user):
        credential = MFACredential.objects.filter(user=user, enabled=True).first()
        if not credential or token.get('mfa_version') != credential.version or token.get('amr') != ['pwd', 'otp']:
            raise AuthenticationFailed('MFA login required.', code='mfa_required')
