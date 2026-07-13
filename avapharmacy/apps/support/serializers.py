from rest_framework import serializers
from .models import ComplianceEvidence, NewsletterSubscriber, SiteSettings, SupportTicket, SupportNote


class SiteSettingsSerializer(serializers.ModelSerializer):
    active_delivery_zones_list = serializers.ListField(
        child=serializers.CharField(),
        read_only=True,
    )

    class Meta:
        model = SiteSettings
        fields = (
            'support_email',
            'support_phone',
            'whatsapp_phone',
            'support_address',
            'support_hours',
            'postal_address',
            'health_safety_code',
            'premises_registration_number',
            'online_pharmacy_license_number',
            'superintendent_name',
            'superintendent_registration_number',
            'pharmacist_consultation_hours',
            'ppb_contact_name',
            'ppb_contact_address',
            'ppb_contact_phone',
            'ppb_contact_email',
            'ppb_website',
            'complaint_policy_url',
            'privacy_policy_url',
            'returns_policy_url',
            'base_delivery_fee',
            'free_delivery_threshold',
            'active_delivery_zones',
            'active_delivery_zones_list',
            'updated_at',
        )
        read_only_fields = ('active_delivery_zones_list', 'updated_at')


class ComplianceEvidenceSerializer(serializers.ModelSerializer):
    evidence_type_display = serializers.ReadOnlyField(source='get_evidence_type_display')
    status_display = serializers.ReadOnlyField(source='get_status_display')
    created_by_name = serializers.ReadOnlyField(source='created_by.full_name')
    updated_by_name = serializers.ReadOnlyField(source='updated_by.full_name')

    class Meta:
        model = ComplianceEvidence
        fields = (
            'id', 'evidence_type', 'evidence_type_display', 'title', 'reference_number',
            'issuing_authority', 'file', 'external_url', 'issued_at', 'expires_at',
            'status', 'status_display', 'notes', 'created_by', 'created_by_name',
            'updated_by', 'updated_by_name', 'created_at', 'updated_at',
        )
        read_only_fields = (
            'id', 'evidence_type_display', 'status_display', 'created_by',
            'created_by_name', 'updated_by', 'updated_by_name', 'created_at', 'updated_at',
        )


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
