from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APIClient
from apps.accounts.models import User
from apps.products.models import Product
from apps.orders.models import Cart, CartItem, Coupon
from apps.orders.views import build_order_totals


@override_settings(CHECKOUT_COUPONS_ENABLED=False)
class PausedCouponTests(TestCase):
    def test_saved_coupon_cannot_reduce_cart_or_checkout_and_apply_is_rejected(self):
        user = User.objects.create_user(email='paused-coupons@example.test')
        coupon = Coupon.objects.create(code='PAUSED', value=20)
        product = Product.objects.create(name='Coupon pause item', price=100)
        cart = Cart.objects.create(user=user, coupon=coupon)
        CartItem.objects.create(cart=cart, variant=product.variants.get(), quantity=1)
        self.assertFalse(coupon.is_available(user))
        self.assertEqual(cart.discount_total, 0)
        self.assertEqual(build_order_totals(cart)[1], 0)
        self.assertEqual(build_order_totals(cart, items=list(cart.items.select_related('variant')))[1], 0)
        client = APIClient(); client.force_authenticate(user)
        for endpoint in ('cart-apply-coupon', 'cart-apply-promo'):
            response = client.post(reverse(endpoint), {'code': 'PAUSED'}, format='json')
            self.assertEqual(response.status_code, 400)
            self.assertIn('unavailable', response.data['detail'])
        self.assertTrue(Coupon.objects.filter(pk=coupon.pk).exists())
