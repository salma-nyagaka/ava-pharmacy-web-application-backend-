import uuid
from django.db import models


def prescription_upload_path(instance, filename):
    return f"prescriptions/{instance.prescription.id}/{filename}"


class Prescription(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_APPROVED = 'approved'
    STATUS_CLARIFICATION = 'clarification'
    STATUS_REJECTED = 'rejected'

    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_APPROVED, 'Approved'),
        (STATUS_CLARIFICATION, 'Clarification Required'),
        (STATUS_REJECTED, 'Rejected'),
    ]

    DISPATCH_NOT_STARTED = 'not_started'
    DISPATCH_QUEUED = 'queued'
    DISPATCH_PACKED = 'packed'
    DISPATCH_DISPATCHED = 'dispatched'
    DISPATCH_DELIVERED = 'delivered'

    DISPATCH_CHOICES = [
        (DISPATCH_NOT_STARTED, 'Not Started'),
        (DISPATCH_QUEUED, 'Queued'),
        (DISPATCH_PACKED, 'Packed'),
        (DISPATCH_DISPATCHED, 'Dispatched'),
        (DISPATCH_DELIVERED, 'Delivered'),
    ]

    reference = models.CharField(max_length=20, unique=True, blank=True)
    patient = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL, null=True, related_name='prescriptions'
    )
    patient_name = models.CharField(max_length=200)
    doctor_name = models.CharField(max_length=200, blank=True)
    pharmacist = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='reviewed_prescriptions'
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    dispatch_status = models.CharField(max_length=20, choices=DISPATCH_CHOICES, default=DISPATCH_NOT_STARTED)
    notes = models.TextField(blank=True)
    pharmacist_notes = models.TextField(blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-submitted_at']

    def __str__(self):
        return self.reference

    def save(self, *args, **kwargs):
        if not self.reference:
            self.reference = f"RX-{uuid.uuid4().hex[:6].upper()}"
        super().save(*args, **kwargs)


class PrescriptionFile(models.Model):
    prescription = models.ForeignKey(Prescription, on_delete=models.CASCADE, related_name='files')
    file = models.FileField(upload_to=prescription_upload_path)
    filename = models.CharField(max_length=255)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.prescription.reference} - {self.filename}"


class PrescriptionItem(models.Model):
    prescription = models.ForeignKey(Prescription, on_delete=models.CASCADE, related_name='items')
    name = models.CharField(max_length=200)
    dose = models.CharField(max_length=100, blank=True)
    frequency = models.CharField(max_length=100, blank=True)
    quantity = models.PositiveIntegerField(default=1)

    def __str__(self):
        return f"{self.prescription.reference} - {self.name}"


class PrescriptionAuditLog(models.Model):
    prescription = models.ForeignKey(Prescription, on_delete=models.CASCADE, related_name='audit_logs')
    action = models.CharField(max_length=500)
    performed_by = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL, null=True, blank=True
    )
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.prescription.reference} - {self.action}"
