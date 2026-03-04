import uuid
from django.db import models


class DoctorProfile(models.Model):
    TYPE_DOCTOR = 'doctor'
    TYPE_PEDIATRICIAN = 'pediatrician'
    TYPE_CHOICES = [
        (TYPE_DOCTOR, 'Doctor'),
        (TYPE_PEDIATRICIAN, 'Pediatrician'),
    ]

    STATUS_ACTIVE = 'active'
    STATUS_PENDING = 'pending'
    STATUS_SUSPENDED = 'suspended'
    STATUS_CHOICES = [
        (STATUS_ACTIVE, 'Active'),
        (STATUS_PENDING, 'Pending'),
        (STATUS_SUSPENDED, 'Suspended'),
    ]

    reference = models.CharField(max_length=20, unique=True, blank=True)
    user = models.OneToOneField(
        'accounts.User', on_delete=models.CASCADE, related_name='doctor_profile', null=True, blank=True
    )
    name = models.CharField(max_length=200)
    type = models.CharField(max_length=20, choices=TYPE_CHOICES, default=TYPE_DOCTOR)
    specialty = models.CharField(max_length=200)
    email = models.EmailField()
    phone = models.CharField(max_length=20)
    license_number = models.CharField(max_length=100)
    facility = models.CharField(max_length=200, blank=True)
    availability = models.CharField(max_length=200, blank=True)
    languages = models.JSONField(default=list)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    status_note = models.TextField(blank=True)
    commission = models.DecimalField(max_digits=5, decimal_places=2, default=10.00)
    consult_fee = models.DecimalField(max_digits=10, decimal_places=2, default=500.00)
    rating = models.DecimalField(max_digits=3, decimal_places=1, default=0.0)
    verified_at = models.DateTimeField(null=True, blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-submitted_at']

    def __str__(self):
        return f"{self.name} ({self.type})"

    def save(self, *args, **kwargs):
        if not self.reference:
            prefix = 'DOC' if self.type == self.TYPE_DOCTOR else 'PED'
            self.reference = f"{prefix}-{uuid.uuid4().hex[:6].upper()}"
        super().save(*args, **kwargs)


class DoctorDocument(models.Model):
    STATUS_SUBMITTED = 'submitted'
    STATUS_VERIFIED = 'verified'
    STATUS_MISSING = 'missing'
    STATUS_CHOICES = [
        (STATUS_SUBMITTED, 'Submitted'),
        (STATUS_VERIFIED, 'Verified'),
        (STATUS_MISSING, 'Missing'),
    ]

    doctor = models.ForeignKey(DoctorProfile, on_delete=models.CASCADE, related_name='documents')
    name = models.CharField(max_length=200)
    file = models.FileField(upload_to='doctors/documents/', null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_SUBMITTED)
    note = models.TextField(blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.doctor.name} - {self.name}"


class Consultation(models.Model):
    STATUS_WAITING = 'waiting'
    STATUS_IN_PROGRESS = 'in_progress'
    STATUS_COMPLETED = 'completed'
    STATUS_CANCELLED = 'cancelled'
    STATUS_CHOICES = [
        (STATUS_WAITING, 'Waiting'),
        (STATUS_IN_PROGRESS, 'In Progress'),
        (STATUS_COMPLETED, 'Completed'),
        (STATUS_CANCELLED, 'Cancelled'),
    ]

    PRIORITY_ROUTINE = 'routine'
    PRIORITY_PRIORITY = 'priority'
    PRIORITY_CHOICES = [
        (PRIORITY_ROUTINE, 'Routine'),
        (PRIORITY_PRIORITY, 'Priority'),
    ]

    reference = models.CharField(max_length=20, unique=True, blank=True)
    doctor = models.ForeignKey(DoctorProfile, on_delete=models.SET_NULL, null=True, related_name='consultations')
    patient = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL, null=True, related_name='consultations'
    )
    patient_name = models.CharField(max_length=200)
    patient_age = models.PositiveIntegerField(null=True, blank=True)
    issue = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_WAITING)
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default=PRIORITY_ROUTINE)
    channel = models.CharField(max_length=20, default='chat')
    scheduled_at = models.DateTimeField(null=True, blank=True)

    # Pediatric fields
    is_pediatric = models.BooleanField(default=False)
    guardian_name = models.CharField(max_length=200, blank=True)
    child_name = models.CharField(max_length=200, blank=True)
    child_age = models.PositiveIntegerField(null=True, blank=True)
    weight_kg = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    consent_status = models.CharField(
        max_length=20,
        choices=[('pending', 'Pending'), ('granted', 'Granted')],
        default='pending'
    )
    dosage_alert = models.BooleanField(default=False)

    last_message_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.reference

    def save(self, *args, **kwargs):
        if not self.reference:
            self.reference = f"CONS-{uuid.uuid4().hex[:6].upper()}"
        super().save(*args, **kwargs)


class ConsultationMessage(models.Model):
    consultation = models.ForeignKey(Consultation, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True)
    sender_name = models.CharField(max_length=200)
    message = models.TextField()
    sent_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['sent_at']

    def __str__(self):
        return f"{self.consultation.reference} - {self.sender_name}"


class DoctorPrescription(models.Model):
    STATUS_DRAFT = 'draft'
    STATUS_SENT = 'sent'
    STATUS_DISPENSED = 'dispensed'
    STATUS_CHOICES = [
        (STATUS_DRAFT, 'Draft'),
        (STATUS_SENT, 'Sent'),
        (STATUS_DISPENSED, 'Dispensed'),
    ]

    reference = models.CharField(max_length=20, unique=True, blank=True)
    doctor = models.ForeignKey(DoctorProfile, on_delete=models.SET_NULL, null=True, related_name='issued_prescriptions')
    consultation = models.ForeignKey(Consultation, on_delete=models.SET_NULL, null=True, blank=True, related_name='prescriptions')
    patient_name = models.CharField(max_length=200)
    items = models.JSONField(default=list)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.reference

    def save(self, *args, **kwargs):
        if not self.reference:
            self.reference = f"DRXP-{uuid.uuid4().hex[:6].upper()}"
        super().save(*args, **kwargs)


class DoctorEarning(models.Model):
    doctor = models.ForeignKey(DoctorProfile, on_delete=models.CASCADE, related_name='earnings')
    consultation = models.ForeignKey(Consultation, on_delete=models.SET_NULL, null=True, blank=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.CharField(max_length=200, blank=True)
    earned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-earned_at']

    def __str__(self):
        return f"{self.doctor.name} - KSh {self.amount}"
