"""Branded QA instructions only; never use these to email production passwords."""
from datetime import datetime
from email.mime.image import MIMEImage
from pathlib import Path
from urllib.parse import urlsplit

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string


QA_EMAIL_TYPES = {
    'change_password': {
        'subject': 'AVA Pharmacy QA: Change your password',
        'heading': 'Change your password',
        'preheader': 'Your QA account password-change check is ready.',
        'action_label': 'Change password',
        'plain_intro': 'Open Account Settings > Password to update it.',
        'action_note': 'Already completed this check? Keep the test password you chose.',
    },
    'reset_password': {
        'subject': 'AVA Pharmacy QA: Reset your password',
        'heading': 'Reset your password',
        'preheader': 'Reset your QA account password with your secure link.',
        'action_label': 'Reset password',
        'plain_intro': 'Set and confirm your new test password.',
        'action_note': 'Use your newest reset email. A reset link cannot be used again after a successful reset.',
    },
    'activate_doctor': {
        'subject': 'AVA Pharmacy QA: Activate your doctor account',
        'heading': 'Activate your doctor account',
        'preheader': 'Your QA doctor account is ready for activation.',
        'action_label': 'Activate account',
        'plain_intro': 'Set your password and accept the terms to activate.',
        'action_note': 'Use the newest activation link. After activation, sign in to open your doctor dashboard.',
    },
    'signup': {
        'subject': 'AVA Pharmacy QA: Create your account',
        'heading': 'Create your account',
        'preheader': 'Your QA customer signup details, all in one place.',
        'action_label': 'Create account',
        'plain_intro': 'Register with these details, then verify your email.',
        'action_note': 'Already registered? Sign in instead. Otherwise, check your verification email after signup.',
    },
}


def render_qa_email(*, kind, account_email, test_password, action_url,
                    current_password='', registration_details=()):
    if kind not in QA_EMAIL_TYPES:
        raise ValueError('Unknown QA email type.')
    parsed = urlsplit(action_url)
    if parsed.scheme not in {'http', 'https'} or not parsed.netloc:
        raise ValueError('QA action links must be absolute HTTP(S) URLs.')
    context = {
        **QA_EMAIL_TYPES[kind],
        'account_email': account_email,
        'test_password': test_password,
        'current_password': current_password,
        'action_url': action_url,
        'registration_details': registration_details,
        'site_url': getattr(settings, 'FRONTEND_BASE_URL', 'http://localhost:3000'),
        'support_email': getattr(settings, 'ADMIN_EMAIL', 'support@avapharmacy.co.ke'),
        'year': datetime.now().year,
    }
    return {
        'subject': context['subject'],
        'text': render_to_string('accounts/emails/qa/message.txt', context),
        'html': render_to_string(f'accounts/emails/qa/{kind}.html', context),
    }


def send_qa_email(*, recipient, kind, account_email, test_password, action_url,
                  current_password='', registration_details=(), connection=None):
    rendered = render_qa_email(
        kind=kind, account_email=account_email, test_password=test_password,
        action_url=action_url, current_password=current_password,
        registration_details=registration_details,
    )
    message = EmailMultiAlternatives(
        subject=rendered['subject'], body=rendered['text'],
        from_email=settings.DEFAULT_FROM_EMAIL, to=[recipient], connection=connection,
    )
    message.attach_alternative(rendered['html'], 'text/html')
    message.mixed_subtype = 'related'
    logo_path = Path(settings.BASE_DIR) / 'templates/emails/assets/ava-logo.jpg'
    logo = MIMEImage(logo_path.read_bytes(), _subtype='jpeg')
    logo.add_header('Content-ID', '<ava-logo>')
    logo.add_header('Content-Disposition', 'inline', filename='ava-logo.jpg')
    message.attach(logo)
    return message.send(fail_silently=False)
