from rest_framework import serializers
from .models import NewsletterSubscriber, SupportTicket, SupportNote


class NewsletterSubscriptionRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()
    source = serializers.CharField(max_length=100, required=False, allow_blank=True, default='website')

    def validate_email(self, value):
        return value.strip().lower()

    def validate_source(self, value):
        cleaned = value.strip()
        return cleaned or 'website'


class NewsletterSubscriberSerializer(serializers.ModelSerializer):
    class Meta:
        model = NewsletterSubscriber
        fields = ('id', 'email', 'source', 'is_active', 'subscribed_at', 'last_confirmation_sent_at')
        read_only_fields = ('id', 'is_active', 'subscribed_at', 'last_confirmation_sent_at')


class SupportNoteSerializer(serializers.ModelSerializer):
    class Meta:
        model = SupportNote
        fields = ('id', 'author', 'author_name', 'message', 'created_at')
        read_only_fields = ('id', 'author', 'author_name', 'created_at')


class SupportTicketSerializer(serializers.ModelSerializer):
    notes = SupportNoteSerializer(many=True, read_only=True)
    assigned_to_name = serializers.ReadOnlyField(source='assigned_to.full_name')

    class Meta:
        model = SupportTicket
        fields = (
            'id', 'reference', 'customer', 'customer_name', 'customer_email',
            'channel', 'reference_id', 'subject', 'priority', 'status',
            'assigned_to', 'assigned_to_name', 'notes', 'created_at', 'updated_at'
        )
        read_only_fields = ('id', 'reference', 'customer', 'created_at', 'updated_at')


class SupportTicketCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = SupportTicket
        fields = ('channel', 'reference_id', 'subject', 'priority')


class SupportTicketUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = SupportTicket
        fields = ('status', 'priority', 'assigned_to')


class SupportNoteCreateSerializer(serializers.Serializer):
    message = serializers.CharField()
