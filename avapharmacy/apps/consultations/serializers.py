from rest_framework import serializers

from .models import (
    ChildPatient,
    ClinicianDocument,
    ClinicianEarning,
    ClinicianPrescription,
    ClinicianProfile,
    Consultation,
    ConsultationMessage,
    ConsultationPaymentIntent,
)


def _guardian_snapshot(user):
    if not user or not getattr(user, 'is_authenticated', False):
        return {}
    return {
        'id': user.id,
        'name': user.full_name,
        'email': user.email,
        'phone': user.phone,
    }


def _child_snapshot(child):
    if not child:
        return {}
    return {
        'id': child.id,
        'reference': child.reference,
        'first_name': child.first_name,
        'last_name': child.last_name,
        'full_name': child.full_name,
        'date_of_birth': child.date_of_birth.isoformat() if child.date_of_birth else None,
        'age_years': child.age_years,
        'gender': child.gender,
        'weight_kg': str(child.weight_kg) if child.weight_kg is not None else None,
        'height_cm': str(child.height_cm) if child.height_cm is not None else None,
        'bmi': str(child.bmi) if child.bmi is not None else None,
        'muac_cm': str(child.muac_cm) if child.muac_cm is not None else None,
        'blood_glucose_mmol_l': str(child.blood_glucose_mmol_l) if child.blood_glucose_mmol_l is not None else None,
        'allergies': child.allergies or [],
        'chronic_conditions': child.chronic_conditions or [],
        'current_medications': child.current_medications or [],
        'vaccination_notes': child.vaccination_notes or '',
        'notes': child.notes or '',
    }


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


def _serialize_consultation_prescription_item(item):
    return {
        'drug_name': item.get('drug_name') or item.get('name') or item.get('catalog_name') or '',
        'dose': item.get('dose') or item.get('dosage') or '',
        'frequency': item.get('frequency') or '',
        'duration': item.get('duration') or '',
        'quantity': item.get('quantity') or 1,
        'notes': item.get('notes') or item.get('note') or '',
        'catalog_name': item.get('catalog_name') or '',
        'sku': item.get('sku') or '',
    }


def _serialize_consultation_prescription(prescription):
    raw_items = prescription.items if isinstance(prescription.items, list) else []
    items = [
        _serialize_consultation_prescription_item(item)
        for item in raw_items
        if isinstance(item, dict)
    ]
    return {
        'id': prescription.id,
        'reference': prescription.reference,
        'status': prescription.status,
        'items_count': len(items),
        'items': items,
        'notes': prescription.notes or '',
        'sent_at': prescription.sent_at.isoformat() if prescription.sent_at else None,
        'created_at': prescription.created_at.isoformat() if prescription.created_at else None,
    }


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


class ChildPatientSerializer(serializers.ModelSerializer):
    full_name = serializers.ReadOnlyField()

    class Meta:
        model = ChildPatient
        fields = (
            'id', 'reference', 'guardian', 'first_name', 'last_name', 'full_name',
            'date_of_birth', 'age_years', 'gender', 'weight_kg', 'height_cm', 'bmi', 'muac_cm',
            'blood_glucose_mmol_l', 'allergies',
            'chronic_conditions', 'current_medications', 'vaccination_notes',
            'notes', 'is_active', 'created_at', 'updated_at',
        )
        read_only_fields = ('id', 'reference', 'guardian', 'full_name', 'is_active', 'created_at', 'updated_at')

    def validate(self, attrs):
        if not attrs.get('date_of_birth') and attrs.get('age_years') is None and self.instance is None:
            raise serializers.ValidationError({'age_years': 'Provide age or date of birth.'})
        return attrs

    def create(self, validated_data):
        request = self.context.get('request')
        return ChildPatient.objects.create(guardian=request.user, **validated_data)


