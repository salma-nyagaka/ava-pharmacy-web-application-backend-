"""Create payable records from completed work; never execute money transfers."""
from decimal import Decimal, ROUND_HALF_UP

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from .models import LabRevenueAgreement, LabRevenueAllocation, Payout, PayoutAuditLog

ZERO = Decimal('0.00')


def _create(recipient, role, source_type, reference, gross, net, method, hold_reason='', metadata=None, completed_at=None):
    if recipient is None:
        return None
    with transaction.atomic():
        payout, created = Payout.objects.get_or_create(
            recipient=recipient, role=role, source_type=source_type, source_reference=reference,
            defaults={
                'recipient_name': recipient.full_name,
                'period': timezone.localtime(completed_at).strftime('%B %Y') if completed_at else timezone.localdate().strftime('%B %Y'),
                'gross_amount': gross, 'commission_amount': gross - net, 'amount': net,
                'method': method, 'currency': 'KES',
                'status': Payout.STATUS_ON_HOLD if hold_reason else Payout.STATUS_PENDING,
                'hold_reason': hold_reason,
                'idempotency_key': f'auto:{source_type}:{reference}:{recipient.pk}:{role}',
                'notes': f'Automatically created from completed {source_type.replace("_", " ")} {reference}.',
            },
        )
        if created:
            PayoutAuditLog.objects.create(payout=payout, action='automatically_created', to_status=payout.status, metadata=metadata or {})
    return payout


def create_consultation_payout(earning, gross, paid):
    consultation, clinician = earning.consultation, earning.clinician
    net = Decimal(earning.amount)
    gross = max(Decimal(gross), net)
    reason = '' if paid and net > 0 else 'Customer payment or a positive recorded earning must be confirmed before approval.'
    return _create(clinician.user, clinician.provider_type, 'consultation', consultation.reference,
                   gross, net, clinician.payout_method, reason, completed_at=consultation.ended_at or consultation.updated_at)


def _lab_amounts(request):
    from apps.lab.models import LabRequest
    # Serialise concurrent completion/release against the same booked request.
    LabRequest.objects.select_for_update().get(pk=request.pk)
    allocation = LabRevenueAllocation.objects.filter(request=request).first()
    if allocation:
        return allocation
    agreement = LabRevenueAgreement.objects.filter(partner_id=request.assigned_partner_id, is_active=True).first()
    fee = request.quoted_test_price
    if not agreement or fee is None:
        return None
    fee = Decimal(fee)
    partner = (fee * agreement.partner_percent / 100).quantize(Decimal('.01'), rounding=ROUND_HALF_UP)
    technician = min(fee - partner, (fee * agreement.technician_percent / 100).quantize(Decimal('.01'), rounding=ROUND_HALF_UP))
    return LabRevenueAllocation.objects.create(
        request=request, agreement=agreement, booked_fee=fee,
        partner_amount=partner, technician_amount=technician,
        terms={'agreement_id': agreement.pk, 'booked_fee': str(fee), 'partner_percent': str(agreement.partner_percent), 'technician_percent': str(agreement.technician_percent), 'ava_percent': str(agreement.ava_percent), 'ava_amount': str(fee - partner - technician)},
    )


@transaction.atomic
def create_lab_payouts(request):
    amounts = _lab_amounts(request)
    partner = request.assigned_partner
    recipients = [
        (partner.user if partner else None, Payout.ROLE_LAB_PARTNER, partner.payout_method if partner else Payout.METHOD_MPESA, 'partner_amount'),
        (request.assigned_technician, Payout.ROLE_LAB_TECHNICIAN, Payout.METHOD_MPESA, 'technician_amount'),
    ]
    for recipient, role, method, index in recipients:
        net = getattr(amounts, index) if amounts else ZERO
        if amounts and net == 0:
            continue  # This agreement allocates no payout to this role.
        reason = ''
        if not amounts:
            reason = 'Configure an active lab revenue-sharing agreement and confirm the booked test price.'
        elif request.payment_status != request.PAYMENT_PAID:
            reason = 'Customer lab payment must be confirmed before approval.'
        elif amounts.partner_amount > 0 and (not partner or not partner.user_id):
            reason = 'The agreement allocates a lab share but the laboratory has no payment account.'
        elif amounts.technician_amount > 0 and request.assigned_technician_id is None:
            reason = 'The agreement allocates a technician share but no technician is assigned.'
        metadata = {}
        if amounts:
            metadata = amounts.terms
        _create(recipient, role, 'lab_request', request.reference, net, net, method, reason, metadata)


