import uuid
from django.db import models


class LabPartner(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_VERIFIED = 'verified'
    STATUS_SUSPENDED = 'suspended'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_VERIFIED, 'Verified'),
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
        'accounts.User', on_delete=models.CASCADE, related_name='lab_partner_profile',
        null=True, blank=True
    )
    name = models.CharField(max_length=200)
    email = models.EmailField()
    phone = models.CharField(max_length=20)
    location = models.CharField(max_length=200, blank=True)
    contact_name = models.CharField(max_length=200, blank=True)
    accreditation = models.CharField(max_length=200, blank=True)
    license_number = models.CharField(max_length=100, blank=True)
    license_expiry = models.DateField(null=True, blank=True)
    id_number = models.CharField(max_length=50, blank=True)
    county = models.CharField(max_length=100, blank=True)
    address = models.TextField(blank=True)
    years_in_operation = models.PositiveIntegerField(null=True, blank=True)
    payout_method = models.CharField(max_length=20, choices=PAYOUT_CHOICES, default=PAYOUT_MPESA)
    payout_account = models.CharField(max_length=100, blank=True)
    references = models.JSONField(default=list)
    document_checklist = models.JSONField(default=list)
    background_consent = models.BooleanField(default=False)
    compliance_declaration = models.BooleanField(default=False)
    agreed_to_terms = models.BooleanField(default=False)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    status_note = models.TextField(blank=True)
    rejection_note = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    created_by = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='created_lab_partners'
    )
    updated_by = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='updated_lab_partners'
    )
    verified_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-submitted_at']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.reference:
            self.reference = f"LP-{uuid.uuid4().hex[:6].upper()}"
        super().save(*args, **kwargs)


class LabPartnerDocument(models.Model):
    partner = models.ForeignKey(LabPartner, on_delete=models.CASCADE, related_name='documents')
    name = models.CharField(max_length=200)
    file = models.FileField(upload_to='lab_partners/documents/', null=True, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.partner.name} - {self.name}"


class LabTechnicianProfile(models.Model):
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

    user = models.OneToOneField(
        'accounts.User', on_delete=models.CASCADE, related_name='lab_tech_profile',
        null=True, blank=True
    )
    partner = models.ForeignKey(LabPartner, on_delete=models.SET_NULL, null=True, blank=True, related_name='technicians')
    name = models.CharField(max_length=200, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    specialty = models.CharField(max_length=200, blank=True)
    license_number = models.CharField(max_length=100, blank=True)
    license_board = models.CharField(max_length=200, blank=True)
    license_country = models.CharField(max_length=100, blank=True)
    license_expiry = models.DateField(null=True, blank=True)
    id_number = models.CharField(max_length=50, blank=True)
    availability = models.CharField(max_length=200, blank=True)
    years_experience = models.PositiveIntegerField(null=True, blank=True)
    county = models.CharField(max_length=100, blank=True)
    address = models.TextField(blank=True)
    bio = models.TextField(blank=True)
    references = models.JSONField(default=list)
    document_checklist = models.JSONField(default=list)
    payout_method = models.CharField(max_length=20, choices=PAYOUT_CHOICES, default=PAYOUT_MPESA)
    payout_account = models.CharField(max_length=100, blank=True)
    background_consent = models.BooleanField(default=False)
    compliance_declaration = models.BooleanField(default=False)
    agreed_to_terms = models.BooleanField(default=False)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_ACTIVE)
    status_note = models.TextField(blank=True)
    rejection_note = models.TextField(blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    created_by = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='created_lab_technicians'
    )
    updated_by = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='updated_lab_technicians'
    )

    def __str__(self):
        return f"Lab Tech: {self.name or (self.user.full_name if self.user else 'Unknown')}"


class LabTechDocument(models.Model):
    STATUS_SUBMITTED = 'submitted'
    STATUS_VERIFIED = 'verified'
    STATUS_MISSING = 'missing'
    STATUS_CHOICES = [
        (STATUS_SUBMITTED, 'Submitted'),
        (STATUS_VERIFIED, 'Verified'),
        (STATUS_MISSING, 'Missing'),
    ]

    tech = models.ForeignKey(LabTechnicianProfile, on_delete=models.CASCADE, related_name='documents')
    name = models.CharField(max_length=200)
    file = models.FileField(upload_to='lab_tech/documents/', null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_SUBMITTED)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        tech_name = self.tech.name or 'Unknown'
        return f"{tech_name} - {self.name}"