class ChildPatientSummarySerializer(serializers.ModelSerializer):
    full_name = serializers.ReadOnlyField()

    class Meta:
        model = ChildPatient
        fields = (
            'id', 'reference', 'first_name', 'last_name', 'full_name',
            'date_of_birth', 'age_years', 'gender', 'weight_kg', 'height_cm', 'bmi', 'muac_cm',
            'blood_glucose_mmol_l',
            'allergies', 'chronic_conditions', 'current_medications',
            'vaccination_notes', 'notes',
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
    child_patient_detail = ChildPatientSummarySerializer(source='child_patient', read_only=True)
    messages = ConsultationMessageSerializer(many=True, read_only=True)
    prescriptions = serializers.SerializerMethodField()

    class Meta:
        model = Consultation
        fields = (
            'id', 'reference', 'doctor', 'pediatrician', 'doctor_name', 'doctor_specialty',
            'patient', 'patient_name', 'patient_email', 'patient_phone', 'patient_age', 'issue', 'status', 'priority',
            'channel', 'scheduled_at', 'requested_specialty', 'is_pediatric', 'child_patient',
            'child_patient_detail', 'guardian_name', 'child_name',
            'child_age', 'weight_kg', 'height_cm', 'bmi', 'muac_cm', 'blood_glucose_mmol_l',
            'guardian_snapshot', 'child_snapshot', 'consent_status', 'dosage_alert',
            'last_message_at', 'ended_at', 'messages', 'prescriptions', 'created_at', 'updated_at'
        )
        read_only_fields = ('id', 'reference', 'patient', 'created_at', 'updated_at')

    def get_prescriptions(self, obj):
        prescriptions = obj.clinician_prescriptions.exclude(status=ClinicianPrescription.STATUS_DRAFT)
        return [_serialize_consultation_prescription(prescription) for prescription in prescriptions]


class ConsultationListSerializer(serializers.ModelSerializer):
    doctor = serializers.SerializerMethodField()
    pediatrician = serializers.SerializerMethodField()
    doctor_name = serializers.ReadOnlyField(source='provider_name')
    patient_name = serializers.SerializerMethodField()
    issue = serializers.SerializerMethodField()
    prescriptions = serializers.SerializerMethodField()
    messages = serializers.SerializerMethodField()

    class Meta:
        model = Consultation
        fields = (
            'id', 'reference', 'doctor', 'pediatrician', 'doctor_name', 'patient_name', 'issue',
            'status', 'priority', 'requested_specialty', 'is_pediatric', 'child_patient',
            'guardian_name', 'child_name', 'child_age', 'weight_kg', 'height_cm', 'bmi', 'muac_cm',
            'blood_glucose_mmol_l', 'consent_status', 'dosage_alert',
            'last_message_at', 'created_at',
            'messages', 'prescriptions'
        )

    def get_doctor(self, obj):
        return obj.clinician_id if obj.clinician and obj.clinician.provider_type == ClinicianProfile.TYPE_DOCTOR else None

    def get_pediatrician(self, obj):
        return obj.clinician_id if obj.clinician and obj.clinician.provider_type == ClinicianProfile.TYPE_PEDIATRICIAN else None

    def get_messages(self, obj):
        if self._is_limited_open_queue_record(obj):
            return []
        return ConsultationMessageSerializer(obj.messages.all(), many=True, context=self.context).data

    def _is_limited_open_queue_record(self, obj):
        request = self.context.get('request')
        user = getattr(request, 'user', None)
        return (
            user
            and getattr(user, 'role', '') in ['doctor', 'pediatrician']
            and obj.clinician_id is None
        )

    def get_patient_name(self, obj):
        if not self._is_limited_open_queue_record(obj):
            return obj.patient_name
        parts = [part for part in (obj.patient_name or 'Patient').split() if part]
        if not parts:
            return 'Patient'
        if len(parts) == 1:
            return parts[0]
        return f"{parts[0]} {parts[-1][0]}."

    def get_issue(self, obj):
        issue = obj.issue or ''
        if not self._is_limited_open_queue_record(obj):
            return issue
        summary = issue.replace('\n', ' ').strip()
        if len(summary) > 120:
            return f'{summary[:117].rstrip()}...'
        return summary

    def get_prescriptions(self, obj):
        prescriptions = obj.clinician_prescriptions.exclude(status=ClinicianPrescription.STATUS_DRAFT)
        return [_serialize_consultation_prescription(prescription) for prescription in prescriptions]


class ConsultationCreateSerializer(serializers.ModelSerializer):
    doctor = serializers.IntegerField(required=False, allow_null=True, write_only=True)
    pediatrician = serializers.IntegerField(required=False, allow_null=True, write_only=True)
    child_patient_id = serializers.IntegerField(required=False, allow_null=True, write_only=True)

    class Meta:
        model = Consultation
        fields = (
            'doctor', 'pediatrician', 'patient_name', 'patient_email', 'patient_phone',
            'patient_age', 'issue', 'requested_specialty', 'priority', 'scheduled_at', 'is_pediatric',
            'child_patient_id', 'guardian_name', 'child_name',
            'child_age', 'weight_kg', 'height_cm', 'bmi', 'muac_cm', 'blood_glucose_mmol_l'
        )

    def _preferred_specialty_from_issue(self, issue):
        marker = 'Preferred specialty:'
        for line in str(issue or '').splitlines():
            if marker.lower() in line.lower():
                return line.split(':', 1)[1].strip()
        return ''

    def _default_doctor_for_issue(self, issue, requested_specialty=''):
        doctors = ClinicianProfile.objects.doctors().active().select_related('user').order_by('id')
        preferred_specialty = (requested_specialty or self._preferred_specialty_from_issue(issue)).strip()
        if preferred_specialty:
            specialty_doctors = doctors.filter(specialty__iexact=preferred_specialty)
            clinician = specialty_doctors.first()
            if clinician:
                return clinician
        return doctors.first()

    def create(self, validated_data):
        validated_data.pop('_billing_clinician', None)
        open_doctor_queue = validated_data.pop('_open_doctor_queue', False)
        if open_doctor_queue:
            validated_data['clinician'] = None
        return super().create(validated_data)

    def validate(self, attrs):
        request = self.context.get('request')
        user = getattr(request, 'user', None)
        doctor_identifier = attrs.pop('doctor', None)
        pediatrician_identifier = attrs.pop('pediatrician', None)
        child_patient_id = attrs.pop('child_patient_id', None)
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
            clinician = self._default_doctor_for_issue(attrs.get('issue'), attrs.get('requested_specialty'))
            attrs['_open_doctor_queue'] = True
        if clinician is None:
            raise serializers.ValidationError('A doctor or pediatrician is required.')
        if clinician.status != ClinicianProfile.STATUS_ACTIVE:
            field = 'pediatrician' if clinician.provider_type == ClinicianProfile.TYPE_PEDIATRICIAN else 'doctor'
            raise serializers.ValidationError({field: 'Selected clinician is not active.'})
        if clinician.user_id and (not clinician.user.is_active or clinician.user.status != 'active'):
            field = 'pediatrician' if clinician.provider_type == ClinicianProfile.TYPE_PEDIATRICIAN else 'doctor'
            raise serializers.ValidationError({field: 'Selected clinician account is not active.'})
        if clinician.provider_type == ClinicianProfile.TYPE_PEDIATRICIAN:
            if not child_patient_id:
                raise serializers.ValidationError({'child_patient_id': 'Select a registered child before booking a pediatrician.'})
            child = ChildPatient.objects.filter(pk=child_patient_id, is_active=True).first()
            if child is None:
                raise serializers.ValidationError({'child_patient_id': 'Selected child was not found.'})
            if user and getattr(user, 'is_authenticated', False) and child.guardian_id != user.id:
                raise serializers.ValidationError({'child_patient_id': 'Selected child does not belong to this guardian.'})
            attrs['child_patient'] = child
            attrs['is_pediatric'] = True
            attrs['guardian_name'] = attrs.get('guardian_name') or (user.full_name if user else child.guardian.full_name)
            attrs['child_name'] = child.full_name
            attrs['child_age'] = child.age_years
            if child.weight_kg is not None:
                attrs['weight_kg'] = child.weight_kg
            for field in ('height_cm', 'bmi', 'muac_cm', 'blood_glucose_mmol_l'):
                value = getattr(child, field)
                if value is not None:
                    attrs[field] = value
            attrs['guardian_snapshot'] = _guardian_snapshot(user or child.guardian)
            attrs['child_snapshot'] = _child_snapshot(child)
        elif child_patient_id:
            raise serializers.ValidationError({'child_patient_id': 'Child profiles are only used for pediatric consultations.'})
        attrs['_billing_clinician'] = clinician
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
    is_paid_for = serializers.SerializerMethodField()
    child_patient = serializers.SerializerMethodField()
    guardian_name = serializers.SerializerMethodField()

    class Meta:
        model = ClinicianPrescription
        fields = (
            'id', 'reference', 'doctor', 'consultation', 'patient_name', 'items',
            'status', 'digital_signature', 'notes', 'sent_at', 'dispensed_at', 'created_at',
            'is_paid_for', 'child_patient', 'guardian_name',
        )
        read_only_fields = ('id', 'reference', 'created_at')

    def validate_items(self, value):
        return validate_clinician_prescription_items(value)

    def get_is_paid_for(self, obj):
        from apps.orders.models import Order

        return obj.linked_prescriptions.filter(
            items__order_items__order__payment_status=Order.PAYMENT_STATUS_PAID,
        ).exclude(
            items__order_items__order__status__in=[Order.STATUS_CANCELLED, Order.STATUS_REFUNDED],
        ).exists()

    def get_child_patient(self, obj):
        return obj.consultation.child_patient_id if obj.consultation_id else None

    def get_guardian_name(self, obj):
        return obj.consultation.guardian_name if obj.consultation_id and obj.consultation.is_pediatric else ''


class PediatricianPrescriptionSerializer(serializers.ModelSerializer):
    pediatrician = ClinicianCompatibilityField(provider_type=ClinicianProfile.TYPE_PEDIATRICIAN, source='clinician', required=False, allow_null=True)
    is_paid_for = serializers.SerializerMethodField()
    child_patient = serializers.SerializerMethodField()
    guardian_name = serializers.SerializerMethodField()

    class Meta:
        model = ClinicianPrescription
        fields = (
            'id', 'reference', 'pediatrician', 'consultation', 'patient_name', 'items',
            'status', 'digital_signature', 'notes', 'sent_at', 'dispensed_at', 'created_at',
            'is_paid_for', 'child_patient', 'guardian_name',
        )
        read_only_fields = ('id', 'reference', 'created_at')

    def validate_items(self, value):
        return validate_clinician_prescription_items(value)

    def get_is_paid_for(self, obj):
        from apps.orders.models import Order

        return obj.linked_prescriptions.filter(
            items__order_items__order__payment_status=Order.PAYMENT_STATUS_PAID,
        ).exclude(
            items__order_items__order__status__in=[Order.STATUS_CANCELLED, Order.STATUS_REFUNDED],
        ).exists()

    def get_child_patient(self, obj):
        return obj.consultation.child_patient_id if obj.consultation_id else None

    def get_guardian_name(self, obj):
        return obj.consultation.guardian_name if obj.consultation_id else ''


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

        dose = str(item.get('dose') or item.get('dosage') or '').strip()
        frequency = str(item.get('frequency') or '').strip()
        duration = str(item.get('duration') or '').strip()
        quantity_measurement = str(item.get('quantity_measurement') or item.get('measurement') or 'unit(s)').strip()
        item['dose'] = dose
        item['frequency'] = frequency
        item['duration'] = duration
        item['quantity_measurement'] = quantity_measurement

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
