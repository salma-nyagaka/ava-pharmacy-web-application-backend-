from rest_framework import serializers

from .models import (
    ClinicianDocument,
    ClinicianEarning,
    ClinicianPrescription,
    ClinicianProfile,
    Consultation,
    ConsultationMessage,
    ConsultationPaymentIntent,
)


def _resolve_clinician_identifier(value, provider_type):
    if value in (None, '', 0, '0'):
        return None

    queryset = ClinicianProfile.objects.filter(provider_type=provider_type)
    legacy_field = 'legacy_doctor_id' if provider_type == ClinicianProfile.TYPE_DOCTOR else 'legacy_pediatrician_id'
    return queryset.filter(pk=value).first() or queryset.filter(**{legacy_field: value}).first()


def _validate_unique_professional_phone(phone, instance=None):
    phone = (phone or '').strip()
    if not phone:
        return phone

    from apps.accounts.models import User

    if User.objects.filter(phone=phone).exists():
        raise serializers.ValidationError('A user with this phone number already exists.')

    clinician_qs = ClinicianProfile.objects.filter(phone=phone)
    if instance is not None:
        clinician_qs = clinician_qs.exclude(pk=instance.pk)
    if clinician_qs.exists():
        raise serializers.ValidationError('An application with this phone number already exists.')
    return phone


def _validate_unique_professional_email(email, instance=None):
    from apps.accounts.models import User

    if User.objects.filter(email=email).exists():
        raise serializers.ValidationError('A user with this email already exists.')

    clinician_qs = ClinicianProfile.objects.filter(email=email)
    if instance is not None:
        clinician_qs = clinician_qs.exclude(pk=instance.pk)
    if clinician_qs.exists():
        raise serializers.ValidationError('An application with this email already exists.')
    return email


class ClinicianCompatibilityField(serializers.Field):
    default_error_messages = {
        'invalid': 'Selected clinician was not found.',
    }

    def __init__(self, *, provider_type, **kwargs):
        self.provider_type = provider_type
        super().__init__(**kwargs)

    def to_representation(self, value):
        if value and value.provider_type == self.provider_type:
            return value.pk
        return None

    def to_internal_value(self, data):
        clinician = _resolve_clinician_identifier(data, self.provider_type)
        if clinician is None:
            self.fail('invalid')
        return clinician


class ClinicianDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClinicianDocument
        fields = ('id', 'name', 'file', 'status', 'note', 'uploaded_at')
        read_only_fields = ('id', 'uploaded_at')


class DoctorDocumentSerializer(ClinicianDocumentSerializer):
    pass


class PediatricianDocumentSerializer(ClinicianDocumentSerializer):
    pass


class DoctorProfileSerializer(serializers.ModelSerializer):
    type = serializers.CharField(source='provider_type', read_only=True)
    documents = ClinicianDocumentSerializer(many=True, read_only=True)

    class Meta:
        model = ClinicianProfile
        fields = (
            'id', 'reference', 'user', 'name', 'type', 'gender', 'date_of_birth', 'specialty', 'email', 'phone',
            'license_number', 'license_board', 'license_country', 'license_expiry', 'id_number',
            'facility', 'availability', 'availability_schedule', 'bio', 'languages', 'consult_modes',
            'years_experience', 'county', 'address', 'references', 'document_checklist',
            'payout_method', 'payout_account', 'currency',
            'background_consent', 'compliance_declaration', 'agreed_to_terms',
            'status', 'is_verified', 'status_note', 'rejection_note', 'suspension_reason',
            'commission', 'consult_fee', 'rating',
            'verified_at', 'submitted_at', 'created_at', 'updated_at',
            'created_by', 'updated_by', 'documents'
        )
        read_only_fields = (
            'id', 'reference', 'status', 'verified_at', 'submitted_at',
            'created_at', 'updated_at', 'created_by', 'updated_by'
        )


