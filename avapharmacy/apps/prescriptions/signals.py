import logging

from django.conf import settings
from django.db import transaction
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from apps.accounts.models import User
from apps.notifications.utils import create_notification
from apps.notifications.emailing import build_frontend_url, send_rendered_email

from .models import Prescription


logger = logging.getLogger(__name__)


def _queue_admin_upload_email(prescription):
    prescription_id = prescription.id

    def _send():
        try:
            uploaded = Prescription.objects.select_related('patient').get(pk=prescription_id)
            subject = f'New prescription upload {uploaded.reference}'
            send_rendered_email(
                subject=subject,
                recipient_list=[getattr(settings, 'PRESCRIPTION_UPLOAD_ALERT_EMAIL', 'info@avapharmacy.co.ke')],
                text_template='emails/notification.txt',
                html_template='emails/notification.html',
                context={
                    'subject': subject,
                    'heading': 'Prescription awaiting review',
                    'intro': 'A customer has uploaded a prescription and it is ready for administrative review.',
                    'detail_rows': [
                        {'label': 'Reference', 'value': uploaded.reference},
                        {'label': 'Patient', 'value': uploaded.patient_name or getattr(uploaded.patient, 'full_name', '')},
                        {'label': 'Status', 'value': uploaded.get_status_display()},
                    ],
                    'cta_url': build_frontend_url(f'/admin/prescriptions?prescription={uploaded.id}'),
                    'cta_label': 'Review prescription',
                    'support_email': getattr(settings, 'ADMIN_EMAIL', settings.DEFAULT_FROM_EMAIL),
                },
                fail_silently=False,
            )
        except Exception:
            logger.exception('Failed to send admin prescription upload alert for %s', prescription_id)

    transaction.on_commit(_send)


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
        if instance.source == Prescription.SOURCE_UPLOAD:
            _queue_admin_upload_email(instance)
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
        data={
            'url': f'/account/prescriptions?prescription={instance.id}',
            'reference': instance.reference,
            'prescription_id': instance.id,
            'status': instance.get_status_display(),
        },
        send_email=True,
    )
