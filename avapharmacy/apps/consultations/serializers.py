from rest_framework import serializers
from .models import DoctorProfile, DoctorDocument, Consultation, ConsultationMessage, DoctorPrescription, DoctorEarning


class DoctorDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = DoctorDocument
        fields = ('id', 'name', 'file', 'status', 'note', 'uploaded_at')
        read_only_fields = ('id', 'uploaded_at')


class DoctorProfileSerializer(serializers.ModelSerializer):
    documents = DoctorDocumentSerializer(many=True, read_only=True)

    class Meta:
        model = DoctorProfile
        fields = (
            'id', 'reference', 'user', 'name', 'type', 'specialty', 'email', 'phone',
            'license_number', 'facility', 'availability', 'languages', 'status',
            'status_note', 'commission', 'consult_fee', 'rating',
            'verified_at', 'submitted_at', 'updated_at', 'documents'
        )
        read_only_fields = ('id', 'reference', 'status', 'verified_at', 'submitted_at', 'updated_at')


class DoctorProfileListSerializer(serializers.ModelSerializer):
    class Meta:
        model = DoctorProfile
        fields = (
            'id', 'reference', 'name', 'type', 'specialty', 'facility',
            'consult_fee', 'rating', 'availability', 'status'
        )


class DoctorOnboardingSerializer(serializers.ModelSerializer):
    documents = serializers.ListField(
        child=serializers.FileField(), required=False, write_only=True
    )
    document_names = serializers.ListField(
        child=serializers.CharField(), required=False, write_only=True
    )

    class Meta:
        model = DoctorProfile
        fields = (
            'name', 'type', 'specialty', 'email', 'phone', 'license_number',
            'facility', 'availability', 'languages', 'consult_fee',
            'documents', 'document_names'
        )

    def create(self, validated_data):
        documents = validated_data.pop('documents', [])
        document_names = validated_data.pop('document_names', [])
        profile = DoctorProfile.objects.create(**validated_data)
        for i, doc_file in enumerate(documents):
            name = document_names[i] if i < len(document_names) else doc_file.name
            DoctorDocument.objects.create(doctor=profile, name=name, file=doc_file)
        return profile


class AdminDoctorUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = DoctorProfile
        fields = ('status', 'status_note', 'commission', 'consult_fee', 'verified_at')


class ConsultationMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ConsultationMessage
        fields = ('id', 'sender', 'sender_name', 'message', 'sent_at')
        read_only_fields = ('id', 'sent_at')


class ConsultationSerializer(serializers.ModelSerializer):
    doctor_name = serializers.ReadOnlyField(source='doctor.name')
    doctor_specialty = serializers.ReadOnlyField(source='doctor.specialty')
    messages = ConsultationMessageSerializer(many=True, read_only=True)

    class Meta:
        model = Consultation
        fields = (
            'id', 'reference', 'doctor', 'doctor_name', 'doctor_specialty',
            'patient', 'patient_name', 'patient_age', 'issue', 'status', 'priority',
            'channel', 'scheduled_at', 'is_pediatric', 'guardian_name', 'child_name',
            'child_age', 'weight_kg', 'consent_status', 'dosage_alert',
            'last_message_at', 'messages', 'created_at', 'updated_at'
        )
        read_only_fields = ('id', 'reference', 'patient', 'created_at', 'updated_at')


class ConsultationListSerializer(serializers.ModelSerializer):
    doctor_name = serializers.ReadOnlyField(source='doctor.name')

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
            'doctor', 'patient_name', 'patient_age', 'issue', 'priority',
            'scheduled_at', 'is_pediatric', 'guardian_name', 'child_name',
            'child_age', 'weight_kg'
        )


class ConsultationUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Consultation
        fields = ('status', 'consent_status', 'dosage_alert')


class DoctorPrescriptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = DoctorPrescription
        fields = ('id', 'reference', 'doctor', 'consultation', 'patient_name', 'items', 'status', 'notes', 'created_at')
        read_only_fields = ('id', 'reference', 'created_at')


class DoctorEarningSerializer(serializers.ModelSerializer):
    class Meta:
        model = DoctorEarning
        fields = ('id', 'consultation', 'amount', 'description', 'earned_at')
        read_only_fields = ('id', 'earned_at')
