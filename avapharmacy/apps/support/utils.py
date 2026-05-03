from django.conf import settings

from apps.notifications.emailing import send_rendered_email


def send_newsletter_subscription_email(email):
    frontend_base = getattr(settings, 'FRONTEND_BASE_URL', 'http://localhost:3000').rstrip('/')
    context = {
        'email': email,
        'shop_url': getattr(settings, 'FRONTEND_SHOP_URL', f'{frontend_base}/products'),
        'support_email': getattr(settings, 'ADMIN_EMAIL', settings.DEFAULT_FROM_EMAIL),
    }
    subject = 'Welcome to the Ava Pharmacy newsletter'
    send_rendered_email(
        subject=subject,
        recipient_list=[email],
        text_template='support/emails/newsletter_subscription.txt',
        html_template='support/emails/newsletter_subscription.html',
        context=context,
        fail_silently=False,
    )
