from rest_framework import serializers
from decimal import Decimal
from django.conf import settings
from .models import Cart, CartItem, Order, OrderItem, OrderNote
from apps.products.serializers import ProductListSerializer


class CartItemSerializer(serializers.ModelSerializer):
    product = ProductListSerializer(read_only=True)
    product_id = serializers.IntegerField(write_only=True)
    subtotal = serializers.ReadOnlyField()

    class Meta:
        model = CartItem
        fields = ('id', 'product', 'product_id', 'quantity', 'prescription_id', 'subtotal', 'added_at')
        read_only_fields = ('id', 'added_at')


class CartSerializer(serializers.ModelSerializer):
    items = CartItemSerializer(many=True, read_only=True)
    total = serializers.ReadOnlyField()
    item_count = serializers.ReadOnlyField()

    class Meta:
        model = Cart
        fields = ('id', 'items', 'total', 'item_count', 'updated_at')


class OrderItemSerializer(serializers.ModelSerializer):
    subtotal = serializers.ReadOnlyField()

    class Meta:
        model = OrderItem
        fields = ('id', 'product_name', 'product_sku', 'quantity', 'unit_price', 'subtotal')


class OrderNoteSerializer(serializers.ModelSerializer):
    created_by_name = serializers.ReadOnlyField(source='created_by.full_name')

    class Meta:
        model = OrderNote
        fields = ('id', 'content', 'created_by_name', 'created_at')


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    notes = OrderNoteSerializer(many=True, read_only=True)
    shipping_address = serializers.ReadOnlyField()

    class Meta:
        model = Order
        fields = (
            'id', 'order_number', 'status', 'payment_method', 'payment_status',
            'shipping_first_name', 'shipping_last_name', 'shipping_email',
            'shipping_phone', 'shipping_street', 'shipping_city', 'shipping_county',
            'shipping_address', 'subtotal', 'shipping_fee', 'total',
            'items', 'notes', 'created_at', 'updated_at'
        )


class CheckoutSerializer(serializers.Serializer):
    first_name = serializers.CharField(max_length=100)
    last_name = serializers.CharField(max_length=100)
    email = serializers.EmailField()
    phone = serializers.CharField(max_length=20)
    street = serializers.CharField(max_length=200)
    city = serializers.CharField(max_length=100)
    county = serializers.CharField(max_length=100)
    payment_method = serializers.ChoiceField(choices=[
        ('mpesa_stk', 'M-Pesa STK Push'),
        ('mpesa_paybill', 'M-Pesa Paybill'),
        ('card', 'Card'),
        ('cash_on_delivery', 'Cash on Delivery'),
    ])


class AdminOrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    notes = OrderNoteSerializer(many=True, read_only=True)
    customer_name = serializers.ReadOnlyField(source='customer.full_name')
    customer_email = serializers.ReadOnlyField(source='customer.email')
    customer_phone = serializers.ReadOnlyField(source='customer.phone')
    shipping_address = serializers.ReadOnlyField()

    class Meta:
        model = Order
        fields = (
            'id', 'order_number', 'customer', 'customer_name', 'customer_email',
            'customer_phone', 'status', 'payment_method', 'payment_status',
            'payment_reference', 'shipping_street', 'shipping_city', 'shipping_county',
            'shipping_address', 'subtotal', 'shipping_fee', 'total',
            'items', 'notes', 'created_at', 'updated_at'
        )
        read_only_fields = ('id', 'order_number', 'customer', 'items', 'subtotal', 'total', 'created_at')


class AdminOrderUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Order
        fields = ('status', 'payment_status', 'payment_reference')


class OrderNoteCreateSerializer(serializers.Serializer):
    content = serializers.CharField()
