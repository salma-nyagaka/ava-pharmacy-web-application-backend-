from rest_framework import serializers
from .models import Notification, NotificationDelivery, NotificationPreference


class NotificationSerializer(serializers.ModelSerializer):
    type_display = serializers.ReadOnlyField(source='get_type_display')

    class Meta:
        model = Notification
        fields = ('id', 'type', 'type_display', 'title', 'message', 'data', 'is_read', 'created_at')
        read_only_fields = ('id', 'type', 'type_display', 'title', 'message', 'data', 'created_at')


class NotificationPreferenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationPreference
        fields = (
            'email_enabled', 'sms_enabled', 'push_enabled',
            'marketing_enabled', 'order_updates_email', 'order_updates_sms',
            'created_at', 'updated_at'
        )
        read_only_fields = ('created_at', 'updated_at')


class NotificationDeliverySerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationDelivery
        fields = (
            'id', 'channel', 'destination', 'subject', 'message', 'provider',
            'provider_reference', 'status', 'error_message', 'metadata',
            'sent_at', 'created_at'
        )
        read_only_fields = fields
