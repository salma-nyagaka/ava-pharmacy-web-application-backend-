"""Application guards, including admin/cascade deletion paths.
Database retention triggers provide independent protection for PostgreSQL bulk SQL.
"""
from datetime import timedelta
from django.core.exceptions import ValidationError
from django.db.models.deletion import ProtectedError
from django.db.models.signals import pre_delete, pre_save
from django.dispatch import receiver
from django.utils import timezone

PERMANENT = {'prescriptions.prescription', 'prescriptions.prescriptionfile', 'prescriptions.prescriptionauditlog', 'prescriptions.prescriptionreviewdecision', 'prescriptions.prescriptionversion'}
RETENTION = {
 'support.medicineassessment': 'created_at', 'support.complianceevent': 'created_at', 'support.supplyallocation': 'created_at',
 'consultations.consultation': 'created_at', 'consultations.consultationmessage': 'sent_at',
 'consultations.clinicianprescription': 'created_at', 'consultations.consultationauditlog': 'created_at',
 'lab.labrequest': 'requested_at', 'lab.labresult': 'uploaded_at', 'lab.labauditlog': 'timestamp',
 'orders.order': 'created_at', 'orders.orderevent': 'created_at', 'orders.deliveryaudit': 'recorded_at',
}
IMMUTABLE = {'prescriptions.prescriptionauditlog', 'prescriptions.prescriptionreviewdecision', 'support.medicineassessment', 'consultations.consultationauditlog', 'lab.labauditlog', 'orders.deliveryaudit', 'orders.orderevent', 'prescriptions.prescriptionversion', 'prescriptions.prescriptionfile', 'support.complianceevent', 'support.supplyallocation'}


@receiver(pre_delete)
def preserve_clinical_record(sender, instance, **kwargs):
    label = sender._meta.label_lower
    field = RETENTION.get(label)
    if label in PERMANENT or getattr(instance, 'legal_hold', False) or (field and getattr(instance, field) >= timezone.now()-timedelta(days=5*366)):
        raise ProtectedError('Clinical record retention prevents deletion. Use the approved privacy/retention workflow.', [instance])
    if label == 'prescriptions.prescriptionitem' and instance.prescription.status == 'approved':
        raise ProtectedError('Approved prescription items are permanent records.', [instance])


@receiver(pre_save)
def clinical_write_guards(sender, instance, raw=False, **kwargs):
    if raw:
        return
    label = sender._meta.label_lower
    if instance.pk and label in IMMUTABLE and sender.objects.filter(pk=instance.pk).exists():
        raise ValidationError('Audit and professional decision records are append-only.')
    if label == 'prescriptions.prescription' and instance.status == 'approved':
        from apps.prescriptions.compliance import approval_error
        error = approval_error(instance)
        if error:
            raise ValidationError(error)
    if label == 'consultations.clinicianprescription':
        if not instance.clinician.eligible_to_practice:
            raise ValidationError('Current verified Kenyan clinician credentials are required to issue a prescription.')
    if label == 'orders.order' and instance.pk:
        previous = sender.objects.filter(pk=instance.pk).values_list('status', flat=True).first()
        if previous != instance.status and instance.status in {'shipped', 'delivered'}:
            from apps.products.compliance import supply_error
            for item in instance.items.select_related('variant'):
                from .compliance import assessment_error
                from apps.prescriptions.compliance import approval_error
                error = supply_error(item.variant) or assessment_error(item)
                if not error and item.prescription_id:
                    error = approval_error(item.prescription)
                if error:
                    raise ValidationError(error)
            if instance.status == 'delivered':
                from .compliance import delivery_error
                error = delivery_error(instance)
                if error:
                    raise ValidationError(error)


from django.db.models.signals import post_save

@receiver(post_save)
def preserve_approved_prescription(sender, instance, raw=False, **kwargs):
    if raw or sender._meta.label_lower != 'prescriptions.prescription' or instance.status != 'approved':
        return
    from apps.prescriptions.models import PrescriptionVersion
    from apps.prescriptions.compliance import EVIDENCE_FIELDS
    snapshot = {f: str(getattr(instance, f) or '') for f in EVIDENCE_FIELDS}
    snapshot['source'] = instance.source
    snapshot['reference'] = instance.reference
    snapshot['patient_name'] = instance.patient_name
    snapshot['patient_id'] = instance.patient_id
    snapshot['notes'] = instance.notes
    snapshot['files'] = list(instance.files.values('filename', 'file'))
    snapshot['items'] = list(instance.items.values('name', 'variant_id', 'product_id', 'dose', 'frequency', 'duration', 'quantity'))
    previous = instance.preserved_versions.order_by('-created_at', '-pk').first()
    if not previous or previous.snapshot != snapshot:
        PrescriptionVersion.objects.create(prescription=instance, snapshot=snapshot, reviewed_by=instance.verified_by)
