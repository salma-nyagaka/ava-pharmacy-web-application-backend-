from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Order
from .utils import queue_mpesa_receipt_email


@receiver(post_save, sender=Order)
def order_send_mpesa_receipt_after_payment(sender, instance, **kwargs):
    if (
        instance.payment_status == Order.PAYMENT_STATUS_PAID
        and instance.receipt_emailed_at is None
        and instance.payment_method in {Order.PAYMENT_MPESA_STK, Order.PAYMENT_MPESA_PAYBILL}
    ):
        queue_mpesa_receipt_email(instance)
