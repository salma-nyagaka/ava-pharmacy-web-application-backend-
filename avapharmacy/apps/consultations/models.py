import uuid
from django.db import models

from avapharmacy.fields import OptionalEncryptedCharField


class BaseClinicianProfile(models.Model):
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

    GENDER_MALE = 'male'
    GENDER_FEMALE = 'female'
    GENDER_OTHER = 'other'
    GENDER_CHOICES = [
        (GENDER_MALE, 'Male'),
        (GENDER_FEMALE, 'Female'),
        (GENDER_OTHER, 'Other'),
    ]

    reference = models.CharField(max_length=20, unique=True, blank=True)
    user = models.OneToOneField(
        'accounts.User', on_delete=models.CASCADE, null=True, blank=True
    )
    name = models.CharField(max_length=200)
    gender = models.CharField(max_length=20, choices=GENDER_CHOICES, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
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
    availability_schedule = models.JSONField(default=list, blank=True)
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
    payout_account_number = OptionalEncryptedCharField(max_length=255, blank=True)
    currency = models.CharField(max_length=10, default='KES')
    background_consent = models.BooleanField(default=False)
    compliance_declaration = models.BooleanField(default=False)
    agreed_to_terms = models.BooleanField(default=False)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    is_verified = models.BooleanField(default=False)
    suspension_reason = models.TextField(blank=True)
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
        related_name='+'
    )
    updated_by = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='+'
    )

    class Meta:
        abstract = True
        ordering = ['-submitted_at']
    @property
    def provider_type(self):
        raise NotImplementedError

    @property
    def role_label(self):
        return self.provider_type.replace('_', ' ')


class ClinicianQuerySet(models.QuerySet):
    def doctors(self):
        return self.filter(provider_type=ClinicianProfile.TYPE_DOCTOR)

    def pediatricians(self):
        return self.filter(provider_type=ClinicianProfile.TYPE_PEDIATRICIAN)

    def active(self):
        return self.filter(status=ClinicianProfile.STATUS_ACTIVE)


class ClinicianProfile(BaseClinicianProfile):
    TYPE_DOCTOR = 'doctor'
    TYPE_PEDIATRICIAN = 'pediatrician'
    TYPE_CHOICES = [
        (TYPE_DOCTOR, 'Doctor'),
        (TYPE_PEDIATRICIAN, 'Pediatrician'),
    ]

    user = models.OneToOneField(
        'accounts.User', on_delete=models.CASCADE, related_name='clinician_profile', null=True, blank=True
    )
    provider_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    legacy_doctor_id = models.PositiveIntegerField(null=True, blank=True, unique=True)
    legacy_pediatrician_id = models.PositiveIntegerField(null=True, blank=True, unique=True)
    created_by = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='created_clinician_profiles'
    )
    updated_by = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='updated_clinician_profiles'
    )

    objects = ClinicianQuerySet.as_manager()

    class Meta(BaseClinicianProfile.Meta):
        indexes = [
            models.Index(fields=['provider_type', 'status']),
            models.Index(fields=['status', '-submitted_at']),
            models.Index(fields=['user', 'status']),
        ]

    @property
    def provider_type_label(self):
        return dict(self.TYPE_CHOICES).get(self.provider_type, self.provider_type)

    def __str__(self):
        return f"{self.name} ({self.provider_type})"

    def save(self, *args, **kwargs):
        if not self.reference:
            prefix = 'DOC' if self.provider_type == self.TYPE_DOCTOR else 'PED'
            self.reference = f"{prefix}-{uuid.uuid4().hex[:6].upper()}"
        super().save(*args, **kwargs)


