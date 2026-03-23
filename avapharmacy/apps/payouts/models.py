import uuid
from django.db import models


class Payout(models.Model):
    ROLE_DOCTOR = 'doctor'
    ROLE_PEDIATRICIAN = 'pediatrician'
    ROLE_PHARMACIST = 'pharmacist'
    ROLE_LAB_PARTNER = 'lab_partner'
    ROLE_CHOICES = [
        (ROLE_DOCTOR, 'Doctor'),
        (ROLE_PEDIATRICIAN, 'Pediatrician'),
        (ROLE_PHARMACIST, 'Pharmacist'),
        (ROLE_LAB_PARTNER, 'Lab Partner'),
    ]

    METHOD_BANK = 'bank_transfer'
    METHOD_MPESA = 'mpesa'
    METHOD_CHEQUE = 'cheque'
    METHOD_CASH = 'cash'
    METHOD_CHOICES = [
        (METHOD_BANK, 'Bank Transfer'),
        (METHOD_MPESA, 'M-Pesa'),
        (METHOD_CHEQUE, 'Cheque'),
        (METHOD_CASH, 'Cash'),
    ]

    STATUS_PENDING = 'pending'
    STATUS_PAID = 'paid'
    STATUS_FAILED = 'failed'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_PAID, 'Paid'),
        (STATUS_FAILED, 'Failed'),
    ]

    reference = models.CharField(max_length=20, unique=True, blank=True)
    recipient = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='payouts'
    )
    recipient_name = models.CharField(max_length=200)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    period = models.CharField(max_length=100)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    method = models.CharField(max_length=20, choices=METHOD_CHOICES, default=METHOD_MPESA)
    payment_reference = models.CharField(max_length=100, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    notes = models.TextField(blank=True)
    requested_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='created_payouts'
    )

    class Meta:
        ordering = ['-requested_at']
        indexes = [
            models.Index(fields=['recipient', 'status']),
            models.Index(fields=['role', 'status']),
            models.Index(fields=['status', '-requested_at']),
        ]

    def __str__(self):
        return self.reference

    def save(self, *args, **kwargs):
        if not self.reference:
            self.reference = f"PAY-{uuid.uuid4().hex[:6].upper()}"
        super().save(*args, **kwargs)


class PayoutRule(models.Model):
    ROLE_DOCTOR = 'doctor'
    ROLE_PEDIATRICIAN = 'pediatrician'
    ROLE_PHARMACIST = 'pharmacist'
    ROLE_LAB_PARTNER = 'lab_partner'
    ROLE_CHOICES = [
        (ROLE_DOCTOR, 'Doctor'),
        (ROLE_PEDIATRICIAN, 'Pediatrician'),
        (ROLE_PHARMACIST, 'Pharmacist'),
        (ROLE_LAB_PARTNER, 'Lab Partner'),
    ]

    role = models.CharField(max_length=20, choices=ROLE_CHOICES, unique=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    currency = models.CharField(max_length=10, default='KSh')
    is_active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['role']

    def __str__(self):
        return f"{self.role} - {self.currency} {self.amount}"
