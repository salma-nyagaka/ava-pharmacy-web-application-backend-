"""
Production settings for the AvaPharma project.

Extends base settings with HTTPS redirects, HSTS, secure cookies, SMTP email
backend, and stricter logging that emails ERROR-level events to the configured
ADMINS list via AdminEmailHandler.
"""
from .base import *

DEBUG = False

ALLOWED_HOSTS = [host.strip() for host in config('ALLOWED_HOSTS', default='').split(',') if host.strip()]
CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in config('CSRF_TRUSTED_ORIGINS', default='').split(',')
    if origin.strip()
]

SECURE_SSL_REDIRECT = True
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True

EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '[{levelname}] {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
    },
    'filters': {
        'require_debug_false': {
            '()': 'django.utils.log.RequireDebugFalse',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
        'file_error': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': BASE_DIR / 'logs/errors.log',
            'maxBytes': 10 * 1024 * 1024,
            'backupCount': 10,
            'level': 'ERROR',
            'formatter': 'verbose',
        },
        'file_general': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': BASE_DIR / 'logs/general.log',
            'maxBytes': 10 * 1024 * 1024,
            'backupCount': 10,
            'formatter': 'verbose',
        },
        'mail_admins': {
            'level': 'ERROR',
            'class': 'django.utils.log.AdminEmailHandler',
            'filters': ['require_debug_false'],
            'include_html': True,
        },
    },
    'root': {
        'handlers': ['console', 'file_general'],
        'level': 'WARNING',
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'file_error', 'mail_admins'],
            'level': 'ERROR',
            'propagate': False,
        },
        'django.request': {
            'handlers': ['console', 'file_error', 'mail_admins'],
            'level': 'ERROR',
            'propagate': False,
        },
        'avapharmacy': {
            'handlers': ['console', 'file_error', 'mail_admins'],
            'level': 'WARNING',
            'propagate': False,
        },
    },
}
