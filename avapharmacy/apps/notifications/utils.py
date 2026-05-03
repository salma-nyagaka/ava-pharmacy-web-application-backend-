import json
import logging
from urllib import error, request

from asgiref.sync import async_to_sync
from django.conf import settings
from django.utils import timezone

from .emailing import build_login_redirect_url, send_rendered_email
from apps.orders.utils import queue_order_status_email

logger = logging.getLogger(__name__)


def get_notification_preferences(user):
    from .models import NotificationPreference

    if not user:
        return None
    preferences, _ = NotificationPreference.objects.get_or_create(user=user)
    return preferences


def create_notification(recipient, notification_type, title, message, data=None, send_email=False, send_sms=False):
    from .models import Notification
    from .serializers import NotificationSerializer

    if not recipient:
        return None

    try:
        notification = Notification.objects.create(
            recipient=recipient,
            type=notification_type,
            title=title,
            message=message,
            data=data or {},
        )
        _push_to_websocket(recipient.id, NotificationSerializer(notification).data)

        preferences = get_notification_preferences(recipient)
        if send_email and preferences and preferences.email_enabled:
            deliver_email(notification, recipient.email, title, message)
        if send_sms and preferences and preferences.sms_enabled and recipient.phone:
            deliver_sms(notification, recipient.phone, message)
        return notification
    except Exception as exc:
        logger.error("Failed to create notification for user %s: %s", getattr(recipient, 'id', '?'), exc)
        return None


def record_delivery(notification, recipient, channel, destination, subject='', message='', provider='', metadata=None):
    from .models import NotificationDelivery

    return NotificationDelivery.objects.create(
        notification=notification,
        recipient=recipient,
        channel=channel,
        destination=destination,
        subject=subject,
        message=message,
        provider=provider,
        metadata=metadata or {},
    )


def mark_delivery_sent(delivery, provider_reference=''):
    delivery.status = delivery.STATUS_SENT
    delivery.provider_reference = provider_reference
    delivery.sent_at = timezone.now()
    delivery.error_message = ''
    delivery.save(update_fields=['status', 'provider_reference', 'sent_at', 'error_message'])


def mark_delivery_failed(delivery, error_message):
    delivery.status = delivery.STATUS_FAILED
    delivery.error_message = str(error_message)[:255]
    delivery.save(update_fields=['status', 'error_message'])


def deliver_email(notification, destination, subject, message):
    if not destination:
        return None

    delivery = record_delivery(
        notification=notification,
        recipient=notification.recipient,
        channel='email',
        destination=destination,
        subject=subject,
        message=message,
        provider='django_email',
    )
    try:
        data = notification.data or {}
        raw_url = data.get('url') or ''
        cta_url = build_login_redirect_url(raw_url) if raw_url else ''
        detail_rows = []
        if data.get('reference'):
            detail_rows.append({'label': 'Reference', 'value': data['reference']})
        if data.get('status'):
            detail_rows.append({'label': 'Status', 'value': data['status']})

        send_rendered_email(
            subject=subject,
            recipient_list=[destination],
            text_template='emails/notification.txt',
            html_template='emails/notification.html',
            context={
                'subject': subject,
                'heading': subject,
                'intro': message,
                'body_lines': [message],
                'detail_rows': detail_rows,
                'cta_url': cta_url,
                'cta_label': 'Open in your account' if cta_url else '',
                'support_email': getattr(settings, 'ADMIN_EMAIL', settings.DEFAULT_FROM_EMAIL),
            },
            fail_silently=False,
        )
        mark_delivery_sent(delivery)
    except Exception as exc:
        logger.error("Email delivery failed: %s", exc)
        mark_delivery_failed(delivery, exc)
    return delivery


def deliver_sms(notification, destination, message):
    if not destination:
        return None

    backend = getattr(settings, 'SMS_BACKEND', 'console')
    delivery = record_delivery(
        notification=notification,
        recipient=notification.recipient,
        channel='sms',
        destination=destination,
        subject='',
        message=message,
        provider=backend,
    )
    try:
        if backend == 'console':
            logger.info("SMS to %s: %s", destination, message)
            mark_delivery_sent(delivery, provider_reference='console')
            return delivery

        if backend == 'webhook':
            payload = json.dumps({
                'to': destination,
                'from': settings.SMS_FROM,
                'message': message,
            }).encode('utf-8')
            req = request.Request(
                settings.SMS_WEBHOOK_URL,
                data=payload,
                headers={
                    'Content-Type': 'application/json',
                    'Authorization': f'Bearer {settings.SMS_WEBHOOK_TOKEN}',
                },
                method='POST',
            )
            with request.urlopen(req, timeout=10) as response:
                provider_payload = json.loads(response.read().decode('utf-8') or '{}')
            provider_reference = provider_payload.get('reference', '')
            mark_delivery_sent(delivery, provider_reference=provider_reference)
            return delivery

        raise ValueError(f'Unsupported SMS backend: {backend}')
    except Exception as exc:
        logger.error("SMS delivery failed: %s", exc)
        mark_delivery_failed(delivery, exc)
        return delivery