class PediatricianProfileSerializer(serializers.ModelSerializer):
    documents = ClinicianDocumentSerializer(many=True, read_only=True)

    class Meta:
        model = ClinicianProfile
        fields = (
            'id', 'reference', 'user', 'name', 'gender', 'date_of_birth', 'specialty', 'email', 'phone',
            'license_number', 'license_board', 'license_country', 'license_expiry', 'id_number',
            'facility', 'availability', 'availability_schedule', 'bio', 'languages', 'consult_modes',
            'years_experience', 'county', 'address', 'references', 'document_checklist',
            'payout_method', 'payout_account', 'currency',
            'background_consent', 'compliance_declaration', 'agreed_to_terms',
            'status', 'is_verified', 'status_note', 'rejection_note', 'suspension_reason',
            'commission', 'consult_fee', 'rating',
            'verified_at', 'submitted_at', 'created_at', 'updated_at',
            'created_by', 'updated_by', 'documents'
        )
        read_only_fields = (
            'id', 'reference', 'status', 'verified_at', 'submitted_at',
            'created_at', 'updated_at', 'created_by', 'updated_by'
        )


class DoctorProfileListSerializer(serializers.ModelSerializer):
    type = serializers.CharField(source='provider_type', read_only=True)

    class Meta:
        model = ClinicianProfile
        fields = (
            'id', 'reference', 'name', 'type', 'specialty', 'facility',
            'consult_fee', 'rating', 'availability', 'status'
        )


class PediatricianProfileListSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClinicianProfile
        fields = (
            'id', 'reference', 'name', 'specialty', 'facility',
            'consult_fee', 'rating', 'availability', 'status'
        )


class BaseClinicianOnboardingSerializer(serializers.ModelSerializer):
    documents = serializers.ListField(child=serializers.FileField(), required=False, write_only=True)
    document_names = serializers.ListField(child=serializers.CharField(), required=False, write_only=True)
    cv_files = serializers.ListField(child=serializers.FileField(), required=False, write_only=True)
    provider_type = None

    def validate_email(self, value):
        return _validate_unique_professional_email(value, instance=self.instance)

    def validate_phone(self, value):
        return _validate_unique_professional_phone(value, instance=self.instance)

    def validate_background_consent(self, value):
        if not value:
            raise serializers.ValidationError('Background consent is required.')
        return value

    def validate_compliance_declaration(self, value):
        if not value:
            raise serializers.ValidationError('Compliance declaration is required.')
        return value

    def validate_agreed_to_terms(self, value):
        if not value:
            raise serializers.ValidationError('You must agree to the terms.')
        return value

    def create(self, validated_data):
        documents = validated_data.pop('documents', [])
        document_names = validated_data.pop('document_names', [])
        cv_files = validated_data.pop('cv_files', [])
        request = self.context.get('request')
        actor = request.user if request and getattr(request.user, 'is_authenticated', False) else None
        profile = ClinicianProfile.objects.create(
            provider_type=self.provider_type,
            status=ClinicianProfile.STATUS_PENDING,
            commission=15,
            created_by=actor,
            updated_by=actor,
            **validated_data,
        )
        for index, doc_file in enumerate(documents):
            doc_name = document_names[index] if index < len(document_names) else doc_file.name
            ClinicianDocument.objects.create(clinician=profile, name=doc_name, file=doc_file)
        for cv_file in cv_files:
            ClinicianDocument.objects.create(clinician=profile, name=f'CV: {cv_file.name}', file=cv_file)
        return profile


class DoctorOnboardingSerializer(BaseClinicianOnboardingSerializer):
    provider_type = ClinicianProfile.TYPE_DOCTOR

    class Meta:
        model = ClinicianProfile
        fields = (
            'name', 'specialty', 'email', 'phone',
            'license_number', 'license_board', 'license_country', 'license_expiry', 'id_number',
            'facility', 'availability', 'bio', 'languages', 'consult_modes', 'consult_fee',
            'years_experience', 'county', 'address', 'references', 'document_checklist',
            'payout_method', 'payout_account',
            'background_consent', 'compliance_declaration', 'agreed_to_terms',
            'documents', 'document_names', 'cv_files',
        )


