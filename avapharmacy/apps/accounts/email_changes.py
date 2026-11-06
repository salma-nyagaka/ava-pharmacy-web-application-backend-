"""Reauthenticated, old-address approval for changing a login email."""
import hashlib
import logging
import secrets
from datetime import timedelta
from urllib.parse import urlencode
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework import serializers
from rest_framework.throttling import UserRateThrottle
from rest_framework.exceptions import Throttled
from .models import EmailChangeRequest, User
from apps.notifications.emailing import send_rendered_email

logger = logging.getLogger(__name__)


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


class EmailChangeThrottle(UserRateThrottle):
    scope = 'email_change'
    rate = '5/hour'


def save_with_email_verification(serializer):
    data = serializer.validated_data
    target = data.get('email')
    user = serializer.instance
    password = data.pop('current_password', '')
    if not target or target.lower() == user.email.lower():
        return serializer.save()
    request = serializer.context['request']
    throttle = EmailChangeThrottle()
    if not throttle.allow_request(request, None):
        raise Throttled(wait=throttle.wait())
    actor = request.user
    if not password:
        raise serializers.ValidationError({'current_password': ['Enter your current AVA Pharmacy sign-in password.']})
    if not actor.has_usable_password():
        raise serializers.ValidationError({'current_password': ['Set an AVA Pharmacy password using Forgot password before changing your email.']})
    if not actor.check_password(password):
        raise serializers.ValidationError({'current_password': ['Incorrect current password. Use your AVA Pharmacy sign-in password, not your email account password.']})
    data.pop('email')
    old_token, new_token = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    with transaction.atomic():
        locked = User.objects.select_for_update().get(pk=user.pk)
        if locked.email != user.email or locked.password != user.password:
            raise serializers.ValidationError({'email': ['Account changed. Reload and try again.']})
        EmailChangeRequest.objects.filter(user=user, used_at__isnull=True).update(used_at=timezone.now())
        saved = serializer.save()
        pending = EmailChangeRequest.objects.create(
            user=user, old_email=locked.email, new_email=target,
            password_fingerprint=digest(saved.password),
            old_token_hash=digest(old_token), new_token_hash=digest(new_token),
            expires_at=timezone.now()+timedelta(minutes=30),
        )
    result = {'pending_email': target, 'sent_to': [], 'failed_to': []}
    # Send after the request is durable; never claim delivery on an SMTP error.
    for recipient, token in ((pending.old_email, old_token),):
        try:
            count = send_rendered_email(
                subject='Confirm your AVA Pharmacy email change', recipient_list=[recipient],
                text_template='accounts/emails/email_change_request.txt',
                html_template='accounts/emails/email_change_request.html',
                context={'first_name': user.first_name or 'there', 'new_email': target,
                         'confirmation_url': settings.FRONTEND_BASE_URL.rstrip('/')+'/confirm-email-change?'+urlencode({'token': token})},
            )
            result['sent_to' if count else 'failed_to'].append(recipient)
        except Exception:
            logger.exception('Email change confirmation delivery failed for request %s', pending.pk)
            result['failed_to'].append(recipient)
    saved.email_change = result
    return saved
