from django.utils import timezone
from .compliance import EVIDENCE_FIELDS, approval_error, working_day_due
from rest_framework import serializers
from django.core import signing
from django.urls import reverse
from urllib.parse import urlencode
from pathlib import PurePosixPath
from .models import (
    Prescription,
    PrescriptionFile,
    PrescriptionItem,
    PrescriptionAuditLog,
    PrescriptionReviewDecision,
    PrescriptionClarificationMessage,
)
from apps.products.models import Product, Variant
from apps.orders.models import Order


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
            request = self.context.get('request')
            if not request or not request.user.is_authenticated:
                return ''
            token = signing.dumps({'file': obj.pk, 'user': request.user.pk}, salt='prescription-download')
            return request.build_absolute_uri(reverse('prescription-file-download-named', args=[obj.prescription_id, obj.pk, PurePosixPath(obj.filename or obj.file.name).name]) + '?' + urlencode({'token': token}))
        except Exception:
            return ''

    def get_filename(self, obj):
        if not _prescription_file_exists(obj):
            return ''
        return obj.filename or obj.file.name.rsplit('/', 1)[-1]


class PrescriptionItemSerializer(serializers.ModelSerializer):
    product_id = serializers.IntegerField(required=False, allow_null=True)
    variant_id = serializers.IntegerField(required=False, allow_null=True)
    product_name = serializers.ReadOnlyField(source='product.name')
    product_slug = serializers.ReadOnlyField(source='product.slug')
    product_image = serializers.ImageField(source='product.image', read_only=True)
    variant_name = serializers.ReadOnlyField(source='variant.name')
    variant_sku = serializers.ReadOnlyField(source='variant.sku')
    is_paid_for = serializers.SerializerMethodField()

    class Meta:
        model = PrescriptionItem
        fields = (
            'id', 'name', 'product_id', 'product_name', 'product_slug', 'product_image',
            'variant_id', 'variant_name', 'variant_sku',
            'dose', 'frequency', 'duration', 'quantity', 'quantity_measurement',
            'is_controlled_substance', 'is_paid_for',
        )
        read_only_fields = ('id',)

    def get_is_paid_for(self, obj):
        return obj.order_items.filter(
            order__payment_status=Order.PAYMENT_STATUS_PAID,
        ).exclude(order__status__in=[Order.STATUS_CANCELLED, Order.STATUS_REFUNDED]).exists()

    def validate_product_id(self, value):
        if value in (None, ''):
            return None
        if not Product.objects.filter(pk=value, is_active=True).exists():
            raise serializers.ValidationError('Selected product was not found or is inactive.')
        return value

    def validate_variant_id(self, value):
        if value in (None, ''):
            return None
        if not Variant.objects.filter(pk=value, is_active=True, product__is_active=True).exists():
            raise serializers.ValidationError('Selected variant was not found or is inactive.')
        return value


class PrescriptionAuditLogSerializer(serializers.ModelSerializer):
    performed_by_name = serializers.ReadOnlyField(source='performed_by.full_name')

    class Meta:
        model = PrescriptionAuditLog
        fields = ('id', 'action', 'notes', 'performed_by', 'performed_by_name', 'timestamp')
        read_only_fields = ('id', 'timestamp')


