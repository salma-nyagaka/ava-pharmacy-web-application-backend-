import uuid
from decimal import Decimal
from django.db import models


class Payout(models.Model):
    ROLE_DOCTOR = 'doctor'
    ROLE_PEDIATRICIAN = 'pediatrician'
    ROLE_PHARMACIST = 'pharmacist'
    ROLE_LAB_PARTNER = 'lab_partner'
    ROLE_LAB_TECHNICIAN = 'lab_technician'
    ROLE_CHOICES = [
        (ROLE_DOCTOR, 'Doctor'),
        (ROLE_PEDIATRICIAN, 'Pediatrician'),
        (ROLE_PHARMACIST, 'Pharmacist'),
        (ROLE_LAB_PARTNER, 'Lab Partner'),
        (ROLE_LAB_TECHNICIAN, 'Lab Technician'),
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

    STATUS_DRAFT = 'draft'
    STATUS_PENDING = 'pending'
    STATUS_APPROVED = 'approved'
    STATUS_PROCESSING = 'processing'
    STATUS_PAID = 'paid'
    STATUS_FAILED = 'failed'
    STATUS_ON_HOLD = 'on_hold'
    STATUS_REVERSED = 'reversed'
    STATUS_CANCELLED = 'cancelled'
    STATUS_CHOICES = [
        (STATUS_DRAFT, 'Draft'),
        (STATUS_PENDING, 'Pending'),
        (STATUS_APPROVED, 'Approved'),
        (STATUS_PROCESSING, 'Processing'),
        (STATUS_PAID, 'Paid'),
        (STATUS_FAILED, 'Failed'),
        (STATUS_ON_HOLD, 'On Hold'),
        (STATUS_REVERSED, 'Reversed'),
        (STATUS_CANCELLED, 'Cancelled'),
    ]

    RECON_UNMATCHED = 'unmatched'
    RECON_MATCHED = 'matched'
    RECON_EXCEPTION = 'exception'
    RECON_CHOICES = [
        (RECON_UNMATCHED, 'Unmatched'),
        (RECON_MATCHED, 'Matched'),
        (RECON_EXCEPTION, 'Exception'),
    ]

    reference = models.CharField(max_length=20, unique=True, blank=True)
    recipient = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='payouts'
    )
    recipient_name = models.CharField(max_length=200)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    period = models.CharField(max_length=100)
    source_type = models.CharField(max_length=40, blank=True)
    source_reference = models.CharField(max_length=120, blank=True)
    idempotency_key = models.CharField(max_length=120, unique=True, null=True, blank=True)
    gross_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    commission_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    withholding_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    deduction_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=10, default='KES')
    method = models.CharField(max_length=20, choices=METHOD_CHOICES, default=METHOD_MPESA)
    payment_reference = models.CharField(max_length=100, blank=True)
    provider_transaction_id = models.CharField(max_length=120, blank=True)
    batch_reference = models.CharField(max_length=120, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    reconciliation_status = models.CharField(max_length=20, choices=RECON_CHOICES, default=RECON_UNMATCHED)
    notes = models.TextField(blank=True)
    hold_reason = models.TextField(blank=True)
    failure_code = models.CharField(max_length=80, blank=True)
    failure_message = models.TextField(blank=True)
    retry_count = models.PositiveIntegerField(default=0)
    requested_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='created_payouts'
    )
    reviewed_by = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='reviewed_payouts')
    approved_by = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_payouts')
    submitted_by = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='submitted_payouts')

    class Meta:
        ordering = ['-requested_at']
        indexes = [
            models.Index(fields=['recipient', 'status']),
            models.Index(fields=['role', 'status']),
            models.Index(fields=['status', '-requested_at']),
            models.Index(fields=['source_type', 'source_reference']),
            models.Index(fields=['reconciliation_status', '-requested_at']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['recipient', 'role', 'source_type', 'source_reference'],
                condition=~models.Q(source_reference=''),
                name='unique_payout_source_per_recipient',
            ),
            models.UniqueConstraint(
                fields=['provider_transaction_id'],
                condition=~models.Q(provider_transaction_id=''),
                name='unique_payout_provider_transaction',
            ),
            models.UniqueConstraint(
                fields=['payment_reference'],
                condition=~models.Q(payment_reference=''),
                name='unique_payout_payment_reference',
            ),
        ]

    def __str__(self):
        return self.reference

    def save(self, *args, **kwargs):
        if not self.reference:
            self.reference = f"PAY-{uuid.uuid4().hex[:6].upper()}"
        if not self.gross_amount:
            self.gross_amount = self.amount
        calculated_net = (
            Decimal(self.gross_amount or 0)
            - Decimal(self.commission_amount or 0)
            - Decimal(self.withholding_amount or 0)
            - Decimal(self.deduction_amount or 0)
        )
        self.amount = max(calculated_net, Decimal('0.00'))
        super().save(*args, **kwargs)


class PayoutAuditLog(models.Model):
    payout = models.ForeignKey(Payout, on_delete=models.PROTECT, related_name='audit_logs')
    actor = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='payout_audit_logs')
    action = models.CharField(max_length=60)
    from_status = models.CharField(max_length=20, blank=True)
    to_status = models.CharField(max_length=20, blank=True)
    reason = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['payout', '-created_at']), models.Index(fields=['action', '-created_at'])]


class PayoutRule(models.Model):
    ROLE_DOCTOR = 'doctor'
    ROLE_PEDIATRICIAN = 'pediatrician'
    ROLE_PHARMACIST = 'pharmacist'
    ROLE_LAB_PARTNER = 'lab_partner'
    ROLE_LAB_TECHNICIAN = 'lab_technician'
    ROLE_CHOICES = [
        (ROLE_DOCTOR, 'Doctor'),
        (ROLE_PEDIATRICIAN, 'Pediatrician'),
        (ROLE_PHARMACIST, 'Pharmacist'),
        (ROLE_LAB_PARTNER, 'Lab Partner'),
        (ROLE_LAB_TECHNICIAN, 'Lab Technician'),
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
