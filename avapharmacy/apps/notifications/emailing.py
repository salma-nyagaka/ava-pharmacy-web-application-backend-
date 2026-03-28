from urllib.parse import quote

from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string


def frontend_base_url():
    return getattr(settings, 'FRONTEND_BASE_URL', 'http://localhost:3000').rstrip('/')


def backend_base_url():
    return getattr(settings, 'BACKEND_BASE_URL', 'http://127.0.0.1:8000').rstrip('/')


def build_login_redirect_url(path):
    safe_path = (path or '/').strip() or '/'
    if not safe_path.startswith('/'):
        safe_path = f'/{safe_path}'
    login_url = getattr(settings, 'FRONTEND_LOGIN_URL', f'{frontend_base_url()}/login')
    separator = '&' if '?' in login_url else '?'
    return f'{login_url}{separator}redirect={quote(safe_path, safe="/?=&")}'


def build_absolute_media_url(field_or_url):
    if not field_or_url:
        return ''

    url = ''
    if hasattr(field_or_url, 'url'):
        try:
            url = field_or_url.url
        except ValueError:
            url = ''
    else:
        url = str(field_or_url)

    if not url:
        return ''
    if url.startswith('http://') or url.startswith('https://'):
        return url
    return f'{backend_base_url()}{url}'


def send_rendered_email(
    *,
    subject,
    recipient_list,
    text_template,
    html_template,
    context,
    fail_silently=False,
):
    message = render_to_string(text_template, context)
    html_message = render_to_string(html_template, context)
    send_mail(
        subject=subject,
        message=message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=recipient_list,
        html_message=html_message,
        fail_silently=fail_silently,
    )
