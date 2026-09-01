from rest_framework import serializers
from django.urls import reverse
from django.utils import timezone
from .models import (
    LabPartner, LabPartnerDocument, LabTechnicianProfile, LabTechDocument,
    LabTest, LaboratoryFacility, FacilityLabTest, LaboratoryFacilityDocument,
    LabRequest, LabAuditLog, LabResult
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


class FacilityLabTestSerializer(serializers.ModelSerializer):
    test_name = serializers.ReadOnlyField(source='test.name')
    sample_type = serializers.ReadOnlyField(source='test.sample_type')

    class Meta:
        model = FacilityLabTest
        fields = (
            'id', 'test', 'test_name', 'sample_type', 'price', 'turnaround',
            'home_collection_available', 'is_active',
        )
        read_only_fields = ('id',)


class LaboratoryFacilityDocumentSerializer(serializers.ModelSerializer):
    download_url = serializers.SerializerMethodField()

    def get_download_url(self, obj):
        path = reverse('lab-facility-document-download', kwargs={'pk': obj.pk})
        request = self.context.get('request')
        return request.build_absolute_uri(path) if request else path

    class Meta:
        model = LaboratoryFacilityDocument
        fields = ('id', 'name', 'status', 'download_url', 'uploaded_at')
        read_only_fields = fields


class LaboratoryFacilityDocumentCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = LaboratoryFacilityDocument
        fields = ('name', 'file')
        extra_kwargs = {'file': {'write_only': True}}


class LaboratoryFacilitySerializer(serializers.ModelSerializer):
    partner_name = serializers.ReadOnlyField(source='partner.name')
    offerings = FacilityLabTestSerializer(many=True, read_only=True)
    test_ids = serializers.PrimaryKeyRelatedField(
        source='selected_tests',
        queryset=LabTest.objects.filter(is_active=True),
        many=True,
        write_only=True,
        required=False,
    )
    technician_ids = serializers.PrimaryKeyRelatedField(
        source='selected_technicians',
        queryset=LabTechnicianProfile.objects.all(),
        many=True,
        write_only=True,
        required=False,
    )
    test_offerings = serializers.ListField(
        child=serializers.DictField(),
        write_only=True,
        required=False,
    )
    technicians = LabTechnicianProfileSerializer(many=True, read_only=True)
    documents = LaboratoryFacilityDocumentSerializer(many=True, read_only=True)

    class Meta:
        model = LaboratoryFacility
        fields = (
            'id', 'reference', 'partner', 'partner_name', 'name', 'email',
            'phone', 'county', 'address', 'accreditation', 'license_number',
            'license_expiry', 'supported_counties', 'operating_hours',
            'home_collection_enabled', 'physical_result_pickup_enabled',
            'pickup_instructions', 'status', 'status_note', 'is_active',
            'technicians', 'technician_ids', 'offerings', 'test_ids', 'test_offerings', 'documents',
            'submitted_at', 'updated_at', 'verified_at', 'verified_by',
        )
        read_only_fields = (
            'id', 'reference', 'partner', 'status', 'status_note',
            'submitted_at', 'updated_at', 'verified_at', 'verified_by',
        )

    def validate(self, attrs):
        partner = getattr(self.instance, 'partner', None) or self.context.get('partner')
        technicians = attrs.get('selected_technicians', [])
        if partner and any(technician.partner_id != partner.id for technician in technicians):
            raise serializers.ValidationError({
                'technician_ids': 'Every technician must belong to this lab partner.'
            })
        tests = attrs.get('selected_tests')
        if (self.instance is None or tests is not None) and not tests:
            raise serializers.ValidationError({
                'test_ids': 'Select at least one test offered by this laboratory.'
            })
        offering_data = attrs.get('test_offerings', [])
        if offering_data and tests is None:
            raise serializers.ValidationError({'test_offerings': 'Include test_ids when updating offerings.'})
        selected_ids = {test.id for test in (tests or [])}
        for offering in offering_data:
            try:
                test_id = int(offering.get('test'))
                price = float(offering.get('price'))
            except (TypeError, ValueError):
                raise serializers.ValidationError({'test_offerings': 'Each offering needs a valid test and price.'})
            if selected_ids and test_id not in selected_ids:
                raise serializers.ValidationError({'test_offerings': 'Offering tests must also appear in test_ids.'})
            if price <= 0 or not str(offering.get('turnaround', '')).strip():
                raise serializers.ValidationError({'test_offerings': 'Each offering needs a positive price and turnaround.'})
        county = attrs.get('county', getattr(self.instance, 'county', ''))
        supported = list(attrs.get(
            'supported_counties',
            getattr(self.instance, 'supported_counties', []),
        ))
        if county and county not in supported:
            attrs['supported_counties'] = [county, *supported]
        return attrs

    @staticmethod
    def _sync_offerings(facility, tests, offering_data=None):
        selected_ids = {test.id for test in tests}
        overrides = {int(item['test']): item for item in (offering_data or [])}
        facility.offerings.exclude(test_id__in=selected_ids).delete()
        for test in tests:
            override = overrides.get(test.id, {})
            FacilityLabTest.objects.update_or_create(
                facility=facility,
                test=test,
                defaults={
                    'price': override.get('price', test.price),
                    'turnaround': override.get('turnaround', test.turnaround),
                    'home_collection_available': override.get(
                        'home_collection_available',
                        facility.home_collection_enabled,
                    ),
                    'is_active': True,
                },
            )

    def create(self, validated_data):
        tests = validated_data.pop('selected_tests', [])
        technicians = validated_data.pop('selected_technicians', [])
        offering_data = validated_data.pop('test_offerings', [])
        facility = super().create(validated_data)
        facility.technicians.set(technicians)
        self._sync_offerings(facility, tests, offering_data)
        return facility

    def update(self, instance, validated_data):
        tests = validated_data.pop('selected_tests', None)
        technicians = validated_data.pop('selected_technicians', None)
        offering_data = validated_data.pop('test_offerings', None)
        facility = super().update(instance, validated_data)
        if technicians is not None:
            facility.technicians.set(technicians)
        if tests is not None:
            self._sync_offerings(facility, tests, offering_data)
        return facility


class LabAuditLogSerializer(serializers.ModelSerializer):
    performed_by_name = serializers.ReadOnlyField(source='performed_by.full_name')

    class Meta:
        model = LabAuditLog
        fields = ('id', 'action', 'performed_by', 'performed_by_name', 'timestamp')
        read_only_fields = ('id', 'timestamp')


class LabResultSerializer(serializers.ModelSerializer):
    reviewed_by_name = serializers.ReadOnlyField(source='reviewed_by.full_name')
    download_url = serializers.SerializerMethodField()

    def get_download_url(self, obj):
        if not obj.file:
            return None
        path = reverse('lab-result-download', kwargs={'pk': obj.pk})
        request = self.context.get('request')
        return request.build_absolute_uri(path) if request else path

    class Meta:
        model = LabResult
        fields = (
            'id', 'reference', 'summary', 'download_url', 'filename', 'flags',
            'is_abnormal', 'recommendation', 'reviewed_by',
            'reviewed_by_name', 'uploaded_at',
        )
        read_only_fields = ('id', 'reference', 'uploaded_at')


class LabRequestSerializer(serializers.ModelSerializer):
    test_name = serializers.ReadOnlyField(source='test.name')
    test_category = serializers.ReadOnlyField(source='test.category')
    test_price = serializers.ReadOnlyField(source='test.price')
    test_turnaround = serializers.ReadOnlyField(source='test.turnaround')
    test_sample_type = serializers.ReadOnlyField(source='test.sample_type')
    audit_logs = LabAuditLogSerializer(many=True, read_only=True)
    result = serializers.SerializerMethodField()
    partner_name = serializers.ReadOnlyField(source='assigned_partner.name')
    laboratory_name = serializers.ReadOnlyField(source='laboratory.name')
    laboratory_reference = serializers.ReadOnlyField(source='laboratory.reference')
    pharmacist_name = serializers.ReadOnlyField(source='assigned_pharmacist.full_name')
    technician_name = serializers.ReadOnlyField(source='assigned_technician.full_name')
    collection_verified_by_name = serializers.ReadOnlyField(source='collection_verified_by.full_name')
    collection_verification_required = serializers.SerializerMethodField()
    collection_code_active = serializers.SerializerMethodField()

    def get_result(self, obj):
        request = self.context.get('request')
        if request and request.user.role == 'pharmacist':
            return None
        try:
            result = obj.result
        except LabResult.DoesNotExist:
            return None
        return LabResultSerializer(result, context=self.context).data

    def get_collection_verification_required(self, obj):
        return obj.channel == LabRequest.CHANNEL_COLLECTION and obj.collection_verified_at is None

    def get_collection_code_active(self, obj):
        return bool(
            obj.collection_verification_code_hash
            and obj.collection_code_expires_at
            and obj.collection_code_expires_at > timezone.now()
            and obj.collection_verified_at is None
        )

    class Meta:
        model = LabRequest
        fields = (
            'id', 'reference', 'test', 'test_name', 'test_category',
            'test_price', 'test_turnaround', 'test_sample_type',
            'patient', 'patient_name', 'patient_phone', 'patient_email',
            'status', 'payment_status', 'priority', 'channel',
            'result_delivery_method', 'collection_address',
            'collection_instructions', 'result_pickup_location',
            'collection_verification_required', 'collection_code_active',
            'collection_code_requested_at', 'collection_code_expires_at',
            'collection_verification_attempts', 'collection_verified_at',
            'collection_verified_by', 'collection_verified_by_name',
            'ordering_doctor', 'notes',
            'assigned_partner', 'partner_name',
            'laboratory', 'laboratory_name', 'laboratory_reference',
            'assigned_pharmacist', 'pharmacist_name',
            'assigned_technician', 'technician_name',
            'scheduled_at', 'requested_at', 'updated_at', 'audit_logs', 'result'
        )
        read_only_fields = (
            'id', 'reference', 'requested_at', 'updated_at',
            'collection_code_requested_at', 'collection_code_expires_at',
            'collection_verification_attempts', 'collection_verified_at',
            'collection_verified_by',
        )


class LabRequestCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = LabRequest
        fields = (
            'test', 'patient_name', 'patient_phone', 'patient_email',
            'priority', 'channel', 'result_delivery_method',
            'collection_address', 'collection_instructions',
            'result_pickup_location', 'ordering_doctor', 'notes', 'scheduled_at'
        )

    def validate(self, attrs):
        channel = attrs.get('channel', LabRequest.CHANNEL_COLLECTION)
        result_delivery = attrs.get(
            'result_delivery_method',
            LabRequest.RESULT_DIGITAL,
        )
        if channel == LabRequest.CHANNEL_COLLECTION and not attrs.get('collection_address', '').strip():
            raise serializers.ValidationError({
                'collection_address': 'A collection address is required for home sample collection.'
            })
        if (
            result_delivery == LabRequest.RESULT_PHYSICAL_PICKUP
            and not attrs.get('result_pickup_location', '').strip()
        ):
            raise serializers.ValidationError({
                'result_pickup_location': 'Choose a pickup location for physical results.'
            })
        return attrs


class LabRequestUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = LabRequest
        fields = (
            'status', 'payment_status', 'priority', 'assigned_partner', 'laboratory',
            'assigned_pharmacist', 'assigned_technician', 'scheduled_at',
            'collection_address', 'collection_instructions',
            'result_pickup_location', 'notes',
        )

    def validate(self, attrs):
        from apps.accounts.models import User

        partner = attrs.get('assigned_partner', getattr(self.instance, 'assigned_partner', None))
        laboratory = attrs.get('laboratory', getattr(self.instance, 'laboratory', None))
        technician = attrs.get('assigned_technician', getattr(self.instance, 'assigned_technician', None))
        pharmacist = attrs.get('assigned_pharmacist', getattr(self.instance, 'assigned_pharmacist', None))

        if 'laboratory' in attrs:
            if laboratory:
                attrs['assigned_partner'] = laboratory.partner
                partner = laboratory.partner
            elif 'assigned_partner' not in attrs:
                attrs['assigned_partner'] = None
                partner = None

        if partner and partner.status != LabPartner.STATUS_VERIFIED:
            raise serializers.ValidationError({'assigned_partner': 'Only verified lab partners can receive requests.'})

        if laboratory:
            if laboratory.status != LaboratoryFacility.STATUS_VERIFIED or not laboratory.is_active:
                raise serializers.ValidationError({'laboratory': 'Only verified, active laboratories can receive requests.'})
            if partner and laboratory.partner_id != partner.id:
                raise serializers.ValidationError({'laboratory': 'The laboratory does not belong to the assigned partner.'})
            offering = laboratory.offerings.filter(test=self.instance.test, is_active=True).first()
            if not offering:
                raise serializers.ValidationError({'laboratory': 'This laboratory does not offer the requested test.'})
            if self.instance.channel == LabRequest.CHANNEL_COLLECTION and (
                not laboratory.home_collection_enabled or not offering.home_collection_available
            ):
                raise serializers.ValidationError({'laboratory': 'This laboratory does not support home collection for the requested test.'})
            if (
                self.instance.result_delivery_method == LabRequest.RESULT_PHYSICAL_PICKUP
                and not laboratory.physical_result_pickup_enabled
            ):
                raise serializers.ValidationError({'laboratory': 'This laboratory does not support physical result pickup.'})

        if technician:
            try:
                profile = technician.lab_tech_profile
            except LabTechnicianProfile.DoesNotExist:
                raise serializers.ValidationError({'assigned_technician': 'The selected user is not a lab technician.'})
            if profile.status != LabTechnicianProfile.STATUS_ACTIVE:
                raise serializers.ValidationError({'assigned_technician': 'The selected technician is not active.'})
            if partner and profile.partner_id != partner.id:
                raise serializers.ValidationError({
                    'assigned_technician': 'The selected technician does not belong to the assigned lab partner.'
                })
            if laboratory and not laboratory.technicians.filter(pk=profile.pk).exists():
                raise serializers.ValidationError({
                    'assigned_technician': 'The selected technician is not assigned to this laboratory.'
                })

        if pharmacist and pharmacist.role not in (User.PHARMACIST, User.ADMIN):
            raise serializers.ValidationError({'assigned_pharmacist': 'The coordinator must be a pharmacist or administrator.'})

        return attrs


class LabResultCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = LabResult
        fields = ('summary', 'file', 'filename', 'flags', 'is_abnormal', 'recommendation')
