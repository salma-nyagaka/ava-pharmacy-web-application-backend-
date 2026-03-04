from django.db import models


class Notification(models.Model):
    ORDER_STATUS = 'order_status'
    PRESCRIPTION_STATUS = 'prescription_status'
    CONSULTATION_MESSAGE = 'consultation_message'
    NEW_CONSULTATION = 'new_consultation'
    CONSULTATION_STATUS = 'consultation_status'
    LAB_RESULT = 'lab_result'
    LAB_STATUS = 'lab_status'
    SUPPORT_UPDATE = 'support_update'
    PAYOUT_STATUS = 'payout_status'
    DOCTOR_VERIFIED = 'doctor_verified'
    CONSENT_REQUEST = 'consent_request'
    SYSTEM = 'system'

    TYPE_CHOICES = [
        (ORDER_STATUS, 'Order Status Update'),
        (PRESCRIPTION_STATUS, 'Prescription Status Update'),
        (CONSULTATION_MESSAGE, 'New Consultation Message'),
        (NEW_CONSULTATION, 'New Consultation Request'),
        (CONSULTATION_STATUS, 'Consultation Status Update'),
        (LAB_RESULT, 'Lab Result Ready'),
        (LAB_STATUS, 'Lab Request Status Update'),
        (SUPPORT_UPDATE, 'Support Ticket Update'),
        (PAYOUT_STATUS, 'Payout Status Update'),
        (DOCTOR_VERIFIED, 'Doctor Profile Verified'),
        (CONSENT_REQUEST, 'Guardian Consent Request'),
        (SYSTEM, 'System Notification'),
    ]

    recipient = models.ForeignKey(
        'accounts.User', on_delete=models.CASCADE, related_name='notifications'
    )
    type = models.CharField(max_length=30, choices=TYPE_CHOICES)
    title = models.CharField(max_length=255)
    message = models.TextField()
    data = models.JSONField(default=dict)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.recipient.email} — {self.type}: {self.title}"


class NotificationPreference(models.Model):
    user = models.OneToOneField(
        'accounts.User', on_delete=models.CASCADE, related_name='notification_preferences'
    )
    email_enabled = models.BooleanField(default=True)
    sms_enabled = models.BooleanField(default=True)
    push_enabled = models.BooleanField(default=True)
    marketing_enabled = models.BooleanField(default=False)
    order_updates_email = models.BooleanField(default=True)
    order_updates_sms = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Preferences - {self.user.email}"


class NotificationDelivery(models.Model):
    CHANNEL_EMAIL = 'email'
    CHANNEL_SMS = 'sms'
    CHANNEL_PUSH = 'push'
    CHANNEL_CHOICES = [
        (CHANNEL_EMAIL, 'Email'),
        (CHANNEL_SMS, 'SMS'),
        (CHANNEL_PUSH, 'Push'),
    ]

    STATUS_PENDING = 'pending'
    STATUS_SENT = 'sent'
    STATUS_FAILED = 'failed'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_SENT, 'Sent'),
        (STATUS_FAILED, 'Failed'),
    ]

    notification = models.ForeignKey(
        Notification, on_delete=models.CASCADE, null=True, blank=True, related_name='deliveries'
    )
    recipient = models.ForeignKey(
        'accounts.User', on_delete=models.CASCADE, related_name='notification_deliveries'
    )
    channel = models.CharField(max_length=10, choices=CHANNEL_CHOICES)
    destination = models.CharField(max_length=255)
    subject = models.CharField(max_length=255, blank=True)
    message = models.TextField()
    provider = models.CharField(max_length=50, blank=True)
    provider_reference = models.CharField(max_length=120, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_PENDING)
    error_message = models.CharField(max_length=255, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.channel} to {self.destination} ({self.status})"
