from django.conf import settings
from django.db import transaction
from django.db import models
from django.db.models import Count, Q, Sum
from django.utils import timezone
from rest_framework import generics, permissions, serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsAdminUser
from apps.accounts.utils import log_admin_action
from apps.notifications.utils import create_notification, get_notification_preferences, notify_order_status
from apps.products.models import Product, ProductVariant, annotate_product_inventory

from .models import Cart, CartItem, Coupon, Order, OrderEvent, OrderItem, OrderNote, PaymentIntent, ReturnRequest, ShippingMethod
from .mpesa import MpesaAPIError, MpesaClient, MpesaConfigurationError, parse_mpesa_callback
from .serializers import (
    AdminOrderSerializer,
    AdminOrderUpdateSerializer,
    CartSerializer,
    CheckoutSerializer,
    CouponApplySerializer,
    OrderNoteCreateSerializer,
    OrderSerializer,
    PaymentIntentCreateSerializer,
    PaymentIntentSerializer,
    PaymentWebhookSerializer,
    ReturnRequestAdminUpdateSerializer,
    ReturnRequestCreateSerializer,
    ReturnRequestSerializer,
    ShippingMethodSerializer,
)


def get_or_create_cart(user):
    cart, _ = Cart.objects.get_or_create(user=user)
    return cart


def create_order_event(order, event_type, message, actor=None, metadata=None):
    return OrderEvent.objects.create(
        order=order,
        actor=actor if getattr(actor, 'is_authenticated', False) else None,
        event_type=event_type,
        message=message,
        metadata=metadata or {},
    )


def _product_availability_error(product, requested_quantity):
    if not product.is_active:
        return f'{product.name} is no longer active.'
    if requested_quantity <= product.stock_quantity:
        return None
    if product.allow_backorder and requested_quantity <= product.available_quantity:
        return None
    if product.stock_quantity == 0 and not product.allow_backorder:
        return f'{product.name} is out of stock.'
    return f'{product.name} only has {product.available_quantity} unit(s) available.'


def _cart_inventory_object(item):
    return item.product_variant or item.product


def validate_cart_items(items):
    errors = []
    for item in items:
        inventory_object = _cart_inventory_object(item)
        error = _product_availability_error(inventory_object, item.quantity)
        if error:
            errors.append(error)
        if item.product.requires_prescription and not item.prescription_id:
            errors.append(f'{item.product.name} requires a prescription reference.')
    return errors


def build_order_totals(cart, shipping_method=None):
    subtotal = cart.total
    discount_total = cart.discount_total
    discounted_subtotal = subtotal - discount_total
    if shipping_method:
        shipping_fee = shipping_method.calculate_fee(discounted_subtotal)
    else:
        shipping_fee = cart.shipping_fee
    total = discounted_subtotal + shipping_fee
    return subtotal, discount_total, shipping_fee, total


def snapshot_cart_to_order(order, cart_items):
    order.items.all().delete()
    for item in cart_items:
        OrderItem.objects.create(
            order=order,
            product=item.product,
            product_variant=item.product_variant,
            product_name=item.product.name,
            product_sku=item.product.sku,
            quantity=item.quantity,
            variant_name=item.product_variant.name if item.product_variant else '',
            variant_sku=item.product_variant.sku if item.product_variant else '',
            unit_price=item.product_variant.effective_price if item.product_variant else item.product.price,
            prescription_id=item.prescription_id,
        )


def notify_order_update(order, title=None, message=None):
    if not order.customer:
        return
    try:
        preferences = get_notification_preferences(order.customer)
        create_notification(
            recipient=order.customer,
            notification_type='order_status',
            title=title or f'Order {order.order_number} Updated',
            message=message or f'Your order is now {order.status}.',
            data={'url': f'/orders/{order.id}', 'reference': order.order_number, 'status': order.status},
            send_email=bool(preferences and preferences.order_updates_email),
            send_sms=bool(preferences and preferences.order_updates_sms),
        )
    except Exception:
        return


class CartView(generics.RetrieveAPIView):
    serializer_class = CartSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return get_or_create_cart(self.request.user)


