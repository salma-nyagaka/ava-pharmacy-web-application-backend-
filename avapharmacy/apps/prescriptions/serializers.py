from rest_framework import serializers
from .models import (
    Prescription,
    PrescriptionFile,
    PrescriptionItem,
    PrescriptionAuditLog,
    PrescriptionClarificationMessage,
)
from apps.products.models import Product


def _prescription_file_exists(instance):
    field = getattr(instance, 'file', None)
    name = getattr(field, 'name', '')
    if not field or not name:
        return False
    try:
        return field.storage.exists(name)
    except Exception:
        return False


class PrescriptionFileSerializer(serializers.ModelSerializer):
    file = serializers.SerializerMethodField()
    filename = serializers.SerializerMethodField()

    class Meta:
        model = PrescriptionFile
        fields = ('id', 'file', 'filename', 'uploaded_at')
        read_only_fields = ('id', 'uploaded_at')

    def get_file(self, obj):
        if not _prescription_file_exists(obj):
            return ''
        try:
            return obj.file.url
        except Exception:
            return ''

    def get_filename(self, obj):
        if not _prescription_file_exists(obj):
            return ''
        return obj.filename or obj.file.name.rsplit('/', 1)[-1]


class PrescriptionItemSerializer(serializers.ModelSerializer):
    product_id = serializers.IntegerField(required=False, allow_null=True)
    product_name = serializers.ReadOnlyField(source='product.name')
    product_slug = serializers.ReadOnlyField(source='product.slug')
    product_image = serializers.ImageField(source='product.image', read_only=True)

    class Meta:
        model = PrescriptionItem
        fields = (
            'id', 'name', 'product_id', 'product_name', 'product_slug', 'product_image',
            'dose', 'frequency', 'quantity', 'is_controlled_substance',
        )
        read_only_fields = ('id',)

    def validate_product_id(self, value):
        if value in (None, ''):
            return None
        if not Product.objects.filter(pk=value, is_active=True).exists():
            raise serializers.ValidationError('Selected product was not found or is inactive.')
        return value


class PrescriptionAuditLogSerializer(serializers.ModelSerializer):
    performed_by_name = serializers.ReadOnlyField(source='performed_by.full_name')

    class Meta:
        model = PrescriptionAuditLog
        fields = ('id', 'action', 'notes', 'performed_by', 'performed_by_name', 'timestamp')
        read_only_fields = ('id', 'timestamp')


class PrescriptionClarificationMessageSerializer(serializers.ModelSerializer):
    sender_display = serializers.SerializerMethodField()

    class Meta:
        model = PrescriptionClarificationMessage
        fields = (
            'id', 'sender', 'sender_role', 'sender_name', 'sender_display',
            'message', 'created_at', 'updated_at',
        )
        read_only_fields = fields

    def get_sender_display(self, obj):
        if obj.sender_name:
            return obj.sender_name
        if obj.sender:
            return obj.sender.full_name or obj.sender.email
        return obj.get_sender_role_display()


class PrescriptionSerializer(serializers.ModelSerializer):
    files = serializers.SerializerMethodField()
    items = PrescriptionItemSerializer(many=True, read_only=True)
    audit_logs = PrescriptionAuditLogSerializer(many=True, read_only=True)
    clarification_messages = PrescriptionClarificationMessageSerializer(many=True, read_only=True)
    patient_name_display = serializers.ReadOnlyField(source='patient.full_name')
    pharmacist_name = serializers.ReadOnlyField(source='pharmacist.full_name')
    is_overdue = serializers.ReadOnlyField()

    class Meta:
        model = Prescription
        fields = (
            'id', 'reference', 'patient', 'patient_name', 'patient_name_display',
            'doctor_name', 'pharmacist', 'pharmacist_name', 'source', 'status', 'dispatch_status',
            'notes', 'pharmacist_notes', 'clarification_message',
            'files', 'items', 'audit_logs', 'clarification_messages', 'is_overdue',
            'resubmitted_at', 'submitted_at', 'updated_at'
        )
        read_only_fields = ('id', 'reference', 'patient', 'submitted_at', 'updated_at')

    def get_files(self, obj):
        existing_files = [file for file in obj.files.all() if _prescription_file_exists(file)]
        return PrescriptionFileSerializer(existing_files, many=True, context=self.context).data


class PrescriptionUploadItemSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=200)
    dose = serializers.CharField(max_length=100, required=False, allow_blank=True)
    frequency = serializers.CharField(max_length=100, required=False, allow_blank=True)
    quantity = serializers.IntegerField(min_value=1, required=False, default=1)


class PrescriptionUploadSerializer(serializers.Serializer):
    patient_name = serializers.CharField(max_length=200)
    doctor_name = serializers.CharField(max_length=200, required=False, allow_blank=True)
    notes = serializers.CharField(required=False, allow_blank=True)
    items = PrescriptionUploadItemSerializer(many=True, required=False)
    files = serializers.ListField(
        child=serializers.FileField(),
        min_length=1,
        max_length=5,
    )


class PrescriptionUpdateSerializer(serializers.ModelSerializer):
    items = PrescriptionItemSerializer(many=True, required=False)

    class Meta:
        model = Prescription
        fields = ('status', 'dispatch_status', 'pharmacist_notes', 'items')

    def validate(self, attrs):
        next_status = attrs.get('status', self.instance.status)
        items_data = attrs.get('items')
        if next_status != Prescription.STATUS_APPROVED:
            return attrs

        if items_data is None:
            missing_products = list(
                self.instance.items.filter(product__isnull=True).values_list('name', flat=True)
            )
        else:
            missing_products = [
                item.get('name') or 'Unnamed item'
                for item in items_data
                if not item.get('product_id')
            ]

        if missing_products:
            raise serializers.ValidationError({
                'items': (
                    'Approved prescriptions require every item to be mapped to a product. '
                    f'Missing mappings: {", ".join(missing_products)}.'
                )
            })
        return attrs

    def update(self, instance, validated_data):
        items_data = validated_data.pop('items', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if items_data is not None:
            instance.items.all().delete()
            for item_data in items_data:
                product_id = item_data.pop('product_id', None)
                PrescriptionItem.objects.create(
                    prescription=instance,
                    product_id=product_id,
                    **item_data,
                )
        return instance


class PrescriptionAuditCreateSerializer(serializers.Serializer):
    action = serializers.CharField(max_length=500)
    notes = serializers.CharField(required=False, allow_blank=True)


class PharmacistPrescriptionReviewItemSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=200)
    product_id = serializers.IntegerField(required=False, allow_null=True)
    dose = serializers.CharField(max_length=100, required=False, allow_blank=True)
    frequency = serializers.CharField(max_length=100, required=False, allow_blank=True)
    quantity = serializers.IntegerField(min_value=1)


class PharmacistPrescriptionReviewSerializer(serializers.Serializer):
    ACTION_APPROVE = 'approve'
    ACTION_REJECT = 'reject'
    ACTION_REQUEST_CLARIFICATION = 'request_clarification'
    ACTION_CHOICES = [
        (ACTION_APPROVE, 'Approve'),
        (ACTION_REJECT, 'Reject'),
        (ACTION_REQUEST_CLARIFICATION, 'Request Clarification'),
    ]

    action = serializers.ChoiceField(choices=ACTION_CHOICES)
    notes = serializers.CharField(required=False, allow_blank=True)
    items = PharmacistPrescriptionReviewItemSerializer(many=True, required=False)

    def validate(self, attrs):
        action = attrs.get('action')
        notes = (attrs.get('notes') or '').strip()
        if action == self.ACTION_REQUEST_CLARIFICATION and not notes:
            raise serializers.ValidationError({'notes': 'Enter the clarification message for the patient.'})
        return attrs


class PrescriptionResubmitSerializer(serializers.Serializer):
    notes = serializers.CharField(required=False, allow_blank=True)
    files = serializers.ListField(
        child=serializers.FileField(),
        required=False,
        max_length=5,
    )


class PrescriptionClarificationReplySerializer(serializers.Serializer):
    message = serializers.CharField()

    def validate_message(self, value):
        value = (value or '').strip()
        if not value:
            raise serializers.ValidationError('Enter your response before sending.')
        return value