def _push_to_websocket(user_id, notification_data):
    try:
        from channels.layers import get_channel_layer
        from apps.notifications.models import Notification

        channel_layer = get_channel_layer()
        if not channel_layer:
            return

        unread_count = Notification.objects.filter(
            recipient_id=user_id, is_read=False
        ).count()

        async_to_sync(channel_layer.group_send)(
            f"notifications_{user_id}",
            {
                'type': 'notification',
                'data': {
                    'type': 'new_notification',
                    'notification': notification_data,
                    'unread_count': unread_count,
                },
            },
        )
    except Exception as exc:
        logger.warning("WebSocket push failed for user %s: %s", user_id, exc)


def notify_order_status(order):
    if not order.customer:
        return
    preferences = get_notification_preferences(order.customer)
    create_notification(
        recipient=order.customer,
        notification_type='order_status',
        title=f"Order {order.order_number} Updated",
        message=f"Your order status is now: {order.get_status_display()}",
        data={'url': f'/account/orders/{order.id}', 'reference': order.order_number, 'status': order.get_status_display()},
        send_email=False,
        send_sms=bool(preferences and preferences.order_updates_sms),
    )
    if preferences and preferences.order_updates_email:
        queue_order_status_email(
            order,
            subject=f'Order {order.order_number} Updated',
            heading=f'Order {order.order_number} updated',
            intro=f'Your order status is now {order.get_status_display()}.',
        )


def notify_prescription_status(prescription):
    if not prescription.patient:
        return
    create_notification(
        recipient=prescription.patient,
        notification_type='prescription_status',
        title=f"Prescription {prescription.reference} Updated",
        message=f"Your prescription status is now: {prescription.get_status_display()}",
        data={
            'url': f'/account/prescriptions?prescription={prescription.id}',
            'reference': prescription.reference,
            'status': prescription.get_status_display(),
        },
        send_email=True,
    )


def notify_lab_result_ready(lab_request):
    if not lab_request.patient:
        return
    create_notification(
        recipient=lab_request.patient,
        notification_type='lab_result',
        title="Lab Result Ready",
        message=f"Your result for {lab_request.reference} is ready.",
        data={'url': f'/lab/requests/{lab_request.id}', 'reference': lab_request.reference},
        send_email=True,
    )


def notify_new_consultation(doctor_user, consultation):
    if not doctor_user:
        return
    create_notification(
        recipient=doctor_user,
        notification_type='new_consultation',
        title="New Consultation Request",
        message=f"New consultation from {consultation.patient_name}: {consultation.issue[:100]}",
        data={'url': f'/doctor/consultations/{consultation.id}', 'reference': consultation.reference},
        send_email=True,
    )


def notify_consultation_message(recipient, consultation, sender_name):
    create_notification(
        recipient=recipient,
        notification_type='consultation_message',
        title=f"New message from {sender_name}",
        message=f"New message in consultation {consultation.reference}",
        data={'url': f'/consultations/{consultation.id}', 'reference': consultation.reference},
    )


def notify_support_update(ticket):
    if not ticket.customer:
        return
    create_notification(
        recipient=ticket.customer,
        notification_type='support_update',
        title=f"Support Ticket {ticket.reference} Updated",
        message=f"Your ticket status is now: {ticket.get_status_display()}",
        data={'url': f'/support/tickets/{ticket.id}', 'reference': ticket.reference, 'status': ticket.status},
        send_email=True,
    )


def notify_payout_status(payout):
    if not payout.recipient:
        return
    create_notification(
        recipient=payout.recipient,
        notification_type='payout_status',
        title=f"Payout {payout.reference} {payout.get_status_display()}",
        message=f"Your payout of KSh {payout.amount} is {payout.get_status_display().lower()}.",
        data={'reference': payout.reference, 'amount': str(payout.amount), 'status': payout.status},
        send_email=True,
    )


def notify_doctor_verified(doctor_profile):
    if not doctor_profile.user:
        return
    create_notification(
        recipient=doctor_profile.user,
        notification_type='doctor_verified',
        title="Profile Verified",
        message="Your doctor profile has been verified. You can now accept consultations.",
        data={'url': '/doctor/dashboard'},
        send_email=True,
    )
