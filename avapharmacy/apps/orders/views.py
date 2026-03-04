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
from apps.products.models import Product

from .models import Cart, CartItem, Coupon, Order, OrderEvent, OrderItem, OrderNote, PaymentIntent, ReturnRequest
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


def validate_cart_items(items):
    errors = []
    for item in items:
        error = _product_availability_error(item.product, item.quantity)
        if error:
            errors.append(error)
        if item.product.requires_prescription and not item.prescription_id:
            errors.append(f'{item.product.name} requires a prescription reference.')
    return errors


def build_order_totals(cart):
    subtotal = cart.total
    discount_total = cart.discount_total
    shipping_fee = cart.shipping_fee
    total = cart.grand_total
    return subtotal, discount_total, shipping_fee, total


def snapshot_cart_to_order(order, cart_items):
    order.items.all().delete()
    for item in cart_items:
        OrderItem.objects.create(
            order=order,
            product=item.product,
            product_name=item.product.name,
            product_sku=item.product.sku,
            quantity=item.quantity,
            unit_price=item.product.price,
            prescription_id=item.prescription_id,
        )


def notify_order_update(order, title=None, message=None):
    if not order.customer:
        return
    try:
        from apps.notifications.utils import create_notification

        create_notification(
            recipient=order.customer,
            notification_type='order_status',
            title=title or f'Order {order.order_number} Updated',
            message=message or f'Your order is now {order.status}.',
            data={'url': f'/orders/{order.id}', 'reference': order.order_number},
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

        if product.requires_prescription and not prescription_id:
            return Response(
                {'detail': 'This product requires a prescription reference.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        existing_item = CartItem.objects.filter(
            cart=cart,
            product=product,
            prescription_id=prescription_id,
        ).first()
        requested_total = quantity + (existing_item.quantity if existing_item else 0)
        error = _product_availability_error(product, requested_total)
        if error:
            return Response({'detail': error}, status=status.HTTP_400_BAD_REQUEST)

        if existing_item:
            existing_item.quantity = requested_total
            existing_item.save(update_fields=['quantity'])
        else:
            CartItem.objects.create(
                cart=cart,
                product=product,
                quantity=quantity,
                prescription_id=prescription_id,
            )

        return Response(CartSerializer(cart).data, status=status.HTTP_201_CREATED)


class CartItemUpdateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def patch(self, request, pk):
        cart = get_or_create_cart(request.user)
        try:
            item = CartItem.objects.select_related('product').get(pk=pk, cart=cart)
        except CartItem.DoesNotExist:
            return Response({'detail': 'Item not found.'}, status=status.HTTP_404_NOT_FOUND)

        quantity = request.data.get('quantity')
        try:
            quantity = int(quantity)
            if quantity < 1:
                return Response({'quantity': 'Must be at least 1.'}, status=status.HTTP_400_BAD_REQUEST)
        except (TypeError, ValueError):
            return Response({'quantity': 'Invalid quantity.'}, status=status.HTTP_400_BAD_REQUEST)

        error = _product_availability_error(item.product, quantity)
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
            cart.items.select_related('product', 'product__brand', 'product__category')
            .order_by('id')
        )
        if not items:
            return Response({'detail': 'Cart is empty.'}, status=status.HTTP_400_BAD_REQUEST)

        products = {
            product.id: product
            for product in Product.objects.select_for_update().filter(id__in=[item.product_id for item in items])
        }
        for item in items:
            item.product = products[item.product_id]

        errors = validate_cart_items(items)
        if errors:
            return Response({'detail': errors}, status=status.HTTP_400_BAD_REQUEST)

        subtotal, discount_total, shipping_fee, total = build_order_totals(cart)
        order = Order.objects.create(
            customer=request.user,
            coupon=cart.coupon if cart.coupon and cart.coupon.is_available(request.user) else None,
            coupon_code=cart.coupon.code if cart.coupon else '',
            payment_method=data['payment_method'],
            payment_status=Order.PAYMENT_STATUS_PENDING,
            delivery_method=data.get('delivery_method', 'standard'),
            delivery_notes=data.get('delivery_notes', ''),
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
            metadata={'item_count': len(items), 'payment_method': order.payment_method},
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
            client_secret = f'stk_{timezone.now().strftime("%Y%m%d%H%M%S")}'
        elif provider == PaymentIntent.PROVIDER_CARD:
            payload = {'return_url': data.get('return_url', '')}
            client_secret = f'card_{timezone.now().strftime("%Y%m%d%H%M%S")}'

        intent = PaymentIntent.objects.create(
            order=order,
            initiated_by=request.user,
            provider=provider,
            status=status_value,
            amount=order.total,
            client_secret=client_secret,
            payload=payload,
        )

        if provider == PaymentIntent.PROVIDER_MANUAL:
            order.payment_status = Order.PAYMENT_STATUS_PAID
            order.payment_reference = intent.reference
            order.save(update_fields=['payment_status', 'payment_reference', 'updated_at'])
            create_order_event(order, 'payment_captured', 'Manual payment marked as paid.', actor=request.user)
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
        locked_products = {
            product.id: product
            for product in Product.objects.select_for_update().filter(id__in=product_ids)
        }

        errors = []
        for item in order.items.all():
            product = locked_products.get(item.product_id)
            if not product:
                errors.append(f'{item.product_name} is no longer available.')
                continue
            error = _product_availability_error(product, item.quantity)
            if error:
                errors.append(error)
        if errors:
            return Response({'detail': errors}, status=status.HTTP_400_BAD_REQUEST)

        for item in order.items.all():
            product = locked_products.get(item.product_id)
            if not product:
                continue
            product.stock_quantity = max(0, product.stock_quantity - item.quantity)
            product.save()

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
            'items', 'notes', 'events', 'payment_intents', 'return_requests'
        )


class OrderDetailView(generics.RetrieveAPIView):
    serializer_class = OrderSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Order.objects.filter(customer=self.request.user).prefetch_related(
            'items', 'notes', 'events', 'payment_intents', 'return_requests'
        )


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
            for item in order.items.select_related('product').all():
                if item.product:
                    item.product.stock_quantity += item.quantity
                    item.product.save()

        order.status = Order.STATUS_CANCELLED
        order.save(update_fields=['status', 'updated_at'])
        create_order_event(order, 'order_cancelled', 'Order cancelled by customer.', actor=request.user)
        notify_order_update(order, title=f'Order {order.order_number} cancelled', message='Your order was cancelled.')
        return Response({'detail': 'Order cancelled successfully.'})


class ReturnRequestListCreateView(generics.ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return ReturnRequest.objects.filter(customer=self.request.user).select_related('order')

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

        return_request = serializer.save(order=order, customer=self.request.user)
        create_order_event(order, 'return_requested', 'Customer requested a return.', actor=self.request.user)
        return return_request


class AdminOrderListView(generics.ListAPIView):
    permission_classes = [IsAdminUser]
    serializer_class = AdminOrderSerializer
    filterset_fields = ['status', 'payment_status', 'payment_method', 'delivery_method']
    search_fields = ['order_number', 'shipping_email', 'customer__email']
    ordering_fields = ['created_at', 'total']
    ordering = ['-created_at']

    def get_queryset(self):
        return Order.objects.all().select_related('customer', 'coupon').prefetch_related(
            'items', 'notes', 'events', 'payment_intents', 'return_requests'
        )


class AdminOrderDetailView(generics.RetrieveUpdateAPIView):
    permission_classes = [IsAdminUser]
    queryset = Order.objects.all().select_related('customer', 'coupon').prefetch_related(
        'items', 'notes', 'events', 'payment_intents', 'return_requests'
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
            for item in order.items.select_related('product').all():
                if item.product:
                    item.product.stock_quantity += item.quantity
                    item.product.save()

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
            'low_stock_products': Product.objects.filter(
                is_active=True,
                stock_quantity__gt=0,
                stock_quantity__lte=models.F('low_stock_threshold'),
            ).count(),
        })
