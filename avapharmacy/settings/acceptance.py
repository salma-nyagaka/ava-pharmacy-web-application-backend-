"""Opt-in synthetic acceptance only. Refuses the normal development/production DB."""
from .development import *
from django.core.exceptions import ImproperlyConfigured
import os

if not DATABASES['default']['NAME'].startswith('qa_acceptance_'):
    raise ImproperlyConfigured('Acceptance settings require an isolated qa_acceptance_ database.')
if not DATABASES['default']['USER'].startswith('qa_acceptance_'):
    raise ImproperlyConfigured('Acceptance requires a dedicated restricted QA database role.')
ALLOWED_HOSTS=['127.0.0.1','localhost','testserver']
CORS_ALLOWED_ORIGINS=['http://127.0.0.1:5180']
FRONTEND_BASE_URL='http://127.0.0.1:5180'
MEDIA_ROOT=os.environ['QA_MEDIA_ROOT']
EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend'
CHANNEL_LAYERS={'default':{'BACKEND':'channels.layers.InMemoryChannelLayer'}}
CACHES={'default':{'BACKEND':'django.core.cache.backends.locmem.LocMemCache','LOCATION':'synthetic-acceptance'}}
CELERY_TASK_ALWAYS_EAGER=True
BOT_CHALLENGE_REQUIRED=False
TURNSTILE_SECRET_KEY=''
MPESA_CONSUMER_KEY=''
MPESA_CONSUMER_SECRET=''
MPESA_PASSKEY=''
MPESA_ENVIRONMENT='sandbox'
SMS_PROVIDER='console'
TWILIO_ACCOUNT_SID=''
TWILIO_AUTH_TOKEN=''
