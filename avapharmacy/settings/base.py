"""
Base Django settings for the AvaPharma project.

Shared across all environments. Environment-specific files (development,
production) import from this module via ``from .base import *`` and override
values as needed. Sensitive values are read from the environment using
``python-decouple``.
"""
from pathlib import Path
from decouple import config
from datetime import timedelta

BASE_DIR = Path(__file__).resolve().parent.parent.parent
LOG_DIR = BASE_DIR / 'logs'
LOG_DIR.mkdir(exist_ok=True)

SECRET_KEY = config('SECRET_KEY', default='django-insecure-change-this-in-production')

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Third-party
    'rest_framework',
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',
    'corsheaders',
    'django_filters',
    'drf_spectacular',

    # Local apps
    'apps.accounts',
    'apps.products',
    'apps.orders',
    'apps.prescriptions',
    'apps.consultations',
    'apps.lab',
    'apps.support',
    'apps.payouts',
    'apps.notifications',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'avapharmacy.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'avapharmacy.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': config('DATABASE_NAME', default='avapharmacy'),
        'USER': config('DATABASE_USER', default='postgres'),
        'PASSWORD': config('DATABASE_PASSWORD', default='postgres'),
        'HOST': config('DATABASE_HOST', default='localhost'),
        'PORT': config('DATABASE_PORT', default='5432'),
        'CONN_MAX_AGE': 60,
        'OPTIONS': {
            'connect_timeout': 10,
        },
    }
}

AUTH_USER_MODEL = 'accounts.User'

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator', 'OPTIONS': {'min_length': 8}},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Africa/Nairobi'
USE_I18N = True
USE_TZ = True

STATIC_URL = config('STATIC_URL', default='/static/')
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

MEDIA_URL = config('MEDIA_URL', default='/media/')
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ─── Django REST Framework ────────────────────────────────────────────────────
REST_FRAMEWORK = {
    'DEFAULT_RENDERER_CLASSES': (
        'avapharmacy.renderers.StandardizedJSONRenderer',
        'rest_framework.renderers.BrowsableAPIRenderer',
    ),
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    'DEFAULT_FILTER_BACKENDS': (
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ),
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '120/hour',
        'user': '2000/hour',
        'login': '5/min',
        'upload': '30/hour',
        'register': '10/hour',
    },
    'EXCEPTION_HANDLER': 'avapharmacy.exception_handler.custom_exception_handler',
}

# ─── JWT ──────────────────────────────────────────────────────────────────────
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(hours=1),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'AUTH_HEADER_TYPES': ('Bearer',),
    'UPDATE_LAST_LOGIN': True,
    'ALGORITHM': 'HS256',
    'AUTH_TOKEN_CLASSES': ('rest_framework_simplejwt.tokens.AccessToken',),
}

# ─── CORS ─────────────────────────────────────────────────────────────────────
CORS_ALLOWED_ORIGINS = config(
    'CORS_ALLOWED_ORIGINS',
    default='http://localhost:5173,http://localhost:3000'
).split(',')
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_HEADERS = [
    'accept', 'accept-encoding', 'authorization',
    'content-type', 'dnt', 'origin', 'user-agent',
    'x-csrftoken', 'x-requested-with',
]

# ─── API Docs ─────────────────────────────────────────────────────────────────
SPECTACULAR_SETTINGS = {
    'TITLE': 'AvaPharma API',
    'DESCRIPTION': 'Full-featured pharmacy backend API: e-commerce, prescriptions, telemedicine, lab, support, real-time notifications.',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
    'COMPONENT_SPLIT_REQUEST': True,
}

# ─── File Upload Limits ───────────────────────────────────────────────────────
MAX_UPLOAD_SIZE_MB = 10
MAX_UPLOAD_SIZE_BYTES = MAX_UPLOAD_SIZE_MB * 1024 * 1024
ALLOWED_IMAGE_TYPES = ['image/jpeg', 'image/png', 'image/webp']
ALLOWED_DOCUMENT_TYPES = ['image/jpeg', 'image/png', 'application/pdf']

# ─── Business Logic ───────────────────────────────────────────────────────────
FREE_SHIPPING_THRESHOLD = 3000
SHIPPING_FEE = 300
PAYMENT_WEBHOOK_SECRET = config('PAYMENT_WEBHOOK_SECRET', default='')

