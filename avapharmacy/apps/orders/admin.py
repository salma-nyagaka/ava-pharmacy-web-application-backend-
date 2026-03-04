from django.contrib import admin
from .models import Cart, CartItem, Order, OrderItem, OrderNote


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


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        'order_number', 'customer', 'status', 'payment_method',
        'payment_status', 'total', 'created_at'
    )
    list_filter = ('status', 'payment_method', 'payment_status')
    search_fields = ('order_number', 'customer__email', 'shipping_email')
    readonly_fields = ('order_number', 'created_at', 'updated_at', 'shipping_address')
    inlines = [OrderItemInline, OrderNoteInline]
