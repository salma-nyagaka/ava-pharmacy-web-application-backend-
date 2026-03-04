from rest_framework import serializers
from .models import LabPartner, LabPartnerDocument, LabTechnicianProfile, LabTest, LabRequest, LabAuditLog, LabResult


class LabPartnerDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = LabPartnerDocument
        fields = ('id', 'name', 'file', 'uploaded_at')
        read_only_fields = ('id', 'uploaded_at')


class LabTechnicianProfileSerializer(serializers.ModelSerializer):
    user_name = serializers.ReadOnlyField(source='user.full_name')
    user_email = serializers.ReadOnlyField(source='user.email')
    user_phone = serializers.ReadOnlyField(source='user.phone')

    class Meta:
        model = LabTechnicianProfile
        fields = (
            'id', 'user', 'user_name', 'user_email', 'user_phone',
            'specialty', 'license_number', 'license_expiry', 'id_number', 'is_active', 'created_at'
        )
        read_only_fields = ('id', 'created_at')


class LabPartnerSerializer(serializers.ModelSerializer):
    documents = LabPartnerDocumentSerializer(many=True, read_only=True)
    technicians = LabTechnicianProfileSerializer(many=True, read_only=True)

    class Meta:
        model = LabPartner
        fields = (
            'id', 'reference', 'name', 'email', 'phone', 'location', 'contact_name',
            'accreditation', 'license_number', 'license_expiry', 'id_number',
            'county', 'address', 'payout_method', 'payout_account',
            'status', 'notes', 'submitted_at', 'verified_at', 'documents', 'technicians'
        )
        read_only_fields = ('id', 'reference', 'submitted_at')


class LabPartnerCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = LabPartner
        fields = (
            'name', 'email', 'phone', 'location', 'contact_name',
            'accreditation', 'license_number', 'license_expiry', 'id_number',
            'county', 'address', 'payout_method', 'payout_account', 'notes'
        )


class LabPartnerUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = LabPartner
        fields = ('status', 'notes', 'verified_at', 'payout_method', 'payout_account')


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
    audit_logs = LabAuditLogSerializer(many=True, read_only=True)
    result = LabResultSerializer(read_only=True)
    technician_name = serializers.ReadOnlyField(source='assigned_technician.full_name')

    class Meta:
        model = LabRequest
        fields = (
            'id', 'reference', 'test', 'test_name', 'test_category',
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
