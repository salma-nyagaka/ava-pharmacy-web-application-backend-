from django.db import transaction
from django.db.models import F
from django.utils import timezone
from apps.products.tasks import shared_task
from .utils import create_notification


@shared_task(name='apps.notifications.tasks.send_clinical_and_stock_reminders')
def send_clinical_and_stock_reminders():
    from apps.accounts.models import User
    from apps.products.models import VariantInventory
    from apps.prescriptions.models import PrescriptionItem
    from apps.prescriptions.reminders import next_due
    today = timezone.localdate()
    sent = 0
    with transaction.atomic():
        items = PrescriptionItem.objects.select_for_update(of=('self',), skip_locked=True).select_related('prescription__patient').filter(
            is_refill=True, refill_interval__gt=0, next_refill_at__lte=today,
            prescription__status='approved', prescription__patient__is_active=True)
        for item in items:
            rx = item.prescription
            if rx.valid_until and rx.valid_until < today:
                item.next_refill_at = None
            else:
                notification = create_notification(rx.patient, 'system', 'Prescription refill reminder',
                    f'Your refill reminder for {item.name} is due. Contact your pharmacist to review your prescription.',
                    data={'url': '/prescriptions', 'prescription_id': rx.pk, 'item_id': item.pk})
                if not notification:
                    continue
                sent += 1
                # Do not send a backlog of reminders after a scheduler outage.
                item.next_refill_at = next_due(today, item.refill_interval, item.refill_unit)
            item.save(update_fields=['next_refill_at'])
    # Polling also catches bulk inventory updates made by POS/sync jobs.
    VariantInventory.objects.filter(low_stock_notified=True, stock_quantity__gt=F('low_stock_threshold')).update(low_stock_notified=False)
    with transaction.atomic():
        inventories = VariantInventory.objects.select_for_update(of=('self',), skip_locked=True).select_related('variant__product').filter(
            variant__is_active=True, variant__product__is_active=True, stock_quantity__lte=F('low_stock_threshold'), low_stock_notified=False).exclude(status__in=['expired', 'damaged'])
        admins = list(User.objects.filter(role='admin', is_active=True, status='active'))
        for inventory in inventories:
            if not admins:
                continue
            delivered = True
            for admin in admins:
                notification = create_notification(admin, 'system', 'Low inventory alert',
                    f'{inventory.variant.product.name} · {inventory.variant.name}: {inventory.stock_quantity} remaining (threshold {inventory.low_stock_threshold}).',
                    data={'url': '/admin/products', 'inventory_id': inventory.pk, 'product_id': inventory.variant.product_id})
                delivered = delivered and bool(notification)
                sent += bool(notification)
            if delivered:
                inventory.low_stock_notified = True
                inventory.save(update_fields=['low_stock_notified'])
    return sent
