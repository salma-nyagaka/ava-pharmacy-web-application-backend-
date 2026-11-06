"""Accountable workflows; submitted evidence is never automatically verified."""
from django.db import models
from django.conf import settings
from django.utils import timezone


class MedicineAssessment(models.Model):
    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    variant = models.ForeignKey('products.Variant', on_delete=models.PROTECT)
    cart_item = models.ForeignKey('orders.CartItem', on_delete=models.DO_NOTHING, db_constraint=False, null=True, blank=True, help_text='Historical cart identity retained after cart cleanup; not a live cart dependency.')
    quantity = models.PositiveIntegerField()
    screening_digest = models.CharField(max_length=64)
    decision = models.CharField(max_length=20, choices=[('approved', 'Approved'), ('refused', 'Refused'), ('referred', 'Referred')])
    suitability = models.TextField()
    counselling = models.TextField()
    intervention = models.TextField(blank=True)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='medicine_assessments')
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()


class MedicineRecall(models.Model):
    """Retired recall history; no live API, notifications or supply-hold behavior."""
    variant = models.ForeignKey('products.Variant', on_delete=models.PROTECT)
    batch_number = models.CharField(max_length=80, blank=True)
    reference = models.CharField(max_length=160, unique=True)
    reason = models.TextField()
    status = models.CharField(max_length=12, choices=[('open', 'Open'), ('closed', 'Closed')], default='open')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    closure_evidence = models.TextField(blank=True)


class RecallAffectedOrder(models.Model):
    """Retired recall/order audit records retained without an operational workflow."""
    recall = models.ForeignKey(MedicineRecall, on_delete=models.PROTECT, related_name='affected_orders')
    order_item = models.ForeignKey('orders.OrderItem', on_delete=models.PROTECT)
    notification_queued_at = models.DateTimeField(null=True, blank=True)
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    disposition = models.CharField(max_length=30, choices=[('pending', 'Pending'), ('not_supplied', 'Not supplied'), ('quarantined', 'Quarantined'), ('disposed', 'Disposed'), ('not_recoverable', 'Not recoverable')], default='pending')
    resolution_evidence = models.TextField(blank=True)
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['recall', 'order_item'], name='unique_recall_order_item')]


class PrivacyRequest(models.Model):
    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    request_type = models.CharField(max_length=20, choices=[(x, x.title()) for x in ['access', 'correction', 'erasure', 'restriction', 'objection', 'portability']])
    details = models.TextField()
    status = models.CharField(max_length=20, choices=[('open', 'Open'), ('in_review', 'In review'), ('resolved', 'Resolved'), ('refused', 'Refused')], default='open')
    response = models.TextField(blank=True)
    lawful_basis = models.TextField(blank=True)
    identity_verified_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, related_name='verified_privacy_requests')
    handled_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, related_name='handled_privacy_requests')
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)


QA_AUDIT_AREAS = [
    ('qa_personnel', '12.1(a) Personnel, staffing, skills and training'),
    ('qa_communication', '12.1(b) Staff, prescriber and patient communication'),
    ('qa_professional_services', '12.1(c) Quality of professional services'),
    ('qa_receiving_prescriptions', '12.1(d) Receiving prescriptions'),
    ('qa_dispensing', '12.1(e) Dispensing procedures'),
    ('qa_delivery', '12.1(f) Secure posting and delivery'),
    ('qa_documentation', '12.1(g) Documentation and records'),
    ('qa_it_validation', '12.1(h) IT equipment and software validation'),
    ('qa_security', '12.1(i) Security and confidentiality'),
    ('qa_website_information', '12.1(j) Website information'),
    ('qa_feedback', '12.1(k) Customer feedback'),
    ('qa_complaints', '12.1(l) Customer complaints'),
]


class OperationalReview(models.Model):
    area = models.CharField(max_length=60, choices=[(x, x.replace('_', ' ').title()) for x in ['licensing', 'premises', 'staff', 'prescribing', 'dispensing', 'counselling', 'delivery', 'returns_recalls', 'records_privacy', 'equipment', 'capacity_continuity', 'backup_restore']] + QA_AUDIT_AREAS)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    procedure_reference = models.CharField(max_length=500)
    due_on = models.DateField()
    completed_at = models.DateTimeField(null=True, blank=True)
    evidence = models.ForeignKey('support.ComplianceEvidence', on_delete=models.PROTECT, null=True, blank=True)
    findings = models.TextField(blank=True)
    corrective_actions = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class SupplyAllocation(models.Model):
    order_item = models.ForeignKey('orders.OrderItem', on_delete=models.PROTECT, related_name='preserved_allocations')
    event = models.CharField(max_length=12, choices=[('commit', 'Commit'), ('release', 'Release')])
    allocation_snapshot = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)


class ComplianceEvent(models.Model):
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    model_label = models.CharField(max_length=100)
    record_id = models.PositiveBigIntegerField()
    action = models.CharField(max_length=30)
    snapshot = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)
