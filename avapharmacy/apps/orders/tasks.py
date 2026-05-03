try:  # pragma: no cover - optional dependency in local dev
    from celery import shared_task
except ImportError:  # pragma: no cover
    def shared_task(*args, **kwargs):
        def decorator(func):
            return func
        return decorator

from .management.commands.retry_order_pushes import Command as RetryOrderPushesCommand


@shared_task(name='apps.orders.tasks.retry_outbound_order_pushes_task')
def retry_outbound_order_pushes_task():
    command = RetryOrderPushesCommand()
    return command.handle()
