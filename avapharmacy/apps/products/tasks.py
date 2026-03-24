try:  # pragma: no cover - optional dependency in local dev
    from celery import shared_task
except ImportError:  # pragma: no cover
    def shared_task(*args, **kwargs):
        def decorator(func):
            return func
        return decorator

from .inventory_sync import sync_inventory_from_remote


@shared_task(name='apps.products.tasks.sync_inventory_task')
def sync_inventory_task():
    return sync_inventory_from_remote()
