import calendar
from datetime import timedelta
from django.utils import timezone


def next_due(start, interval, unit):
    if unit == 'days':
        return start + timedelta(days=interval)
    month = start.year * 12 + start.month - 1 + interval
    year, month = divmod(month, 12)
    month += 1
    return start.replace(year=year, month=month, day=min(start.day, calendar.monthrange(year, month)[1]))


def schedule_refills(prescription):
    for item in prescription.items.filter(is_refill=True, next_refill_at__isnull=True, refill_interval__gt=0):
        item.next_refill_at = next_due(timezone.localdate(), item.refill_interval, item.refill_unit)
        item.save(update_fields=['next_refill_at'])
