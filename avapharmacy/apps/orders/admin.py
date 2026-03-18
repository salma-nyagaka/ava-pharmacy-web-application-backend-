import json

from django.contrib import admin
from django.utils.html import format_html
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


class PaymentIntentErrorLogFilter(admin.SimpleListFilter):
    title = 'error logs'
    parameter_name = 'has_error_logs'

    def lookups(self, request, model_admin):
        return (
            ('yes', 'Has error logs'),
            ('no', 'No error logs'),
        )

    def queryset(self, request, queryset):
        value = self.value()
        if value == 'yes':
            return queryset.exclude(last_error='')
        if value == 'no':
            return queryset.filter(last_error='')
        return queryset


@admin.register(PaymentIntent)
class PaymentIntentAdmin(admin.ModelAdmin):
    list_display = (
        'reference', 'order', 'provider', 'status', 'amount',
        'has_logged_errors', 'latest_error', 'created_at',
    )
    list_filter = ('provider', 'status', PaymentIntentErrorLogFilter)
    search_fields = ('reference', 'order__order_number', 'phone_number', 'provider_reference', 'last_error')
    readonly_fields = (
        'reference', 'order', 'initiated_by', 'provider', 'status', 'provider_reference',
        'external_reference', 'phone_number', 'merchant_request_id', 'checkout_request_id',
        'amount', 'currency', 'client_secret', 'payload', 'callback_payload', 'last_error',
        'error_logs_preview', 'processed_at', 'created_at', 'updated_at',
    )

    fieldsets = (
        ('Overview', {
            'fields': (
                'reference', 'order', 'initiated_by', 'provider', 'status',
                'amount', 'currency', 'processed_at',
            ),
        }),
        ('Provider Data', {
            'fields': (
                'provider_reference', 'external_reference', 'phone_number',
                'merchant_request_id', 'checkout_request_id', 'client_secret',
            ),
        }),
        ('Errors', {
            'fields': ('last_error', 'error_logs_preview'),
        }),
        ('Payloads', {
            'fields': ('payload', 'callback_payload'),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
        }),
    )

    @admin.display(boolean=True, description='Errors')
    def has_logged_errors(self, obj):
        return bool(obj.last_error or (obj.payload or {}).get('error_logs'))

    @admin.display(description='Latest error')
    def latest_error(self, obj):
        latest = ((obj.payload or {}).get('error_logs') or [])[-1:] or []
        if latest:
            return str(latest[0].get('message', ''))[:80]
        return obj.last_error[:80] if obj.last_error else '—'

    @admin.display(description='Error logs')
    def error_logs_preview(self, obj):
        error_logs = (obj.payload or {}).get('error_logs') or []
        if not error_logs:
            return 'No payment error logs.'
        pretty = json.dumps(error_logs, indent=2, ensure_ascii=False)
        return format_html('<pre style="white-space: pre-wrap; margin: 0;">{}</pre>', pretty)


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