class PediatricianOnboardingSerializer(BaseClinicianOnboardingSerializer):
    provider_type = ClinicianProfile.TYPE_PEDIATRICIAN

    class Meta:
        model = ClinicianProfile
        fields = (
            'name', 'specialty', 'email', 'phone',
            'license_number', 'license_board', 'license_country', 'license_expiry', 'id_number',
            'facility', 'availability', 'bio', 'languages', 'consult_modes', 'consult_fee',
            'years_experience', 'county', 'address', 'references', 'document_checklist',
            'payout_method', 'payout_account',
            'background_consent', 'compliance_declaration', 'agreed_to_terms',
            'documents', 'document_names', 'cv_files',
        )


class AdminDoctorUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClinicianProfile
        fields = ('status', 'status_note', 'rejection_note', 'commission', 'consult_fee', 'verified_at')


class AdminPediatricianUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClinicianProfile
        fields = ('status', 'status_note', 'rejection_note', 'commission', 'consult_fee', 'verified_at')


class ConsultationMessageSerializer(serializers.ModelSerializer):
    message = serializers.CharField(required=False, allow_blank=True)
    attachment = serializers.FileField(required=False, allow_null=True)
    attachment_url = serializers.SerializerMethodField()

    class Meta:
        model = ConsultationMessage
        fields = ('id', 'sender', 'sender_name', 'message', 'message_type', 'attachment', 'attachment_url', 'sent_at')
        read_only_fields = ('id', 'sender', 'sender_name', 'attachment_url', 'sent_at')

    def get_attachment_url(self, obj):
        if not obj.attachment:
            return ''
        from django.urls import reverse

        url = reverse('consultation-message-attachment', args=[obj.id])
        request = self.context.get('request')
        return request.build_absolute_uri(url) if request else url

    def validate(self, attrs):
        message = attrs.get('message', '').strip()
        attachment = attrs.get('attachment')
        message_type = attrs.get('message_type', ConsultationMessage.TYPE_TEXT)
        if not message and not attachment:
            raise serializers.ValidationError('Provide a message or attachment.')
        if message_type == ConsultationMessage.TYPE_IMAGE and attachment is None:
            raise serializers.ValidationError({'attachment': 'Image messages require an attachment.'})
        if message_type == ConsultationMessage.TYPE_FILE and attachment is None:
            raise serializers.ValidationError({'attachment': 'File messages require an attachment.'})
        return attrs


class ConsultationSerializer(serializers.ModelSerializer):
    doctor = ClinicianCompatibilityField(provider_type=ClinicianProfile.TYPE_DOCTOR, source='clinician', required=False, allow_null=True)
    pediatrician = ClinicianCompatibilityField(provider_type=ClinicianProfile.TYPE_PEDIATRICIAN, source='clinician', required=False, allow_null=True)
    doctor_name = serializers.ReadOnlyField(source='provider_name')
    doctor_specialty = serializers.ReadOnlyField(source='provider_specialty')
    messages = ConsultationMessageSerializer(many=True, read_only=True)
    prescriptions = serializers.SerializerMethodField()

    class Meta:
        model = Consultation
        fields = (
            'id', 'reference', 'doctor', 'pediatrician', 'doctor_name', 'doctor_specialty',
            'patient', 'patient_name', 'patient_email', 'patient_phone', 'patient_age', 'issue', 'status', 'priority',
            'channel', 'scheduled_at', 'is_pediatric', 'guardian_name', 'child_name',
            'child_age', 'weight_kg', 'consent_status', 'dosage_alert',
            'last_message_at', 'ended_at', 'messages', 'prescriptions', 'created_at', 'updated_at'
        )
        read_only_fields = ('id', 'reference', 'patient', 'created_at', 'updated_at')

    def get_prescriptions(self, obj):
        prescriptions = obj.clinician_prescriptions.exclude(status=ClinicianPrescription.STATUS_DRAFT)
        return [
            {
                'id': prescription.id,
                'reference': prescription.reference,
                'status': prescription.status,
                'items_count': len(prescription.items or []),
                'sent_at': prescription.sent_at.isoformat() if prescription.sent_at else None,
                'created_at': prescription.created_at.isoformat() if prescription.created_at else None,
            }
            for prescription in prescriptions
        ]


