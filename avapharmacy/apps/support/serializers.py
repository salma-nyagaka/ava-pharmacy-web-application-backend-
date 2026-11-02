from django.core.validators import URLValidator
from django.core.exceptions import ValidationError as DjangoValidationError
from django.urls import reverse
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


    def validate(self, attrs):
        for field in ('base_delivery_fee', 'free_delivery_threshold'):
            if attrs.get(field, 0) < 0:
                raise serializers.ValidationError({field: 'The amount cannot be negative.'})
        for field in ('complaint_policy_url', 'privacy_policy_url', 'returns_policy_url'):
            value = attrs.get(field)
            if value:
                local_path = value.startswith('/') and not value.startswith('//') and '\\' not in value and not any(ord(char) < 32 for char in value)
                if not local_path:
                    try:
                        URLValidator(schemes=['http', 'https'])(value)
                    except DjangoValidationError:
                        raise serializers.ValidationError({field: 'Use a local path or a valid HTTP(S) URL.'})

        return attrs


class ComplianceEvidenceSerializer(serializers.ModelSerializer):
    file = serializers.SerializerMethodField()
    upload = serializers.FileField(write_only=True, required=False, source='file')

    def get_file(self, obj):
        if not obj.file:
            return None
        path = reverse('compliance-evidence-download', args=[obj.pk])
        request = self.context.get('request')
        return request.build_absolute_uri(path) if request else path

    def to_internal_value(self, data):
        if 'file' in data and 'upload' not in data:
            data = data.copy()
            data['upload'] = data['file']
        return super().to_internal_value(data)

    def validate_upload(self, file):
        if file.size > 10 * 1024 * 1024:
            raise serializers.ValidationError('Maximum file size is 10 MB.')
        header = file.read(8); file.seek(0)
        if not (header.startswith(b'%PDF-') or header == b'\x89PNG\r\n\x1a\n' or header.startswith(b'\xff\xd8\xff')):
            raise serializers.ValidationError('Upload a PDF, PNG or JPEG file.')
        return file

    def validate(self, attrs):
        issued = attrs.get('issued_at', getattr(self.instance, 'issued_at', None))
        expires = attrs.get('expires_at', getattr(self.instance, 'expires_at', None))
        if issued and expires and expires < issued:
            raise serializers.ValidationError({'expires_at': 'Expiry cannot precede issue date.'})
        return attrs

    evidence_type_display = serializers.ReadOnlyField(source='get_evidence_type_display')
    status_display = serializers.ReadOnlyField(source='get_status_display')
    created_by_name = serializers.ReadOnlyField(source='created_by.full_name')
    updated_by_name = serializers.ReadOnlyField(source='updated_by.full_name')

    class Meta:
        model = ComplianceEvidence
        fields = (
            'id', 'evidence_type', 'evidence_type_display', 'title', 'reference_number',
            'issuing_authority', 'file', 'upload', 'external_url', 'issued_at', 'expires_at',
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
        fields = ('id', 'author', 'author_name', 'message', 'is_internal', 'created_at')
        read_only_fields = ('id', 'author', 'author_name', 'created_at')


class SupportTicketSerializer(serializers.ModelSerializer):
    notes = serializers.SerializerMethodField()

    def get_notes(self, obj):
        request = self.context.get('request')
        notes = obj.notes.all()
        if not request or request.user.role != 'admin':
            notes = [note for note in notes if not note.is_internal]
        return SupportNoteSerializer(notes, many=True).data
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


    def validate_assigned_to(self, user):
        if user and (user.role != 'admin' or not user.is_active or user.status != 'active'):
            raise serializers.ValidationError('Assign an active support administrator.')
        return user


class SupportNoteCreateSerializer(serializers.Serializer):
    message = serializers.CharField(max_length=10000)
    is_internal = serializers.BooleanField(default=False)
