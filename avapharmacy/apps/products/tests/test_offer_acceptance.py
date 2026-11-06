from datetime import timedelta
from decimal import Decimal
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient
from apps.products.models import Promotion, Product, Variant
from apps.products.serializers import PromotionSerializer
from apps.products.services import calculate_variant_pricing, get_active_promotions_queryset
from apps.orders.models import Coupon, Cart, CartItem
from apps.orders.serializers import CouponSerializer
from apps.accounts.models import User


@override_settings(CHECKOUT_COUPONS_ENABLED=True)
class OfferChecklistTests(TestCase):
    def setUp(self):
        self.today = timezone.now().date()
        self.offer = Promotion.objects.create(title='Checklist offer', code='CHECK15', scope='all', type='percentage', value=15, start_date=self.today, end_date=self.today, status='active')
        self.product = Product.objects.create(name='Checklist item', price=100)
        self.variant = self.product.variants.get()
        self.user = User.objects.create_user(email='offer-check@example.test')
        self.cart = Cart.objects.create(user=self.user)
        CartItem.objects.create(cart=self.cart, variant=self.variant, quantity=1)
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_s05_06_dates_required_and_reversed_rejected(self):
        for data in ({'start_date': str(self.today + timedelta(days=1))}, {'start_date': ''}, {'end_date': ''}):
            serializer = PromotionSerializer(self.offer, data=data, partial=True)
            self.assertFalse(serializer.is_valid())
        serializer = PromotionSerializer(data={'title':'No dates','scope':'all','type':'percentage','value':10})
        self.assertFalse(serializer.is_valid())
        self.assertIn('start_date', serializer.errors)
        self.assertIn('end_date', serializer.errors)

    def test_s05_07_deal_values_and_duplicate_codes(self):
        for data, field in (({'value': -1}, 'value'), ({'value':101}, 'value')):
            serializer = PromotionSerializer(self.offer, data=data, partial=True)
            self.assertFalse(serializer.is_valid())
            self.assertIn(field, serializer.errors)
        other = Promotion.objects.create(title='Other', scope='all', type='percentage', value=5, start_date=self.today, end_date=self.today)
        serializer = PromotionSerializer(other, data={'code':' check15 '}, partial=True)
        self.assertFalse(serializer.is_valid())
        self.assertIn('code', serializer.errors)
        for value in (1,100):
            serializer = PromotionSerializer(self.offer, data={'value':value}, partial=True)
            self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_s05_07_coupon_values_and_duplicate_codes(self):
        Coupon.objects.create(code='EXISTS',value=10)
        for data, field in (({'code':' exists ','value':10},'code'), ({'code':'NEW','value':-1},'value'), ({'code':'NEW','value':101},'value')):
            serializer = CouponSerializer(data=data)
            self.assertFalse(serializer.is_valid())
            self.assertIn(field, serializer.errors)

    def test_s05_08_unavailable_and_minimum_coupons_never_discount(self):
        now = timezone.now()
        for code, fields in [('MIN',{'minimum_subtotal':1000}), ('FUTURE',{'starts_at':now+timedelta(days=1)}), ('EXPIRED',{'ends_at':now-timedelta(days=1)}), ('INACTIVE',{'is_active':False})]:
            coupon = Coupon.objects.create(code=code,value=10,**fields)
            response = self.client.post(reverse('cart-apply-coupon'), {'code':code}, format='json')
            self.assertEqual(response.status_code,400,response.data)
            self.cart.coupon=coupon
            self.cart.save()
            self.assertEqual(self.cart.discount_total,0)

    def test_s05_08_excluded_prescription_items_do_not_contribute(self):
        self.offer.status='draft'; self.offer.save()
        Coupon.objects.create(code='VALID',value=10,minimum_subtotal=50)
        self.variant.requires_prescription=True; self.variant.save()
        response=self.client.post(reverse('cart-apply-coupon'),{'code':'VALID'},format='json')
        self.assertEqual(response.status_code,400)
        product=Product.objects.create(name='Eligible',price=40)
        CartItem.objects.create(cart=self.cart,variant=product.variants.get(),quantity=1)
        response=self.client.post(reverse('cart-apply-coupon'),{'code':'VALID'},format='json')
        self.assertEqual(response.status_code,400)
        coupon=Coupon.objects.get(code='VALID');coupon.minimum_subtotal=0;coupon.save()
        response=self.client.post(reverse('cart-apply-coupon'),{'code':'VALID'},format='json')
        self.assertEqual(response.status_code,200,response.data)
        self.cart.refresh_from_db()
        self.assertEqual(self.cart.discount_total,Decimal('4'))

    def test_s05_09_public_visibility_and_price_follow_dates_and_status(self):
        for changes in ({'start_date':self.today+timedelta(days=1),'end_date':self.today+timedelta(days=2)}, {'start_date':self.today-timedelta(days=2),'end_date':self.today-timedelta(days=1)}, {'start_date':self.today,'end_date':self.today,'status':'draft'}):
            for field,value in changes.items():setattr(self.offer,field,value)
            self.offer.save()
            self.assertFalse(get_active_promotions_queryset().filter(pk=self.offer.pk).exists())
            self.assertEqual(calculate_variant_pricing(self.variant)['discount_total'],0)
            from apps.products.views import PromotionListView
            self.assertFalse(PromotionListView().get_queryset().filter(pk=self.offer.pk).exists())
        self.offer.status='active'; self.offer.save()
        self.assertTrue(get_active_promotions_queryset().filter(pk=self.offer.pk).exists())
        self.assertEqual(calculate_variant_pricing(self.variant)['discount_total'],15)

    def test_s05_08_checkout_totals_and_excluded_offer_target(self):
        from apps.orders.views import build_order_totals
        self.offer.status = 'draft'; self.offer.save()
        coupon = Coupon.objects.create(code='TOTAL', value=10, minimum_subtotal=101)
        self.cart.coupon = coupon; self.cart.save()
        self.assertEqual(build_order_totals(self.cart, items=list(self.cart.items.select_related('variant')))[1], 0)
        self.offer.status = 'active'
        self.offer.scope = 'product'
        self.offer.targets = ['different-item']
        self.offer.save()
        self.assertEqual(calculate_variant_pricing(self.variant)['discount_total'], 0)
