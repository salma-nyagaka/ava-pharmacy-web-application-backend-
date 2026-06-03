from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.notifications.models import Notification
from apps.notifications.utils import create_notification

from .models import VariantInventory


def _remove_unavailable_variant_from_carts(variant):
    from apps.orders.models import CartItem

    available_quantity = variant.available_quantity
    cart_items = (
        CartItem.objects
        .select_related('cart__user', 'variant__product')
        .filter(variant=variant, cart__user__isnull=False, quantity__gt=available_quantity)
    )
    for cart_item in cart_items:
        user = cart_item.cart.user
        product_name = cart_item.variant.product.name
        variant_name = cart_item.variant.name
        selected_quantity = cart_item.quantity
        cart_item.delete()

        if available_quantity > 0:
            message = (
                f'{product_name} ({variant_name}) is no longer available in the quantity you selected '
                f'({selected_quantity}). We removed it from your cart so you can choose an available option.'
            )
        else:
            message = (
                f'{product_name} ({variant_name}) is now out of stock. '
                'We removed it from your cart and will let you know when it is available again.'
            )

        create_notification(
            recipient=user,
            notification_type=Notification.SYSTEM,
            title='Cart item removed',
            message=message,
            data={
                'url': '/cart',
                'product_id': cart_item.variant.product_id,
                'variant_id': cart_item.variant_id,
                'available_quantity': available_quantity,
            },
            send_email=True,
        )


@receiver(post_save, sender=VariantInventory)
def variant_inventory_remove_unavailable_cart_items(sender, instance, **kwargs):
    variant = instance.variant
    transaction.on_commit(lambda: _remove_unavailable_variant_from_carts(variant))
