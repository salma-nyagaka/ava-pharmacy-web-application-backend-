import logging

from django.conf import settings
from django.db import models
from django.db import transaction
from django.utils import timezone

from apps.notifications.emailing import (
    build_absolute_media_url,
    build_login_redirect_url,
    frontend_base_url,
    send_rendered_email,
)

from .models import Order, OrderItem


logger = logging.getLogger(__name__)


def _resolve_order_item_image(item):
    if item.variant and getattr(item.variant, 'image', None):
        return build_absolute_media_url(item.variant.image)
    if item.product and getattr(item.product, 'image', None):
        return build_absolute_media_url(item.product.image)
    return ''


def _build_order_email_context(order, *, heading, intro, preheader, primary_cta_label):
    frontend_base = frontend_base_url()
    account_order_path = f'/account/orders/{order.id}'
    placed_at = order.placed_at or order.created_at
    items = []
    for item in order.items.all():
        item_name = item.product_name
        if item.variant_name:
            item_name = f'{item_name} - {item.variant_name}'
        items.append({
            'name': item_name,
            'quantity': item.quantity,
            'unit_price': item.unit_price,
            'subtotal': item.subtotal,
            'image_url': _resolve_order_item_image(item),
        })

    return {
        'first_name': order.shipping_first_name or 'Customer',
        'customer_full_name': f'{order.shipping_first_name} {order.shipping_last_name}'.strip(),
        'order': order,
        'items': items,
        'item_count': sum(item['quantity'] for item in items),
        'placed_at_display': timezone.localtime(placed_at).strftime('%d %b %Y, %I:%M %p') if placed_at else '',
        'track_order_url': f'{frontend_base}/track-order?order={order.order_number}',
        'account_order_url': build_login_redirect_url(account_order_path),
        'shop_url': getattr(settings, 'FRONTEND_SHOP_URL', f'{frontend_base}/products'),
        'support_email': getattr(settings, 'ADMIN_EMAIL', settings.DEFAULT_FROM_EMAIL),
        'payment_method_label': order.get_payment_method_display(),
        'order_status_label': order.get_status_display(),
        'payment_status_label': order.get_payment_status_display(),
        'shipping_phone': order.shipping_phone,
        'shipping_email': order.shipping_email,
        'shipping_address': order.shipping_address,
        'delivery_method_label': str(order.delivery_method or 'standard').replace('_', ' ').title(),
        'delivery_notes': order.delivery_notes,
        'shipping_method_name': getattr(order.shipping_method, 'name', '') or '',
        'shipping_window': getattr(order.shipping_method, 'estimated_delivery_window', '') or '',
        'email_heading': heading,
        'email_intro': intro,
        'email_preheader': preheader,
        'primary_cta_label': primary_cta_label,
    }


def send_order_confirmation_email(*, order):
    if not order.shipping_email:
        return

    context = _build_order_email_context(
        order,
        heading='Order received successfully',
        intro=f'Hi {order.shipping_first_name or "Customer"}, thank you for shopping with Ava Pharmacy. Your order has been received and is now being prepared.',
        preheader='Order confirmation',
        primary_cta_label='View my order',
    )
    subject = f'We received your order {order.order_number}'
    send_rendered_email(
        subject=subject,
        recipient_list=[order.shipping_email],
        text_template='orders/emails/order_confirmation.txt',
        html_template='orders/emails/order_confirmation.html',
        context=context,
        fail_silently=False,
    )


def send_order_status_email(*, order, subject, heading, intro):
    if not order.shipping_email:
        return

    context = _build_order_email_context(
        order,
        heading=heading,
        intro=intro,
        preheader=subject,
        primary_cta_label='View Order',
    )
    send_rendered_email(
        subject=subject,
        recipient_list=[order.shipping_email],
        text_template='orders/emails/order_confirmation.txt',
        html_template='orders/emails/order_confirmation.html',
        context=context,
        fail_silently=False,
    )


def send_mpesa_receipt_email(*, order):
    """Send the customer a transaction receipt for a confirmed M-Pesa order."""
    if not order.shipping_email:
        return
    paid_at = order.placed_at or order.updated_at
    subject = f'M-Pesa receipt for {order.order_number}'
    item_summary = ', '.join(
        f'{item.product_name} x{item.quantity}' for item in order.items.all()
    ) or 'Ava Pharmacy order'
    send_rendered_email(
        subject=subject,
        recipient_list=[order.shipping_email],
        text_template='emails/notification.txt',
        html_template='emails/notification.html',
        context={
            'subject': subject,
            'heading': 'Payment receipt',
            'intro': f'Hi {order.shipping_first_name or "Customer"}, your M-Pesa payment was received successfully.',
            'detail_rows': [
                {'label': 'Receipt number', 'value': f'REC-{order.order_number}'},
                {'label': 'M-Pesa reference', 'value': order.payment_reference or order.order_number},
                {'label': 'Order', 'value': order.order_number},
                {'label': 'Amount paid', 'value': f'KES {order.total:,.2f}'},
                {'label': 'Paid at', 'value': timezone.localtime(paid_at).strftime('%d %b %Y, %I:%M %p')},
                {'label': 'Items', 'value': item_summary},
            ],
            'body_lines': ['Keep this email as your electronic proof of payment.'],
            'cta_url': build_login_redirect_url(f'/account/orders/{order.id}'),
            'cta_label': 'View order',
            'support_email': getattr(settings, 'ADMIN_EMAIL', settings.DEFAULT_FROM_EMAIL),
        },
        fail_silently=False,
    )


def queue_mpesa_receipt_email(order):
    order_id = order.id

    def _send():
        try:
            receipt_order = Order.objects.prefetch_related('items').get(pk=order_id)
            if receipt_order.receipt_emailed_at or receipt_order.payment_status != Order.PAYMENT_STATUS_PAID:
                return
            if receipt_order.payment_method not in {Order.PAYMENT_MPESA_STK, Order.PAYMENT_MPESA_PAYBILL}:
                return
            send_mpesa_receipt_email(order=receipt_order)
            Order.objects.filter(pk=order_id, receipt_emailed_at__isnull=True).update(receipt_emailed_at=timezone.now())
        except Exception:
            logger.exception('Failed to send M-Pesa receipt for order %s', order_id)

    transaction.on_commit(_send)


def queue_order_confirmation_email(order):
    order_id = order.id

    def _send():
        try:
            order_with_items = (
                Order.objects.select_related('customer', 'shipping_method')
                .prefetch_related(
                    models.Prefetch(
                        'items',
                        queryset=OrderItem.objects.select_related('variant'),
                    )
                )
                .get(pk=order_id)
            )
            send_order_confirmation_email(order=order_with_items)
        except Exception:
            logger.exception('Failed to send order confirmation email for order %s', order_id)

    transaction.on_commit(_send)


def queue_order_status_email(order, *, subject, heading, intro):
    order_id = order.id

    def _send():
        try:
            order_with_items = (
                Order.objects.select_related('customer', 'shipping_method')
                .prefetch_related(
                    models.Prefetch(
                        'items',
                        queryset=OrderItem.objects.select_related('variant'),
                    )
                )
                .get(pk=order_id)
            )
            send_order_status_email(
                order=order_with_items,
                subject=subject,
                heading=heading,
                intro=intro,
            )
        except Exception:
            logger.exception('Failed to send order status email for order %s', order_id)

    transaction.on_commit(_send)
