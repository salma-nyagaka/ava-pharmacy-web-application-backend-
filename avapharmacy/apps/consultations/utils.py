import logging

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.notifications.emailing import build_login_redirect_url, send_rendered_email

from .models import ConsultationPaymentIntent


logger = logging.getLogger(__name__)


def queue_consultation_mpesa_receipt(intent):
    intent_id = intent.id

    def _send():
        try:
            payment = ConsultationPaymentIntent.objects.select_related('consultation', 'initiated_by').get(pk=intent_id)
            if payment.receipt_emailed_at or payment.status != ConsultationPaymentIntent.STATUS_SUCCEEDED:
                return
            recipient = (payment.consultation.patient_email if payment.consultation else '') or getattr(payment.initiated_by, 'email', '')
            if not recipient:
                return
            paid_at = payment.processed_at or payment.updated_at
            consultation = payment.consultation
            subject = f'M-Pesa consultation receipt {payment.reference}'
            send_rendered_email(
                subject=subject,
                recipient_list=[recipient],
                text_template='emails/notification.txt',
                html_template='emails/notification.html',
                context={
                    'subject': subject,
                    'heading': 'Consultation payment receipt',
                    'intro': 'Your M-Pesa consultation payment was received successfully.',
                    'detail_rows': [
                        {'label': 'Receipt number', 'value': f'REC-{payment.reference}'},
                        {'label': 'M-Pesa reference', 'value': payment.provider_reference or payment.reference},
                        {'label': 'Consultation', 'value': consultation.reference if consultation else payment.reference},
                        {'label': 'Amount paid', 'value': f'{payment.currency} {payment.amount:,.2f}'},
                        {'label': 'Paid at', 'value': timezone.localtime(paid_at).strftime('%d %b %Y, %I:%M %p')},
                    ],
                    'body_lines': ['Keep this email as your electronic proof of payment.'],
                    'cta_url': build_login_redirect_url('/account/consultations'),
                    'cta_label': 'View consultations',
                    'support_email': getattr(settings, 'ADMIN_EMAIL', settings.DEFAULT_FROM_EMAIL),
                },
                fail_silently=False,
            )
            ConsultationPaymentIntent.objects.filter(pk=intent_id, receipt_emailed_at__isnull=True).update(receipt_emailed_at=timezone.now())
        except Exception:
            logger.exception('Failed to send M-Pesa receipt for consultation payment %s', intent_id)

    transaction.on_commit(_send)
