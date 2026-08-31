import uuid
from django.db import models


class SiteSettings(models.Model):
    support_email = models.EmailField(default='support@avapharmacy.co.ke')
    support_phone = models.CharField(max_length=50, default='+254 700 000 000')
    whatsapp_phone = models.CharField(max_length=50, default='+254 700 000 000')
    support_address = models.CharField(max_length=255, default='Karen / The Hub, Karen, Nairobi, Kenya')
    support_hours = models.CharField(max_length=120, default='Mon - Sun: 09am - 5pm')
    postal_address = models.CharField(max_length=255, blank=True)
    health_safety_code = models.CharField(max_length=80, blank=True)
    premises_registration_number = models.CharField(max_length=100, blank=True)
    online_pharmacy_license_number = models.CharField(max_length=100, blank=True)
    superintendent_name = models.CharField(max_length=160, blank=True)
    superintendent_registration_number = models.CharField(max_length=100, blank=True)
    pharmacist_consultation_hours = models.CharField(max_length=160, blank=True)
    ppb_contact_name = models.CharField(max_length=160, default='The Pharmacy and Poisons Board')
    ppb_contact_address = models.CharField(
        max_length=255,
        default='Lenana Road Opposite Russian Embassy, P. O. Box 27663-00506, Nairobi, Kenya',
    )
    ppb_contact_phone = models.CharField(max_length=80, default='+254 709 770 100')
    ppb_contact_email = models.EmailField(default='info@pharmacyboardkenya.org.ke')
    ppb_website = models.URLField(default='https://www.pharmacyboardkenya.org.ke')
    complaint_policy_url = models.CharField(max_length=255, default='/help')
    privacy_policy_url = models.CharField(max_length=255, default='/privacy')
    returns_policy_url = models.CharField(max_length=255, default='/returns')
    base_delivery_fee = models.DecimalField(max_digits=10, decimal_places=2, default=300)
    free_delivery_threshold = models.DecimalField(max_digits=10, decimal_places=2, default=3000)
    active_delivery_zones = models.TextField(default='Nairobi, Kiambu, Mombasa')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'site settings'
        verbose_name_plural = 'site settings'

    def __str__(self):
        return 'Site settings'

    @classmethod
    def get_solo(cls):
        settings, _ = cls.objects.get_or_create(pk=1)
        return settings

    @property
    def active_delivery_zones_list(self):
        return [zone.strip() for zone in self.active_delivery_zones.split(',') if zone.strip()]

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)


class NewsletterSubscriber(models.Model):
    email = models.EmailField(unique=True)
    source = models.CharField(max_length=100, blank=True, default='website')
    is_active = models.BooleanField(default=True)
    subscribed_at = models.DateTimeField(auto_now_add=True)
    last_confirmation_sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-subscribed_at']
        indexes = [
            models.Index(fields=['email'], name='support_new_email_4e6b95_idx'),
            models.Index(fields=['is_active', '-subscribed_at'], name='support_new_is_acti_9b5f3a_idx'),
        ]

    def __str__(self):
        return self.email

    def save(self, *args, **kwargs):
        self.email = (self.email or '').strip().lower()
        self.source = (self.source or 'website').strip() or 'website'
        super().save(*args, **kwargs)