# ─── Admins (error emails) ────────────────────────────────────────────────────
ADMINS = [
    (config('ADMIN_NAME', default='AvaPharma Admin'), config('ADMIN_EMAIL', default='admin@avapharmacy.com')),
]
SERVER_EMAIL = config('SERVER_EMAIL', default='errors@avapharmacy.com')
EMAIL_SUBJECT_PREFIX = '[AvaPharma] '

# ─── Email ────────────────────────────────────────────────────────────────────
EMAIL_BACKEND = config('EMAIL_BACKEND', default='django.core.mail.backends.console.EmailBackend')
EMAIL_HOST = config('EMAIL_HOST', default='smtp.gmail.com')
EMAIL_PORT = config('EMAIL_PORT', default=587, cast=int)
EMAIL_USE_TLS = config('EMAIL_USE_TLS', default=True, cast=bool)
EMAIL_HOST_USER = config('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')
DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL', default='noreply@avapharmacy.com')

# ─── Notifications ────────────────────────────────────────────────────────────
SMS_BACKEND = config('SMS_BACKEND', default='console')
SMS_WEBHOOK_URL = config('SMS_WEBHOOK_URL', default='')
SMS_WEBHOOK_TOKEN = config('SMS_WEBHOOK_TOKEN', default='')
SMS_FROM = config('SMS_FROM', default='AvaPharma')

# ─── Frontend / Account Activation ────────────────────────────────────────────
BACKEND_BASE_URL = config('BACKEND_BASE_URL', default='http://127.0.0.1:8000')
FRONTEND_BASE_URL = config('FRONTEND_BASE_URL', default='http://localhost:3000')
FRONTEND_LOGIN_URL = config('FRONTEND_LOGIN_URL', default=f'{FRONTEND_BASE_URL}/login')
FRONTEND_PHARMACIST_DASHBOARD_URL = config(
    'FRONTEND_PHARMACIST_DASHBOARD_URL',
    default=f'{FRONTEND_BASE_URL}/pharmacist/dashboard'
)
FRONTEND_PHARMACIST_ACTIVATION_PATH = config(
    'FRONTEND_PHARMACIST_ACTIVATION_PATH',
    default='/auth/pharmacist/activate'
)
PHARMACIST_ACTIVATION_TTL_HOURS = config('PHARMACIST_ACTIVATION_TTL_HOURS', default=24, cast=int)

# ─── M-Pesa / Daraja ──────────────────────────────────────────────────────────
MPESA_ENVIRONMENT = config('MPESA_ENVIRONMENT', default='sandbox')
MPESA_CONSUMER_KEY = config('MPESA_CONSUMER_KEY', default='')
MPESA_CONSUMER_SECRET = config('MPESA_CONSUMER_SECRET', default='')
MPESA_SHORTCODE = config('MPESA_SHORTCODE', default='')
MPESA_PASSKEY = config('MPESA_PASSKEY', default='')
MPESA_CALLBACK_URL = config('MPESA_CALLBACK_URL', default='')
MPESA_TRANSACTION_TYPE = config('MPESA_TRANSACTION_TYPE', default='CustomerPayBillOnline')
MPESA_TIMEOUT_SECONDS = config('MPESA_TIMEOUT_SECONDS', default=30, cast=int)
MPESA_STK_PUSH_AMOUNT_OVERRIDE = config('MPESA_STK_PUSH_AMOUNT_OVERRIDE', default='', cast=str)
MPESA_PAYBILL_NUMBER = config('MPESA_PAYBILL_NUMBER', default='')
MPESA_C2B_SHORTCODE = config('MPESA_C2B_SHORTCODE', default=MPESA_PAYBILL_NUMBER)
MPESA_C2B_RESPONSE_TYPE = config('MPESA_C2B_RESPONSE_TYPE', default='Completed')
MPESA_C2B_URLS_REGISTERED = config('MPESA_C2B_URLS_REGISTERED', default=False, cast=bool)
MPESA_REQUIRE_PUBLIC_CALLBACK_URLS = config('MPESA_REQUIRE_PUBLIC_CALLBACK_URLS', default=True, cast=bool)
MPESA_STATUS_SYNC_MIN_INTERVAL_SECONDS = config('MPESA_STATUS_SYNC_MIN_INTERVAL_SECONDS', default=15, cast=int)
MPESA_STATUS_SYNC_RETRY_AFTER_429_SECONDS = config('MPESA_STATUS_SYNC_RETRY_AFTER_429_SECONDS', default=65, cast=int)
MPESA_STATUS_SYNC_RETRY_AFTER_403_SECONDS = config('MPESA_STATUS_SYNC_RETRY_AFTER_403_SECONDS', default=180, cast=int)
MPESA_C2B_VALIDATION_URL = config(
    'MPESA_C2B_VALIDATION_URL',
    default=f'{BACKEND_BASE_URL}/api/payments/mpesa/paybill/validation/',
)
MPESA_C2B_CONFIRMATION_URL = config(
    'MPESA_C2B_CONFIRMATION_URL',
    default=f'{BACKEND_BASE_URL}/api/payments/mpesa/paybill/confirmation/',
)
MPESA_PAYBILL_ACCOUNT_PREFIX = config('MPESA_PAYBILL_ACCOUNT_PREFIX', default='')
MPESA_PAYBILL_ACCOUNT_LABEL = config('MPESA_PAYBILL_ACCOUNT_LABEL', default='Account Number')
MPESA_PAYBILL_INSTRUCTIONS = config(
    'MPESA_PAYBILL_INSTRUCTIONS',
    default='Pay using the M-Pesa Paybill details below. We confirm the payment automatically once Safaricom sends the callback.',
)

