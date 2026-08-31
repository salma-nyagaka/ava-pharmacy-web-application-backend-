from rest_framework import serializers

from .models import Payout, PayoutAuditLog, PayoutRule


class PayoutAuditLogSerializer(serializers.ModelSerializer):
    actor_name = serializers.ReadOnlyField(source='actor.full_name')

    class Meta:
        model = PayoutAuditLog
        fields = ('id', 'actor', 'actor_name', 'action', 'from_status', 'to_status', 'reason', 'metadata', 'created_at')


class PayoutSerializer(serializers.ModelSerializer):
    recipient_email = serializers.ReadOnlyField(source='recipient.email')
    created_by_name = serializers.ReadOnlyField(source='created_by.full_name')
    reviewed_by_name = serializers.ReadOnlyField(source='reviewed_by.full_name')
    approved_by_name = serializers.ReadOnlyField(source='approved_by.full_name')
    submitted_by_name = serializers.ReadOnlyField(source='submitted_by.full_name')
    audit_logs = PayoutAuditLogSerializer(many=True, read_only=True)

    class Meta:
        model = Payout
        fields = (
            'id', 'reference', 'recipient', 'recipient_name', 'recipient_email', 'role', 'period',
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
        }

    def validate(self, attrs):
        recipient = attrs.get('recipient')
        role = attrs.get('role')
        if recipient and recipient.role != role:
            raise serializers.ValidationError({'recipient': 'Recipient role does not match the payout role.'})
        gross = attrs.get('gross_amount', 0)
        deductions = sum(attrs.get(field, 0) for field in ('commission_amount', 'withholding_amount', 'deduction_amount'))
        if gross <= 0:
            raise serializers.ValidationError({'gross_amount': 'Gross amount must be greater than zero.'})
        if deductions > gross:
            raise serializers.ValidationError('Total deductions cannot exceed the gross amount.')
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
    batch_reference = serializers.CharField(required=False, allow_blank=True, max_length=120)
    failure_code = serializers.CharField(required=False, allow_blank=True, max_length=80)
    failure_message = serializers.CharField(required=False, allow_blank=True)


class PayoutRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = PayoutRule
        fields = ('id', 'role', 'amount', 'currency', 'is_active', 'updated_at')
        read_only_fields = ('id', 'updated_at')