class PrescriptionReviewDecisionSerializer(serializers.ModelSerializer):
    pharmacist_name = serializers.ReadOnlyField(source='pharmacist.full_name')

    class Meta:
        model = PrescriptionReviewDecision
        fields = (
            'id', 'action', 'from_status', 'to_status', 'notes',
            'pharmacist', 'pharmacist_name', 'created_at',
        )
        read_only_fields = fields


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
    review_decisions = PrescriptionReviewDecisionSerializer(many=True, read_only=True)
    clarification_messages = PrescriptionClarificationMessageSerializer(many=True, read_only=True)
    patient_name_display = serializers.ReadOnlyField(source='patient.full_name')
    pharmacist_name = serializers.ReadOnlyField(source='pharmacist.full_name')
    clinician_type = serializers.SerializerMethodField()
    is_overdue = serializers.ReadOnlyField()

    class Meta:
        model = Prescription
        fields = (
            'id', 'reference', 'patient', 'patient_name', 'patient_name_display',
            *EVIDENCE_FIELDS[1:], 'verified_by', 'verified_at', 'original_due_on', 'legal_hold', 'doctor_name', 'pharmacist', 'pharmacist_name', 'source', 'clinician_type', 'clinician_prescription', 'status', 'dispatch_status',
            'notes', 'pharmacist_notes', 'clarification_message',
            'files', 'items', 'audit_logs', 'review_decisions', 'clarification_messages', 'is_overdue',
            'resubmitted_at', 'submitted_at', 'updated_at'
        )
        read_only_fields = ('id', 'reference', 'patient', 'clinician_prescription', 'submitted_at', 'updated_at')

    def get_files(self, obj):
        existing_files = [file for file in obj.files.all() if _prescription_file_exists(file)]
        return PrescriptionFileSerializer(existing_files, many=True, context=self.context).data

    def get_clinician_type(self, obj):
        clinician = getattr(getattr(obj, 'clinician_prescription', None), 'clinician', None)
        return getattr(clinician, 'provider_type', '') or ''


class PrescriptionUploadItemSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=200)
    product_id = serializers.IntegerField(required=False, allow_null=True)
    variant_id = serializers.IntegerField(required=False, allow_null=True)
    dose = serializers.CharField(max_length=100, required=False, allow_blank=True)
    frequency = serializers.CharField(max_length=100, required=False, allow_blank=True)
    quantity = serializers.IntegerField(min_value=1, required=False, default=1)

    def validate(self, attrs):
        product_id = attrs.get('product_id')
        variant_id = attrs.get('variant_id')
        if variant_id:
            variant = Variant.objects.filter(pk=variant_id, is_active=True, product__is_active=True).select_related('product').first()
            if not variant:
                raise serializers.ValidationError({'variant_id': 'Selected variant was not found or is inactive.'})
            if product_id and product_id != variant.product_id:
                raise serializers.ValidationError({'product_id': 'Product does not match the selected variant.'})
            attrs['product_id'] = variant.product_id
        elif product_id:
            product = Product.objects.filter(pk=product_id, is_active=True).prefetch_related('variants').first()
            if not product:
                raise serializers.ValidationError({'product_id': 'Selected product was not found or is inactive.'})
            representative_variant = product.get_representative_variant()
            if representative_variant:
                attrs['variant_id'] = representative_variant.id
        return attrs


class PrescriptionUploadSerializer(serializers.Serializer):
    patient_name = serializers.CharField(max_length=200)
    doctor_name = serializers.CharField(max_length=200, required=False, allow_blank=True)
    notes = serializers.CharField(required=False, allow_blank=True)
    items = PrescriptionUploadItemSerializer(many=True, required=False)
    bot_challenge_token = serializers.CharField(required=False, allow_blank=True, write_only=True)
    device_id = serializers.CharField(required=False, allow_blank=True, write_only=True)
    website = serializers.CharField(required=False, allow_blank=True, write_only=True)
    files = serializers.ListField(
        child=serializers.FileField(),
        min_length=1,
        max_length=5,
        error_messages={'max_length': 'You can upload up to 5 prescription files.'},
    )