class ConsultationListSerializer(serializers.ModelSerializer):
    doctor_name = serializers.ReadOnlyField(source='provider_name')

    class Meta:
        model = Consultation
        fields = (
            'id', 'reference', 'doctor_name', 'patient_name', 'issue',
            'status', 'priority', 'is_pediatric', 'last_message_at', 'created_at'
        )


class ConsultationCreateSerializer(serializers.ModelSerializer):
    doctor = serializers.IntegerField(required=False, allow_null=True, write_only=True)
    pediatrician = serializers.IntegerField(required=False, allow_null=True, write_only=True)

    class Meta:
        model = Consultation
        fields = (
            'doctor', 'pediatrician', 'patient_name', 'patient_email', 'patient_phone',
            'patient_age', 'issue', 'priority', 'scheduled_at', 'is_pediatric',
            'guardian_name', 'child_name',
            'child_age', 'weight_kg'
        )

    def _preferred_specialty_from_issue(self, issue):
        marker = 'Preferred specialty:'
        for line in str(issue or '').splitlines():
            if marker.lower() in line.lower():
                return line.split(':', 1)[1].strip()
        return ''

    def _default_doctor_for_issue(self, issue):
        doctors = ClinicianProfile.objects.doctors().active().select_related('user').order_by('id')
        preferred_specialty = self._preferred_specialty_from_issue(issue)
        if preferred_specialty:
            specialty_doctors = doctors.filter(specialty__iexact=preferred_specialty)
            clinician = specialty_doctors.first()
            if clinician:
                return clinician
        return doctors.first()

    def validate(self, attrs):
        doctor_identifier = attrs.pop('doctor', None)
        pediatrician_identifier = attrs.pop('pediatrician', None)
        if doctor_identifier and pediatrician_identifier:
            raise serializers.ValidationError('Select either a doctor or a pediatrician, not both.')
        clinician = None
        if doctor_identifier:
            clinician = _resolve_clinician_identifier(doctor_identifier, ClinicianProfile.TYPE_DOCTOR)
            if clinician is None:
                raise serializers.ValidationError({'doctor': 'Selected doctor was not found.'})
        elif pediatrician_identifier:
            clinician = _resolve_clinician_identifier(pediatrician_identifier, ClinicianProfile.TYPE_PEDIATRICIAN)
            if clinician is None:
                raise serializers.ValidationError({'pediatrician': 'Selected pediatrician was not found.'})
            attrs['is_pediatric'] = True
        elif not attrs.get('is_pediatric'):
            clinician = self._default_doctor_for_issue(attrs.get('issue'))
        if clinician is None:
            raise serializers.ValidationError('A doctor or pediatrician is required.')
        if clinician.status != ClinicianProfile.STATUS_ACTIVE:
            field = 'pediatrician' if clinician.provider_type == ClinicianProfile.TYPE_PEDIATRICIAN else 'doctor'
            raise serializers.ValidationError({field: 'Selected clinician is not active.'})
        if clinician.user_id and (not clinician.user.is_active or clinician.user.status != 'active'):
            field = 'pediatrician' if clinician.provider_type == ClinicianProfile.TYPE_PEDIATRICIAN else 'doctor'
            raise serializers.ValidationError({field: 'Selected clinician account is not active.'})
        attrs['clinician'] = clinician
        return attrs


