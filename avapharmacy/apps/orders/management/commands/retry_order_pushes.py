from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.orders.integrations import push_order_to_pos
from apps.orders.models import OutboundOrderPush


class Command(BaseCommand):
    help = 'Retry pending outbound POS order pushes that are due.'

    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, default=20, help='Maximum queued pushes to process.')
        parser.add_argument('--id', type=int, help='Retry a specific queue record id.')

    def handle(self, *args, **options):
        limit = max(1, options['limit'])
        queue_id = options.get('id')

        queryset = OutboundOrderPush.objects.select_related('order').filter(
            status__in=[OutboundOrderPush.STATUS_PENDING, OutboundOrderPush.STATUS_RETRYING],
            next_attempt_at__lte=timezone.now(),
        ).order_by('next_attempt_at', 'created_at')

        if queue_id:
            queryset = queryset.filter(pk=queue_id)

        processed = 0
        succeeded = 0
        exhausted = 0

        for queue_record in queryset[:limit]:
            with transaction.atomic():
                locked = (
                    OutboundOrderPush.objects.select_for_update()
                    .select_related('order')
                    .get(pk=queue_record.pk)
                )
                if locked.status not in [OutboundOrderPush.STATUS_PENDING, OutboundOrderPush.STATUS_RETRYING]:
                    continue
                if locked.next_attempt_at and locked.next_attempt_at > timezone.now():
                    continue

                result = push_order_to_pos(
                    locked.order,
                    locked.action,
                    queue_record=locked,
                    persist_failure=True,
                    max_attempts=1,
                )
                if result is None:
                    self.stdout.write(self.style.WARNING('POS_ORDER_PUSH_URL is not configured; stopping retry run.'))
                    return
                processed += 1
                if result.get('ok'):
                    succeeded += 1
                elif result.get('queue_status') == OutboundOrderPush.STATUS_EXHAUSTED:
                    exhausted += 1

                self.stdout.write(
                    self.style.SUCCESS(
                        f'Queue #{locked.id} -> {"ok" if result.get("ok") else result.get("queue_status", "failed")}'
                    )
                )

        self.stdout.write(
            self.style.SUCCESS(
                f'Processed {processed} queued push(es); succeeded={succeeded}, exhausted={exhausted}.'
            )
        )
