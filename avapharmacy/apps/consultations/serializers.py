from rest_framework import serializers
from .models import (
    DoctorProfile, DoctorDocument, PediatricianProfile, PediatricianDocument,
    Consultation, ConsultationMessage,
    DoctorPrescription, PediatricianPrescription,
    DoctorEarning, PediatricianEarning,
)


def _validate_unique_professional_phone(phone, instance=None):
    phone = (phone or '').strip()
    if not phone:
        return phone

    from apps.accounts.models import User

    user_qs = User.objects.filter(phone=phone)
    if user_qs.exists():
        raise serializers.ValidationError('A user with this phone number already exists.')

    doctor_qs = DoctorProfile.objects.filter(phone=phone)
    pediatrician_qs = PediatricianProfile.objects.filter(phone=phone)
    if instance is not None:
        if isinstance(instance, DoctorProfile):
            doctor_qs = doctor_qs.exclude(pk=instance.pk)
        elif isinstance(instance, PediatricianProfile):
            pediatrician_qs = pediatrician_qs.exclude(pk=instance.pk)
    if doctor_qs.exists() or pediatrician_qs.exists():
        raise serializers.ValidationError('An application with this phone number already exists.')
    return phone


def _validate_unique_professional_email(email, instance=None):
    from apps.accounts.models import User

    if User.objects.filter(email=email).exists():
        raise serializers.ValidationError('A user with this email already exists.')

    doctor_qs = DoctorProfile.objects.filter(email=email)
    pediatrician_qs = PediatricianProfile.objects.filter(email=email)
    if instance is not None:
        if isinstance(instance, DoctorProfile):
            doctor_qs = doctor_qs.exclude(pk=instance.pk)
        elif isinstance(instance, PediatricianProfile):
            pediatrician_qs = pediatrician_qs.exclude(pk=instance.pk)
    if doctor_qs.exists() or pediatrician_qs.exists():
        raise serializers.ValidationError('An application with this email already exists.')
    return email


class DoctorDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = DoctorDocument
        fields = ('id', 'name', 'file', 'status', 'note', 'uploaded_at')
        read_only_fields = ('id', 'uploaded_at')


class PediatricianDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = PediatricianDocument
        fields = ('id', 'name', 'file', 'status', 'note', 'uploaded_at')
        read_only_fields = ('id', 'uploaded_at')


