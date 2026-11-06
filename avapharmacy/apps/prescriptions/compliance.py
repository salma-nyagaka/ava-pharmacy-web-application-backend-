from datetime import timedelta
from django.utils import timezone

EVIDENCE_FIELDS = ('doctor_name', 'prescriber_registration', 'prescriber_verification_reference',
                   'prescribed_on', 'valid_until', 'authenticity_method', 'authenticity_evidence',
                   'original_received_at', 'original_receipt_reference')


def working_day_due(start, days=7):
    # Weekends excluded; include Kenyan public holidays supplied in deployment settings.
    from django.conf import settings
    holidays = set(getattr(settings, 'KENYA_PUBLIC_HOLIDAYS', []))
    while days:
        start += timedelta(days=1)
        if start.weekday() < 5 and start.isoformat() not in holidays:
            days -= 1
    return start


def approval_error(rx):
    today = timezone.localdate()
    if not all(str(getattr(rx, f) or '').strip() for f in
               ['doctor_name', 'prescriber_registration', 'prescriber_verification_reference', 'authenticity_method', 'authenticity_evidence']):
        return 'Prescriber verification and prescription authenticity evidence are required.'
    if not rx.prescribed_on or not rx.valid_until or not rx.prescribed_on <= today <= rx.valid_until:
        return 'A current prescription issue date and validity date are required.'
    from .access import can_review
    if rx.verified_by_id and not can_review(rx.verified_by):
        return 'A currently credentialed pharmacist must verify this prescription.'
    if not rx.verified_by_id or not rx.verified_at:
        return 'An attributable professional verification is required.'
    if rx.source == 'e_prescription':
        clinician = getattr(getattr(rx, 'clinician_prescription', None), 'clinician', None)
        if not clinician or not clinician.eligible_to_practice:
            return 'The issuing clinician must have current verified Kenyan credentials.'
    if rx.original_received_at and rx.original_received_at > timezone.now():
        return 'An original receipt cannot be dated in the future.'
    if rx.original_received_at and not rx.original_receipt_reference.strip():
        return 'Record the reference for the received original.'
    due = rx.original_due_on or (working_day_due(timezone.localdate(rx.submitted_at)) if rx.submitted_at else None)
    if due and today > due and not rx.original_received_at:
        return 'The original prescription is overdue; further supply is on hold.'
    return None