class ConsultationPaymentIntentSerializer(serializers.ModelSerializer):
    paybill_number = serializers.SerializerMethodField()
    paybill_account_reference = serializers.SerializerMethodField()
    paybill_account_label = serializers.SerializerMethodField()
    paybill_instructions = serializers.SerializerMethodField()

    class Meta:
        model = ConsultationPaymentIntent
        fields = (
            'id', 'provider', 'status', 'reference', 'provider_reference',
            'external_reference', 'phone_number', 'merchant_request_id',
            'checkout_request_id', 'amount', 'currency', 'client_secret',
            'payload', 'last_error', 'processed_at', 'consultation',
            'paybill_number', 'paybill_account_reference', 'paybill_account_label',
            'paybill_instructions', 'created_at', 'updated_at',
        )
        read_only_fields = fields

    def get_paybill_number(self, obj):
        if obj.provider != ConsultationPaymentIntent.PROVIDER_PAYBILL:
            return ''
        from apps.orders.payment_helpers import get_paybill_number
        return get_paybill_number()

    def get_paybill_account_reference(self, obj):
        return obj.external_reference if obj.provider == ConsultationPaymentIntent.PROVIDER_PAYBILL else ''

    def get_paybill_account_label(self, obj):
        if obj.provider != ConsultationPaymentIntent.PROVIDER_PAYBILL:
            return ''
        from apps.orders.payment_helpers import get_paybill_account_label
        return get_paybill_account_label()

    def get_paybill_instructions(self, obj):
        if obj.provider != ConsultationPaymentIntent.PROVIDER_PAYBILL:
            return ''
        from apps.orders.payment_helpers import get_paybill_instructions
        return get_paybill_instructions()


class ConsultationPaymentIntentCreateSerializer(serializers.Serializer):
    provider = serializers.ChoiceField(choices=ConsultationPaymentIntent.PROVIDER_CHOICES)
    phone = serializers.CharField(max_length=20, required=False, allow_blank=True)
    consultation = ConsultationCreateSerializer()


class ConsultationPaymentFinalizeSerializer(serializers.Serializer):
    payment_intent_id = serializers.IntegerField()


class ConsultationUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Consultation
        fields = ('status', 'consent_status', 'dosage_alert')


class DoctorPrescriptionSerializer(serializers.ModelSerializer):
    doctor = ClinicianCompatibilityField(provider_type=ClinicianProfile.TYPE_DOCTOR, source='clinician', required=False, allow_null=True)

    class Meta:
        model = ClinicianPrescription
        fields = (
            'id', 'reference', 'doctor', 'consultation', 'patient_name', 'items',
            'status', 'digital_signature', 'notes', 'sent_at', 'dispensed_at', 'created_at'
        )
        read_only_fields = ('id', 'reference', 'created_at')

    def validate_items(self, value):
        return validate_clinician_prescription_items(value)


class PediatricianPrescriptionSerializer(serializers.ModelSerializer):
    pediatrician = ClinicianCompatibilityField(provider_type=ClinicianProfile.TYPE_PEDIATRICIAN, source='clinician', required=False, allow_null=True)

    class Meta:
        model = ClinicianPrescription
        fields = (
            'id', 'reference', 'pediatrician', 'consultation', 'patient_name', 'items',
            'status', 'digital_signature', 'notes', 'sent_at', 'dispensed_at', 'created_at'
        )
        read_only_fields = ('id', 'reference', 'created_at')

    def validate_items(self, value):
        return validate_clinician_prescription_items(value)


