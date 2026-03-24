from rest_framework import serializers

from .models import Cart, CartItem, Coupon, Order, OrderEvent, OrderItem, OrderNote, OutboundOrderPush, PaymentIntent, ReturnRequest, ShippingMethod
from .payment_helpers import (
    build_paybill_account_reference,
    get_paybill_account_label,
    get_paybill_instructions,
    get_paybill_number,
    resolve_order_number_from_paybill_reference,
)
from apps.accounts.models import Address
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
    prescription_id = serializers.CharField(source='prescription_reference', required=False, allow_null=True, allow_blank=True)
    prescription = serializers.IntegerField(source='prescription_id', read_only=True)
    prescription_item = serializers.IntegerField(source='prescription_item_id', read_only=True)

    class Meta:
        model = CartItem
        fields = (
            'id', 'product', 'product_id', 'product_variant', 'product_variant_id', 'quantity', 'prescription_id',
            'prescription', 'prescription_item',
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
    prescription_id = serializers.CharField(source='prescription_reference', read_only=True)
    prescription = serializers.IntegerField(source='prescription_id', read_only=True)
    prescription_item = serializers.IntegerField(source='prescription_item_id', read_only=True)

    class Meta:
        model = OrderItem
        fields = (
            'id', 'product_name', 'product_sku', 'product_variant', 'variant_name', 'variant_sku',
            'quantity', 'unit_price', 'discount_total', 'prescription_id', 'prescription', 'prescription_item', 'subtotal'
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
    next_action_url = serializers.SerializerMethodField()
    error_logs = serializers.SerializerMethodField()
    paybill_number = serializers.SerializerMethodField()
    paybill_account_reference = serializers.SerializerMethodField()
    paybill_account_label = serializers.SerializerMethodField()
    paybill_instructions = serializers.SerializerMethodField()
    submitted_reference = serializers.SerializerMethodField()

    def get_next_action_url(self, obj):
        if obj.provider == PaymentIntent.PROVIDER_CARD:
            return obj.client_secret or obj.payload.get('data', {}).get('link', '')
        return ''

    def get_error_logs(self, obj):
        return list((obj.payload or {}).get('error_logs') or [])

    def get_paybill_number(self, obj):
        return get_paybill_number() if obj.provider == PaymentIntent.PROVIDER_PAYBILL else ''

    def get_paybill_account_reference(self, obj):
        if obj.provider != PaymentIntent.PROVIDER_PAYBILL:
            return ''
        return obj.external_reference or build_paybill_account_reference(obj.order)

    def get_paybill_account_label(self, obj):
        return get_paybill_account_label() if obj.provider == PaymentIntent.PROVIDER_PAYBILL else ''

    def get_paybill_instructions(self, obj):
        return get_paybill_instructions() if obj.provider == PaymentIntent.PROVIDER_PAYBILL else ''

    def get_submitted_reference(self, obj):
        return (obj.payload or {}).get('submitted_reference', '') or obj.provider_reference

    class Meta:
        model = PaymentIntent
        fields = (
            'id', 'provider', 'status', 'reference', 'provider_reference',
            'external_reference', 'phone_number', 'merchant_request_id', 'checkout_request_id',
            'amount', 'currency', 'client_secret', 'next_action_url', 'payload', 'callback_payload', 'last_error',
            'error_logs', 'paybill_number', 'paybill_account_reference', 'paybill_account_label',
            'paybill_instructions', 'submitted_reference',
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
    paybill_number = serializers.SerializerMethodField()
    paybill_account_reference = serializers.SerializerMethodField()
    paybill_account_label = serializers.SerializerMethodField()
    paybill_instructions = serializers.SerializerMethodField()
    coupon = CouponSerializer(read_only=True)
    shipping_method = ShippingMethodSerializer(read_only=True)

    def get_paybill_number(self, obj):
        return get_paybill_number()

    def get_paybill_account_reference(self, obj):
        return build_paybill_account_reference(obj)

    def get_paybill_account_label(self, obj):
        return get_paybill_account_label()

    def get_paybill_instructions(self, obj):
        return get_paybill_instructions()

    class Meta:
        model = Order
        fields = (
            'id', 'order_number', 'status', 'payment_method', 'payment_status',
            'payment_reference', 'flutterwave_tx_ref', 'flutterwave_tx_id',
            'coupon', 'coupon_code', 'delivery_method', 'delivery_notes', 'shipping_method',
            'shipping_first_name', 'shipping_last_name', 'shipping_email',
            'shipping_phone', 'shipping_street', 'shipping_city', 'shipping_county',
            'shipping_address', 'paybill_number', 'paybill_account_reference', 'paybill_account_label',
            'paybill_instructions', 'subtotal', 'discount_total', 'shipping_fee', 'total',
            'inventory_committed',
            'items', 'notes', 'events', 'payment_intents', 'return_requests',
            'placed_at', 'created_at', 'updated_at'
        )


class CheckoutSerializer(serializers.Serializer):
    first_name = serializers.CharField(max_length=100)
    last_name = serializers.CharField(max_length=100)
    email = serializers.EmailField()
    phone = serializers.CharField(max_length=20)
    street = serializers.CharField(max_length=200, required=False, allow_blank=True, default='')
    city = serializers.CharField(max_length=100, required=False, allow_blank=True, default='')
    county = serializers.CharField(max_length=100, required=False, allow_blank=True, default='')
    address_id = serializers.IntegerField(required=False, allow_null=True)
    save_address = serializers.BooleanField(required=False, default=False)
    address_label = serializers.CharField(max_length=50, required=False, allow_blank=True, default='')
    set_default_address = serializers.BooleanField(required=False, default=False)
    payment_method = serializers.ChoiceField(choices=Order.PAYMENT_CHOICES)
    delivery_method = serializers.CharField(max_length=30, default='standard')
    shipping_method_id = serializers.IntegerField(required=False, allow_null=True)
    delivery_notes = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs):
        request = self.context.get('request')
        user = getattr(request, 'user', None)
        address = None
        address_id = attrs.get('address_id')

        if address_id is not None:
            if not getattr(user, 'is_authenticated', False):
                raise serializers.ValidationError({'address_id': 'Authentication is required to use a saved address.'})
            try:
                address = Address.objects.get(pk=address_id, user=user)
            except Address.DoesNotExist:
                raise serializers.ValidationError({'address_id': 'Saved address not found.'})
            attrs['street'] = address.street
            attrs['city'] = address.city
            attrs['county'] = address.county

        if not attrs.get('street', '').strip() or not attrs.get('city', '').strip() or not attrs.get('county', '').strip():
            raise serializers.ValidationError({'address': 'Street, city, and county are required.'})

        attrs['saved_address'] = address
        attrs['street'] = attrs['street'].strip()
        attrs['city'] = attrs['city'].strip()
        attrs['county'] = attrs['county'].strip()
        attrs['address_label'] = attrs.get('address_label', '').strip()
        return attrs


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
    paybill_number = serializers.SerializerMethodField()
    paybill_account_reference = serializers.SerializerMethodField()
    paybill_account_label = serializers.SerializerMethodField()
    paybill_instructions = serializers.SerializerMethodField()
    coupon = CouponSerializer(read_only=True)
    shipping_method = ShippingMethodSerializer(read_only=True)

    def get_paybill_number(self, obj):
        return get_paybill_number()

    def get_paybill_account_reference(self, obj):
        return build_paybill_account_reference(obj)

    def get_paybill_account_label(self, obj):
        return get_paybill_account_label()

    def get_paybill_instructions(self, obj):
        return get_paybill_instructions()

    class Meta:
        model = Order
        fields = (
            'id', 'order_number', 'customer', 'customer_name', 'customer_email',
            'customer_phone', 'status', 'payment_method', 'payment_status',
            'payment_reference', 'flutterwave_tx_ref', 'flutterwave_tx_id',
            'coupon', 'coupon_code', 'delivery_method',
            'delivery_notes', 'shipping_method', 'shipping_first_name', 'shipping_last_name',
            'shipping_email', 'shipping_phone', 'shipping_street', 'shipping_city',
            'shipping_county', 'shipping_address', 'paybill_number', 'paybill_account_reference',
            'paybill_account_label', 'paybill_instructions', 'subtotal', 'discount_total',
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
    reference_code = serializers.CharField(max_length=120, required=False, allow_blank=True)
    metadata = serializers.JSONField(required=False)


class FlutterwaveInitiateSerializer(serializers.Serializer):
    order_id = serializers.IntegerField()
    return_url = serializers.URLField(required=False, allow_blank=True)


class FlutterwaveStatusSerializer(serializers.Serializer):
    transaction_id = serializers.CharField(max_length=120, required=False, allow_blank=True)


class AdminPaybillReconcileSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=[
        (PaymentIntent.STATUS_SUCCEEDED, 'Succeeded'),
        (PaymentIntent.STATUS_FAILED, 'Failed'),
    ])
    provider_reference = serializers.CharField(max_length=120, required=False, allow_blank=True)
    message = serializers.CharField(max_length=255, required=False, allow_blank=True)
    payload = serializers.JSONField(required=False)


class MpesaC2BRegisterSerializer(serializers.Serializer):
    response_type = serializers.ChoiceField(
        choices=[('Completed', 'Completed'), ('Cancelled', 'Cancelled')],
        required=False,
    )


class PaybillWebhookSerializer(serializers.Serializer):
    order_number = serializers.CharField(max_length=20, required=False, allow_blank=True)
    account_reference = serializers.CharField(max_length=120, required=False, allow_blank=True)
    transaction_reference = serializers.CharField(max_length=120)
    status = serializers.ChoiceField(choices=[
        (PaymentIntent.STATUS_SUCCEEDED, 'Succeeded'),
        (PaymentIntent.STATUS_FAILED, 'Failed'),
        (PaymentIntent.STATUS_PENDING, 'Pending'),
        (PaymentIntent.STATUS_REQUIRES_ACTION, 'Requires Action'),
    ], default=PaymentIntent.STATUS_SUCCEEDED)
    phone = serializers.CharField(max_length=20, required=False, allow_blank=True)
    amount = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)
    message = serializers.CharField(max_length=255, required=False, allow_blank=True)
    payload = serializers.JSONField(required=False)

    def validate(self, attrs):
        if not attrs.get('order_number', '').strip() and not attrs.get('account_reference', '').strip():
            raise serializers.ValidationError({'order_number': 'order_number or account_reference is required.'})
        if not attrs.get('order_number', '').strip() and attrs.get('account_reference', '').strip():
            attrs['order_number'] = resolve_order_number_from_paybill_reference(attrs['account_reference'])
        return attrs


class PaymentWebhookSerializer(serializers.Serializer):
    reference = serializers.CharField(max_length=64)
    status = serializers.ChoiceField(choices=PaymentIntent.STATUS_CHOICES)
    provider_reference = serializers.CharField(max_length=120, required=False, allow_blank=True)
    message = serializers.CharField(max_length=255, required=False, allow_blank=True)
    payload = serializers.JSONField(required=False)


class OrderStatusWebhookSerializer(serializers.Serializer):
    order_number = serializers.CharField(max_length=20)
    status = serializers.ChoiceField(choices=Order.STATUS_CHOICES)
    message = serializers.CharField(max_length=255, required=False, allow_blank=True)
    payload = serializers.JSONField(required=False)


class OutboundOrderPushSerializer(serializers.ModelSerializer):
    order_number = serializers.ReadOnlyField(source='order.order_number')

    class Meta:
        model = OutboundOrderPush
        fields = (
            'id', 'order', 'order_number', 'action', 'status', 'attempt_count',
            'max_attempts', 'next_attempt_at', 'last_attempt_at', 'processed_at',
            'response_status_code', 'response_body', 'last_error', 'created_at', 'updated_at',
        )


class AdminInvoiceSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    customer_name = serializers.SerializerMethodField()
    customer_email = serializers.SerializerMethodField()
    customer_phone = serializers.SerializerMethodField()
    shipping_address = serializers.ReadOnlyField()
    coupon = CouponSerializer(read_only=True)
    shipping_method = ShippingMethodSerializer(read_only=True)
    payment_intent_status = serializers.SerializerMethodField()

    def get_customer_name(self, obj):
        if obj.customer:
            return obj.customer.full_name
        return f"{obj.shipping_first_name} {obj.shipping_last_name}".strip()

    def get_customer_email(self, obj):
        if obj.customer:
            return obj.customer.email
        return obj.shipping_email

    def get_customer_phone(self, obj):
        if obj.customer:
            return getattr(obj.customer, 'phone', obj.shipping_phone)
        return obj.shipping_phone

    def get_payment_intent_status(self, obj):
        latest = obj.payment_intents.order_by('-created_at').first()
        return latest.status if latest else None

    class Meta:
        model = Order
        fields = (
            'id', 'order_number', 'status', 'payment_method', 'payment_status',
            'payment_reference', 'customer_name', 'customer_email', 'customer_phone',
            'coupon', 'coupon_code', 'shipping_method', 'delivery_method', 'delivery_notes',
            'shipping_first_name', 'shipping_last_name', 'shipping_email',
            'shipping_phone', 'shipping_street', 'shipping_city', 'shipping_county',
            'shipping_address', 'subtotal', 'discount_total', 'shipping_fee', 'total',
            'items', 'payment_intent_status', 'placed_at', 'created_at', 'updated_at',
        )


class ReturnRequestCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReturnRequest
        fields = ('order_item', 'request_type', 'reason', 'requested_refund_amount')


class ReturnRequestAdminUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReturnRequest
        fields = ('status', 'resolution_notes', 'requested_refund_amount')