class ComplianceEvidence(models.Model):
    TYPE_ODPC_CERTIFICATE = 'odpc_certificate'
    TYPE_DATA_CENTER_PROOF = 'data_center_proof'
    TYPE_X509_CERTIFICATE = 'x509_certificate'
    TYPE_THIRD_PARTY_SLA = 'third_party_sla'
    TYPE_BACKUP_EVIDENCE = 'backup_evidence'
    TYPE_ISO27001_CONTROL = 'iso27001_control'
    TYPE_PPB_AUTHORIZATION = 'ppb_authorization'
    TYPE_QA_AUDIT_REPORT = 'qa_audit_report'
    TYPE_CHOICES = [
        (TYPE_ODPC_CERTIFICATE, 'ODPC certificate'),
        (TYPE_DATA_CENTER_PROOF, 'Kenya data-center proof'),
        (TYPE_X509_CERTIFICATE, 'X.509 / SSL certificate'),
        (TYPE_THIRD_PARTY_SLA, 'Third-party SLA'),
        (TYPE_BACKUP_EVIDENCE, 'Backup evidence'),
        (TYPE_ISO27001_CONTROL, 'ISO/IEC 27001 control evidence'),
        (TYPE_PPB_AUTHORIZATION, 'PPB authorization'),
        (TYPE_QA_AUDIT_REPORT, 'QA audit report'),
    ]

    STATUS_ACTIVE = 'active'
    STATUS_REVIEW_DUE = 'review_due'
    STATUS_EXPIRED = 'expired'
    STATUS_CHOICES = [
        (STATUS_ACTIVE, 'Active'),
        (STATUS_REVIEW_DUE, 'Review due'),
        (STATUS_EXPIRED, 'Expired'),
    ]

    evidence_type = models.CharField(max_length=40, choices=TYPE_CHOICES)
    title = models.CharField(max_length=200)
    reference_number = models.CharField(max_length=120, blank=True)
    issuing_authority = models.CharField(max_length=160, blank=True)
    file = models.FileField(upload_to='compliance/evidence/', blank=True)
    external_url = models.URLField(blank=True)
    issued_at = models.DateField(null=True, blank=True)
    expires_at = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_ACTIVE)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_compliance_evidence',
    )
    updated_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='updated_compliance_evidence',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['evidence_type', 'expires_at', 'title']
        indexes = [
            models.Index(fields=['evidence_type', 'status']),
            models.Index(fields=['expires_at']),
        ]

    def __str__(self):
        return f'{self.get_evidence_type_display()} - {self.title}'


class SupportTicket(models.Model):
    CHANNEL_ORDER = 'order'
    CHANNEL_PRESCRIPTION = 'prescription'
    CHANNEL_CONSULTATION = 'consultation'
    CHANNEL_OTHER = 'other'
    CHANNEL_CHOICES = [
        (CHANNEL_ORDER, 'Order'),
        (CHANNEL_PRESCRIPTION, 'Prescription'),
        (CHANNEL_CONSULTATION, 'Consultation'),
        (CHANNEL_OTHER, 'Other'),
    ]

    PRIORITY_LOW = 'low'
    PRIORITY_MEDIUM = 'medium'
    PRIORITY_HIGH = 'high'
    PRIORITY_CHOICES = [
        (PRIORITY_LOW, 'Low'),
        (PRIORITY_MEDIUM, 'Medium'),
        (PRIORITY_HIGH, 'High'),
    ]

    STATUS_OPEN = 'open'
    STATUS_IN_PROGRESS = 'in_progress'
    STATUS_RESOLVED = 'resolved'
    STATUS_CHOICES = [
        (STATUS_OPEN, 'Open'),
        (STATUS_IN_PROGRESS, 'In Progress'),
        (STATUS_RESOLVED, 'Resolved'),
    ]

    reference = models.CharField(max_length=20, unique=True, blank=True)
    customer = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL, null=True, related_name='support_tickets'
    )
    customer_name = models.CharField(max_length=200)
    customer_email = models.EmailField()
    channel = models.CharField(max_length=20, choices=CHANNEL_CHOICES, default=CHANNEL_OTHER)
    reference_id = models.CharField(max_length=50, blank=True)
    subject = models.CharField(max_length=500)
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default=PRIORITY_MEDIUM)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_OPEN)
    assigned_to = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_tickets'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['customer', 'status']),
            models.Index(fields=['assigned_to', 'status']),
            models.Index(fields=['status', 'priority', '-created_at']),
        ]

    def __str__(self):
        return self.reference

    def save(self, *args, **kwargs):
        if not self.reference:
            self.reference = f"SUP-{uuid.uuid4().hex[:6].upper()}"
        super().save(*args, **kwargs)


class SupportNote(models.Model):
    ticket = models.ForeignKey(SupportTicket, on_delete=models.CASCADE, related_name='notes')
    author = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL, null=True
    )
    author_name = models.CharField(max_length=200)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['ticket', 'created_at']),
        ]

    def __str__(self):
        return f"{self.ticket.reference} - {self.author_name}"