def validate_clinician_prescription_items(items):
    if not isinstance(items, list) or not items:
        raise serializers.ValidationError('Add at least one medication item.')

    from apps.products.models import Variant

    validated = []
    for index, raw_item in enumerate(items):
        if not isinstance(raw_item, dict):
            raise serializers.ValidationError({index: 'Medication item must be an object.'})

        item = raw_item.copy()
        variant_id = item.get('variant_id') or item.get('product_variant_id')
        is_catalog_fallback = bool(item.get('catalog_fallback') or item.get('is_catalog_fallback'))

        try:
            quantity = int(item.get('quantity') or 1)
        except (TypeError, ValueError):
            raise serializers.ValidationError({index: {'quantity': 'Quantity must be a whole number.'}})
        if quantity < 1:
            raise serializers.ValidationError({index: {'quantity': 'Quantity must be at least 1.'}})
        item['quantity'] = quantity

        if variant_id:
            try:
                variant = Variant.objects.select_related('product', 'product__brand').prefetch_related('inventories').get(pk=variant_id)
            except Variant.DoesNotExist:
                raise serializers.ValidationError({index: {'variant_id': 'Selected catalog item was not found.'}})
            if not variant.is_active or not variant.product.is_active:
                raise serializers.ValidationError({index: {'variant_id': 'Selected catalog item is inactive.'}})
            if variant.available_quantity < quantity:
                raise serializers.ValidationError({index: {'quantity': f'Only {variant.available_quantity} unit(s) are available.'}})

            item['variant_id'] = variant.id
            item['product_variant_id'] = variant.id
            item['product_id'] = variant.product_id
            item['sku'] = variant.sku
            item['drug_name'] = item.get('drug_name') or f'{variant.product.name} {variant.name}'.strip()
            item['catalog_name'] = f'{variant.product.name} {variant.name}'.strip()
            item['requires_prescription'] = variant.requires_prescription
            item['stock_status'] = variant.inventory_status
            item['available_quantity'] = variant.available_quantity
            item['catalog_fallback'] = False
        else:
            if not is_catalog_fallback:
                raise serializers.ValidationError({index: {'variant_id': 'Select a catalog item or mark this as a non-catalog item for pharmacist review.'}})
            if not str(item.get('drug_name') or item.get('name') or '').strip():
                raise serializers.ValidationError({index: {'drug_name': 'Enter the medication name.'}})
            item['catalog_fallback'] = True

        validated.append(item)
    return validated


class DoctorEarningSerializer(serializers.ModelSerializer):
    doctor = ClinicianCompatibilityField(provider_type=ClinicianProfile.TYPE_DOCTOR, source='clinician', required=False, allow_null=True)

    class Meta:
        model = ClinicianEarning
        fields = ('id', 'doctor', 'consultation', 'amount', 'description', 'earned_at')
        read_only_fields = ('id', 'earned_at')


class PediatricianEarningSerializer(serializers.ModelSerializer):
    pediatrician = ClinicianCompatibilityField(provider_type=ClinicianProfile.TYPE_PEDIATRICIAN, source='clinician', required=False, allow_null=True)

    class Meta:
        model = ClinicianEarning
        fields = ('id', 'pediatrician', 'consultation', 'amount', 'description', 'earned_at')
        read_only_fields = ('id', 'earned_at')


class DoctorOnboardingProfileStepSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClinicianProfile
        fields = ('name', 'gender', 'date_of_birth', 'phone', 'bio')


class DoctorOnboardingAvailabilityStepSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClinicianProfile
        fields = ('consult_fee', 'currency', 'availability_schedule')

    def validate_availability_schedule(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError('availability_schedule must be a list.')
        for item in value:
            if not isinstance(item, dict):
                raise serializers.ValidationError('Each availability slot must be an object.')
            for key in ('day', 'start_time', 'end_time'):
                if not item.get(key):
                    raise serializers.ValidationError(f'Availability slot missing {key}.')
        return value


class DoctorOnboardingPayoutStepSerializer(serializers.ModelSerializer):
    payout_account_number = serializers.CharField(max_length=255)

    class Meta:
        model = ClinicianProfile
        fields = ('payout_method', 'payout_account_number')


class DoctorVerificationActionSerializer(serializers.Serializer):
    reason = serializers.CharField(required=False, allow_blank=True)
