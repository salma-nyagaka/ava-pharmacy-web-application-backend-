"""Confirmation notifications for persisted account credential changes."""
from django.conf import settings
from apps.notifications.emailing import send_rendered_email


def send_account_change_confirmation(*, first_name, recipient, email_changed, password_changed, new_email):
    changes = []
    if email_changed:
        changes.append(f'Your account email address was changed to {new_email}.')
    if password_changed:
        changes.append('Your account password was changed successfully.')
    return send_rendered_email(
        subject='AVA Pharmacy account details changed',
        recipient_list=[recipient],
        text_template='accounts/emails/account_changed.txt',
        html_template='accounts/emails/account_changed.html',
        context={
            'first_name': first_name or 'there',
            'changes': changes,
            'support_email': getattr(settings, 'ADMIN_EMAIL', 'admin@avapharmacy.co.ke'),
        },
    )


def deliver_account_confirmation(*, delivery, **kwargs):
    import logging
    recipient = kwargs['recipient']
    try:
        sent = send_account_change_confirmation(**kwargs)
        delivery['sent_to' if sent else 'failed_to'].append(recipient)
    except Exception:
        logging.getLogger(__name__).exception('Account change email delivery failed')
        delivery['failed_to'].append(recipient)
