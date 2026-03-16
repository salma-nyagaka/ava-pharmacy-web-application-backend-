from django.contrib import admin
from .models import Cart, CartItem, Coupon, Order, OrderEvent, OrderItem, OrderNote, OutboundOrderPush, PaymentIntent, ReturnRequest, ShippingMethod


class CartItemInline(admin.TabularInline):
    model = CartItem
    extra = 0


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ('user', 'item_count', 'updated_at')
    inlines = [CartItemInline]


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ('subtotal',)


class OrderNoteInline(admin.TabularInline):
    model = OrderNote
    extra = 0


class OrderEventInline(admin.TabularInline):
    model = OrderEvent
    extra = 0
    readonly_fields = ('event_type', 'message', 'metadata', 'actor', 'created_at')


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        'order_number', 'customer', 'status', 'payment_method',
        'payment_status', 'total', 'created_at'
    )
    list_filter = ('status', 'payment_method', 'payment_status')
    search_fields = ('order_number', 'customer__email', 'shipping_email')
    readonly_fields = ('order_number', 'created_at', 'updated_at', 'shipping_address')
    inlines = [OrderItemInline, OrderNoteInline, OrderEventInline]


@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display = ('code', 'discount_type', 'value', 'minimum_subtotal', 'is_active')
    list_filter = ('discount_type', 'is_active')
    search_fields = ('code', 'description')


@admin.register(ShippingMethod)
class ShippingMethodAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'fee', 'free_shipping_threshold', 'is_active', 'sort_order')
    list_filter = ('is_active',)
    search_fields = ('code', 'name')


@admin.register(PaymentIntent)
class PaymentIntentAdmin(admin.ModelAdmin):
    list_display = ('reference', 'order', 'provider', 'status', 'amount', 'phone_number', 'created_at')
    list_filter = ('provider', 'status')
    search_fields = ('reference', 'order__order_number', 'phone_number', 'provider_reference')


@admin.register(ReturnRequest)
class ReturnRequestAdmin(admin.ModelAdmin):
    list_display = ('order', 'customer', 'request_type', 'status', 'requested_refund_amount', 'created_at')
    list_filter = ('request_type', 'status')
    search_fields = ('order__order_number', 'customer__email')


@admin.register(OutboundOrderPush)
class OutboundOrderPushAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'order', 'action', 'status', 'attempt_count', 'max_attempts',
        'response_status_code', 'next_attempt_at', 'last_attempt_at', 'processed_at',
    )
    list_filter = ('status', 'action')
    search_fields = ('order__order_number', 'response_body', 'last_error')
    readonly_fields = (
        'order', 'action', 'payload', 'attempt_count', 'max_attempts', 'response_status_code',
        'response_body', 'last_error', 'next_attempt_at', 'last_attempt_at', 'processed_at',
        'created_at', 'updated_at',
    )
