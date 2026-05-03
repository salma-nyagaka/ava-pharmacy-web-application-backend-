import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'avapharmacy.settings.development')

try:  # pragma: no cover - optional dependency in local dev
    from celery import Celery
except ImportError:  # pragma: no cover
    app = None
else:
    app = Celery('avapharmacy')
    app.config_from_object('django.conf:settings', namespace='CELERY')
    app.autodiscover_tasks()
