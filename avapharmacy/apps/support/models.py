import uuid
from django.db import models


class NewsletterSubscriber(models.Model):
    email = models.EmailField(unique=True)
    source = models.CharField(max_length=100, blank=True, default='website')
    is_active = models.BooleanField(default=True)
    subscribed_at = models.DateTimeField(auto_now_add=True)
    last_confirmation_sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-subscribed_at']
        indexes = [
            models.Index(fields=['email']),
            models.Index(fields=['is_active', '-subscribed_at']),
        ]

    def __str__(self):
        return self.email

    def save(self, *args, **kwargs):
        self.email = (self.email or '').strip().lower()
        self.source = (self.source or 'website').strip() or 'website'
        super().save(*args, **kwargs)


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