class LabTest(models.Model):
    CATEGORY_BLOOD = 'blood'
    CATEGORY_CARDIAC = 'cardiac'
    CATEGORY_INFECTIOUS = 'infectious'
    CATEGORY_WELLNESS = 'wellness'
    CATEGORY_METABOLIC = 'metabolic'
    CATEGORY_CHOICES = [
        (CATEGORY_BLOOD, 'Blood'),
        (CATEGORY_CARDIAC, 'Cardiac'),
        (CATEGORY_INFECTIOUS, 'Infectious'),
        (CATEGORY_WELLNESS, 'Wellness'),
        (CATEGORY_METABOLIC, 'Metabolic'),
    ]

    reference = models.CharField(max_length=20, unique=True, blank=True)
    name = models.CharField(max_length=200)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default=CATEGORY_BLOOD)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    turnaround = models.CharField(max_length=100)
    sample_type = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.reference:
            self.reference = f"LAB-T-{uuid.uuid4().hex[:4].upper()}"
        super().save(*args, **kwargs)


class LabRequest(models.Model):
    STATUS_AWAITING = 'awaiting_sample'
    STATUS_COLLECTED = 'sample_collected'
    STATUS_PROCESSING = 'processing'
    STATUS_READY = 'result_ready'
    STATUS_COMPLETED = 'completed'
    STATUS_CANCELLED = 'cancelled'
    STATUS_CHOICES = [
        (STATUS_AWAITING, 'Awaiting Sample'),
        (STATUS_COLLECTED, 'Sample Collected'),
        (STATUS_PROCESSING, 'Processing'),
        (STATUS_READY, 'Result Ready'),
        (STATUS_COMPLETED, 'Completed'),
        (STATUS_CANCELLED, 'Cancelled'),
    ]

    PAYMENT_PAID = 'paid'
    PAYMENT_PENDING = 'pending'
    PAYMENT_CHOICES = [
        (PAYMENT_PAID, 'Paid'),
        (PAYMENT_PENDING, 'Pending'),
    ]

    PRIORITY_ROUTINE = 'routine'
    PRIORITY_PRIORITY = 'priority'
    PRIORITY_CHOICES = [
        (PRIORITY_ROUTINE, 'Routine'),
        (PRIORITY_PRIORITY, 'Priority'),
    ]

    CHANNEL_WALKIN = 'walk_in'
    CHANNEL_COLLECTION = 'collection'
    CHANNEL_CHOICES = [
        (CHANNEL_WALKIN, 'Walk-in'),
        (CHANNEL_COLLECTION, 'Collection'),
    ]

    reference = models.CharField(max_length=20, unique=True, blank=True)
    test = models.ForeignKey(LabTest, on_delete=models.SET_NULL, null=True, related_name='requests')
    patient = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='lab_requests'
    )
    patient_name = models.CharField(max_length=200)
    patient_phone = models.CharField(max_length=20)
    patient_email = models.EmailField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_AWAITING)
    payment_status = models.CharField(max_length=20, choices=PAYMENT_CHOICES, default=PAYMENT_PENDING)
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default=PRIORITY_ROUTINE)
    channel = models.CharField(max_length=20, choices=CHANNEL_CHOICES, default=CHANNEL_WALKIN)
    ordering_doctor = models.CharField(max_length=200, blank=True)
    notes = models.TextField(blank=True)
    assigned_technician = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_lab_requests'
    )
    scheduled_at = models.DateTimeField(null=True, blank=True)
    requested_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-requested_at']

    def __str__(self):
        return self.reference

    def save(self, *args, **kwargs):
        if not self.reference:
            self.reference = f"LAB-{uuid.uuid4().hex[:6].upper()}"
        super().save(*args, **kwargs)


class LabAuditLog(models.Model):
    request = models.ForeignKey(LabRequest, on_delete=models.CASCADE, related_name='audit_logs')
    action = models.CharField(max_length=500)
    performed_by = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL, null=True, blank=True
    )
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.request.reference} - {self.action}"


class LabResult(models.Model):
    reference = models.CharField(max_length=20, unique=True, blank=True)
    request = models.OneToOneField(LabRequest, on_delete=models.CASCADE, related_name='result')
    summary = models.TextField()
    file = models.FileField(upload_to='lab/results/', null=True, blank=True)
    filename = models.CharField(max_length=255, blank=True)
    flags = models.JSONField(default=list)
    is_abnormal = models.BooleanField(default=False)
    recommendation = models.TextField(blank=True)
    reviewed_by = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL, null=True, blank=True
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.reference

    def save(self, *args, **kwargs):
        if not self.reference:
            self.reference = f"RES-{uuid.uuid4().hex[:6].upper()}"
        super().save(*args, **kwargs)
