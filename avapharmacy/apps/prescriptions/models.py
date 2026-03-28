import uuid
from datetime import timedelta
from django.db import models
from django.utils import timezone


def prescription_upload_path(instance, filename):
    return f"prescriptions/{instance.prescription.id}/{filename}"


class Prescription(models.Model):
    SOURCE_UPLOAD = 'upload'
    SOURCE_E_PRESCRIPTION = 'e_prescription'
    SOURCE_CHOICES = [
        (SOURCE_UPLOAD, 'Upload'),
        (SOURCE_E_PRESCRIPTION, 'E-Prescription'),
    ]

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
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default=SOURCE_UPLOAD)
    clinician_prescription = models.ForeignKey(
        'consultations.ClinicianPrescription',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='linked_prescriptions',
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    dispatch_status = models.CharField(max_length=20, choices=DISPATCH_CHOICES, default=DISPATCH_NOT_STARTED)
    notes = models.TextField(blank=True)
    pharmacist_notes = models.TextField(blank=True)
    clarification_message = models.TextField(blank=True)
    resubmitted_at = models.DateTimeField(null=True, blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-submitted_at']
        indexes = [
            models.Index(fields=['patient', 'status']),
            models.Index(fields=['status', '-submitted_at']),
            models.Index(fields=['dispatch_status', '-submitted_at']),
            models.Index(fields=['source', 'status']),
        ]

    def __str__(self):
        return self.reference

    def save(self, *args, **kwargs):
        if not self.reference:
            self.reference = f"RX-{uuid.uuid4().hex[:6].upper()}"
        super().save(*args, **kwargs)

    @property
    def is_overdue(self):
        if self.status != self.STATUS_PENDING:
            return False
        return self.submitted_at <= timezone.now() - timedelta(hours=24)


class PrescriptionFile(models.Model):
    prescription = models.ForeignKey(Prescription, on_delete=models.CASCADE, related_name='files')
    file = models.FileField(upload_to=prescription_upload_path)
    filename = models.CharField(max_length=255)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['prescription', '-uploaded_at']),
        ]

    def __str__(self):
        return f"{self.prescription.reference} - {self.filename}"


class PrescriptionItem(models.Model):
    prescription = models.ForeignKey(Prescription, on_delete=models.CASCADE, related_name='items')
    name = models.CharField(max_length=200)
    product = models.ForeignKey(
        'products.Product',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='prescription_items',
    )
    dose = models.CharField(max_length=100, blank=True)
    frequency = models.CharField(max_length=100, blank=True)
    quantity = models.PositiveIntegerField(default=1)
    is_controlled_substance = models.BooleanField(default=False)

    class Meta:
        indexes = [
            models.Index(fields=['prescription', 'product']),
        ]

    def __str__(self):
        return f"{self.prescription.reference} - {self.name}"


class PrescriptionAuditLog(models.Model):
    prescription = models.ForeignKey(Prescription, on_delete=models.CASCADE, related_name='audit_logs')
    action = models.CharField(max_length=500)
    notes = models.TextField(blank=True)
    performed_by = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL, null=True, blank=True
    )
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['prescription', '-timestamp']),
        ]

    def __str__(self):
        return f"{self.prescription.reference} - {self.action}"


class PrescriptionClarificationMessage(models.Model):
    SENDER_PATIENT = 'patient'
    SENDER_PHARMACIST = 'pharmacist'
    SENDER_ADMIN = 'admin'
    SENDER_SYSTEM = 'system'

    SENDER_CHOICES = [
        (SENDER_PATIENT, 'Patient'),
        (SENDER_PHARMACIST, 'Pharmacist'),
        (SENDER_ADMIN, 'Admin'),
        (SENDER_SYSTEM, 'System'),
    ]

    prescription = models.ForeignKey(
        Prescription,
        on_delete=models.CASCADE,
        related_name='clarification_messages',
    )
    sender = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='prescription_clarification_messages',
    )
    sender_role = models.CharField(max_length=20, choices=SENDER_CHOICES, default=SENDER_SYSTEM)
    sender_name = models.CharField(max_length=200, blank=True)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['prescription', 'created_at']),
            models.Index(fields=['sender_role', 'created_at']),
        ]

    def __str__(self):
        return f"{self.prescription.reference} - {self.sender_role}"
