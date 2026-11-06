from django import forms
from django.contrib.admin import AdminSite
from django.contrib.admin.forms import AdminAuthenticationForm
from django.core.exceptions import ValidationError
from django.db import transaction

from . import mfa
from .models import MFACredential, User


class MFAAdminAuthenticationForm(AdminAuthenticationForm):
    mfa_code = forms.CharField(label='Authenticator or recovery code', max_length=64, required=False,
                               widget=forms.TextInput(attrs={'autocomplete': 'one-time-code'}))

    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        if user.status != User.STATUS_ACTIVE:
            raise ValidationError('This account is inactive.')
        with transaction.atomic():
            locked_user = User.objects.select_for_update().get(pk=user.pk)
            if not locked_user.is_active or locked_user.status != User.STATUS_ACTIVE or locked_user.password != user.password:
                raise ValidationError('Account credentials changed. Please log in again.')
            credential = MFACredential.objects.filter(user=locked_user, enabled=True).first()
            if not credential:
                raise ValidationError('Set up MFA through the application login before signing in to Django admin.')
            code = self.cleaned_data.get('mfa_code', '').strip()
            valid = bool(code) and mfa.verify_code(credential, code)
            version = credential.version
        # Raise outside atomic so failed attempt counters remain committed.
        if not valid:
            raise ValidationError('Invalid or already used MFA code, or MFA is temporarily locked.')
        self.request.session['admin_mfa_version'] = version


class MFAAdminSite(AdminSite):
    login_form = MFAAdminAuthenticationForm
    login_template = 'admin/mfa_login.html'

    def has_permission(self, request):
        if not super().has_permission(request) or request.user.status != User.STATUS_ACTIVE:
            return False
        version = request.session.get('admin_mfa_version')
        return bool(version and MFACredential.objects.filter(user=request.user, enabled=True, version=version).exists())
