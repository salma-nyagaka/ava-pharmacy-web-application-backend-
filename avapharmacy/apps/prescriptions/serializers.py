from rest_framework import serializers
from .models import Prescription, PrescriptionFile, PrescriptionItem, PrescriptionAuditLog


class PrescriptionFileSerializer(serializers.ModelSerializer):
    class Meta:
        model = PrescriptionFile
        fields = ('id', 'file', 'filename', 'uploaded_at')
        read_only_fields = ('id', 'uploaded_at')


class PrescriptionItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = PrescriptionItem
        fields = ('id', 'name', 'dose', 'frequency', 'quantity')
        read_only_fields = ('id',)


class PrescriptionAuditLogSerializer(serializers.ModelSerializer):
    performed_by_name = serializers.ReadOnlyField(source='performed_by.full_name')

    class Meta:
        model = PrescriptionAuditLog
        fields = ('id', 'action', 'performed_by', 'performed_by_name', 'timestamp')
        read_only_fields = ('id', 'timestamp')


class PrescriptionSerializer(serializers.ModelSerializer):
    files = PrescriptionFileSerializer(many=True, read_only=True)
    items = PrescriptionItemSerializer(many=True, read_only=True)
    audit_logs = PrescriptionAuditLogSerializer(many=True, read_only=True)
    patient_name_display = serializers.ReadOnlyField(source='patient.full_name')
    pharmacist_name = serializers.ReadOnlyField(source='pharmacist.full_name')

    class Meta:
        model = Prescription
        fields = (
            'id', 'reference', 'patient', 'patient_name', 'patient_name_display',
            'doctor_name', 'pharmacist', 'pharmacist_name', 'status', 'dispatch_status',
            'notes', 'pharmacist_notes', 'files', 'items', 'audit_logs',
            'submitted_at', 'updated_at'
        )
        read_only_fields = ('id', 'reference', 'patient', 'submitted_at', 'updated_at')


class PrescriptionUploadSerializer(serializers.Serializer):
    patient_name = serializers.CharField(max_length=200)
    doctor_name = serializers.CharField(max_length=200, required=False, allow_blank=True)
    notes = serializers.CharField(required=False, allow_blank=True)
    files = serializers.ListField(
        child=serializers.FileField(),
        min_length=1
    )


class PrescriptionUpdateSerializer(serializers.ModelSerializer):
    items = PrescriptionItemSerializer(many=True, required=False)

    class Meta:
        model = Prescription
        fields = ('status', 'dispatch_status', 'pharmacist_notes', 'items')

    def update(self, instance, validated_data):
        items_data = validated_data.pop('items', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if items_data is not None:
            instance.items.all().delete()
            for item_data in items_data:
                PrescriptionItem.objects.create(prescription=instance, **item_data)
        return instance


class PrescriptionAuditCreateSerializer(serializers.Serializer):
    action = serializers.CharField(max_length=500)
