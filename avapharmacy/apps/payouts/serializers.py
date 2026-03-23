from rest_framework import serializers
from .models import Payout, PayoutRule


class PayoutSerializer(serializers.ModelSerializer):
    recipient_email = serializers.ReadOnlyField(source='recipient.email')
    created_by_name = serializers.ReadOnlyField(source='created_by.full_name')

    class Meta:
        model = Payout
        fields = (
            'id', 'reference', 'recipient', 'recipient_name', 'recipient_email',
            'role', 'period', 'amount', 'method', 'payment_reference',
            'status', 'notes', 'requested_at', 'paid_at', 'created_by', 'created_by_name'
        )
        read_only_fields = ('id', 'reference', 'requested_at', 'created_by')


class PayoutCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payout
        fields = ('recipient', 'recipient_name', 'role', 'period', 'amount', 'method', 'notes')


class PayoutUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payout
        fields = ('status', 'payment_reference', 'paid_at', 'notes')


class PayoutRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = PayoutRule
        fields = ('id', 'role', 'amount', 'currency', 'is_active', 'updated_at')
        read_only_fields = ('id', 'updated_at')
