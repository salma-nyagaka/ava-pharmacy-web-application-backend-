from apps.accounts.models import User


def can_review(user):
    if not user or not user.is_authenticated or not user.is_active or user.status != User.STATUS_ACTIVE:
        return False
    if user.role == User.ADMIN:
        return True
    profile = getattr(user, 'pharmacist', None)
    return bool(user.role == User.PHARMACIST and profile and profile.has_permission(profile.PERMISSION_PRESCRIPTION_REVIEW))


def can_read(user, prescription):
    if not user or not user.is_authenticated or not user.is_active or user.status != User.STATUS_ACTIVE:
        return False
    return prescription.patient_id == user.pk or can_review(user) or user.role == User.PPB_INSPECTOR