# ─── Flutterwave / Card Payments ──────────────────────────────────────────────
FLUTTERWAVE_SECRET_KEY = config('FLUTTERWAVE_SECRET_KEY', default='')
FLUTTERWAVE_SECRET_HASH = config('FLUTTERWAVE_SECRET_HASH', default='')
FLUTTERWAVE_BASE_URL = config('FLUTTERWAVE_BASE_URL', default='https://api.flutterwave.com')
FLUTTERWAVE_TIMEOUT_SECONDS = config('FLUTTERWAVE_TIMEOUT_SECONDS', default=30, cast=int)
FLUTTERWAVE_REDIRECT_URL = config('FLUTTERWAVE_REDIRECT_URL', default=f'{FRONTEND_BASE_URL}/checkout')

# ─── POS / External Order Push ────────────────────────────────────────────────
POS_LINK_STRATEGY = config('POS_LINK_STRATEGY', default='sku_or_pos_id')
POS_ORDER_PUSH_URL = config('POS_ORDER_PUSH_URL', default='')
POS_ORDER_PUSH_TOKEN = config('POS_ORDER_PUSH_TOKEN', default='')
POS_ORDER_PUSH_TIMEOUT_SECONDS = config('POS_ORDER_PUSH_TIMEOUT_SECONDS', default=15, cast=int)
POS_ORDER_PUSH_MAX_ATTEMPTS = config('POS_ORDER_PUSH_MAX_ATTEMPTS', default=3, cast=int)
POS_ORDER_PUSH_BACKOFF_SECONDS = config('POS_ORDER_PUSH_BACKOFF_SECONDS', default=1.0, cast=float)
POS_ORDER_PUSH_MAX_BACKOFF_SECONDS = config('POS_ORDER_PUSH_MAX_BACKOFF_SECONDS', default=8.0, cast=float)
POS_ORDER_PUSH_QUEUE_MAX_ATTEMPTS = config('POS_ORDER_PUSH_QUEUE_MAX_ATTEMPTS', default=10, cast=int)
POS_INVENTORY_LOOKUP_URL = config('POS_INVENTORY_LOOKUP_URL', default='')
POS_INVENTORY_LOOKUP_TOKEN = config('POS_INVENTORY_LOOKUP_TOKEN', default='')
POS_INVENTORY_LOOKUP_TIMEOUT_SECONDS = config('POS_INVENTORY_LOOKUP_TIMEOUT_SECONDS', default=8, cast=int)
POS_INVENTORY_LOOKUP_TTL_SECONDS = config('POS_INVENTORY_LOOKUP_TTL_SECONDS', default=300, cast=int)

# ─── Custom exception handler ─────────────────────────────────────────────────
REST_FRAMEWORK_EXCEPTION_HANDLER = 'avapharmacy.exception_handler.custom_exception_handler'

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '%(asctime)s [%(levelname)s] %(name)s %(message)s',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
        'payments_file': {
            'class': 'logging.FileHandler',
            'filename': LOG_DIR / 'payments.log',
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'payments': {
            'handlers': ['console', 'payments_file'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}
