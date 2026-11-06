import hashlib
import secrets

import pyotp
from django.db import transaction
from django.utils import timezone
from rest_framework import serializers
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView

from . import mfa
from .models import AdminAuditLog, MFAChallenge, MFACredential, User


class MFAThrottle(AnonRateThrottle):
    scope = 'mfa'


class MFAInput(serializers.Serializer):
    challenge_token = serializers.CharField(max_length=128)
    code = serializers.CharField(max_length=64, required=False, trim_whitespace=True)


class MFAView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [MFAThrottle]
    action = 'verify'

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response['Cache-Control'] = 'no-store'
        return response

    def post(self, request):
        data = MFAInput(data=request.data)
        data.is_valid(raise_exception=True)
        raw = data.validated_data['challenge_token']
        digest = hashlib.sha256(raw.encode()).hexdigest()
        candidate = MFAChallenge.objects.filter(token_hash=digest).first()
        if not candidate:
            return self.invalid()
        with transaction.atomic():
            # Same lock order for login, enrollment, API verification and admin.
            user = User.objects.select_for_update().filter(pk=candidate.user_id).first()
            if not user:
                return self.invalid()
            challenge = MFAChallenge.objects.filter(pk=candidate.pk).first()
            if (not challenge or challenge.consumed or challenge.expires_at <= timezone.now()
                    or challenge.credential_fingerprint != mfa.fingerprint(user)
                    or not user.is_active or user.status != User.STATUS_ACTIVE
                    or not mfa.required(user)):
                return self.invalid()
            credential = MFACredential.objects.get(user=user)
            if mfa.locked(credential):
                return Response({'detail': 'Too many incorrect MFA codes. Try again in 15 minutes.'}, status=429)
            if self.action == 'setup':
                if not challenge.enrollment or credential.enabled:
                    return self.invalid()
                if not challenge.pending_secret:
                    challenge.pending_secret = mfa.cipher().encrypt(pyotp.random_base32().encode()).decode()
                    challenge.save(update_fields=['pending_secret'])
                secret = mfa.cipher().decrypt(challenge.pending_secret.encode()).decode()
                response = Response({
                    'secret': secret,
                    'otpauth_uri': pyotp.TOTP(secret).provisioning_uri(user.email, issuer_name='Ava Pharmacy'),
                    'expires_at': challenge.expires_at,
                })
            else:
                enrollment = self.action == 'confirm'
                if enrollment != challenge.enrollment or (enrollment and (credential.enabled or not challenge.pending_secret)):
                    return self.invalid()
                if not enrollment and not credential.enabled:
                    return self.invalid()
                secret = mfa.cipher().decrypt(challenge.pending_secret.encode()).decode() if enrollment else None
                code = data.validated_data.get('code', '')
                if not code:
                    return Response({'detail': 'An MFA code is required.'}, status=400)
                if not mfa.verify_code(credential, code, secret=secret, allow_recovery=not enrollment):
                    return Response({'detail': 'Invalid or already used MFA code.'}, status=400)
                recovery_codes = None
                if enrollment:
                    recovery_codes = [secrets.token_hex(8) for _ in range(10)]
                    credential.secret = challenge.pending_secret
                    credential.enabled = True
                    credential.version = secrets.token_hex(16)
                    credential.recovery_hashes = [mfa.recovery_hash(code) for code in recovery_codes]
                    credential.save()
                    AdminAuditLog.objects.create(actor=user, action='mfa_enrolled', entity_type='user',
                                                 entity_id=str(user.pk), message='Authenticator MFA enrolled')
                challenge.consumed = True
                challenge.pending_secret = ''
                challenge.save(update_fields=['consumed', 'pending_secret'])
                payload = mfa.token_payload(user, credential)
                if recovery_codes is not None:
                    payload['recovery_codes'] = recovery_codes
                response = Response(payload)
            response['Cache-Control'] = 'no-store'
            return response

    @staticmethod
    def invalid():
        return Response({'detail': 'Invalid or expired MFA challenge. Log in again.'}, status=400)


class MFASetupView(MFAView):
    action = 'setup'


class MFAConfirmView(MFAView):
    action = 'confirm'
