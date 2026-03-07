import uuid
from django.db import models


class DoctorProfile(models.Model):
    TYPE_DOCTOR = 'doctor'
    TYPE_CHOICES = [
        (TYPE_DOCTOR, 'Doctor'),
    ]

    STATUS_ACTIVE = 'active'
    STATUS_PENDING = 'pending'
    STATUS_SUSPENDED = 'suspended'
    STATUS_CHOICES = [
        (STATUS_ACTIVE, 'Active'),
        (STATUS_PENDING, 'Pending'),
        (STATUS_SUSPENDED, 'Suspended'),
    ]

    PAYOUT_MPESA = 'mpesa'
    PAYOUT_BANK = 'bank_transfer'
    PAYOUT_CHOICES = [
        (PAYOUT_MPESA, 'M-Pesa'),
        (PAYOUT_BANK, 'Bank Transfer'),
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
    license_board = models.CharField(max_length=200, blank=True)
    license_country = models.CharField(max_length=100, blank=True)
    license_expiry = models.DateField(null=True, blank=True)
    id_number = models.CharField(max_length=100, blank=True)
    facility = models.CharField(max_length=200, blank=True)
    availability = models.CharField(max_length=200, blank=True)
    bio = models.TextField(blank=True)
    languages = models.JSONField(default=list)
    consult_modes = models.JSONField(default=list)
    years_experience = models.PositiveIntegerField(null=True, blank=True)
    county = models.CharField(max_length=100, blank=True)
    address = models.TextField(blank=True)
    references = models.JSONField(default=list)
    document_checklist = models.JSONField(default=list)
    payout_method = models.CharField(max_length=20, choices=PAYOUT_CHOICES, default=PAYOUT_MPESA)
    payout_account = models.CharField(max_length=100, blank=True)
    background_consent = models.BooleanField(default=False)
    compliance_declaration = models.BooleanField(default=False)
    agreed_to_terms = models.BooleanField(default=False)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    status_note = models.TextField(blank=True)
    rejection_note = models.TextField(blank=True)
    commission = models.DecimalField(max_digits=5, decimal_places=2, default=10.00)
    consult_fee = models.DecimalField(max_digits=10, decimal_places=2, default=500.00)
    rating = models.DecimalField(max_digits=3, decimal_places=1, default=0.0)
    verified_at = models.DateTimeField(null=True, blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='created_doctor_profiles'
    )
    updated_by = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='updated_doctor_profiles'
    )

    class Meta:
        ordering = ['-submitted_at']

    def __str__(self):
        return f"{self.name} ({self.type})"

    def save(self, *args, **kwargs):
        if not self.reference:
            self.reference = f"DOC-{uuid.uuid4().hex[:6].upper()}"
        self.type = self.TYPE_DOCTOR
        super().save(*args, **kwargs)


class PediatricianProfile(models.Model):
    STATUS_ACTIVE = 'active'
    STATUS_PENDING = 'pending'
    STATUS_SUSPENDED = 'suspended'
    STATUS_CHOICES = [
        (STATUS_ACTIVE, 'Active'),
        (STATUS_PENDING, 'Pending'),
        (STATUS_SUSPENDED, 'Suspended'),
    ]

    PAYOUT_MPESA = 'mpesa'
    PAYOUT_BANK = 'bank_transfer'
    PAYOUT_CHOICES = [
        (PAYOUT_MPESA, 'M-Pesa'),
        (PAYOUT_BANK, 'Bank Transfer'),
    ]

    reference = models.CharField(max_length=20, unique=True, blank=True)
    user = models.OneToOneField(
        'accounts.User', on_delete=models.CASCADE, related_name='pediatrician_profile', null=True, blank=True
    )
    name = models.CharField(max_length=200)
    specialty = models.CharField(max_length=200)
    email = models.EmailField()
    phone = models.CharField(max_length=20)
    license_number = models.CharField(max_length=100)
    license_board = models.CharField(max_length=200, blank=True)
    license_country = models.CharField(max_length=100, blank=True)
    license_expiry = models.DateField(null=True, blank=True)
    id_number = models.CharField(max_length=100, blank=True)
    facility = models.CharField(max_length=200, blank=True)
    availability = models.CharField(max_length=200, blank=True)
    bio = models.TextField(blank=True)
    languages = models.JSONField(default=list)
    consult_modes = models.JSONField(default=list)
    years_experience = models.PositiveIntegerField(null=True, blank=True)
    county = models.CharField(max_length=100, blank=True)
    address = models.TextField(blank=True)
    references = models.JSONField(default=list)
    document_checklist = models.JSONField(default=list)
    payout_method = models.CharField(max_length=20, choices=PAYOUT_CHOICES, default=PAYOUT_MPESA)
    payout_account = models.CharField(max_length=100, blank=True)
    background_consent = models.BooleanField(default=False)
    compliance_declaration = models.BooleanField(default=False)
    agreed_to_terms = models.BooleanField(default=False)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    status_note = models.TextField(blank=True)
    rejection_note = models.TextField(blank=True)
    commission = models.DecimalField(max_digits=5, decimal_places=2, default=10.00)
    consult_fee = models.DecimalField(max_digits=10, decimal_places=2, default=500.00)
    rating = models.DecimalField(max_digits=3, decimal_places=1, default=0.0)
    verified_at = models.DateTimeField(null=True, blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='created_pediatrician_profiles'
    )
    updated_by = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='updated_pediatrician_profiles'
    )

    class Meta:
        ordering = ['-submitted_at']

    def __str__(self):
        return f"{self.name} (pediatrician)"

    def save(self, *args, **kwargs):
        if not self.reference:
            self.reference = f"PED-{uuid.uuid4().hex[:6].upper()}"
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


