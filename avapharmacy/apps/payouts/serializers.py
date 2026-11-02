from django.utils import timezone
from rest_framework import serializers

from .models import Payout, PayoutAuditLog, PayoutRule


class PayoutAuditLogSerializer(serializers.ModelSerializer):
    actor_name = serializers.ReadOnlyField(source='actor.full_name')

    class Meta:
        model = PayoutAuditLog
        fields = ('id', 'actor', 'actor_name', 'action', 'from_status', 'to_status', 'reason', 'metadata', 'created_at')


class PayoutSerializer(serializers.ModelSerializer):
    execution_mode = serializers.SerializerMethodField()

    def get_execution_mode(self, obj):
        return 'administrative_record'

    recipient_email = serializers.ReadOnlyField(source='recipient.email')
    created_by_name = serializers.ReadOnlyField(source='created_by.full_name')
    reviewed_by_name = serializers.ReadOnlyField(source='reviewed_by.full_name')
    approved_by_name = serializers.ReadOnlyField(source='approved_by.full_name')
    submitted_by_name = serializers.ReadOnlyField(source='submitted_by.full_name')
    audit_logs = PayoutAuditLogSerializer(many=True, read_only=True)

    class Meta:
        model = Payout
        fields = (
            'id', 'reference', 'execution_mode', 'recipient', 'recipient_name', 'recipient_email', 'role', 'period',
            'source_type', 'source_reference', 'idempotency_key',
            'gross_amount', 'commission_amount', 'withholding_amount', 'deduction_amount',
            'amount', 'currency', 'method', 'payment_reference', 'provider_transaction_id',
            'batch_reference', 'status', 'reconciliation_status', 'notes', 'hold_reason',
            'failure_code', 'failure_message', 'retry_count', 'requested_at', 'reviewed_at',
            'approved_at', 'submitted_at', 'paid_at', 'created_by', 'created_by_name',
            'reviewed_by', 'reviewed_by_name', 'approved_by', 'approved_by_name',
            'submitted_by', 'submitted_by_name', 'audit_logs',
        )
        read_only_fields = fields


class PayoutCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payout
        fields = (
            'recipient', 'recipient_name', 'role', 'period', 'source_type', 'source_reference',
            'idempotency_key', 'gross_amount', 'commission_amount', 'withholding_amount',
            'deduction_amount', 'currency', 'method', 'notes',
        )
        validators = []
        extra_kwargs = {
            'idempotency_key': {'validators': []},
            'recipient_name': {'required': False},
        }

    def validate(self, attrs):
        recipient = attrs.get('recipient')
        if not recipient or not recipient.is_active or recipient.status != 'active':
            raise serializers.ValidationError({'recipient': 'Select an active professional account.'})
        attrs['recipient_name'] = recipient.full_name
        for field in ('commission_amount', 'withholding_amount', 'deduction_amount'):
            if attrs.get(field, 0) < 0:
                raise serializers.ValidationError({field: 'Amounts cannot be negative.'})
        currency = attrs.get('currency', 'KES').strip().upper()
        if currency not in ('KES', 'KSH'):
            raise serializers.ValidationError({'currency': 'Only KES payouts are supported.'})
        attrs['currency'] = 'KES'
        attrs['source_type'] = attrs.get('source_type', '').strip() or 'manual_adjustment'
        attrs['source_reference'] = attrs.get('source_reference', '').strip()
        attrs['idempotency_key'] = attrs.get('idempotency_key') or None
        role = attrs.get('role')
        if recipient and recipient.role != role:
            raise serializers.ValidationError({'recipient': 'Recipient role does not match the payout role.'})
        gross = attrs.get('gross_amount', 0)
        deductions = sum(attrs.get(field, 0) for field in ('commission_amount', 'withholding_amount', 'deduction_amount'))
        if gross <= 0:
            raise serializers.ValidationError({'gross_amount': 'Gross amount must be greater than zero.'})
        if deductions > gross:
            raise serializers.ValidationError('Total deductions cannot exceed the gross amount.')
        source_type = attrs['source_type']
        if source_type == 'consultation':
            from apps.consultations.models import Consultation, ClinicianEarning, ConsultationPaymentIntent
            consultation = Consultation.objects.filter(reference=attrs['source_reference'], clinician__user=recipient, status='completed').first()
            earning = ClinicianEarning.objects.filter(consultation=consultation, clinician__user=recipient).first() if consultation else None
            payment = ConsultationPaymentIntent.objects.filter(consultation=consultation, status='succeeded').first() if consultation else None
            if not earning or not payment:
                raise serializers.ValidationError({'source_reference': 'Choose a completed, paid consultation with a recorded earning for this recipient.'})
            if gross != payment.amount or attrs.get('commission_amount', 0) != payment.amount - earning.amount:
                raise serializers.ValidationError({'gross_amount': 'Gross and commission must match the recorded consultation payment and earning.'})
        elif source_type == 'manual_adjustment' and attrs['source_reference'].upper().startswith('CONS-'):
            raise serializers.ValidationError({'source_reference': 'Consultation references must use the consultation source type.'})
        elif source_type != 'manual_adjustment':
            raise serializers.ValidationError({'source_type': 'Use consultation for a verified earning or manual_adjustment for an explicitly documented adjustment.'})
        if not attrs['source_reference']:
            raise serializers.ValidationError({'source_reference': 'A unique source reference is required.'})
        return attrs


class PayoutActionSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=(
        'submit', 'approve', 'hold', 'release', 'process', 'mark_paid', 'mark_failed',
        'retry', 'reverse', 'cancel', 'reconcile', 'unmatch', 'flag_exception',
    ))
    reason = serializers.CharField(required=False, allow_blank=True)
    payment_reference = serializers.CharField(required=False, allow_blank=True, max_length=100)
    provider_transaction_id = serializers.CharField(required=False, allow_blank=True, max_length=120)
    method = serializers.ChoiceField(choices=Payout.METHOD_CHOICES, required=False)
    paid_at = serializers.DateTimeField(required=False)

    def validate_paid_at(self, value):
        if value > timezone.now():
            raise serializers.ValidationError('Payment time cannot be in the future.')
        return value
    batch_reference = serializers.CharField(required=False, allow_blank=True, max_length=120)
    failure_code = serializers.CharField(required=False, allow_blank=True, max_length=80)
    failure_message = serializers.CharField(required=False, allow_blank=True)


class PayoutRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = PayoutRule
        fields = ('id', 'role', 'amount', 'currency', 'is_active', 'updated_at')
        read_only_fields = ('id', 'updated_at')

    def validate_currency(self, value):
        if value.strip().upper() not in ('KES', 'KSH'):
            raise serializers.ValidationError('Only KES payout rules are supported.')
        return 'KES'

    def validate_amount(self, value):
        if value < 0:
            raise serializers.ValidationError('The task rate cannot be negative.')
        return value
