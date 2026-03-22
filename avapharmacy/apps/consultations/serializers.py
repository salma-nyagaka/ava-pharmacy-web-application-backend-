from rest_framework import serializers

from .models import (
    ClinicianDocument,
    ClinicianEarning,
    ClinicianPrescription,
    ClinicianProfile,
    Consultation,
    ConsultationMessage,
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
            'id', 'reference', 'user', 'name', 'type', 'specialty', 'email', 'phone',
            'license_number', 'license_board', 'license_country', 'license_expiry', 'id_number',
            'facility', 'availability', 'bio', 'languages', 'consult_modes',
            'years_experience', 'county', 'address', 'references', 'document_checklist',
            'payout_method', 'payout_account',
            'background_consent', 'compliance_declaration', 'agreed_to_terms',
            'status', 'status_note', 'rejection_note',
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
            'id', 'reference', 'user', 'name', 'specialty', 'email', 'phone',
            'license_number', 'license_board', 'license_country', 'license_expiry', 'id_number',
            'facility', 'availability', 'bio', 'languages', 'consult_modes',
            'years_experience', 'county', 'address', 'references', 'document_checklist',
            'payout_method', 'payout_account',
            'background_consent', 'compliance_declaration', 'agreed_to_terms',
            'status', 'status_note', 'rejection_note',
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
    class Meta:
        model = ConsultationMessage
        fields = ('id', 'sender', 'sender_name', 'message', 'sent_at')
        read_only_fields = ('id', 'sent_at')


class ConsultationSerializer(serializers.ModelSerializer):
    doctor = ClinicianCompatibilityField(provider_type=ClinicianProfile.TYPE_DOCTOR, source='clinician', required=False, allow_null=True)
    pediatrician = ClinicianCompatibilityField(provider_type=ClinicianProfile.TYPE_PEDIATRICIAN, source='clinician', required=False, allow_null=True)
    doctor_name = serializers.ReadOnlyField(source='provider_name')
    doctor_specialty = serializers.ReadOnlyField(source='provider_specialty')
    messages = ConsultationMessageSerializer(many=True, read_only=True)

    class Meta:
        model = Consultation
        fields = (
            'id', 'reference', 'doctor', 'pediatrician', 'doctor_name', 'doctor_specialty',
            'patient', 'patient_name', 'patient_email', 'patient_phone', 'patient_age', 'issue', 'status', 'priority',
            'channel', 'scheduled_at', 'is_pediatric', 'guardian_name', 'child_name',
            'child_age', 'weight_kg', 'consent_status', 'dosage_alert',
            'last_message_at', 'messages', 'created_at', 'updated_at'
        )
        read_only_fields = ('id', 'reference', 'patient', 'created_at', 'updated_at')


class ConsultationListSerializer(serializers.ModelSerializer):
    doctor_name = serializers.ReadOnlyField(source='provider_name')
    doctor_specialty = serializers.ReadOnlyField(source='provider_specialty')

    class Meta:
        model = Consultation
        fields = (
            'id', 'reference', 'doctor_name', 'doctor_specialty', 'patient_name', 'issue',
            'status', 'priority', 'scheduled_at', 'is_pediatric', 'child_name',
            'consent_status', 'last_message_at', 'created_at'
        )


class ConsultationCreateSerializer(serializers.ModelSerializer):
    doctor = serializers.IntegerField(required=False, allow_null=True, write_only=True)
    pediatrician = serializers.IntegerField(required=False, allow_null=True, write_only=True)

    class Meta:
        model = Consultation
        fields = (
            'doctor', 'pediatrician', 'patient_name', 'patient_email', 'patient_phone', 'patient_age', 'issue', 'priority',
            'scheduled_at', 'is_pediatric', 'guardian_name', 'child_name',
            'child_age', 'weight_kg'
        )

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
        if clinician is None:
            raise serializers.ValidationError('A doctor or pediatrician is required.')
        attrs['clinician'] = clinician
        return attrs


class ConsultationUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Consultation
        fields = ('status', 'consent_status', 'dosage_alert')


class DoctorPrescriptionSerializer(serializers.ModelSerializer):
    doctor = ClinicianCompatibilityField(provider_type=ClinicianProfile.TYPE_DOCTOR, source='clinician', required=False, allow_null=True)

    class Meta:
        model = ClinicianPrescription
        fields = ('id', 'reference', 'doctor', 'consultation', 'patient_name', 'items', 'status', 'notes', 'created_at')
        read_only_fields = ('id', 'reference', 'created_at')


class PediatricianPrescriptionSerializer(serializers.ModelSerializer):
    pediatrician = ClinicianCompatibilityField(provider_type=ClinicianProfile.TYPE_PEDIATRICIAN, source='clinician', required=False, allow_null=True)

    class Meta:
        model = ClinicianPrescription
        fields = ('id', 'reference', 'pediatrician', 'consultation', 'patient_name', 'items', 'status', 'notes', 'created_at')
        read_only_fields = ('id', 'reference', 'created_at')


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