class PediatricianDocument(models.Model):
    STATUS_SUBMITTED = 'submitted'
    STATUS_VERIFIED = 'verified'
    STATUS_MISSING = 'missing'
    STATUS_CHOICES = [
        (STATUS_SUBMITTED, 'Submitted'),
        (STATUS_VERIFIED, 'Verified'),
        (STATUS_MISSING, 'Missing'),
    ]

    pediatrician = models.ForeignKey(PediatricianProfile, on_delete=models.CASCADE, related_name='documents')
    name = models.CharField(max_length=200)
    file = models.FileField(upload_to='pediatricians/documents/', null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_SUBMITTED)
    note = models.TextField(blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.pediatrician.name} - {self.name}"


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
    pediatrician = models.ForeignKey(PediatricianProfile, on_delete=models.SET_NULL, null=True, blank=True, related_name='consultations')
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

    @property
    def provider_profile(self):
        return self.pediatrician or self.doctor

    @property
    def provider_name(self):
        provider = self.provider_profile
        return provider.name if provider else ''

    @property
    def provider_specialty(self):
        provider = self.provider_profile
        return provider.specialty if provider else ''

    def save(self, *args, **kwargs):
        if not self.reference:
            self.reference = f"CONS-{uuid.uuid4().hex[:6].upper()}"
        if self.pediatrician_id:
            self.is_pediatric = True
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


class PediatricianPrescription(models.Model):
    STATUS_DRAFT = 'draft'
    STATUS_SENT = 'sent'
    STATUS_DISPENSED = 'dispensed'
    STATUS_CHOICES = [
        (STATUS_DRAFT, 'Draft'),
        (STATUS_SENT, 'Sent'),
        (STATUS_DISPENSED, 'Dispensed'),
    ]

    reference = models.CharField(max_length=20, unique=True, blank=True)
    pediatrician = models.ForeignKey(PediatricianProfile, on_delete=models.SET_NULL, null=True, related_name='issued_prescriptions')
    consultation = models.ForeignKey(Consultation, on_delete=models.SET_NULL, null=True, blank=True, related_name='pediatrician_prescriptions')
    patient_name = models.CharField(max_length=200)
    items = models.JSONField(default=list)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.reference

    def save(self, *args, **kwargs):
        if not self.reference:
            self.reference = f"PED-RX-{uuid.uuid4().hex[:6].upper()}"
        super().save(*args, **kwargs)


class DoctorEarning(models.Model):
    doctor = models.ForeignKey(DoctorProfile, on_delete=models.CASCADE, null=True, blank=True, related_name='earnings')
    consultation = models.ForeignKey(Consultation, on_delete=models.SET_NULL, null=True, blank=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.CharField(max_length=200, blank=True)
    earned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-earned_at']

    def __str__(self):
        return f"{self.doctor.name if self.doctor else 'Unknown'} - KSh {self.amount}"


class PediatricianEarning(models.Model):
    pediatrician = models.ForeignKey(PediatricianProfile, on_delete=models.CASCADE, related_name='earnings')
    consultation = models.ForeignKey(Consultation, on_delete=models.SET_NULL, null=True, blank=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.CharField(max_length=200, blank=True)
    earned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-earned_at']

    def __str__(self):
        return f"{self.pediatrician.name if self.pediatrician else 'Unknown'} - KSh {self.amount}"