@transaction.atomic
def validate_automatic_payout(payout):
    """Validate the source again before releasing, approving or recording payment."""
    if not (payout.idempotency_key or '').startswith('auto:'):
        return
    if not payout.recipient or not payout.recipient.is_active or payout.recipient.status != 'active':
        raise ValidationError({'detail': 'The payout recipient must have an active account.'})
    if payout.source_type == 'consultation':
        from apps.consultations.models import Consultation, ConsultationPaymentIntent
        consultation = Consultation.objects.filter(reference=payout.source_reference, status='completed', clinician__user=payout.recipient).first()
        if not consultation or not ConsultationPaymentIntent.objects.filter(consultation=consultation, status='succeeded', amount__gte=payout.gross_amount).exists():
            raise ValidationError({'detail': 'A completed, paid consultation is required before payment approval.'})
    elif payout.source_type == 'lab_request':
        from apps.lab.models import LabRequest
        request = LabRequest.objects.filter(reference=payout.source_reference, status='completed', payment_status='paid').first()
        if not request:
            raise ValidationError({'detail': 'A completed, paid lab request is required before payment approval.'})
        if payout.role == Payout.ROLE_LAB_PARTNER:
            assigned_id = request.assigned_partner.user_id if request.assigned_partner else None
        else:
            assigned_id = request.assigned_technician_id
        if assigned_id != payout.recipient_id:
            raise ValidationError({'detail': 'The recipient no longer matches this completed lab request.'})
        allocation = _lab_amounts(request)
        if allocation and allocation.partner_amount > 0 and (not request.assigned_partner or not request.assigned_partner.user_id):
            raise ValidationError({'detail': 'The laboratory must have a linked payment account for its agreed share.'})
        if allocation and allocation.technician_amount > 0 and not request.assigned_technician_id:
            raise ValidationError({'detail': 'A technician must be assigned for the agreed technician share.'})
        if payout.amount == 0:
            amounts = _lab_amounts(request)
            if not amounts:
                raise ValidationError({'detail': 'Configure an active lab agreement and booked test price first.'})
            net = amounts.partner_amount if payout.role == Payout.ROLE_LAB_PARTNER else amounts.technician_amount
            payout.gross_amount = payout.amount = net
            payout.commission_amount = ZERO
            PayoutAuditLog.objects.create(payout=payout, action='agreement_applied', from_status=payout.status, to_status=payout.status, metadata=amounts.terms)
    if payout.amount <= 0:
        raise ValidationError({'detail': 'A positive payable amount is required.'})


def sync_completed_consultation_payouts():
    """Bring historical completed work into the admin queue without changing paid rows."""
    from django.db.models import Exists, OuterRef
    from apps.consultations.models import Consultation, ClinicianEarning, ConsultationPaymentIntent

    existing = Payout.objects.filter(
        recipient_id=OuterRef('clinician__user_id'),
        source_type='consultation', source_reference=OuterRef('reference'),
    )
    consultations = Consultation.objects.filter(
        status='completed', clinician__user__isnull=False,
        clinician__provider_type__in=('doctor', 'pediatrician'),
    ).annotate(has_payout=Exists(existing)).filter(has_payout=False)
    created = 0
    for pk in consultations.values_list('pk', flat=True).iterator(chunk_size=200):
        with transaction.atomic():
            consultation = Consultation.objects.select_for_update(of=('self',)).select_related('clinician__user').get(pk=pk)
            clinician = consultation.clinician
            if consultation.status != 'completed' or not clinician or not clinician.user_id:
                continue
            if Payout.objects.filter(recipient=clinician.user, source_type='consultation', source_reference=consultation.reference).exists():
                continue
            payment = ConsultationPaymentIntent.objects.filter(consultation=consultation, status='succeeded').first()
            earning = ClinicianEarning.objects.filter(consultation=consultation, clinician=clinician).first()
            gross = payment.amount if payment else consultation.agreed_total or ZERO
            if not earning and consultation.agreed_total is not None and consultation.agreed_clinician_share is not None:
                # Historical fixed shares are recorded terms; never infer earnings from today's rates.
                net = consultation.agreed_clinician_share if gross >= consultation.agreed_total else ZERO
                earning, _ = ClinicianEarning.objects.get_or_create(
                    consultation=consultation, clinician=clinician,
                    defaults={'amount': net, 'description': f'Recorded agreed share for completed consultation {consultation.reference}.'},
                )
            if earning:
                create_consultation_payout(earning, gross, payment is not None)
            else:
                _create(clinician.user, clinician.provider_type, 'consultation', consultation.reference,
                        gross, ZERO, clinician.payout_method,
                        'Confirm the historical consultation earning before approving payment.',
                        completed_at=consultation.ended_at or consultation.updated_at)
            created += 1
    return created