class BaseClinicianDocument(models.Model):
    STATUS_SUBMITTED = 'submitted'
    STATUS_VERIFIED = 'verified'
    STATUS_MISSING = 'missing'
    STATUS_CHOICES = [
        (STATUS_SUBMITTED, 'Submitted'),
        (STATUS_VERIFIED, 'Verified'),
        (STATUS_MISSING, 'Missing'),
    ]

    name = models.CharField(max_length=200)
    file = models.FileField(upload_to='doctors/documents/', null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_SUBMITTED)
    note = models.TextField(blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract = True


class ClinicianDocument(BaseClinicianDocument):
    clinician = models.ForeignKey(ClinicianProfile, on_delete=models.CASCADE, related_name='documents')

    def upload_to(self):
        if self.clinician.provider_type == ClinicianProfile.TYPE_PEDIATRICIAN:
            return 'pediatricians/documents/'
        return 'doctors/documents/'

    def __str__(self):
        return f"{self.clinician.name} - {self.name}"


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
    clinician = models.ForeignKey(
        'ClinicianProfile',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='consultations',
    )
    patient = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL, null=True, related_name='consultations'
    )
    patient_name = models.CharField(max_length=200)
    patient_email = models.EmailField(blank=True)
    patient_phone = models.CharField(max_length=20, blank=True)
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
    ended_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['clinician', 'status']),
            models.Index(fields=['patient', 'status']),
            models.Index(fields=['status', '-created_at']),
            models.Index(fields=['is_pediatric', 'status']),
        ]

    def __str__(self):
        return self.reference

    @property
    def provider_profile(self):
        return self.clinician

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
        if self.clinician_id:
            self.is_pediatric = self.clinician.provider_type == ClinicianProfile.TYPE_PEDIATRICIAN
        super().save(*args, **kwargs)


class ConsultationMessage(models.Model):
    TYPE_TEXT = 'text'
    TYPE_IMAGE = 'image'
    TYPE_FILE = 'file'
    TYPE_E_PRESCRIPTION = 'e_prescription'
    TYPE_CHOICES = [
        (TYPE_TEXT, 'Text'),
        (TYPE_IMAGE, 'Image'),
        (TYPE_FILE, 'File'),
        (TYPE_E_PRESCRIPTION, 'E-Prescription'),
    ]

    consultation = models.ForeignKey(Consultation, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True)
    sender_name = models.CharField(max_length=200)
    message = models.TextField()
    message_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default=TYPE_TEXT)
    attachment = models.FileField(upload_to='consultations/messages/', null=True, blank=True)
    sent_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['sent_at']
        indexes = [
            models.Index(fields=['consultation', 'sent_at']),
        ]

    def __str__(self):
        return f"{self.consultation.reference} - {self.sender_name}"


class BaseClinicianPrescription(models.Model):
    STATUS_DRAFT = 'draft'
    STATUS_SENT = 'sent'
    STATUS_DISPENSED = 'dispensed'
    STATUS_CHOICES = [
        (STATUS_DRAFT, 'Draft'),
        (STATUS_SENT, 'Sent'),
        (STATUS_DISPENSED, 'Dispensed'),
    ]

    reference = models.CharField(max_length=20, unique=True, blank=True)
    consultation = models.ForeignKey(Consultation, on_delete=models.SET_NULL, null=True, blank=True, related_name='prescriptions')
    patient_name = models.CharField(max_length=200)
    items = models.JSONField(default=list)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    digital_signature = models.CharField(max_length=255, blank=True)
    notes = models.TextField(blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    dispensed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract = True
        ordering = ['-created_at']

    def __str__(self):
        return self.reference


class ClinicianPrescription(BaseClinicianPrescription):
    clinician = models.ForeignKey(ClinicianProfile, on_delete=models.SET_NULL, null=True, related_name='issued_prescriptions')
    consultation = models.ForeignKey(
        Consultation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='clinician_prescriptions',
    )

    class Meta(BaseClinicianPrescription.Meta):
        indexes = [
            models.Index(fields=['clinician', 'status']),
            models.Index(fields=['consultation', 'status']),
        ]

    def save(self, *args, **kwargs):
        if not self.reference:
            prefix = 'DRXP' if self.clinician and self.clinician.provider_type == ClinicianProfile.TYPE_DOCTOR else 'PED-RX'
            self.reference = f"{prefix}-{uuid.uuid4().hex[:6].upper()}"
        super().save(*args, **kwargs)


class BaseClinicianEarning(models.Model):
    consultation = models.ForeignKey(Consultation, on_delete=models.SET_NULL, null=True, blank=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.CharField(max_length=200, blank=True)
    earned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract = True
        ordering = ['-earned_at']


class ClinicianEarning(BaseClinicianEarning):
    clinician = models.ForeignKey(ClinicianProfile, on_delete=models.CASCADE, related_name='earnings')

    class Meta(BaseClinicianEarning.Meta):
        indexes = [
            models.Index(fields=['clinician', '-earned_at']),
        ]

    def __str__(self):
        return f"{self.clinician.name if self.clinician else 'Unknown'} - KSh {self.amount}"
