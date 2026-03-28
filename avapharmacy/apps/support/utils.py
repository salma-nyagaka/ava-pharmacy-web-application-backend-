from django.conf import settings
from django.core.mail import send_mail


def send_newsletter_subscription_email(email):
    subject = 'Welcome to the Ava Pharmacy newsletter'
    message = (
        "Hello,\n\n"
        "You have successfully subscribed to the Ava Pharmacy newsletter.\n"
        "We will send you new product updates, offers, and pharmacy tips to this email address.\n\n"
        "If you did not request this subscription, please contact our support team.\n\n"
        "Ava Pharmacy"
    )
    send_mail(
        subject=subject,
        message=message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[email],
        fail_silently=False,
    )
