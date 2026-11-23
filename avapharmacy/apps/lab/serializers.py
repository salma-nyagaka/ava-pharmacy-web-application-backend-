from rest_framework import serializers
from django.urls import reverse
from django.db import transaction
from django.core.validators import FileExtensionValidator
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
    download_url = serializers.SerializerMethodField()

    def get_download_url(self, obj):
        path = reverse('lab-partner-document-download', kwargs={'pk': obj.pk})
        request = self.context.get('request')
        return request.build_absolute_uri(path) if request else path

    class Meta:
        model = LabPartnerDocument
        fields = ('id', 'name', 'download_url', 'uploaded_at')
        read_only_fields = ('id', 'uploaded_at')


class LabTechDocumentSerializer(serializers.ModelSerializer):
    file = serializers.SerializerMethodField()

    def get_file(self, obj):
        if not obj.file:
            return None
        path = reverse('lab-tech-document-download', args=[obj.pk])
        request = self.context.get('request')
        return request.build_absolute_uri(path) if request else path

    class Meta:
        model = LabTechDocument
        fields = ('id', 'name', 'file', 'status', 'uploaded_at')
        read_only_fields = fields


class LabTechnicianProfileSerializer(serializers.ModelSerializer):
    account_active = serializers.SerializerMethodField()
    activation_status = serializers.SerializerMethodField()

    def get_account_active(self, obj):
        return bool(obj.user_id and obj.user.is_active and obj.user.status == 'active' and obj.user.has_usable_password())

    def get_activation_status(self, obj):
        if obj.status == 'suspended':
            return 'suspended'
        if not obj.user_id:
            return 'pending_setup'
        if not self.get_account_active(obj):
            return 'pending_activation'
        return 'active' if obj.status == 'active' else 'pending'

    laboratory = serializers.PrimaryKeyRelatedField(queryset=LaboratoryFacility.objects.all(), write_only=True, required=False)

    @transaction.atomic
    def create(self, validated_data):
        laboratory = validated_data.pop('laboratory', None)
        if laboratory and (laboratory.partner_id != getattr(validated_data.get('partner'), 'pk', None) or laboratory.status != 'verified' or not laboratory.is_active):
            raise serializers.ValidationError({'laboratory': 'Choose an approved, active laboratory belonging to your partner account.'})
        technician = super().create(validated_data)
        if laboratory:
            laboratory.technicians.add(technician)
        return technician

    def validate_laboratory(self, value):
        if self.instance:
            raise serializers.ValidationError('Manage laboratory assignments from the laboratory workspace.')
        return value

    user_name = serializers.ReadOnlyField(source='user.full_name')
    user_email = serializers.ReadOnlyField(source='user.email')
    user_phone = serializers.ReadOnlyField(source='user.phone')
    documents = LabTechDocumentSerializer(many=True, read_only=True)

    class Meta:
        model = LabTechnicianProfile
        fields = (
            'id', 'user', 'user_name', 'user_email', 'user_phone', 'account_active', 'activation_status',
            'name', 'email', 'phone', 'laboratory',
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
    documents = serializers.ListField(
        child=serializers.FileField(), min_length=1, write_only=True,
        error_messages={'min_length': 'Upload at least one legal or compliance document.'},
    )
    document_names = serializers.ListField(
        child=serializers.CharField(), required=False, write_only=True,
    )

    class Meta:
        model = LabPartner
        fields = (
            'name', 'email', 'phone', 'location', 'contact_name',
            'accreditation', 'license_number', 'license_expiry', 'id_number',
            'county', 'address', 'years_in_operation', 'references', 'document_checklist',
            'payout_method', 'payout_account', 'notes', 'documents', 'document_names'
        )

    def create(self, validated_data):
        documents = validated_data.pop('documents', [])
        document_names = validated_data.pop('document_names', [])
        partner = LabPartner.objects.create(**validated_data)
        for index, document in enumerate(documents):
            LabPartnerDocument.objects.create(
                partner=partner,
                name=document_names[index] if index < len(document_names) else document.name,
                file=document,
            )
        return partner


class LabPartnerRegistrationSerializer(serializers.ModelSerializer):
    documents = serializers.ListField(
        child=serializers.FileField(), min_length=1, write_only=True,
        error_messages={'min_length': 'Upload at least one legal or compliance document.'},
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
            'notes', 'payout_method', 'payout_account'
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


def bookable_offerings(test):
    return test.facility_offerings.filter(
        is_active=True, facility__status='verified', facility__is_active=True,
        facility__partner__status='verified', facility__partner__user__is_active=True,
        facility__partner__user__status='active',
    ).select_related('facility__partner').order_by('price', 'pk')


class LabTestSerializer(serializers.ModelSerializer):
    laboratories = serializers.SerializerMethodField()

    def get_laboratories(self, obj):
        return [{
            'id': offering.facility_id, 'name': offering.facility.name,
            'partner_id': offering.facility.partner_id, 'partner_name': offering.facility.partner.name, 'county': offering.facility.county,
            'price': str(offering.price), 'turnaround': offering.turnaround,
            'home_collection_available': offering.home_collection_available and offering.facility.home_collection_enabled,
            'physical_pickup_available': offering.facility.physical_result_pickup_enabled,
        } for offering in bookable_offerings(obj)]

    class Meta:
        model = LabTest
        fields = ('id', 'reference', 'name', 'category', 'price', 'turnaround', 'sample_type', 'description', 'is_active', 'created_at', 'laboratories')
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
    registration_document = serializers.FileField(write_only=True, required=False, validators=[FileExtensionValidator(allowed_extensions=['pdf', 'jpg', 'jpeg', 'png'])])
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
            'submitted_at', 'updated_at', 'verified_at', 'verified_by', 'registration_document',
        )
        read_only_fields = (
            'id', 'reference', 'partner', 'status', 'status_note',
            'submitted_at', 'updated_at', 'verified_at', 'verified_by',
        )

    def validate(self, attrs):
        if self.instance is None:
            errors = {}
            for field in ('name', 'email', 'phone', 'county', 'address', 'accreditation', 'license_number'):
                if not str(attrs.get(field, '')).strip():
                    errors[field] = 'This field is required.'
            if not attrs.get('license_expiry'):
                errors['license_expiry'] = 'Licence expiry is required.'
            elif attrs['license_expiry'] < timezone.localdate():
                errors['license_expiry'] = 'The licence must not be expired.'
            if not attrs.get('supported_counties') or not all(isinstance(county, str) and county.strip() for county in attrs.get('supported_counties', [])):
                errors['supported_counties'] = 'Enter at least one service county.'
            hours = attrs.get('operating_hours')
            if not isinstance(hours, dict) or any(not str(hours.get(day, '')).strip() for day in ('monday_friday', 'saturday')):
                errors['operating_hours'] = 'Enter weekday and Saturday hours; use Closed for non-operating days.'
            for field in ('home_collection_enabled', 'physical_result_pickup_enabled'):
                if field not in attrs:
                    errors[field] = 'Choose whether this service is available.'
            if attrs.get('physical_result_pickup_enabled') and not str(attrs.get('pickup_instructions', '')).strip():
                errors['pickup_instructions'] = 'Pickup instructions are required when physical pickup is enabled.'
            if not attrs.get('registration_document'):
                errors['registration_document'] = 'Upload the laboratory licence or accreditation document.'
            if errors:
                raise serializers.ValidationError(errors)
        partner = getattr(self.instance, 'partner', None) or self.context.get('partner')
        if self.instance is None and ('test_ids' in self.initial_data or 'test_offerings' in self.initial_data):
            raise serializers.ValidationError({
                'test_offerings': 'Submit the laboratory for approval first. The test catalogue is available after Ava verifies the facility.'
            })
        if (
            'technician_ids' in self.initial_data
            and (self.instance is None or self.instance.status != LaboratoryFacility.STATUS_VERIFIED)
        ):
            raise serializers.ValidationError({
                'technician_ids': 'Technicians can be assigned only after Ava verifies this laboratory.'
            })
        if self.instance and self.instance.status != LaboratoryFacility.STATUS_VERIFIED and (
            'test_ids' in self.initial_data or 'test_offerings' in self.initial_data
        ):
            raise serializers.ValidationError({
                'test_offerings': 'The test catalogue can be changed only after Ava verifies this laboratory.'
            })
        technicians = attrs.get('selected_technicians', [])
        if partner and any(technician.partner_id != partner.id for technician in technicians):
            raise serializers.ValidationError({
                'technician_ids': 'Every technician must belong to this lab partner.'
            })
        tests = attrs.get('selected_tests')
        if 'test_ids' in self.initial_data and tests is not None and not tests:
            raise serializers.ValidationError({
                'test_ids': 'Select at least one test when updating the test catalogue.'
            })
        offering_data = attrs.get('test_offerings', [])
        if offering_data and tests is None:
            raise serializers.ValidationError({'test_offerings': 'Include test_ids when updating offerings.'})
        selected_ids = {test.id for test in (tests or [])}
        for offering in offering_data:
            try:
                test_id = int(offering.get('test'))
                from decimal import Decimal, InvalidOperation
                price = Decimal(str(offering.get('price')))
            except (TypeError, ValueError, InvalidOperation):
                raise serializers.ValidationError({'test_offerings': 'Each offering needs a valid test and price.'})
            if selected_ids and test_id not in selected_ids:
                raise serializers.ValidationError({'test_offerings': 'Offering tests must also appear in test_ids.'})
            if not price.is_finite() or price <= 0 or not str(offering.get('turnaround', '')).strip():
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

    @transaction.atomic
    def create(self, validated_data):
        document = validated_data.pop('registration_document')
        tests = validated_data.pop('selected_tests', [])
        technicians = validated_data.pop('selected_technicians', [])
        offering_data = validated_data.pop('test_offerings', [])
        facility = super().create(validated_data)
        LaboratoryFacilityDocument.objects.create(facility=facility, name='Registration licence', file=document)
        facility.technicians.set(technicians)
        if tests:
            self._sync_offerings(facility, tests, offering_data)
        return facility

    @transaction.atomic
    def update(self, instance, validated_data):
        document = validated_data.pop('registration_document', None)
        tests = validated_data.pop('selected_tests', None)
        technicians = validated_data.pop('selected_technicians', None)
        offering_data = validated_data.pop('test_offerings', None)
        if 'test_ids' not in self.initial_data:
            tests = None
        if 'technician_ids' not in self.initial_data:
            technicians = None
        facility = super().update(instance, validated_data)
        if document:
            LaboratoryFacilityDocument.objects.create(facility=facility, name='Updated licence', file=document)
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
    collection_fee = serializers.SerializerMethodField()
    collection_paid = serializers.SerializerMethodField()

    def get_collection_fee(self, obj):
        return str(obj.collection_fee_amount)

    def get_collection_paid(self, obj):
        return obj.payments.filter(stage='collection', status='succeeded').exists()

    test_name = serializers.ReadOnlyField(source='test.name')
    test_category = serializers.ReadOnlyField(source='test.category')
    test_price = serializers.SerializerMethodField()

    def get_test_price(self, obj):
        return obj.quoted_test_price if obj.quoted_test_price is not None else (obj.test.price if obj.test else None)
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

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get('request')
        if request and request.user.role == 'lab_technician' and instance.assigned_technician_id != request.user.pk:
            for field in ('patient_phone', 'patient_email', 'collection_address', 'collection_instructions', 'ordering_doctor', 'notes'):
                data[field] = ''
            data.update(patient=None, patient_name='Unassigned patient', audit_logs=[], result=None)
        return data

    def get_result(self, obj):
        request = self.context.get('request')
        if not request or request.user.role == 'pharmacist':
            return None
        if request.user.role == 'lab_technician' and obj.assigned_technician_id != request.user.pk:
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
            'id', 'reference', 'collection_fee', 'collection_paid', 'test', 'test_name', 'test_category',
            'test_price', 'test_turnaround', 'test_sample_type',
            'patient', 'patient_name', 'patient_phone', 'patient_email',
            'status', 'payment_status', 'priority', 'channel',
            'result_delivery_method', 'collection_address',
            'collection_instructions', 'result_pickup_location',
            'collection_verification_required', 'collection_code_active',
            'collection_code_requested_at', 'collection_code_expires_at',
            'collection_verification_attempts', 'collection_verified_at',
            'collection_verified_by', 'collection_verified_by_name',
            'consultation', 'ordering_doctor', 'notes',
            'assigned_partner', 'partner_name',
            'laboratory', 'laboratory_name', 'laboratory_reference',
            'assigned_pharmacist', 'pharmacist_name',
            'assigned_technician', 'technician_name',
            'scheduled_at', 'rider_dispatched_at', 'samples_sent_at', 'samples_received_at', 'requested_at', 'updated_at', 'audit_logs', 'result'
        )
        read_only_fields = (
            'id', 'reference', 'requested_at', 'updated_at', 'rider_dispatched_at', 'samples_sent_at', 'samples_received_at',
            'collection_code_requested_at', 'collection_code_expires_at',
            'collection_verification_attempts', 'collection_verified_at',
            'collection_verified_by',
        )


