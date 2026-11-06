from apps.accounts.models import User, Pharmacist


def can_access_queue(user):
    if not user or not user.is_authenticated or not user.is_active or user.status != User.STATUS_ACTIVE:
        return False
    profile = Pharmacist.objects.filter(user_id=user.pk).first()
    return bool(user.role == User.PHARMACIST and profile and profile.has_permission(profile.PERMISSION_PRESCRIPTION_REVIEW))


def can_review(user):
    if not user or not user.is_authenticated or not user.is_active or user.status != User.STATUS_ACTIVE:
        return False
    # Account activation and admin-granted permissions authorize review.
    # Credential verification is retained as a record, not a second approval gate.
    profile = Pharmacist.objects.filter(user_id=user.pk).first()
    return bool(user.role in [User.PHARMACIST, User.ADMIN] and profile
                and profile.has_permission(profile.PERMISSION_PRESCRIPTION_REVIEW))


def can_read(user, prescription):
    if not user or not user.is_authenticated or not user.is_active or user.status != User.STATUS_ACTIVE:
        return False
    return prescription.patient_id == user.pk or user.role == User.ADMIN or can_review(user) or (can_access_queue(user) and prescription.pharmacist_id in (None, user.pk)) or user.role == User.PPB_INSPECTOR
