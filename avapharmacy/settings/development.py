"""
Development settings for the AvaPharma project.

Extends base settings with DEBUG=True, open ALLOWED_HOSTS, and verbose
console/file logging. SQL query logging can be enabled by setting
SHOW_SQL_DEBUG=True in the environment.
"""
from .base import *

DEBUG = True

ALLOWED_HOSTS = ['*']

# A single storefront render performs several parallel reads and React's
# development checks may run effects more than once. Keep the general browsing
# buckets roomy locally; explicitly scoped login, registration, checkout and
# upload throttles retain the stricter rates declared in base settings.
REST_FRAMEWORK = {
    **REST_FRAMEWORK,
    'DEFAULT_THROTTLE_RATES': {
        **REST_FRAMEWORK['DEFAULT_THROTTLE_RATES'],
        'anon': config('DEV_API_ANON_THROTTLE_RATE', default='10000/hour'),
        'user': config('DEV_API_USER_THROTTLE_RATE', default='10000/hour'),
    },
}

SHOW_SQL_DEBUG = config('SHOW_SQL_DEBUG', default=False, cast=bool)

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '[{levelname}] {asctime} {module} {message}',
            'style': '{',
        },
        'simple': {
            'format': '[{levelname}] {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
        'file_error': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': BASE_DIR / 'logs/errors.log',
            'maxBytes': 10 * 1024 * 1024,  # 10 MB
            'backupCount': 5,
            'level': 'ERROR',
            'formatter': 'verbose',
        },
        'file_general': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': BASE_DIR / 'logs/general.log',
            'maxBytes': 10 * 1024 * 1024,
            'backupCount': 5,
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console', 'file_general'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'file_error'],
            'level': 'ERROR',
            'propagate': False,
        },
        'django.request': {
            'handlers': ['console', 'file_error'],
            'level': 'ERROR',
            'propagate': False,
        },
        'django.server': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'django.db.backends': {
            'handlers': ['console'],
            'level': 'DEBUG' if SHOW_SQL_DEBUG else 'WARNING',
            'propagate': False,
        },
        'avapharmacy': {
            'handlers': ['console', 'file_error'],
            'level': 'DEBUG',
            'propagate': False,
        },
    },
}

# A separate Redis database lets local web, worker and beat processes share
# tasks. The in-memory broker cannot deliver between separate processes.
CELERY_BROKER_URL = config('CELERY_BROKER_URL', default='redis://127.0.0.1:6379/14')
CELERY_RESULT_BACKEND = config('CELERY_RESULT_BACKEND', default='redis://127.0.0.1:6379/15')
CELERY_TASK_DEFAULT_QUEUE = config('DEV_CELERY_TASK_QUEUE', default='ava_local_dev')