class DoctorProfileSerializer(serializers.ModelSerializer):
    documents = DoctorDocumentSerializer(many=True, read_only=True)

    class Meta:
        model = DoctorProfile
        fields = (
            'id', 'reference', 'user', 'name', 'type', 'specialty', 'email', 'phone',
            'license_number', 'license_board', 'license_country', 'license_expiry', 'id_number',
            'facility', 'availability', 'bio', 'languages', 'consult_modes',
            'years_experience', 'county', 'references', 'document_checklist',
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
    documents = PediatricianDocumentSerializer(many=True, read_only=True)

    class Meta:
        model = PediatricianProfile
        fields = (
            'id', 'reference', 'user', 'name', 'specialty', 'email', 'phone',
            'license_number', 'license_board', 'license_country', 'license_expiry', 'id_number',
            'facility', 'availability', 'bio', 'languages', 'consult_modes',
            'years_experience', 'county', 'references', 'document_checklist',
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
    class Meta:
        model = DoctorProfile
        fields = (
            'id', 'reference', 'name', 'type', 'specialty', 'facility',
            'consult_fee', 'rating', 'availability', 'status'
        )


class PediatricianProfileListSerializer(serializers.ModelSerializer):
    class Meta:
        model = PediatricianProfile
        fields = (
            'id', 'reference', 'name', 'specialty', 'facility',
            'consult_fee', 'rating', 'availability', 'status'
        )


class DoctorOnboardingSerializer(serializers.ModelSerializer):
    documents = serializers.ListField(
        child=serializers.FileField(), required=False, write_only=True
    )
    document_names = serializers.ListField(
        child=serializers.CharField(), required=False, write_only=True
    )
    cv_files = serializers.ListField(
        child=serializers.FileField(), required=False, write_only=True
    )

    class Meta:
        model = DoctorProfile
        fields = (
            'name', 'type', 'specialty', 'email', 'phone',
            'license_number', 'license_board', 'license_country', 'license_expiry', 'id_number',
            'facility', 'availability', 'bio', 'languages', 'consult_modes', 'consult_fee',
            'years_experience', 'county', 'references', 'document_checklist',
            'payout_method', 'payout_account',
            'background_consent', 'compliance_declaration', 'agreed_to_terms',
            'documents', 'document_names', 'cv_files',
        )

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
        profile = DoctorProfile.objects.create(
            status=DoctorProfile.STATUS_PENDING,
            commission=15,
            created_by=actor,
            updated_by=actor,
            **validated_data,
        )
        for i, doc_file in enumerate(documents):
            doc_name = document_names[i] if i < len(document_names) else doc_file.name
            DoctorDocument.objects.create(doctor=profile, name=doc_name, file=doc_file)
        for cv_file in cv_files:
            DoctorDocument.objects.create(doctor=profile, name=f'CV: {cv_file.name}', file=cv_file)

        return profile


class PediatricianOnboardingSerializer(serializers.ModelSerializer):
    documents = serializers.ListField(
        child=serializers.FileField(), required=False, write_only=True
    )
    document_names = serializers.ListField(
        child=serializers.CharField(), required=False, write_only=True
    )
    cv_files = serializers.ListField(
        child=serializers.FileField(), required=False, write_only=True
    )

    class Meta:
        model = PediatricianProfile
        fields = (
            'name', 'specialty', 'email', 'phone',
            'license_number', 'license_board', 'license_country', 'license_expiry', 'id_number',
            'facility', 'availability', 'bio', 'languages', 'consult_modes', 'consult_fee',
            'years_experience', 'county', 'references', 'document_checklist',
            'payout_method', 'payout_account',
            'background_consent', 'compliance_declaration', 'agreed_to_terms',
            'documents', 'document_names', 'cv_files',
        )

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
        profile = PediatricianProfile.objects.create(
            status=PediatricianProfile.STATUS_PENDING,
            commission=15,
            created_by=actor,
            updated_by=actor,
            **validated_data,
        )
        for i, doc_file in enumerate(documents):
            doc_name = document_names[i] if i < len(document_names) else doc_file.name
            PediatricianDocument.objects.create(pediatrician=profile, name=doc_name, file=doc_file)
        for cv_file in cv_files:
            PediatricianDocument.objects.create(pediatrician=profile, name=f'CV: {cv_file.name}', file=cv_file)
        return profile


class AdminDoctorUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = DoctorProfile
        fields = ('status', 'status_note', 'rejection_note', 'commission', 'consult_fee', 'verified_at')


class AdminPediatricianUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = PediatricianProfile
        fields = ('status', 'status_note', 'rejection_note', 'commission', 'consult_fee', 'verified_at')


class ConsultationMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ConsultationMessage
        fields = ('id', 'sender', 'sender_name', 'message', 'sent_at')
        read_only_fields = ('id', 'sent_at')


class ConsultationSerializer(serializers.ModelSerializer):
    doctor_name = serializers.ReadOnlyField(source='provider_name')
    doctor_specialty = serializers.ReadOnlyField(source='provider_specialty')
    messages = ConsultationMessageSerializer(many=True, read_only=True)

    class Meta:
        model = Consultation
        fields = (
            'id', 'reference', 'doctor', 'pediatrician', 'doctor_name', 'doctor_specialty',
            'patient', 'patient_name', 'patient_age', 'issue', 'status', 'priority',
            'channel', 'scheduled_at', 'is_pediatric', 'guardian_name', 'child_name',
            'child_age', 'weight_kg', 'consent_status', 'dosage_alert',
            'last_message_at', 'messages', 'created_at', 'updated_at'
        )
        read_only_fields = ('id', 'reference', 'patient', 'created_at', 'updated_at')


class ConsultationListSerializer(serializers.ModelSerializer):
    doctor_name = serializers.ReadOnlyField(source='provider_name')

    class Meta:
        model = Consultation
        fields = (
            'id', 'reference', 'doctor_name', 'patient_name', 'issue',
            'status', 'priority', 'is_pediatric', 'last_message_at', 'created_at'
        )


class ConsultationCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Consultation
        fields = (
            'doctor', 'pediatrician', 'patient_name', 'patient_age', 'issue', 'priority',
            'scheduled_at', 'is_pediatric', 'guardian_name', 'child_name',
            'child_age', 'weight_kg'
        )

    def validate(self, attrs):
        doctor = attrs.get('doctor')
        pediatrician = attrs.get('pediatrician')
        if doctor and pediatrician:
            raise serializers.ValidationError('Select either a doctor or a pediatrician, not both.')
        if not doctor and not pediatrician:
            raise serializers.ValidationError('A doctor or pediatrician is required.')
        if pediatrician:
            attrs['is_pediatric'] = True
        return attrs


class ConsultationUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Consultation
        fields = ('status', 'consent_status', 'dosage_alert')


class DoctorPrescriptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = DoctorPrescription
        fields = ('id', 'reference', 'doctor', 'consultation', 'patient_name', 'items', 'status', 'notes', 'created_at')
        read_only_fields = ('id', 'reference', 'created_at')


class PediatricianPrescriptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = PediatricianPrescription
        fields = ('id', 'reference', 'pediatrician', 'consultation', 'patient_name', 'items', 'status', 'notes', 'created_at')
        read_only_fields = ('id', 'reference', 'created_at')


class DoctorEarningSerializer(serializers.ModelSerializer):
    class Meta:
        model = DoctorEarning
        fields = ('id', 'doctor', 'consultation', 'amount', 'description', 'earned_at')
        read_only_fields = ('id', 'earned_at')


class PediatricianEarningSerializer(serializers.ModelSerializer):
    class Meta:
        model = PediatricianEarning
        fields = ('id', 'pediatrician', 'consultation', 'amount', 'description', 'earned_at')
        read_only_fields = ('id', 'earned_at')