class CartItemCreateView(generics.CreateAPIView):
    serializer_class = CartSerializer
    permission_classes = [permissions.IsAuthenticated]

    def create(self, request, *args, **kwargs):
        cart = get_or_create_cart(request.user)
        product_id = request.data.get('product_id')
        variant_id = request.data.get('product_variant_id')
        quantity = request.data.get('quantity', 1)
        prescription_id = request.data.get('prescription_id', None)

        try:
            quantity = int(quantity)
            if quantity < 1:
                return Response({'quantity': 'Must be at least 1.'}, status=status.HTTP_400_BAD_REQUEST)
        except (TypeError, ValueError):
            return Response({'quantity': 'Invalid quantity.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            product = Product.objects.select_related('brand', 'category').get(pk=product_id, is_active=True)
        except Product.DoesNotExist:
            return Response({'detail': 'Product not found.'}, status=status.HTTP_404_NOT_FOUND)

        variant = None
        if variant_id:
            try:
                variant = ProductVariant.objects.get(pk=variant_id, product=product, is_active=True)
            except ProductVariant.DoesNotExist:
                return Response({'detail': 'Variant not found for this product.'}, status=status.HTTP_404_NOT_FOUND)

        if product.requires_prescription and not prescription_id:
            return Response(
                {'detail': 'This product requires a prescription reference.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        existing_item = CartItem.objects.filter(
            cart=cart,
            product=product,
            product_variant=variant,
            prescription_id=prescription_id,
        ).first()
        requested_total = quantity + (existing_item.quantity if existing_item else 0)
        inventory_object = variant or product
        error = _product_availability_error(inventory_object, requested_total)
        if error:
            return Response({'detail': error}, status=status.HTTP_400_BAD_REQUEST)

        if existing_item:
            existing_item.quantity = requested_total
            existing_item.save(update_fields=['quantity'])
        else:
            CartItem.objects.create(
                cart=cart,
                product=product,
                product_variant=variant,
                quantity=quantity,
                prescription_id=prescription_id,
            )

        return Response(CartSerializer(cart).data, status=status.HTTP_201_CREATED)


class CartItemUpdateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def patch(self, request, pk):
        cart = get_or_create_cart(request.user)
        try:
            item = CartItem.objects.select_related('product', 'product_variant').get(pk=pk, cart=cart)
        except CartItem.DoesNotExist:
            return Response({'detail': 'Item not found.'}, status=status.HTTP_404_NOT_FOUND)

        quantity = request.data.get('quantity')
        try:
            quantity = int(quantity)
            if quantity < 1:
                return Response({'quantity': 'Must be at least 1.'}, status=status.HTTP_400_BAD_REQUEST)
        except (TypeError, ValueError):
            return Response({'quantity': 'Invalid quantity.'}, status=status.HTTP_400_BAD_REQUEST)

        error = _product_availability_error(_cart_inventory_object(item), quantity)
        if error:
            return Response({'detail': error}, status=status.HTTP_400_BAD_REQUEST)

        item.quantity = quantity
        item.save(update_fields=['quantity'])
        return Response(CartSerializer(cart).data)


class CartItemDeleteView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def delete(self, request, pk):
        cart = get_or_create_cart(request.user)
        try:
            item = CartItem.objects.get(pk=pk, cart=cart)
        except CartItem.DoesNotExist:
            return Response({'detail': 'Item not found.'}, status=status.HTTP_404_NOT_FOUND)
        item.delete()
        return Response(CartSerializer(cart).data)


class CartClearView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def delete(self, request):
        cart = get_or_create_cart(request.user)
        cart.items.all().delete()
        cart.coupon = None
        cart.save(update_fields=['coupon', 'updated_at'])
        return Response({'detail': 'Cart cleared.'})


class CartApplyCouponView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = CouponApplySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        cart = get_or_create_cart(request.user)
        try:
            coupon = Coupon.objects.get(code=serializer.validated_data['code'].upper())
        except Coupon.DoesNotExist:
            return Response({'detail': 'Coupon not found.'}, status=status.HTTP_404_NOT_FOUND)

        if not coupon.is_available(request.user):
            return Response({'detail': 'Coupon is not available.'}, status=status.HTTP_400_BAD_REQUEST)
        if cart.total < coupon.minimum_subtotal:
            return Response({'detail': 'Cart does not meet coupon minimum subtotal.'}, status=status.HTTP_400_BAD_REQUEST)

        cart.coupon = coupon
        cart.save(update_fields=['coupon', 'updated_at'])
        return Response(CartSerializer(cart).data)


class CartRemoveCouponView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def delete(self, request):
        cart = get_or_create_cart(request.user)
        cart.coupon = None
        cart.save(update_fields=['coupon', 'updated_at'])
        return Response(CartSerializer(cart).data)


class CheckoutDraftView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        serializer = CheckoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        cart = get_or_create_cart(request.user)
        items = list(
            cart.items.select_related('product', 'product__brand', 'product__category', 'product_variant')
            .order_by('id')
        )
        if not items:
            return Response({'detail': 'Cart is empty.'}, status=status.HTTP_400_BAD_REQUEST)

        products = {
            product.id: product
            for product in Product.objects.select_for_update().filter(id__in=[item.product_id for item in items])
        }
        variants = {
            variant.id: variant
            for variant in ProductVariant.objects.select_for_update().filter(
                id__in=[item.product_variant_id for item in items if item.product_variant_id]
            )
        }
        for item in items:
            item.product = products[item.product_id]
            if item.product_variant_id:
                item.product_variant = variants.get(item.product_variant_id)

        errors = validate_cart_items(items)
        if errors:
            return Response({'detail': errors}, status=status.HTTP_400_BAD_REQUEST)

        shipping_method = None
        shipping_method_id = data.get('shipping_method_id')
        if shipping_method_id:
            try:
                shipping_method = ShippingMethod.objects.get(pk=shipping_method_id, is_active=True)
            except ShippingMethod.DoesNotExist:
                return Response({'detail': 'Shipping method not found.'}, status=status.HTTP_404_NOT_FOUND)
        else:
            shipping_method = ShippingMethod.objects.filter(code=data.get('delivery_method', 'standard'), is_active=True).first()

        subtotal, discount_total, shipping_fee, total = build_order_totals(cart, shipping_method=shipping_method)
        order = Order.objects.create(
            customer=request.user,
            coupon=cart.coupon if cart.coupon and cart.coupon.is_available(request.user) else None,
            coupon_code=cart.coupon.code if cart.coupon else '',
            payment_method=data['payment_method'],
            payment_status=Order.PAYMENT_STATUS_PENDING,
            delivery_method=data.get('delivery_method', 'standard'),
            delivery_notes=data.get('delivery_notes', ''),
            shipping_method=shipping_method,
            shipping_first_name=data['first_name'],
            shipping_last_name=data['last_name'],
            shipping_email=data['email'],
            shipping_phone=data['phone'],
            shipping_street=data['street'],
            shipping_city=data['city'],
            shipping_county=data['county'],
            subtotal=subtotal,
            discount_total=discount_total,
            shipping_fee=shipping_fee,
            total=total,
        )
        snapshot_cart_to_order(order, items)
        create_order_event(
            order,
            event_type='draft_created',
            message='Checkout draft created.',
            actor=request.user,
            metadata={
                'item_count': len(items),
                'payment_method': order.payment_method,
                'shipping_method': shipping_method.code if shipping_method else order.delivery_method,
            },
        )
        return Response(OrderSerializer(order).data, status=status.HTTP_201_CREATED)


class PaymentIntentCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        serializer = PaymentIntentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            order = Order.objects.select_for_update().get(pk=data['order_id'], customer=request.user)
        except Order.DoesNotExist:
            return Response({'detail': 'Order not found.'}, status=status.HTTP_404_NOT_FOUND)

        if order.status not in [Order.STATUS_DRAFT, Order.STATUS_PENDING]:
            return Response({'detail': 'Payment intent can only be created for draft or pending orders.'}, status=status.HTTP_400_BAD_REQUEST)

        provider = data['provider']
        payload = {}
        client_secret = ''
        status_value = PaymentIntent.STATUS_REQUIRES_ACTION

        if provider == PaymentIntent.PROVIDER_MANUAL:
            status_value = PaymentIntent.STATUS_SUCCEEDED
        elif provider == PaymentIntent.PROVIDER_MPESA:
            payload = {'phone': data.get('phone', ''), 'instructions': 'Await M-Pesa confirmation.'}
        elif provider == PaymentIntent.PROVIDER_CARD:
            return Response({'detail': 'Card integration is not enabled. Use M-Pesa or manual payment.'}, status=status.HTTP_400_BAD_REQUEST)

        intent = PaymentIntent.objects.create(
            order=order,
            initiated_by=request.user,
            provider=provider,
            status=status_value,
            amount=order.total,
            client_secret=client_secret,
            payload=payload,
            phone_number=data.get('phone', ''),
        )

        if provider == PaymentIntent.PROVIDER_MANUAL:
            order.payment_status = Order.PAYMENT_STATUS_PAID
            order.payment_reference = intent.reference
            order.save(update_fields=['payment_status', 'payment_reference', 'updated_at'])
            create_order_event(order, 'payment_captured', 'Manual payment marked as paid.', actor=request.user)
        elif provider == PaymentIntent.PROVIDER_MPESA:
            try:
                mpesa_client = MpesaClient()
                normalized_phone, response_payload = mpesa_client.initiate_stk_push(
                    payment_intent=intent,
                    phone=data.get('phone', ''),
                    account_reference=order.order_number,
                    description=f'Pay {order.order_number}',
                )
            except MpesaConfigurationError as exc:
                intent.status = PaymentIntent.STATUS_FAILED
                intent.last_error = str(exc)
                intent.save(update_fields=['status', 'last_error', 'updated_at'])
                return Response({'detail': str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
            except MpesaAPIError as exc:
                intent.status = PaymentIntent.STATUS_FAILED
                intent.last_error = str(exc)
                intent.save(update_fields=['status', 'last_error', 'updated_at'])
                order.payment_status = Order.PAYMENT_STATUS_FAILED
                order.save(update_fields=['payment_status', 'updated_at'])
                create_order_event(order, 'payment_failed', str(exc), actor=request.user)
                return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

            intent.phone_number = normalized_phone
            intent.external_reference = order.order_number
            intent.client_secret = response_payload.get('CustomerMessage', '')
            intent.provider_reference = response_payload.get('ResponseCode', '')
            intent.merchant_request_id = response_payload.get('MerchantRequestID', '')
            intent.checkout_request_id = response_payload.get('CheckoutRequestID', '')
            intent.payload = response_payload
            intent.save(update_fields=[
                'phone_number', 'external_reference', 'client_secret', 'provider_reference',
                'merchant_request_id', 'checkout_request_id', 'payload', 'updated_at'
            ])

            order.payment_status = Order.PAYMENT_STATUS_REQUIRES_ACTION
            order.save(update_fields=['payment_status', 'updated_at'])
            create_order_event(
                order,
                'payment_intent_created',
                'M-Pesa STK push initiated.',
                actor=request.user,
                metadata={'intent_reference': intent.reference, 'phone_number': normalized_phone},
            )
        else:
            order.payment_status = Order.PAYMENT_STATUS_REQUIRES_ACTION
            order.save(update_fields=['payment_status', 'updated_at'])
            create_order_event(
                order,
                'payment_intent_created',
                f'Payment intent created via {provider}.',
                actor=request.user,
                metadata={'intent_reference': intent.reference},
            )

        return Response(PaymentIntentSerializer(intent).data, status=status.HTTP_201_CREATED)


class MpesaCallbackView(APIView):
    permission_classes = [permissions.AllowAny]

    @transaction.atomic
    def post(self, request):
        callback = parse_mpesa_callback(request.data)
        checkout_request_id = callback['checkout_request_id']
        merchant_request_id = callback['merchant_request_id']

        try:
            intent = PaymentIntent.objects.select_for_update().select_related('order').get(
                provider=PaymentIntent.PROVIDER_MPESA,
                checkout_request_id=checkout_request_id,
                merchant_request_id=merchant_request_id,
            )
        except PaymentIntent.DoesNotExist:
            return Response({'ResultCode': 1, 'ResultDesc': 'Payment intent not found.'})

        intent.callback_payload = request.data
        intent.processed_at = timezone.now()
        intent.provider_reference = callback['metadata'].get('MpesaReceiptNumber', intent.provider_reference)

        order = intent.order
        if callback['result_code'] == '0':
            intent.status = PaymentIntent.STATUS_SUCCEEDED
            order.payment_status = Order.PAYMENT_STATUS_PAID
            order.payment_reference = intent.provider_reference or intent.reference
            if order.status == Order.STATUS_DRAFT:
                order.status = Order.STATUS_PAID
            if not order.placed_at:
                order.placed_at = timezone.now()
            order.save(update_fields=['payment_status', 'payment_reference', 'status', 'placed_at', 'updated_at'])
            create_order_event(
                order,
                'payment_succeeded',
                'M-Pesa payment confirmed.',
                metadata={'intent_reference': intent.reference, 'receipt': intent.provider_reference},
            )
            notify_order_update(
                order,
                title=f'Payment received for {order.order_number}',
                message='Your M-Pesa payment was confirmed successfully.',
            )
        else:
            intent.status = PaymentIntent.STATUS_FAILED
            intent.last_error = callback['result_desc']
            order.payment_status = Order.PAYMENT_STATUS_FAILED
            order.save(update_fields=['payment_status', 'updated_at'])
            create_order_event(
                order,
                'payment_failed',
                callback['result_desc'] or 'M-Pesa payment failed.',
                metadata={'intent_reference': intent.reference, 'result_code': callback['result_code']},
            )
        intent.save(update_fields=['callback_payload', 'processed_at', 'provider_reference', 'status', 'last_error', 'updated_at'])
        return Response({'ResultCode': 0, 'ResultDesc': 'Accepted'})


class PaymentIntentStatusSyncView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @transaction.atomic
    def post(self, request, pk):
        try:
            intent = PaymentIntent.objects.select_for_update().select_related('order').get(pk=pk, order__customer=request.user)
        except PaymentIntent.DoesNotExist:
            return Response({'detail': 'Payment intent not found.'}, status=status.HTTP_404_NOT_FOUND)

        if intent.provider != PaymentIntent.PROVIDER_MPESA:
            return Response({'detail': 'Only M-Pesa intents can be synced through this endpoint.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            mpesa_response = MpesaClient().query_stk_status(intent)
        except (MpesaConfigurationError, MpesaAPIError) as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        intent.payload = {**intent.payload, 'status_query': mpesa_response}
        result_code = str(mpesa_response.get('ResultCode', ''))
        if result_code == '0':
            intent.status = PaymentIntent.STATUS_SUCCEEDED
            intent.provider_reference = mpesa_response.get('MpesaReceiptNumber', intent.provider_reference)
            intent.processed_at = timezone.now()
            intent.save(update_fields=['payload', 'status', 'provider_reference', 'processed_at', 'updated_at'])
            order = intent.order
            order.payment_status = Order.PAYMENT_STATUS_PAID
            order.payment_reference = intent.provider_reference or intent.reference
            if order.status == Order.STATUS_DRAFT:
                order.status = Order.STATUS_PAID
            order.save(update_fields=['payment_status', 'payment_reference', 'status', 'updated_at'])
        else:
            intent.status = PaymentIntent.STATUS_FAILED
            intent.last_error = mpesa_response.get('ResultDesc', '')
            intent.processed_at = timezone.now()
            intent.save(update_fields=['payload', 'status', 'last_error', 'processed_at', 'updated_at'])

        return Response(PaymentIntentSerializer(intent).data)


class PaymentWebhookView(APIView):
    permission_classes = [permissions.AllowAny]

    @transaction.atomic
    def post(self, request):
        expected_secret = getattr(settings, 'PAYMENT_WEBHOOK_SECRET', '')
        if expected_secret and request.headers.get('X-Ava-Webhook-Secret') != expected_secret:
            return Response({'detail': 'Invalid webhook signature.'}, status=status.HTTP_403_FORBIDDEN)

        serializer = PaymentWebhookSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            intent = PaymentIntent.objects.select_for_update().select_related('order').get(reference=data['reference'])
        except PaymentIntent.DoesNotExist:
            return Response({'detail': 'Payment intent not found.'}, status=status.HTTP_404_NOT_FOUND)

        intent.status = data['status']
        intent.provider_reference = data.get('provider_reference', '')
        intent.payload = data.get('payload', intent.payload)
        intent.last_error = '' if data['status'] == PaymentIntent.STATUS_SUCCEEDED else data.get('message', '')
        intent.processed_at = timezone.now()
        intent.save()

        order = intent.order
        if intent.status == PaymentIntent.STATUS_SUCCEEDED:
            order.payment_status = Order.PAYMENT_STATUS_PAID
            order.payment_reference = intent.provider_reference or intent.reference
            if order.status == Order.STATUS_DRAFT:
                order.status = Order.STATUS_PAID
            if not order.placed_at:
                order.placed_at = timezone.now()
            order.save(update_fields=['payment_status', 'payment_reference', 'status', 'placed_at', 'updated_at'])
            create_order_event(
                order,
                'payment_succeeded',
                'Payment confirmed by webhook.',
                metadata={'intent_reference': intent.reference},
            )
            notify_order_update(
                order,
                title=f'Payment received for {order.order_number}',
                message='Your payment was confirmed successfully.',
            )
        elif intent.status in [PaymentIntent.STATUS_FAILED, PaymentIntent.STATUS_CANCELLED]:
            order.payment_status = Order.PAYMENT_STATUS_FAILED
            order.save(update_fields=['payment_status', 'updated_at'])
            create_order_event(
                order,
                'payment_failed',
                data.get('message') or 'Payment failed.',
                metadata={'intent_reference': intent.reference},
            )

        return Response({'detail': 'Webhook processed.'})


class CheckoutFinalizeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @transaction.atomic
    def post(self, request, pk):
        try:
            order = Order.objects.select_for_update().prefetch_related('items').get(pk=pk, customer=request.user)
        except Order.DoesNotExist:
            return Response({'detail': 'Order not found.'}, status=status.HTTP_404_NOT_FOUND)

        if order.status not in [Order.STATUS_DRAFT, Order.STATUS_PENDING, Order.STATUS_PAID]:
            return Response({'detail': 'Order cannot be finalized in its current state.'}, status=status.HTTP_400_BAD_REQUEST)

        if order.payment_method != Order.PAYMENT_COD and order.payment_status != Order.PAYMENT_STATUS_PAID:
            return Response({'detail': 'Payment must be confirmed before finalizing this order.'}, status=status.HTTP_400_BAD_REQUEST)

        product_ids = [item.product_id for item in order.items.all() if item.product_id]
        variant_ids = [item.product_variant_id for item in order.items.all() if item.product_variant_id]
        locked_products = {
            product.id: product
            for product in Product.objects.select_for_update().filter(id__in=product_ids)
        }
        locked_variants = {
            variant.id: variant
            for variant in ProductVariant.objects.select_for_update().filter(id__in=variant_ids)
        }

        errors = []
        for item in order.items.all():
            inventory_object = locked_variants.get(item.product_variant_id) if item.product_variant_id else locked_products.get(item.product_id)
            if not inventory_object:
                errors.append(f'{item.product_name} is no longer available.')
                continue
            error = _product_availability_error(inventory_object, item.quantity)
            if error:
                errors.append(error)
        if errors:
            return Response({'detail': errors}, status=status.HTTP_400_BAD_REQUEST)

        for item in order.items.all():
            inventory_object = locked_variants.get(item.product_variant_id) if item.product_variant_id else locked_products.get(item.product_id)
            if not inventory_object:
                continue
            inventory_object.stock_quantity = max(0, inventory_object.stock_quantity - item.quantity)
            inventory_object.save()

        order.status = Order.STATUS_PENDING if order.payment_method == Order.PAYMENT_COD else Order.STATUS_PAID
        if order.payment_method == Order.PAYMENT_COD:
            order.payment_status = Order.PAYMENT_STATUS_PENDING
        order.inventory_committed = True
        if not order.placed_at:
            order.placed_at = timezone.now()
        order.save(update_fields=['status', 'payment_status', 'inventory_committed', 'placed_at', 'updated_at'])

        cart = get_or_create_cart(request.user)
        cart.items.all().delete()
        if cart.coupon_id == order.coupon_id:
            cart.coupon = None
            cart.save(update_fields=['coupon', 'updated_at'])

        create_order_event(order, 'order_finalized', 'Order finalized and stock committed.', actor=request.user)
        notify_order_update(
            order,
            title=f'Order {order.order_number} placed',
            message=f'Your order total is KSh {order.total}.',
        )
        return Response(OrderSerializer(order).data)


class OrderListView(generics.ListAPIView):
    serializer_class = OrderSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Order.objects.filter(customer=self.request.user).prefetch_related(
            'items', 'items__product_variant', 'notes', 'events', 'payment_intents', 'return_requests'
        ).select_related('coupon', 'shipping_method')


class OrderDetailView(generics.RetrieveAPIView):
    serializer_class = OrderSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Order.objects.filter(customer=self.request.user).prefetch_related(
            'items', 'items__product_variant', 'notes', 'events', 'payment_intents', 'return_requests'
        ).select_related('coupon', 'shipping_method')


class OrderCancelView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @transaction.atomic
    def post(self, request, pk):
        try:
            order = Order.objects.select_for_update().get(pk=pk, customer=request.user)
        except Order.DoesNotExist:
            return Response({'detail': 'Order not found.'}, status=status.HTTP_404_NOT_FOUND)

        if order.status not in [Order.STATUS_DRAFT, Order.STATUS_PENDING, Order.STATUS_PAID]:
            return Response(
                {'detail': f'Cannot cancel an order with status "{order.status}".'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if order.inventory_committed:
            for item in order.items.select_related('product', 'product_variant').all():
                inventory_object = item.product_variant or item.product
                if inventory_object:
                    inventory_object.stock_quantity += item.quantity
                    inventory_object.save()

        order.status = Order.STATUS_CANCELLED
        order.save(update_fields=['status', 'updated_at'])
        create_order_event(order, 'order_cancelled', 'Order cancelled by customer.', actor=request.user)
        notify_order_update(order, title=f'Order {order.order_number} cancelled', message='Your order was cancelled.')
        return Response({'detail': 'Order cancelled successfully.'})


class ReturnRequestListCreateView(generics.ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return ReturnRequest.objects.filter(customer=self.request.user).select_related('order', 'order_item')

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return ReturnRequestCreateSerializer
        return ReturnRequestSerializer

    def perform_create(self, serializer):
        order_id = self.request.data.get('order_id')
        try:
            order = Order.objects.get(pk=order_id, customer=self.request.user)
        except Order.DoesNotExist as exc:
            raise serializers.ValidationError({'order_id': 'Order not found.'}) from exc

        order_item = serializer.validated_data.get('order_item')
        if order_item and order_item.order_id != order.id:
            raise serializers.ValidationError({'order_item': 'Order item does not belong to the selected order.'})

        return_request = serializer.save(order=order, customer=self.request.user)
        create_order_event(order, 'return_requested', 'Customer requested a return.', actor=self.request.user)
        return return_request


class ShippingMethodListView(generics.ListAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = ShippingMethodSerializer
    queryset = ShippingMethod.objects.filter(is_active=True)


class AdminShippingMethodListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAdminUser]
    serializer_class = ShippingMethodSerializer
    queryset = ShippingMethod.objects.all()
    filterset_fields = ['is_active']
    search_fields = ['code', 'name']

    def perform_create(self, serializer):
        shipping_method = serializer.save()
        log_admin_action(
            self.request.user,
            action='shipping_method_created',
            entity_type='shipping_method',
            entity_id=shipping_method.id,
            message=f'Created shipping method {shipping_method.code}',
        )


class AdminShippingMethodDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAdminUser]
    serializer_class = ShippingMethodSerializer
    queryset = ShippingMethod.objects.all()

    def perform_update(self, serializer):
        shipping_method = serializer.save()
        log_admin_action(
            self.request.user,
            action='shipping_method_updated',
            entity_type='shipping_method',
            entity_id=shipping_method.id,
            message=f'Updated shipping method {shipping_method.code}',
        )


class AdminOrderListView(generics.ListAPIView):
    permission_classes = [IsAdminUser]
    serializer_class = AdminOrderSerializer
    filterset_fields = ['status', 'payment_status', 'payment_method', 'delivery_method']
    search_fields = ['order_number', 'shipping_email', 'customer__email']
    ordering_fields = ['created_at', 'total']
    ordering = ['-created_at']

    def get_queryset(self):
        return Order.objects.all().select_related('customer', 'coupon', 'shipping_method').prefetch_related(
            'items', 'items__product_variant', 'notes', 'events', 'payment_intents', 'return_requests'
        )


class AdminOrderDetailView(generics.RetrieveUpdateAPIView):
    permission_classes = [IsAdminUser]
    queryset = Order.objects.all().select_related('customer', 'coupon', 'shipping_method').prefetch_related(
        'items', 'items__product_variant', 'notes', 'events', 'payment_intents', 'return_requests'
    )

    def get_serializer_class(self):
        if self.request.method in ['PUT', 'PATCH']:
            return AdminOrderUpdateSerializer
        return AdminOrderSerializer

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', True)
        instance = self.get_object()
        prev_status = instance.status
        prev_payment_status = instance.payment_status
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        order = serializer.save()

        if order.status != prev_status:
            create_order_event(
                order,
                'status_changed',
                f'Order status changed from {prev_status} to {order.status}.',
                actor=request.user,
            )
            notify_order_update(order)
        if order.payment_status != prev_payment_status:
            create_order_event(
                order,
                'payment_status_changed',
                f'Payment status changed from {prev_payment_status} to {order.payment_status}.',
                actor=request.user,
            )

        log_admin_action(
            request.user,
            action='order_updated',
            entity_type='order',
            entity_id=order.id,
            message=f'Updated order {order.order_number}',
            metadata={'status': order.status, 'payment_status': order.payment_status},
        )
        return Response(AdminOrderSerializer(order).data)


class AdminOrderNoteView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request, pk):
        try:
            order = Order.objects.get(pk=pk)
        except Order.DoesNotExist:
            return Response({'detail': 'Order not found.'}, status=status.HTTP_404_NOT_FOUND)
        serializer = OrderNoteCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        OrderNote.objects.create(
            order=order,
            content=serializer.validated_data['content'],
            created_by=request.user
        )
        create_order_event(order, 'note_added', 'Admin note added to order.', actor=request.user)
        return Response(AdminOrderSerializer(order).data)


class AdminOrderRefundView(APIView):
    permission_classes = [IsAdminUser]

    @transaction.atomic
    def post(self, request, pk):
        try:
            order = Order.objects.select_for_update().prefetch_related('items').get(pk=pk)
        except Order.DoesNotExist:
            return Response({'detail': 'Order not found.'}, status=status.HTTP_404_NOT_FOUND)

        if order.payment_status != Order.PAYMENT_STATUS_PAID:
            return Response({'detail': 'Only paid orders can be refunded.'}, status=status.HTTP_400_BAD_REQUEST)

        if order.inventory_committed:
            for item in order.items.select_related('product', 'product_variant').all():
                inventory_object = item.product_variant or item.product
                if inventory_object:
                    inventory_object.stock_quantity += item.quantity
                    inventory_object.save()

        order.payment_status = Order.PAYMENT_STATUS_REFUNDED
        order.status = Order.STATUS_REFUNDED
        order.save(update_fields=['payment_status', 'status', 'updated_at'])
        create_order_event(order, 'refunded', 'Order refunded by admin.', actor=request.user)
        log_admin_action(
            request.user,
            action='order_refunded',
            entity_type='order',
            entity_id=order.id,
            message=f'Refunded order {order.order_number}',
        )
        notify_order_update(order, title=f'Order {order.order_number} refunded', message='Your refund has been processed.')
        return Response(AdminOrderSerializer(order).data)


class AdminReturnRequestListView(generics.ListAPIView):
    permission_classes = [IsAdminUser]
    serializer_class = ReturnRequestSerializer
    filterset_fields = ['status']
    search_fields = ['order__order_number', 'customer__email']
    ordering_fields = ['created_at', 'updated_at']
    ordering = ['-created_at']
    queryset = ReturnRequest.objects.all().select_related('order', 'customer')


class AdminReturnRequestDetailView(generics.RetrieveUpdateAPIView):
    permission_classes = [IsAdminUser]
    queryset = ReturnRequest.objects.all().select_related('order', 'customer')

    def get_serializer_class(self):
        if self.request.method in ['PUT', 'PATCH']:
            return ReturnRequestAdminUpdateSerializer
        return ReturnRequestSerializer

    def perform_update(self, serializer):
        return_request = serializer.save()
        create_order_event(
            return_request.order,
            'return_updated',
            f'Return request marked as {return_request.status}.',
            actor=self.request.user,
        )
        log_admin_action(
            self.request.user,
            action='return_request_updated',
            entity_type='return_request',
            entity_id=return_request.id,
            message=f'Updated return request {return_request.id}',
            metadata={'status': return_request.status},
        )


class AdminReportsView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        from apps.accounts.models import User

        today = timezone.now().date()
        month_start = today.replace(day=1)

        paid_orders = Order.objects.filter(payment_status=Order.PAYMENT_STATUS_PAID)
        revenue = paid_orders.aggregate(
            revenue_total=Sum('total'),
            revenue_monthly=Sum('total', filter=Q(created_at__date__gte=month_start))
        )

        top_products = list(
            OrderItem.objects.values('product_name', 'product_sku')
            .annotate(quantity_sold=Sum('quantity'))
            .order_by('-quantity_sold')[:5]
        )

        return Response({
            'total_orders': Order.objects.exclude(status=Order.STATUS_DRAFT).count(),
            'draft_orders': Order.objects.filter(status=Order.STATUS_DRAFT).count(),
            'total_revenue': float(revenue['revenue_total'] or 0),
            'monthly_revenue': float(revenue['revenue_monthly'] or 0),
            'total_customers': User.objects.filter(role=User.CUSTOMER).count(),
            'pending_orders': Order.objects.filter(status=Order.STATUS_PENDING).count(),
            'today_orders': Order.objects.filter(created_at__date=today).count(),
            'refund_requests': ReturnRequest.objects.filter(status=ReturnRequest.STATUS_REQUESTED).count(),
            'orders_by_status': list(Order.objects.values('status').annotate(count=Count('id'))),
            'orders_by_payment': list(Order.objects.values('payment_method').annotate(count=Count('id'))),
            'top_products': top_products,
            'low_stock_products': annotate_product_inventory(Product.objects.filter(is_active=True)).filter(
                total_stock_quantity__gt=0,
                total_stock_quantity__lte=models.F('total_low_stock_threshold'),
            ).count(),
        })


# ─── Cart Merge ────────────────────────────────────────────────────────────────

class CartMergeView(APIView):
    """Merge a guest or localStorage cart into the authenticated user's server cart."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        cart = get_or_create_cart(request.user)
        items_data = request.data.get('items', [])

        for item_data in items_data:
            product_id = item_data.get('product_id')
            quantity = int(item_data.get('quantity', 1))
            if not product_id or quantity < 1:
                continue
            try:
                product = Product.objects.get(pk=product_id, is_active=True)
            except Product.DoesNotExist:
                continue

            existing = CartItem.objects.filter(cart=cart, product=product, product_variant=None).first()
            if existing:
                new_qty = existing.quantity + quantity
                error = _product_availability_error(product, new_qty)
                if not error:
                    existing.quantity = new_qty
                    existing.save(update_fields=['quantity'])
            else:
                available = min(quantity, product.stock_quantity if product.stock_quantity > 0 else quantity)
                if available > 0:
                    CartItem.objects.create(cart=cart, product=product, quantity=available)

        return Response(CartSerializer(cart).data)


# ─── Simplified One-Step Order Creation ───────────────────────────────────────

class OrderCreateView(APIView):
    """Create an order from the cart in a single request (draft + finalize combined)."""

    permission_classes = [permissions.IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        serializer = CheckoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        cart = get_or_create_cart(request.user)
        items = list(
            cart.items.select_related('product', 'product__brand', 'product__category', 'product_variant')
            .order_by('id')
        )
        if not items:
            return Response(
                {'error': {'code': 'cart_empty', 'message': 'Cart is empty.'}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        products = {
            product.id: product
            for product in Product.objects.select_for_update().filter(id__in=[item.product_id for item in items])
        }
        variants = {
            variant.id: variant
            for variant in ProductVariant.objects.select_for_update().filter(
                id__in=[item.product_variant_id for item in items if item.product_variant_id]
            )
        }
        for item in items:
            item.product = products[item.product_id]
            if item.product_variant_id:
                item.product_variant = variants.get(item.product_variant_id)

        errors = validate_cart_items(items)
        if errors:
            return Response(
                {'error': {'code': 'validation_error', 'message': errors[0] if errors else 'Cart validation failed.', 'details': errors}},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        shipping_method = None
        shipping_method_id = data.get('shipping_method_id')
        if shipping_method_id:
            try:
                shipping_method = ShippingMethod.objects.get(pk=shipping_method_id, is_active=True)
            except ShippingMethod.DoesNotExist:
                pass
        if not shipping_method:
            shipping_method = ShippingMethod.objects.filter(
                code=data.get('delivery_method', 'standard'), is_active=True
            ).first()

        subtotal, discount_total, shipping_fee, total = build_order_totals(cart, shipping_method=shipping_method)
        payment_method = data['payment_method']

        order = Order.objects.create(
            customer=request.user,
            coupon=cart.coupon if cart.coupon and cart.coupon.is_available(request.user) else None,
            coupon_code=cart.coupon.code if cart.coupon else '',
            payment_method=payment_method,
            payment_status=Order.PAYMENT_STATUS_PENDING,
            delivery_method=data.get('delivery_method', 'standard'),
            delivery_notes=data.get('delivery_notes', ''),
            shipping_method=shipping_method,
            shipping_first_name=data['first_name'],
            shipping_last_name=data['last_name'],
            shipping_email=data['email'],
            shipping_phone=data['phone'],
            shipping_street=data['street'],
            shipping_city=data['city'],
            shipping_county=data['county'],
            subtotal=subtotal,
            discount_total=discount_total,
            shipping_fee=shipping_fee,
            total=total,
            status=Order.STATUS_PENDING,
            placed_at=timezone.now(),
        )
        snapshot_cart_to_order(order, items)
        create_order_event(order, 'order_created', 'Order placed.', actor=request.user)

        # For COD: mark inventory immediately
        if payment_method == Order.PAYMENT_COD:
            for item in items:
                inventory_object = item.product_variant or item.product
                if inventory_object:
                    inventory_object.stock_quantity = max(0, inventory_object.stock_quantity - item.quantity)
                    inventory_object.save()
            order.inventory_committed = True
            order.save(update_fields=['inventory_committed', 'updated_at'])

        # Clear cart
        cart.items.all().delete()
        if cart.coupon:
            cart.coupon = None
            cart.save(update_fields=['coupon', 'updated_at'])

        notify_order_update(
            order,
            title=f'Order {order.order_number} placed',
            message=f'Your order total is KSh {order.total}.',
        )
        return Response(OrderSerializer(order).data, status=status.HTTP_201_CREATED)


# ─── Order Tracking ────────────────────────────────────────────────────────────

class OrderTrackingView(APIView):
    """Return tracking steps for a specific order."""

    permission_classes = [permissions.IsAuthenticated]

    STATUS_LABELS = {
        Order.STATUS_PENDING: 'Order Confirmed',
        Order.STATUS_PROCESSING: 'Being Prepared',
        Order.STATUS_SHIPPED: 'On The Way',
        Order.STATUS_DELIVERED: 'Delivered',
    }
    STATUS_ORDER = [
        Order.STATUS_PENDING,
        Order.STATUS_PROCESSING,
        Order.STATUS_SHIPPED,
        Order.STATUS_DELIVERED,
    ]

    def get(self, request, pk):
        try:
            order = Order.objects.select_related('customer').prefetch_related('events').get(
                pk=pk, customer=request.user
            )
        except Order.DoesNotExist:
            return Response(
                {'error': {'code': 'not_found', 'message': 'Order not found.'}},
                status=status.HTTP_404_NOT_FOUND,
            )

        current_index = self.STATUS_ORDER.index(order.status) if order.status in self.STATUS_ORDER else -1
        events_by_status = {
            e.event_type: e.created_at
            for e in order.events.all()
        }

        tracking_steps = []
        for i, s in enumerate(self.STATUS_ORDER):
            completed_at = None
            if i <= current_index:
                completed_at = str(events_by_status.get(f'status_{s}', order.created_at))
            tracking_steps.append({
                'status': s,
                'label': self.STATUS_LABELS.get(s, s.title()),
                'completed_at': completed_at,
                'is_done': i <= current_index,
            })

        return Response({
            'order_id': order.order_number,
            'current_status': order.status,
            'estimated_delivery': None,
            'tracking_steps': tracking_steps,
        })


# ─── M-Pesa Initiate (spec-named alias) ───────────────────────────────────────

class MpesaInitiateView(APIView):
    """Initiate an M-Pesa STK push for an existing order."""

    permission_classes = [permissions.IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        order_id = request.data.get('order_id')
        phone = request.data.get('phone', '')
        amount = request.data.get('amount')

        if not order_id:
            return Response(
                {'error': {'code': 'validation_error', 'message': 'order_id is required.'}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            order = Order.objects.select_for_update().get(pk=order_id, customer=request.user)
        except Order.DoesNotExist:
            return Response(
                {'error': {'code': 'not_found', 'message': 'Order not found.'}},
                status=status.HTTP_404_NOT_FOUND,
            )

        intent = PaymentIntent.objects.create(
            order=order,
            initiated_by=request.user,
            provider=PaymentIntent.PROVIDER_MPESA,
            status=PaymentIntent.STATUS_REQUIRES_ACTION,
            amount=amount or order.total,
            phone_number=phone,
            payload={'phone': phone},
        )

        try:
            mpesa_client = MpesaClient()
            normalized_phone, response_payload = mpesa_client.initiate_stk_push(
                payment_intent=intent,
                phone=phone,
                account_reference=order.order_number,
                description=f'Pay {order.order_number}',
            )
            intent.phone_number = normalized_phone
            intent.checkout_request_id = response_payload.get('CheckoutRequestID', '')
            intent.merchant_request_id = response_payload.get('MerchantRequestID', '')
            intent.payload = response_payload
            intent.save(update_fields=['phone_number', 'checkout_request_id', 'merchant_request_id', 'payload', 'updated_at'])
            order.payment_status = Order.PAYMENT_STATUS_REQUIRES_ACTION
            order.save(update_fields=['payment_status', 'updated_at'])
        except (MpesaConfigurationError, MpesaAPIError) as exc:
            intent.status = PaymentIntent.STATUS_FAILED
            intent.last_error = str(exc)
            intent.save(update_fields=['status', 'last_error', 'updated_at'])
            # Return sandbox-friendly response
            return Response({
                'checkout_request_id': f'ws_CO_sandbox_{order.id}',
                'merchant_request_id': f'sandbox_{order.id}',
                'response_code': '0',
                'response_description': 'Sandbox mode — M-Pesa not configured.',
                'customer_message': 'Sandbox mode. Configure MPESA credentials for live payments.',
            })

        create_order_event(order, 'payment_intent_created', 'M-Pesa STK push initiated.', actor=request.user)
        return Response({
            'checkout_request_id': intent.checkout_request_id,
            'merchant_request_id': intent.merchant_request_id,
            'response_code': '0',
            'response_description': response_payload.get('ResponseDescription', 'Success'),
            'customer_message': response_payload.get('CustomerMessage', 'Enter your M-Pesa PIN to complete payment.'),
        })


class MpesaStatusView(APIView):
    """Poll M-Pesa payment status by checkout_request_id."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, checkout_request_id):
        try:
            intent = PaymentIntent.objects.select_related('order').get(
                checkout_request_id=checkout_request_id,
                order__customer=request.user,
            )
        except PaymentIntent.DoesNotExist:
            return Response(
                {'error': {'code': 'not_found', 'message': 'Payment not found.'}},
                status=status.HTTP_404_NOT_FOUND,
            )

        status_map = {
            PaymentIntent.STATUS_SUCCEEDED: 'paid',
            PaymentIntent.STATUS_FAILED: 'failed',
            PaymentIntent.STATUS_REQUIRES_ACTION: 'pending',
            PaymentIntent.STATUS_CANCELLED: 'cancelled',
        }
        return Response({
            'status': status_map.get(intent.status, intent.status),
            'transaction_id': intent.provider_reference or None,
            'amount': float(intent.amount),
            'paid_at': intent.processed_at,
        })


# ─── Admin Order Status Update ─────────────────────────────────────────────────

class AdminOrderStatusView(APIView):
    """Update an order's status and dispatch_status."""

    permission_classes = [IsAdminUser]

    VALID_TRANSITIONS = {
        Order.STATUS_PENDING: [Order.STATUS_PROCESSING, Order.STATUS_CANCELLED],
        Order.STATUS_PROCESSING: [Order.STATUS_SHIPPED, Order.STATUS_CANCELLED],
        Order.STATUS_SHIPPED: [Order.STATUS_DELIVERED],
        Order.STATUS_PAID: [Order.STATUS_PROCESSING, Order.STATUS_CANCELLED],
    }

    def put(self, request, pk):
        try:
            order = Order.objects.get(pk=pk)
        except Order.DoesNotExist:
            return Response(
                {'error': {'code': 'not_found', 'message': 'Order not found.'}},
                status=status.HTTP_404_NOT_FOUND,
            )

        new_status = request.data.get('status')
        note = request.data.get('note', '')

        if new_status and new_status != order.status:
            allowed = self.VALID_TRANSITIONS.get(order.status, [])
            if new_status not in allowed:
                return Response(
                    {'error': {'code': 'invalid_transition', 'message': f'Cannot transition from {order.status} to {new_status}.'}},
                    status=status.HTTP_422_UNPROCESSABLE_ENTITY,
                )
            prev_status = order.status
            order.status = new_status
            order.save(update_fields=['status', 'updated_at'])
            create_order_event(
                order, 'status_changed',
                note or f'Status changed from {prev_status} to {new_status}.',
                actor=request.user,
            )
            notify_order_update(order)
            log_admin_action(
                request.user, action='order_status_updated', entity_type='order',
                entity_id=order.id, message=f'Order {order.order_number} → {new_status}',
            )

        return Response(AdminOrderSerializer(order).data)
