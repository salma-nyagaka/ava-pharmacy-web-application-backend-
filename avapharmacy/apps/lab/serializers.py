from rest_framework import serializers
from .models import (
    LabPartner, LabPartnerDocument, LabTechnicianProfile, LabTechDocument,
    LabTest, LabRequest, LabAuditLog, LabResult
)


def _validate_unique_lab_phone(phone, instance=None, partner=False):
    phone = (phone or '').strip()
    if not phone:
        return phone

    from apps.accounts.models import User

    if User.objects.filter(phone=phone).exists():
        raise serializers.ValidationError('A user with this phone number already exists.')

    model = LabPartner if partner else LabTechnicianProfile
    queryset = model.objects.filter(phone=phone)
    if instance is not None:
        queryset = queryset.exclude(pk=instance.pk)
    if queryset.exists():
        raise serializers.ValidationError('An application with this phone number already exists.')
    return phone


class LabPartnerDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = LabPartnerDocument
        fields = ('id', 'name', 'file', 'uploaded_at')
        read_only_fields = ('id', 'uploaded_at')


class LabTechDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = LabTechDocument
        fields = ('id', 'name', 'file', 'status', 'uploaded_at')
        read_only_fields = ('id', 'uploaded_at')


class LabTechnicianProfileSerializer(serializers.ModelSerializer):
    user_name = serializers.ReadOnlyField(source='user.full_name')
    user_email = serializers.ReadOnlyField(source='user.email')
    user_phone = serializers.ReadOnlyField(source='user.phone')
    documents = LabTechDocumentSerializer(many=True, read_only=True)

    class Meta:
        model = LabTechnicianProfile
        fields = (
            'id', 'user', 'user_name', 'user_email', 'user_phone',
            'name', 'email', 'phone',
            'partner', 'specialty', 'license_number', 'license_board', 'license_country',
            'license_expiry', 'id_number', 'availability',
            'years_experience', 'county', 'address', 'bio', 'references', 'document_checklist',
            'payout_method', 'payout_account',
            'background_consent', 'compliance_declaration', 'agreed_to_terms',
            'status', 'status_note', 'rejection_note',
            'submitted_at', 'created_at', 'updated_at', 'created_by', 'updated_by',
            'documents'
        )
        read_only_fields = (
            'id', 'created_at', 'updated_at', 'submitted_at',
            'created_by', 'updated_by'
        )


class LabPartnerSerializer(serializers.ModelSerializer):
    documents = LabPartnerDocumentSerializer(many=True, read_only=True)
    technicians = LabTechnicianProfileSerializer(many=True, read_only=True)
    user_email = serializers.ReadOnlyField(source='user.email')

    class Meta:
        model = LabPartner
        fields = (
            'id', 'reference', 'user', 'user_email', 'name', 'email', 'phone', 'location', 'contact_name',
            'accreditation', 'license_number', 'license_expiry', 'id_number',
            'county', 'address', 'years_in_operation', 'references', 'document_checklist',
            'payout_method', 'payout_account',
            'background_consent', 'compliance_declaration', 'agreed_to_terms',
            'status', 'status_note', 'rejection_note', 'notes',
            'submitted_at', 'created_at', 'updated_at', 'verified_at',
            'created_by', 'updated_by', 'documents', 'technicians'
        )
        read_only_fields = (
            'id', 'reference', 'submitted_at', 'created_at', 'updated_at',
            'created_by', 'updated_by'
        )


class LabPartnerCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = LabPartner
        fields = (
            'name', 'email', 'phone', 'location', 'contact_name',
            'accreditation', 'license_number', 'license_expiry', 'id_number',
            'county', 'address', 'years_in_operation', 'references', 'document_checklist',
            'payout_method', 'payout_account', 'notes'
        )


class LabPartnerRegistrationSerializer(serializers.ModelSerializer):
    documents = serializers.ListField(
        child=serializers.FileField(), required=False, write_only=True
    )
    document_names = serializers.ListField(
        child=serializers.CharField(), required=False, write_only=True
    )

    class Meta:
        model = LabPartner
        fields = (
            'name', 'email', 'phone', 'location', 'contact_name',
            'accreditation', 'license_number', 'license_expiry', 'id_number',
            'county', 'address', 'years_in_operation', 'references', 'document_checklist',
            'payout_method', 'payout_account',
            'background_consent', 'compliance_declaration', 'agreed_to_terms',
            'notes', 'documents', 'document_names',
        )

    def validate_email(self, value):
        from apps.accounts.models import User
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError('A user with this email already exists.')
        if LabPartner.objects.filter(email=value).exists():
            raise serializers.ValidationError('A lab partner with this email already exists.')
        return value

    def validate_phone(self, value):
        return _validate_unique_lab_phone(value, instance=self.instance, partner=True)

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
        request = self.context.get('request')
        actor = request.user if request and getattr(request.user, 'is_authenticated', False) else None
        partner = LabPartner.objects.create(
            created_by=actor,
            updated_by=actor,
            **validated_data
        )
        for i, doc_file in enumerate(documents):
            doc_name = document_names[i] if i < len(document_names) else doc_file.name
            LabPartnerDocument.objects.create(partner=partner, name=doc_name, file=doc_file)
        return partner


class LabPartnerUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = LabPartner
        fields = (
            'status', 'status_note', 'rejection_note', 'notes',
            'verified_at', 'payout_method', 'payout_account'
        )


class LabTechnicianRegistrationSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=200)
    email = serializers.EmailField()
    phone = serializers.CharField(max_length=20)
    partner_id = serializers.IntegerField()
    specialty = serializers.CharField(max_length=200, required=False, allow_blank=True, default='')
    license_number = serializers.CharField(max_length=100)
    license_board = serializers.CharField(max_length=200, required=False, allow_blank=True, default='')
    license_country = serializers.CharField(max_length=100, required=False, allow_blank=True, default='')
    license_expiry = serializers.DateField(required=False, allow_null=True)
    id_number = serializers.CharField(max_length=50)
    availability = serializers.CharField(max_length=200, required=False, allow_blank=True, default='')
    years_experience = serializers.IntegerField(required=False, allow_null=True)
    county = serializers.CharField(max_length=100, required=False, allow_blank=True, default='')
    address = serializers.CharField(required=False, allow_blank=True, default='')
    bio = serializers.CharField(required=False, allow_blank=True, default='')
    references = serializers.ListField(child=serializers.DictField(), required=False, default=list)
    document_checklist = serializers.ListField(
        child=serializers.CharField(), required=False, default=list
    )
    payout_method = serializers.ChoiceField(
        choices=[c[0] for c in LabTechnicianProfile.PAYOUT_CHOICES],
        default=LabTechnicianProfile.PAYOUT_MPESA
    )
    payout_account = serializers.CharField(max_length=100)
    background_consent = serializers.BooleanField()
    compliance_declaration = serializers.BooleanField()
    agreed_to_terms = serializers.BooleanField()
    documents = serializers.ListField(child=serializers.FileField(), required=False)
    document_names = serializers.ListField(child=serializers.CharField(), required=False)

    def validate_email(self, value):
        from apps.accounts.models import User
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError('A user with this email already exists.')
        if LabTechnicianProfile.objects.filter(email=value).exists():
            raise serializers.ValidationError('An application with this email already exists.')
        return value

    def validate_phone(self, value):
        return _validate_unique_lab_phone(value, instance=getattr(self, 'instance', None))

    def validate_partner_id(self, value):
        try:
            LabPartner.objects.get(pk=value)
        except LabPartner.DoesNotExist:
            raise serializers.ValidationError('Lab partner not found.')
        return value

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
        partner_id = validated_data.pop('partner_id')
        partner = LabPartner.objects.get(pk=partner_id)
        request = self.context.get('request')
        actor = request.user if request and getattr(request.user, 'is_authenticated', False) else None
        tech = LabTechnicianProfile.objects.create(
            partner=partner,
            status=LabTechnicianProfile.STATUS_PENDING,
            created_by=actor,
            updated_by=actor,
            **validated_data
        )
        for i, doc_file in enumerate(documents):
            doc_name = document_names[i] if i < len(document_names) else doc_file.name
            LabTechDocument.objects.create(tech=tech, name=doc_name, file=doc_file)

        return tech


class PublicLabPartnerOptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = LabPartner
        fields = ('id', 'reference', 'name', 'location', 'accreditation', 'status')


class LabTestSerializer(serializers.ModelSerializer):
    class Meta:
        model = LabTest
        fields = ('id', 'reference', 'name', 'category', 'price', 'turnaround', 'sample_type', 'description', 'is_active', 'created_at')
        read_only_fields = ('id', 'reference', 'created_at')


class LabAuditLogSerializer(serializers.ModelSerializer):
    performed_by_name = serializers.ReadOnlyField(source='performed_by.full_name')

    class Meta:
        model = LabAuditLog
        fields = ('id', 'action', 'performed_by', 'performed_by_name', 'timestamp')
        read_only_fields = ('id', 'timestamp')


class LabResultSerializer(serializers.ModelSerializer):
    reviewed_by_name = serializers.ReadOnlyField(source='reviewed_by.full_name')

    class Meta:
        model = LabResult
        fields = ('id', 'reference', 'summary', 'file', 'filename', 'flags', 'is_abnormal', 'recommendation', 'reviewed_by', 'reviewed_by_name', 'uploaded_at')
        read_only_fields = ('id', 'reference', 'uploaded_at')


class LabRequestSerializer(serializers.ModelSerializer):
    test_name = serializers.ReadOnlyField(source='test.name')
    test_category = serializers.ReadOnlyField(source='test.category')
    test_price = serializers.ReadOnlyField(source='test.price')
    test_turnaround = serializers.ReadOnlyField(source='test.turnaround')
    test_sample_type = serializers.ReadOnlyField(source='test.sample_type')
    audit_logs = LabAuditLogSerializer(many=True, read_only=True)
    result = LabResultSerializer(read_only=True)
    technician_name = serializers.ReadOnlyField(source='assigned_technician.full_name')

    class Meta:
        model = LabRequest
        fields = (
            'id', 'reference', 'test', 'test_name', 'test_category', 'test_price', 'test_turnaround', 'test_sample_type',
            'patient', 'patient_name', 'patient_phone', 'patient_email',
            'status', 'payment_status', 'priority', 'channel',
            'ordering_doctor', 'notes', 'assigned_technician', 'technician_name',
            'scheduled_at', 'requested_at', 'updated_at', 'audit_logs', 'result'
        )
        read_only_fields = ('id', 'reference', 'requested_at', 'updated_at')


class LabRequestCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = LabRequest
        fields = (
            'test', 'patient_name', 'patient_phone', 'patient_email',
            'priority', 'channel', 'ordering_doctor', 'notes', 'scheduled_at'
        )


class LabRequestUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = LabRequest
        fields = ('status', 'payment_status', 'priority', 'assigned_technician', 'notes')


class LabResultCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = LabResult
        fields = ('summary', 'file', 'filename', 'flags', 'is_abnormal', 'recommendation')