class LabRequestCreateSerializer(serializers.ModelSerializer):
    patient_name = serializers.CharField(required=False, allow_blank=True)
    patient_phone = serializers.CharField(required=False, allow_blank=True)
    patient_email = serializers.EmailField(required=False, allow_blank=True)
    ordering_doctor = serializers.CharField(read_only=True)
    def create(self, validated_data):
        # Booking records customer intent; only an admin can choose the provider later.
        from django.conf import settings
        from decimal import Decimal
        validated_data['collection_fee_amount'] = Decimal(settings.LAB_COLLECTION_FEE) if validated_data.get('channel', 'collection') == 'collection' else 0
        validated_data['quoted_test_price'] = validated_data['test'].price
        return super().create(validated_data)

    def validate_test(self, test):
        if not test.is_active or not test.facility_offerings.filter(is_active=True, facility__status='verified', facility__is_active=True, facility__partner__status='verified', facility__partner__user__is_active=True, facility__partner__user__status='active').exists():
            raise serializers.ValidationError('This test has no approved, active laboratory offering.')
        return test

    class Meta:
        model = LabRequest
        fields = (
            'test', 'consultation', 'assigned_partner', 'patient_name', 'patient_phone', 'patient_email',
            'priority', 'channel', 'result_delivery_method',
            'collection_address', 'collection_instructions',
            'result_pickup_location', 'ordering_doctor', 'notes', 'scheduled_at'
        )

    def validate(self, attrs):
        if any(self.initial_data.get(field) not in (None, '') for field in ('laboratory', 'assigned_technician')):
            raise serializers.ValidationError({'laboratory': 'The lab partner selects its laboratory and technician.'})
        consultation = attrs.get('consultation')
        user = self.context['request'].user
        if not consultation or not consultation.clinician_id or consultation.clinician.user_id != user.id:
            raise serializers.ValidationError({'consultation': 'Select a consultation assigned to you.'})
        if consultation.status not in ('in_progress', 'completed') or not consultation.clinician.eligible_to_practice:
            raise serializers.ValidationError({'consultation': 'Tests can be ordered during or after an active consultation.'})
        if not consultation.patient_id:
            raise serializers.ValidationError({'consultation': 'This consultation has no linked patient account.'})
        partner = attrs.get('assigned_partner')
        if not partner or not bookable_offerings(attrs['test']).filter(facility__partner=partner).exists():
            raise serializers.ValidationError({'assigned_partner': 'Choose a verified partner offering this test.'})
        attrs.update(patient_name=consultation.child_name or consultation.patient_name,
                     patient_email=consultation.patient_email, patient_phone=consultation.patient_phone,
                     ordering_doctor=user.full_name)
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
        offerings = bookable_offerings(attrs['test'])
        if channel == LabRequest.CHANNEL_COLLECTION:
            offerings = offerings.filter(home_collection_available=True, facility__home_collection_enabled=True)
        if result_delivery == LabRequest.RESULT_PHYSICAL_PICKUP:
            offerings = offerings.filter(facility__physical_result_pickup_enabled=True)
        if not offerings.filter(facility__partner=partner).exists():
            raise serializers.ValidationError({'assigned_partner': 'This partner does not support the selected collection or result delivery method.'})
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

        if set(attrs) == {'status'} and attrs['status'] == LabRequest.STATUS_CANCELLED:
            return attrs

        partner = attrs.get('assigned_partner', getattr(self.instance, 'assigned_partner', None))
        laboratory = attrs.get('laboratory', getattr(self.instance, 'laboratory', None))
        technician = attrs.get('assigned_technician', getattr(self.instance, 'assigned_technician', None))
        pharmacist = attrs.get('assigned_pharmacist', getattr(self.instance, 'assigned_pharmacist', None))

        actor = getattr(self.context.get('request'), 'user', None)
        if actor and actor.role == 'lab_partner' and laboratory and laboratory.partner_id != self.instance.assigned_partner_id:
            raise serializers.ValidationError({'laboratory': 'Select a laboratory belonging to the partner assigned by the administrator.'})
        if 'assigned_partner' in attrs and attrs['assigned_partner'] != self.instance.assigned_partner:
            if partner and not attrs.get('assigned_technician'):
                raise serializers.ValidationError({'assigned_technician': 'Choose a technician together with the lab partner.'})
            attrs['laboratory'] = None
            attrs['assigned_technician'] = attrs.get('assigned_technician') if partner else None
            laboratory = None
            technician = attrs['assigned_technician']
        if 'laboratory' in attrs:
            if laboratory:
                attrs['assigned_partner'] = laboratory.partner
                partner = laboratory.partner
            elif 'assigned_partner' not in attrs:
                attrs['assigned_partner'] = None
                partner = None

        if partner and (partner.status != LabPartner.STATUS_VERIFIED or not partner.user_id or not partner.user.is_active or partner.user.status != 'active'):
            raise serializers.ValidationError({'assigned_partner': 'Only verified lab partners can receive requests.'})

        if partner and not self.instance.consultation_id and self.instance.collection_fee_amount > 0 and not self.instance.payments.filter(stage='collection', status='succeeded').exists():
            raise serializers.ValidationError({'assigned_partner': 'The customer must pay the collection fee before provider assignment.'})

        if partner and 'assigned_partner' in attrs and not laboratory:
            if not self.instance.test:
                raise serializers.ValidationError({'assigned_partner': 'The requested test no longer exists.'})
            offerings = bookable_offerings(self.instance.test).filter(facility__partner=partner)
            if self.instance.channel == LabRequest.CHANNEL_COLLECTION:
                offerings = offerings.filter(home_collection_available=True, facility__home_collection_enabled=True)
            if self.instance.result_delivery_method == LabRequest.RESULT_PHYSICAL_PICKUP:
                offerings = offerings.filter(facility__physical_result_pickup_enabled=True)
            if not offerings.exists():
                raise serializers.ValidationError({'assigned_partner': 'Choose a partner offering this test and the required collection/result delivery method.'})

        if laboratory:
            if laboratory.status != LaboratoryFacility.STATUS_VERIFIED or not laboratory.is_active:
                raise serializers.ValidationError({'laboratory': 'Only verified, active laboratories can receive requests.'})
            if partner and laboratory.partner_id != partner.id:
                raise serializers.ValidationError({'laboratory': 'The laboratory does not belong to the assigned partner.'})
            offering = laboratory.offerings.filter(test=self.instance.test, is_active=True).first()
            if not offering:
                raise serializers.ValidationError({'laboratory': 'This laboratory does not offer the requested test.'})
            if 'laboratory' in attrs and laboratory.pk != self.instance.laboratory_id:
                if self.instance.payments.filter(stage='test', status='pending').exists():
                    raise serializers.ValidationError({'laboratory': 'Wait for the pending test payment to resolve before changing laboratories.'})
                if self.instance.payment_status == LabRequest.PAYMENT_PAID and self.instance.quoted_test_price != offering.price:
                    raise serializers.ValidationError({'laboratory': 'The assigned lab price differs from the paid amount. Resolve payment before reassignment.'})
                attrs['quoted_test_price'] = offering.price
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
            if profile.status != LabTechnicianProfile.STATUS_ACTIVE or not technician.is_active or technician.status != 'active':
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