class PrescriptionUpdateSerializer(serializers.ModelSerializer):
    items = PrescriptionItemSerializer(many=True, required=False)

    class Meta:
        model = Prescription
        fields = ('status', 'dispatch_status', 'pharmacist_notes', 'items', *EVIDENCE_FIELDS)

    def validate(self, attrs):
        instance = self.instance
        if attrs.get('items') is not None and instance.status == 'approved':
            raise serializers.ValidationError({'items': 'Approved prescriptions are permanent; issue a new prescription to change medication.'})
        if attrs.get('items') is not None and instance.items.filter(order_items__isnull=False).exists():
            raise serializers.ValidationError({'items': 'Items linked to an order cannot be replaced.'})
        next_status = attrs.get('status', instance.status)
        items = attrs.get('items')
        if next_status == Prescription.STATUS_APPROVED:
            import copy
            candidate = copy.copy(instance)
            for field in EVIDENCE_FIELDS:
                if field in attrs:
                    setattr(candidate, field, attrs[field])
            if any(field in attrs for field in EVIDENCE_FIELDS):
                candidate.verified_by = self.context['request'].user
                candidate.verified_at = timezone.now()
            error = approval_error(candidate)
            if error:
                raise serializers.ValidationError({'verification': error})
            rows = items if items is not None else list(instance.items.values('name', 'product_id', 'variant_id', 'quantity', 'is_controlled_substance'))
            if not rows:
                raise serializers.ValidationError({'items': 'At least one mapped medication is required.'})
            for row in rows:
                variant = Variant.objects.filter(pk=row.get('variant_id'), is_active=True, product__is_active=True).first()
                if not variant or (row.get('product_id') and row['product_id'] != variant.product_id):
                    raise serializers.ValidationError({'items': 'Select the exact active catalog variant for every medication.'})
                from apps.products.compliance import supply_error
                error = supply_error(variant)
                if error:
                    raise serializers.ValidationError({'items': error})
                from .views import _is_controlled_substance
                if row.get('is_controlled_substance') or _is_controlled_substance(row.get('name'), instance.notes, variant.product.name, variant.name):
                    raise serializers.ValidationError({'items': 'Controlled drugs cannot be supplied online.'})
                if row.get('quantity', 0) < 1:
                    raise serializers.ValidationError({'items': 'Quantity must be at least 1.'})
        dispatch = attrs.get('dispatch_status', instance.dispatch_status)
        if dispatch != instance.dispatch_status:
            states = [value for value, _ in Prescription.DISPATCH_CHOICES]
            if next_status != Prescription.STATUS_APPROVED or states.index(dispatch) != states.index(instance.dispatch_status) + 1:
                raise serializers.ValidationError({'dispatch_status': 'Approve the prescription and progress through queued, packed, dispatched, delivered in order.'})
        if next_status in [Prescription.STATUS_REJECTED, Prescription.STATUS_CLARIFICATION] and not (attrs.get('pharmacist_notes') or instance.pharmacist_notes).strip():
            raise serializers.ValidationError({'pharmacist_notes': 'Enter the rejection reason.'})
        return attrs

    def update(self, instance, validated_data):
        items_data = validated_data.pop('items', None)
        if items_data is not None:
            instance.items.all().delete()
            for item_data in items_data:
                product_id = item_data.pop('product_id', None)
                variant_id = item_data.pop('variant_id', None)
                if variant_id and not product_id:
                    product_id = Variant.objects.filter(pk=variant_id).values_list('product_id', flat=True).first()
                PrescriptionItem.objects.create(prescription=instance, product_id=product_id, variant_id=variant_id, **item_data)
        if any(field in validated_data for field in EVIDENCE_FIELDS):
            instance.verified_by = self.context['request'].user
            instance.verified_at = timezone.now()
            instance.original_due_on = instance.original_due_on or working_day_due(timezone.localdate(instance.submitted_at))
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if 'status' in validated_data:
            instance.clarification_message = instance.pharmacist_notes if instance.status in [Prescription.STATUS_REJECTED, Prescription.STATUS_CLARIFICATION] else ''
        instance.save()
        return instance


class PrescriptionAuditCreateSerializer(serializers.Serializer):
    action = serializers.CharField(max_length=500)
    notes = serializers.CharField(required=False, allow_blank=True)


class PharmacistPrescriptionReviewItemSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=200)
    product_id = serializers.IntegerField(required=False, allow_null=True)
    variant_id = serializers.IntegerField(required=False, allow_null=True)
    dose = serializers.CharField(max_length=100, required=False, allow_blank=True)
    frequency = serializers.CharField(max_length=100, required=False, allow_blank=True)
    quantity = serializers.IntegerField(min_value=1)
    duration = serializers.CharField(max_length=100, required=False, allow_blank=True)
    quantity_measurement = serializers.CharField(max_length=60, required=False, allow_blank=True)

    def validate(self, attrs):
        product_id = attrs.get('product_id')
        variant_id = attrs.get('variant_id')
        if variant_id:
            variant = Variant.objects.filter(pk=variant_id, is_active=True, product__is_active=True).select_related('product').first()
            if not variant:
                raise serializers.ValidationError({'variant_id': 'Selected variant was not found or is inactive.'})
            if product_id and product_id != variant.product_id:
                raise serializers.ValidationError({'product_id': 'Product does not match the selected variant.'})
            attrs['product_id'] = variant.product_id
        elif product_id and not Product.objects.filter(pk=product_id, is_active=True).exists():
            raise serializers.ValidationError({'product_id': 'Selected product was not found or is inactive.'})
        return attrs


class PharmacistPrescriptionReviewSerializer(serializers.Serializer):
    ACTION_APPROVE = 'approve'
    ACTION_REJECT = 'reject'
    ACTION_REQUEST_CLARIFICATION = 'request_clarification'
    ACTION_CHOICES = [
        (ACTION_APPROVE, 'Approve'),
        (ACTION_REJECT, 'Reject'),
        (ACTION_REQUEST_CLARIFICATION, 'Request Clarification'),
    ]

    doctor_name = serializers.CharField(required=False, allow_blank=True)
    prescriber_registration = serializers.CharField(required=False, allow_blank=True)
    prescriber_verification_reference = serializers.CharField(required=False, allow_blank=True)
    authenticity_method = serializers.CharField(required=False, allow_blank=True)
    authenticity_evidence = serializers.CharField(required=False, allow_blank=True)
    original_receipt_reference = serializers.CharField(required=False, allow_blank=True)
    prescribed_on = serializers.DateField(required=False)
    valid_until = serializers.DateField(required=False)
    original_received_at = serializers.DateTimeField(required=False, allow_null=True)
    action = serializers.ChoiceField(choices=ACTION_CHOICES)
    notes = serializers.CharField(required=False, allow_blank=True)
    items = PharmacistPrescriptionReviewItemSerializer(many=True, required=False)

    def validate(self, attrs):
        action = attrs.get('action')
        notes = (attrs.get('notes') or '').strip()
        if action == self.ACTION_REQUEST_CLARIFICATION and not notes:
            raise serializers.ValidationError({'notes': 'Enter the clarification message for the patient.'})
        if action == self.ACTION_REJECT and not notes:
            raise serializers.ValidationError({'notes': 'Enter the rejection reason.'})
        if action == self.ACTION_APPROVE:
            items = attrs.get('items')
            if items is not None:
                missing_products = [
                    item.get('name') or 'Unnamed item'
                    for item in items
                    if not item.get('variant_id')
                ]
                if missing_products:
                    raise serializers.ValidationError({
                        'items': (
                            'Approved prescriptions require every medication to be mapped to a product. '
                            f'Missing: {", ".join(missing_products)}.'
                        )
                    })
        return attrs


class PrescriptionResubmitSerializer(serializers.Serializer):
    notes = serializers.CharField(required=False, allow_blank=True)
    files = serializers.ListField(
        child=serializers.FileField(),
        required=False,
        max_length=5,
        error_messages={'max_length': 'You can upload up to 5 prescription files.'},
    )


class PrescriptionClarificationReplySerializer(serializers.Serializer):
    message = serializers.CharField()

    def validate_message(self, value):
        value = (value or '').strip()
        if not value:
            raise serializers.ValidationError('Enter your response before sending.')
        return value
