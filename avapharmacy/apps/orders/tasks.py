try:  # pragma: no cover - optional dependency in local dev
    from celery import shared_task
except ImportError:  # pragma: no cover
    def shared_task(*args, **kwargs):
        def decorator(func):
            return func
        return decorator

from django.core.management import call_command


@shared_task(name='apps.orders.tasks.retry_outbound_order_pushes_task')
def retry_outbound_order_pushes_task():
    return call_command('retry_order_pushes')
