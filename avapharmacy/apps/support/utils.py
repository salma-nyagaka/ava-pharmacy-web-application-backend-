from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string


def send_newsletter_subscription_email(email):
    frontend_base = getattr(settings, 'FRONTEND_BASE_URL', 'http://localhost:3000').rstrip('/')
    context = {
        'email': email,
        'shop_url': getattr(settings, 'FRONTEND_SHOP_URL', f'{frontend_base}/products'),
        'support_email': getattr(settings, 'ADMIN_EMAIL', settings.DEFAULT_FROM_EMAIL),
    }
    subject = 'Welcome to the Ava Pharmacy newsletter'
    message = render_to_string('support/emails/newsletter_subscription.txt', context)
    html_message = render_to_string('support/emails/newsletter_subscription.html', context)
    send_mail(
        subject=subject,
        message=message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[email],
        html_message=html_message,
        fail_silently=False,
    )
