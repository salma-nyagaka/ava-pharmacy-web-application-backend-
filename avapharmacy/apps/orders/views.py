from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from django.conf import settings
from django.db import transaction
from django.db.models import Sum, Count, Q
from django.utils import timezone

from .models import Cart, CartItem, Order, OrderItem, OrderNote
from .serializers import (
    CartSerializer, CartItemSerializer, OrderSerializer, CheckoutSerializer,
    AdminOrderSerializer, AdminOrderUpdateSerializer, OrderNoteCreateSerializer
)
from apps.accounts.permissions import IsAdminUser
from apps.products.models import Product


def get_or_create_cart(user):
    cart, _ = Cart.objects.get_or_create(user=user)
    return cart


# ─── Cart ─────────────────────────────────────────────────────────────────────

class CartView(generics.RetrieveAPIView):
    serializer_class = CartSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return get_or_create_cart(self.request.user)


class CartItemCreateView(generics.CreateAPIView):
    serializer_class = CartItemSerializer
    permission_classes = [permissions.IsAuthenticated]

    def create(self, request, *args, **kwargs):
        cart = get_or_create_cart(request.user)
        product_id = request.data.get('product_id')
        quantity = request.data.get('quantity', 1)
        prescription_id = request.data.get('prescription_id', None)

        # Validate quantity
        try:
            quantity = int(quantity)
            if quantity < 1:
                return Response({'quantity': 'Must be at least 1.'}, status=status.HTTP_400_BAD_REQUEST)
        except (TypeError, ValueError):
            return Response({'quantity': 'Invalid quantity.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            product = Product.objects.get(pk=product_id, is_active=True)
        except Product.DoesNotExist:
            return Response({'detail': 'Product not found.'}, status=status.HTTP_404_NOT_FOUND)

        if product.stock_source == Product.STOCK_OUT or product.stock_quantity == 0:
            return Response({'detail': 'Product is out of stock.'}, status=status.HTTP_400_BAD_REQUEST)

        if product.requires_prescription and not prescription_id:
            return Response(
                {'detail': 'This product requires a prescription reference.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if quantity > product.stock_quantity:
            return Response(
                {'detail': f'Only {product.stock_quantity} unit(s) available.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        item, created = CartItem.objects.get_or_create(
            cart=cart,
            product=product,
            prescription_id=prescription_id,
            defaults={'quantity': quantity}
        )
        if not created:
            new_qty = item.quantity + quantity
            if new_qty > product.stock_quantity:
                return Response(
                    {'detail': f'Only {product.stock_quantity} unit(s) available.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            item.quantity = new_qty
            item.save()

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

        if quantity > item.product.stock_quantity:
            return Response(
                {'detail': f'Only {item.product.stock_quantity} unit(s) available.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        item.quantity = quantity
        item.save()
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
        return Response({'detail': 'Cart cleared.'})


# ─── Checkout ─────────────────────────────────────────────────────────────────

class CheckoutView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        serializer = CheckoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        cart = get_or_create_cart(request.user)
        items = list(cart.items.select_related('product').all())

        if not items:
            return Response({'detail': 'Cart is empty.'}, status=status.HTTP_400_BAD_REQUEST)

        # ── Stock validation ─────────────────────────────────────────────────
        out_of_stock = []
        insufficient = []
        for item in items:
            product = item.product
            if not product.is_active:
                out_of_stock.append(product.name)
            elif product.stock_source == Product.STOCK_OUT or product.stock_quantity == 0:
                out_of_stock.append(product.name)
            elif item.quantity > product.stock_quantity:
                insufficient.append(
                    f"{product.name} (requested {item.quantity}, available {product.stock_quantity})"
                )

        if out_of_stock:
            return Response(
                {'detail': f'Out of stock: {", ".join(out_of_stock)}. Please update your cart.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        if insufficient:
            return Response(
                {'detail': f'Insufficient stock: {", ".join(insufficient)}'},
                status=status.HTTP_400_BAD_REQUEST
            )

        free_threshold = getattr(settings, 'FREE_SHIPPING_THRESHOLD', 3000)
        shipping_fee_cfg = getattr(settings, 'SHIPPING_FEE', 300)

        subtotal = sum(item.subtotal for item in items)
        shipping_fee = 0 if subtotal >= free_threshold else shipping_fee_cfg
        total = subtotal + shipping_fee

        order = Order.objects.create(
            customer=request.user,
            payment_method=data['payment_method'],
            shipping_first_name=data['first_name'],
            shipping_last_name=data['last_name'],
            shipping_email=data['email'],
            shipping_phone=data['phone'],
            shipping_street=data['street'],
            shipping_city=data['city'],
            shipping_county=data['county'],
            subtotal=subtotal,
            shipping_fee=shipping_fee,
            total=total,
        )

        for item in items:
            OrderItem.objects.create(
                order=order,
                product=item.product,
                product_name=item.product.name,
                product_sku=item.product.sku,
                quantity=item.quantity,
                unit_price=item.product.price,
            )
            # Deduct stock
            Product.objects.filter(pk=item.product.pk).update(
                stock_quantity=item.product.stock_quantity - item.quantity
            )

        cart.items.all().delete()

        # Notify customer of order confirmation
        try:
            from apps.notifications.utils import create_notification
            create_notification(
                recipient=request.user,
                notification_type='order_status',
                title=f"Order {order.order_number} Placed",
                message=f"Your order of KSh {order.total} has been received.",
                data={'url': f'/orders/{order.id}', 'reference': order.order_number},
            )
        except Exception:
            pass

        return Response(OrderSerializer(order).data, status=status.HTTP_201_CREATED)


# ─── Customer Orders ──────────────────────────────────────────────────────────

class OrderListView(generics.ListAPIView):
    serializer_class = OrderSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Order.objects.filter(customer=self.request.user).prefetch_related('items', 'notes')


class OrderDetailView(generics.RetrieveAPIView):
    serializer_class = OrderSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Order.objects.filter(customer=self.request.user).prefetch_related('items', 'notes')


class OrderCancelView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        try:
            order = Order.objects.get(pk=pk, customer=request.user)
        except Order.DoesNotExist:
            return Response({'detail': 'Order not found.'}, status=status.HTTP_404_NOT_FOUND)

        if order.status not in [Order.STATUS_PENDING, Order.STATUS_PROCESSING]:
            return Response(
                {'detail': f'Cannot cancel an order with status "{order.status}".'},
                status=status.HTTP_400_BAD_REQUEST
            )

        order.status = Order.STATUS_CANCELLED
        order.save(update_fields=['status', 'updated_at'])

        try:
            from apps.notifications.utils import notify_order_status
            notify_order_status(order)
        except Exception:
            pass

        return Response({'detail': 'Order cancelled successfully.'})


# ─── Admin Orders ─────────────────────────────────────────────────────────────

class AdminOrderListView(generics.ListAPIView):
    permission_classes = [IsAdminUser]
    serializer_class = AdminOrderSerializer
    filterset_fields = ['status', 'payment_status', 'payment_method']
    search_fields = ['order_number', 'shipping_email', 'customer__email']
    ordering_fields = ['created_at', 'total']
    ordering = ['-created_at']

    def get_queryset(self):
        return Order.objects.all().select_related('customer').prefetch_related('items', 'notes')


class AdminOrderDetailView(generics.RetrieveUpdateAPIView):
    permission_classes = [IsAdminUser]
    queryset = Order.objects.all().select_related('customer').prefetch_related('items', 'notes')

    def get_serializer_class(self):
        if self.request.method in ['PUT', 'PATCH']:
            return AdminOrderUpdateSerializer
        return AdminOrderSerializer

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', True)
        instance = self.get_object()
        prev_status = instance.status
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        order = serializer.save()

        # Notify customer when status changes
        if order.status != prev_status and order.customer:
            try:
                from apps.notifications.utils import notify_order_status
                notify_order_status(order)
            except Exception:
                pass

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
        return Response(AdminOrderSerializer(order).data)


# ─── Reports ──────────────────────────────────────────────────────────────────

class AdminReportsView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        from apps.accounts.models import User

        today = timezone.now().date()
        month_start = today.replace(day=1)

        revenue = Order.objects.filter(payment_status='paid').aggregate(
            revenue_total=Sum('total'),
            revenue_monthly=Sum('total', filter=Q(created_at__date__gte=month_start))
        )

        return Response({
            'total_orders': Order.objects.count(),
            'total_revenue': float(revenue['revenue_total'] or 0),
            'monthly_revenue': float(revenue['revenue_monthly'] or 0),
            'total_customers': User.objects.filter(role='customer').count(),
            'pending_orders': Order.objects.filter(status='pending').count(),
            'today_orders': Order.objects.filter(created_at__date=today).count(),
            'orders_by_status': list(Order.objects.values('status').annotate(count=Count('id'))),
            'orders_by_payment': list(Order.objects.values('payment_method').annotate(count=Count('id'))),
        })
