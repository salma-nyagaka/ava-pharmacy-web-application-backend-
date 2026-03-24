from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from apps.accounts.models import User
from apps.notifications.utils import create_notification

from .models import Prescription


@receiver(pre_save, sender=Prescription)
def prescription_capture_previous_status(sender, instance, **kwargs):
    if not instance.pk:
        instance._previous_status = None
        return
    previous = sender.objects.filter(pk=instance.pk).values('status').first()
    instance._previous_status = previous['status'] if previous else None


@receiver(post_save, sender=Prescription)
def prescription_notify_state_changes(sender, instance, created, **kwargs):
    if created:
        pharmacists = User.objects.filter(role=User.PHARMACIST, status=User.STATUS_ACTIVE, is_active=True)
        for pharmacist in pharmacists:
            create_notification(
                recipient=pharmacist,
                notification_type='prescription_status',
                title='New prescription upload',
                message=f'Prescription {instance.reference} is awaiting review.',
                data={'reference': instance.reference, 'prescription_id': instance.id},
            )
        return

    previous_status = getattr(instance, '_previous_status', None)
    if previous_status == instance.status or not instance.patient:
        return

    if instance.status == Prescription.STATUS_APPROVED:
        message = f'Prescription {instance.reference} has been approved.'
    elif instance.status == Prescription.STATUS_REJECTED:
        detail = f' Reason: {instance.clarification_message or instance.pharmacist_notes}'.strip()
        message = f'Prescription {instance.reference} was rejected.{detail}'
    elif instance.status == Prescription.STATUS_CLARIFICATION:
        detail = f' {instance.clarification_message or instance.pharmacist_notes}'.strip()
        message = f'Prescription {instance.reference} needs clarification.{detail}'
    else:
        message = f'Prescription {instance.reference} status changed to {instance.get_status_display()}.'

    create_notification(
        recipient=instance.patient,
        notification_type='prescription_status',
        title=f'Prescription {instance.reference} updated',
        message=message,
        data={'reference': instance.reference, 'prescription_id': instance.id, 'status': instance.status},
        send_email=True,
    )
