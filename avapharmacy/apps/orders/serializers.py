from rest_framework import serializers

from .models import Cart, CartItem, Coupon, Order, OrderEvent, OrderItem, OrderNote, PaymentIntent, ReturnRequest, ShippingMethod
from apps.products.serializers import ProductListSerializer, ProductVariantSerializer


class CouponSerializer(serializers.ModelSerializer):
    class Meta:
        model = Coupon
        fields = (
            'id', 'code', 'description', 'discount_type', 'value', 'minimum_subtotal',
            'maximum_discount', 'usage_limit', 'per_user_limit', 'is_active',
            'starts_at', 'ends_at'
        )


class CartItemSerializer(serializers.ModelSerializer):
    product = ProductListSerializer(read_only=True)
    product_id = serializers.IntegerField(write_only=True)
    product_variant = ProductVariantSerializer(read_only=True)
    product_variant_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    subtotal = serializers.ReadOnlyField()

    class Meta:
        model = CartItem
        fields = (
            'id', 'product', 'product_id', 'product_variant', 'product_variant_id', 'quantity', 'prescription_id',
            'subtotal', 'added_at'
        )
        read_only_fields = ('id', 'added_at')


class CartSerializer(serializers.ModelSerializer):
    items = CartItemSerializer(many=True, read_only=True)
    subtotal = serializers.ReadOnlyField(source='total')
    item_count = serializers.ReadOnlyField()
    discount_total = serializers.ReadOnlyField()
    shipping_fee = serializers.ReadOnlyField()
    grand_total = serializers.ReadOnlyField()
    coupon = CouponSerializer(read_only=True)

    class Meta:
        model = Cart
        fields = (
            'id', 'items', 'coupon', 'subtotal', 'discount_total',
            'shipping_fee', 'grand_total', 'item_count', 'updated_at'
        )


class OrderItemSerializer(serializers.ModelSerializer):
    subtotal = serializers.ReadOnlyField()
    product_variant = ProductVariantSerializer(read_only=True)

    class Meta:
        model = OrderItem
        fields = (
            'id', 'product_name', 'product_sku', 'product_variant', 'variant_name', 'variant_sku',
            'quantity', 'unit_price', 'discount_total', 'prescription_id', 'subtotal'
        )


class OrderNoteSerializer(serializers.ModelSerializer):
    created_by_name = serializers.ReadOnlyField(source='created_by.full_name')

    class Meta:
        model = OrderNote
        fields = ('id', 'content', 'created_by_name', 'created_at')


class OrderEventSerializer(serializers.ModelSerializer):
    actor_name = serializers.ReadOnlyField(source='actor.full_name')

    class Meta:
        model = OrderEvent
        fields = ('id', 'event_type', 'message', 'metadata', 'actor_name', 'created_at')


class PaymentIntentSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentIntent
        fields = (
            'id', 'provider', 'status', 'reference', 'provider_reference',
            'external_reference', 'phone_number', 'merchant_request_id', 'checkout_request_id',
            'amount', 'currency', 'client_secret', 'payload', 'callback_payload', 'last_error',
            'processed_at', 'created_at', 'updated_at'
        )


class ReturnRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReturnRequest
        fields = (
            'id', 'order', 'order_item', 'request_type', 'reason', 'requested_refund_amount',
            'status', 'resolution_notes', 'created_at', 'updated_at'
        )
        read_only_fields = ('id', 'status', 'resolution_notes', 'created_at', 'updated_at')


class ShippingMethodSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShippingMethod
        fields = (
            'id', 'code', 'name', 'description', 'fee', 'free_shipping_threshold',
            'estimated_delivery_window', 'is_active', 'sort_order'
        )


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    notes = OrderNoteSerializer(many=True, read_only=True)
    events = OrderEventSerializer(many=True, read_only=True)
    payment_intents = PaymentIntentSerializer(many=True, read_only=True)
    return_requests = ReturnRequestSerializer(many=True, read_only=True)
    shipping_address = serializers.ReadOnlyField()
    coupon = CouponSerializer(read_only=True)
    shipping_method = ShippingMethodSerializer(read_only=True)

    class Meta:
        model = Order
        fields = (
            'id', 'order_number', 'status', 'payment_method', 'payment_status',
            'payment_reference', 'coupon', 'coupon_code', 'delivery_method', 'delivery_notes', 'shipping_method',
            'shipping_first_name', 'shipping_last_name', 'shipping_email',
            'shipping_phone', 'shipping_street', 'shipping_city', 'shipping_county',
            'shipping_address', 'subtotal', 'discount_total', 'shipping_fee', 'total',
            'inventory_committed',
            'items', 'notes', 'events', 'payment_intents', 'return_requests',
            'placed_at', 'created_at', 'updated_at'
        )


