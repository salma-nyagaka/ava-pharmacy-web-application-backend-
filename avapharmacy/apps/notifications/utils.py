import logging
from asgiref.sync import async_to_sync

logger = logging.getLogger(__name__)


def create_notification(recipient, notification_type, title, message, data=None):
    """
    Create a Notification record and push it via WebSocket.
    Gracefully degrades if channel layer is unavailable.
    Returns the Notification instance or None if recipient is None.
    """
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
        return notification
    except Exception as e:
        logger.error(f"Failed to create notification for user {getattr(recipient, 'id', '?')}: {e}")
        return None


def _push_to_websocket(user_id, notification_data):
    """Push notification payload to the user's WebSocket group."""
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
    except Exception as e:
        logger.warning(f"WebSocket push failed for user {user_id}: {e}")


def notify_order_status(order):
    """Notify customer of an order status change."""
    if not order.customer:
        return
    create_notification(
        recipient=order.customer,
        notification_type='order_status',
        title=f"Order {order.order_number} Updated",
        message=f"Your order status is now: {order.get_status_display()}",
        data={'url': f'/orders/{order.id}', 'reference': order.order_number, 'status': order.status},
    )


def notify_prescription_status(prescription):
    """Notify patient of a prescription status change."""
    if not prescription.patient:
        return
    create_notification(
        recipient=prescription.patient,
        notification_type='prescription_status',
        title=f"Prescription {prescription.reference} Updated",
        message=f"Your prescription status is now: {prescription.get_status_display()}",
        data={'url': f'/prescriptions/{prescription.id}', 'reference': prescription.reference, 'status': prescription.status},
    )


def notify_lab_result_ready(lab_request):
    """Notify patient their lab result is ready."""
    if not lab_request.patient:
        return
    create_notification(
        recipient=lab_request.patient,
        notification_type='lab_result',
        title="Lab Result Ready",
        message=f"Your result for {lab_request.reference} is ready.",
        data={'url': f'/lab/requests/{lab_request.id}', 'reference': lab_request.reference},
    )


def notify_new_consultation(doctor_user, consultation):
    """Notify doctor of a new consultation request."""
    if not doctor_user:
        return
    create_notification(
        recipient=doctor_user,
        notification_type='new_consultation',
        title="New Consultation Request",
        message=f"New consultation from {consultation.patient_name}: {consultation.issue[:100]}",
        data={'url': f'/doctor/consultations/{consultation.id}', 'reference': consultation.reference},
    )


def notify_consultation_message(recipient, consultation, sender_name):
    """Notify participant of a new message."""
    create_notification(
        recipient=recipient,
        notification_type='consultation_message',
        title=f"New message from {sender_name}",
        message=f"New message in consultation {consultation.reference}",
        data={'url': f'/consultations/{consultation.id}', 'reference': consultation.reference},
    )


def notify_support_update(ticket):
    """Notify customer of support ticket update."""
    if not ticket.customer:
        return
    create_notification(
        recipient=ticket.customer,
        notification_type='support_update',
        title=f"Support Ticket {ticket.reference} Updated",
        message=f"Your ticket status is now: {ticket.get_status_display()}",
        data={'url': f'/support/tickets/{ticket.id}', 'reference': ticket.reference, 'status': ticket.status},
    )


def notify_payout_status(payout):
    """Notify recipient of payout status change."""
    if not payout.recipient:
        return
    create_notification(
        recipient=payout.recipient,
        notification_type='payout_status',
        title=f"Payout {payout.reference} {payout.get_status_display()}",
        message=f"Your payout of KSh {payout.amount} is {payout.get_status_display().lower()}.",
        data={'reference': payout.reference, 'amount': str(payout.amount), 'status': payout.status},
    )


def notify_doctor_verified(doctor_profile):
    """Notify doctor their profile was verified."""
    if not doctor_profile.user:
        return
    create_notification(
        recipient=doctor_profile.user,
        notification_type='doctor_verified',
        title="Profile Verified",
        message="Your doctor profile has been verified. You can now accept consultations.",
        data={'url': '/doctor/dashboard'},
    )
