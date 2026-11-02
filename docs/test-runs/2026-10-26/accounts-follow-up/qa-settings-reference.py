from avapharmacy.settings.development import *

DATABASES = {**DATABASES, 'default': {**DATABASES['default'], 'NAME': 'ava_accounts_qa_20261026'}}
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = '127.0.0.1'
EMAIL_PORT = 8025
EMAIL_HOST_USER = ''
EMAIL_HOST_PASSWORD = ''
EMAIL_USE_TLS = False
EMAIL_USE_SSL = False
EMAIL_TIMEOUT = 5
DEFAULT_FROM_EMAIL = 'qa@avapharmacy.test'
ADMIN_EMAIL = 'admin@avapharmacy.test'
FRONTEND_BASE_URL = 'http://localhost:3000'
FRONTEND_LOGIN_URL = FRONTEND_BASE_URL + '/login'
BACKEND_BASE_URL = 'http://127.0.0.1:8002'
CORS_ALLOWED_ORIGINS = ['http://localhost:3000', 'http://127.0.0.1:3000']
MEDIA_ROOT = '/private/tmp/ava-accounts-qa-media'
REST_FRAMEWORK = {**REST_FRAMEWORK, 'DEFAULT_THROTTLE_RATES': {
    **REST_FRAMEWORK['DEFAULT_THROTTLE_RATES'], 'login': '1000/min', 'register': '1000/hour',
    'forgot_password': '1000/hour',
}}