class CheckoutSerializer(serializers.Serializer):
    first_name = serializers.CharField(max_length=100)
    last_name = serializers.CharField(max_length=100)
    email = serializers.EmailField()
    phone = serializers.CharField(max_length=20)
    street = serializers.CharField(max_length=200)
    city = serializers.CharField(max_length=100)
    county = serializers.CharField(max_length=100)
    payment_method = serializers.ChoiceField(choices=Order.PAYMENT_CHOICES)
    delivery_method = serializers.CharField(max_length=30, default='standard')
    shipping_method_id = serializers.IntegerField(required=False, allow_null=True)
    delivery_notes = serializers.CharField(required=False, allow_blank=True)


class CouponApplySerializer(serializers.Serializer):
    code = serializers.CharField(max_length=40)


class AdminOrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    notes = OrderNoteSerializer(many=True, read_only=True)
    events = OrderEventSerializer(many=True, read_only=True)
    payment_intents = PaymentIntentSerializer(many=True, read_only=True)
    return_requests = ReturnRequestSerializer(many=True, read_only=True)
    customer_name = serializers.ReadOnlyField(source='customer.full_name')
    customer_email = serializers.ReadOnlyField(source='customer.email')
    customer_phone = serializers.ReadOnlyField(source='customer.phone')
    shipping_address = serializers.ReadOnlyField()
    coupon = CouponSerializer(read_only=True)
    shipping_method = ShippingMethodSerializer(read_only=True)

    class Meta:
        model = Order
        fields = (
            'id', 'order_number', 'customer', 'customer_name', 'customer_email',
            'customer_phone', 'status', 'payment_method', 'payment_status',
            'payment_reference', 'coupon', 'coupon_code', 'delivery_method',
            'delivery_notes', 'shipping_method', 'shipping_first_name', 'shipping_last_name',
            'shipping_email', 'shipping_phone', 'shipping_street', 'shipping_city',
            'shipping_county', 'shipping_address', 'subtotal', 'discount_total',
            'shipping_fee', 'total', 'inventory_committed', 'items', 'notes', 'events', 'payment_intents',
            'return_requests', 'placed_at', 'created_at', 'updated_at'
        )
        read_only_fields = (
            'id', 'order_number', 'customer', 'items', 'subtotal', 'discount_total',
            'shipping_fee', 'total', 'created_at'
        )


class AdminOrderUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Order
        fields = ('status', 'payment_status', 'payment_reference', 'delivery_method', 'delivery_notes', 'shipping_method')


class OrderNoteCreateSerializer(serializers.Serializer):
    content = serializers.CharField()


class PaymentIntentCreateSerializer(serializers.Serializer):
    order_id = serializers.IntegerField()
    provider = serializers.ChoiceField(choices=PaymentIntent.PROVIDER_CHOICES)
    phone = serializers.CharField(max_length=20, required=False, allow_blank=True)
    return_url = serializers.URLField(required=False, allow_blank=True)


class PaymentWebhookSerializer(serializers.Serializer):
    reference = serializers.CharField(max_length=64)
    status = serializers.ChoiceField(choices=PaymentIntent.STATUS_CHOICES)
    provider_reference = serializers.CharField(max_length=120, required=False, allow_blank=True)
    message = serializers.CharField(max_length=255, required=False, allow_blank=True)
    payload = serializers.JSONField(required=False)


class ReturnRequestCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReturnRequest
        fields = ('order_item', 'request_type', 'reason', 'requested_refund_amount')


class ReturnRequestAdminUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReturnRequest
        fields = ('status', 'resolution_notes', 'requested_refund_amount')
