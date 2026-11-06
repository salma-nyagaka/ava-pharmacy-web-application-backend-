from .models import ClinicianProfile


def can_access_chat(user, consultation):
    if not user or not user.is_authenticated or not user.is_active or user.status != 'active':
        return False
    if consultation.patient_id == user.pk or user.role == 'admin':
        return True
    clinician = consultation.clinician
    return bool(clinician and clinician.user_id == user.pk and clinician.status == ClinicianProfile.STATUS_ACTIVE)
