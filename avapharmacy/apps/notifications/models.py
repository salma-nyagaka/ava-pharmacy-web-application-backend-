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
