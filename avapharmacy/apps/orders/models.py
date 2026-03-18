import uuid
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone
from apps.products.models import Product, ProductVariant


class Coupon(models.Model):
    TYPE_PERCENTAGE = 'percentage'
    TYPE_FIXED = 'fixed'
    TYPE_CHOICES = [
        (TYPE_PERCENTAGE, 'Percentage'),
        (TYPE_FIXED, 'Fixed Amount'),
    ]

    code = models.CharField(max_length=40, unique=True)
    description = models.CharField(max_length=255, blank=True)
    discount_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default=TYPE_PERCENTAGE)
    value = models.DecimalField(max_digits=10, decimal_places=2)
    minimum_subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    maximum_discount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    usage_limit = models.PositiveIntegerField(null=True, blank=True)
    per_user_limit = models.PositiveIntegerField(default=1)
    is_active = models.BooleanField(default=True)
    starts_at = models.DateTimeField(null=True, blank=True)
    ends_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['code']

    def __str__(self):
        return self.code

    def save(self, *args, **kwargs):
        self.code = self.code.upper().strip()
        super().save(*args, **kwargs)

    def is_available(self, user=None):
        from django.utils import timezone

        now = timezone.now()
        if not self.is_active:
            return False
        if self.starts_at and self.starts_at > now:
            return False
        if self.ends_at and self.ends_at < now:
            return False
        if self.usage_limit is not None and self.orders.exclude(status=Order.STATUS_CANCELLED).count() >= self.usage_limit:
            return False
        if user and self.per_user_limit:
            user_uses = self.orders.filter(customer=user).exclude(status=Order.STATUS_CANCELLED).count()
            if user_uses >= self.per_user_limit:
                return False
        return True

    def calculate_discount(self, subtotal):
        subtotal = Decimal(subtotal)
        if subtotal <= 0 or subtotal < self.minimum_subtotal:
            return Decimal('0.00')

        if self.discount_type == self.TYPE_PERCENTAGE:
            discount = (subtotal * self.value) / Decimal('100')
        else:
            discount = self.value

        if self.maximum_discount is not None:
            discount = min(discount, self.maximum_discount)

        return min(discount, subtotal)


class Cart(models.Model):
    user = models.OneToOneField(
        'accounts.User', on_delete=models.CASCADE, related_name='cart', null=True, blank=True
    )
    session_key = models.CharField(max_length=40, null=True, blank=True, unique=True)
    coupon = models.ForeignKey(Coupon, null=True, blank=True, on_delete=models.SET_NULL, related_name='carts')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        if self.user:
            return f"Cart - {self.user.email}"
        return f"Cart - Session {self.session_key}"

    class Meta:
        constraints = [
            models.CheckConstraint(
                check=models.Q(user__isnull=False) | models.Q(session_key__isnull=False),
                name='cart_requires_user_or_session',
            ),
        ]

    @property
    def total(self):
        return sum(item.subtotal for item in self.items.select_related('product').all())

    @property
    def item_count(self):
        return sum(item.quantity for item in self.items.all())

    @property
    def discount_total(self):
        if not self.coupon or not self.coupon.is_available(self.user):
            return Decimal('0.00')
        return self.coupon.calculate_discount(self.total)

    @property
    def shipping_fee(self):
        if self.item_count == 0:
            return Decimal('0.00')
        if self.total - self.discount_total >= Decimal(str(settings.FREE_SHIPPING_THRESHOLD)):
            return Decimal('0.00')
        return Decimal(str(settings.SHIPPING_FEE))

    @property
    def grand_total(self):
        return self.total - self.discount_total + self.shipping_fee


class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    product_variant = models.ForeignKey(
        ProductVariant, on_delete=models.CASCADE, null=True, blank=True, related_name='cart_items'
    )
    quantity = models.PositiveIntegerField(default=1)
    prescription_reference = models.CharField(max_length=20, blank=True, null=True)
    prescription = models.ForeignKey(
        'prescriptions.Prescription',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='cart_items',
    )
    prescription_item = models.ForeignKey(
        'prescriptions.PrescriptionItem',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='cart_items',
    )
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['cart', 'added_at']),
            models.Index(fields=['prescription']),
            models.Index(fields=['prescription_item']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['cart', 'product', 'product_variant', 'prescription', 'prescription_item'],
                name='unique_cart_item_product_variant_prescription',
            ),
        ]

    def __str__(self):
        label = self.product_variant.name if self.product_variant else self.product.name
        return f"{label} x {self.quantity}"

    @property
    def subtotal(self):
        unit_price = self.product_variant.effective_price if self.product_variant else self.product.price
        return unit_price * self.quantity

    @property
    def inventory_object(self):
        return self.product_variant or self.product


class ShippingMethod(models.Model):
    code = models.CharField(max_length=30, unique=True)
    name = models.CharField(max_length=100)
    description = models.CharField(max_length=255, blank=True)
    fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    free_shipping_threshold = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    estimated_delivery_window = models.CharField(max_length=100, blank=True)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['sort_order', 'name']
        indexes = [
            models.Index(fields=['is_active', 'sort_order']),
        ]

    def __str__(self):
        return self.name

    def calculate_fee(self, subtotal):
        subtotal = Decimal(subtotal)
        threshold = self.free_shipping_threshold
        if threshold is not None and subtotal >= threshold:
            return Decimal('0.00')
        return self.fee


class Order(models.Model):
    STATUS_DRAFT = 'draft'
    STATUS_PENDING = 'pending'
    STATUS_PAID = 'paid'
    STATUS_PROCESSING = 'processing'
    STATUS_SHIPPED = 'shipped'
    STATUS_DELIVERED = 'delivered'
    STATUS_CANCELLED = 'cancelled'
    STATUS_REFUNDED = 'refunded'

    STATUS_CHOICES = [
        (STATUS_DRAFT, 'Draft'),
        (STATUS_PENDING, 'Pending'),
        (STATUS_PAID, 'Paid'),
        (STATUS_PROCESSING, 'Processing'),
        (STATUS_SHIPPED, 'Shipped'),
        (STATUS_DELIVERED, 'Delivered'),
        (STATUS_CANCELLED, 'Cancelled'),
        (STATUS_REFUNDED, 'Refunded'),
    ]

    PAYMENT_MPESA_STK = 'mpesa_stk'
    PAYMENT_MPESA_PAYBILL = 'mpesa_paybill'
    PAYMENT_CARD = 'card'
    PAYMENT_COD = 'cash_on_delivery'

    PAYMENT_CHOICES = [
        (PAYMENT_MPESA_STK, 'M-Pesa STK Push'),
        (PAYMENT_MPESA_PAYBILL, 'M-Pesa Paybill'),
        (PAYMENT_CARD, 'Card'),
        (PAYMENT_COD, 'Cash on Delivery'),
    ]

    PAYMENT_STATUS_PENDING = 'pending'
    PAYMENT_STATUS_REQUIRES_ACTION = 'requires_action'
    PAYMENT_STATUS_PAID = 'paid'
    PAYMENT_STATUS_FAILED = 'failed'
    PAYMENT_STATUS_REFUNDED = 'refunded'

    PAYMENT_STATUS_CHOICES = [
        (PAYMENT_STATUS_PENDING, 'Pending'),
        (PAYMENT_STATUS_REQUIRES_ACTION, 'Requires Action'),
        (PAYMENT_STATUS_PAID, 'Paid'),
        (PAYMENT_STATUS_FAILED, 'Failed'),
        (PAYMENT_STATUS_REFUNDED, 'Refunded'),
    ]

    order_number = models.CharField(max_length=20, unique=True, blank=True)
    customer = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL, null=True, related_name='orders'
    )
    coupon = models.ForeignKey(Coupon, null=True, blank=True, on_delete=models.SET_NULL, related_name='orders')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_CHOICES, default=PAYMENT_COD)
    payment_status = models.CharField(
        max_length=20, choices=PAYMENT_STATUS_CHOICES, default=PAYMENT_STATUS_PENDING
    )
    payment_reference = models.CharField(max_length=100, blank=True)
    flutterwave_tx_ref = models.CharField(max_length=64, blank=True)
    flutterwave_tx_id = models.CharField(max_length=64, blank=True)
    coupon_code = models.CharField(max_length=40, blank=True)
    delivery_method = models.CharField(max_length=30, default='standard')
    delivery_notes = models.TextField(blank=True)
    shipping_method = models.ForeignKey(
        ShippingMethod, null=True, blank=True, on_delete=models.SET_NULL, related_name='orders'
    )

    # Shipping info (denormalized snapshot)
    shipping_first_name = models.CharField(max_length=100)
    shipping_last_name = models.CharField(max_length=100)
    shipping_email = models.EmailField()
    shipping_phone = models.CharField(max_length=20)
    shipping_street = models.CharField(max_length=200)
    shipping_city = models.CharField(max_length=100)
    shipping_county = models.CharField(max_length=100)

    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    discount_total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    shipping_fee = models.DecimalField(max_digits=10, decimal_places=2, default=300)
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    inventory_committed = models.BooleanField(default=False)
    placed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['payment_status', 'created_at']),
            models.Index(fields=['customer', 'created_at']),
            models.Index(fields=['payment_method', 'created_at']),
            models.Index(fields=['flutterwave_tx_ref']),
            models.Index(fields=['flutterwave_tx_id']),
        ]

    def __str__(self):
        return self.order_number

    def save(self, *args, **kwargs):
        if not self.order_number:
            self.order_number = f"ORD-{uuid.uuid4().hex[:8].upper()}"
        super().save(*args, **kwargs)

    @property
    def shipping_address(self):
        return f"{self.shipping_street}, {self.shipping_city}, {self.shipping_county}"


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True)
    product_variant = models.ForeignKey(
        ProductVariant, on_delete=models.SET_NULL, null=True, blank=True, related_name='order_items'
    )
    product_name = models.CharField(max_length=200)
    product_sku = models.CharField(max_length=50)
    variant_name = models.CharField(max_length=120, blank=True)
    variant_sku = models.CharField(max_length=60, blank=True)
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    prescription_reference = models.CharField(max_length=20, blank=True, null=True)
    prescription = models.ForeignKey(
        'prescriptions.Prescription',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='order_items',
    )
    prescription_item = models.ForeignKey(
        'prescriptions.PrescriptionItem',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='order_items',
    )
    discount_total = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    def __str__(self):
        return f"{self.product_name} x {self.quantity}"

    @property
    def subtotal(self):
        return self.unit_price * self.quantity


class OrderNote(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='notes')
    content = models.TextField()
    created_by = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['order', '-created_at']),
        ]

    def __str__(self):
        return f"Note on {self.order.order_number}"


class PaymentIntent(models.Model):
    PROVIDER_MPESA = 'mpesa'
    PROVIDER_PAYBILL = 'paybill'
    PROVIDER_CARD = 'card'
    PROVIDER_MANUAL = 'manual'
    PROVIDER_CHOICES = [
        (PROVIDER_MPESA, 'M-Pesa'),
        (PROVIDER_PAYBILL, 'M-Pesa Paybill'),
        (PROVIDER_CARD, 'Card'),
        (PROVIDER_MANUAL, 'Manual'),
    ]

    STATUS_PENDING = 'pending'
    STATUS_REQUIRES_ACTION = 'requires_action'
    STATUS_SUCCEEDED = 'succeeded'
    STATUS_FAILED = 'failed'
    STATUS_CANCELLED = 'cancelled'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_REQUIRES_ACTION, 'Requires Action'),
        (STATUS_SUCCEEDED, 'Succeeded'),
        (STATUS_FAILED, 'Failed'),
        (STATUS_CANCELLED, 'Cancelled'),
    ]

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='payment_intents')
    initiated_by = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='payment_intents'
    )
    provider = models.CharField(max_length=20, choices=PROVIDER_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    reference = models.CharField(max_length=64, unique=True, blank=True)
    provider_reference = models.CharField(max_length=120, blank=True)
    external_reference = models.CharField(max_length=120, blank=True)
    phone_number = models.CharField(max_length=20, blank=True)
    merchant_request_id = models.CharField(max_length=120, blank=True)
    checkout_request_id = models.CharField(max_length=120, blank=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=10, default='KES')
    client_secret = models.CharField(max_length=120, blank=True)
    payload = models.JSONField(default=dict, blank=True)
    callback_payload = models.JSONField(default=dict, blank=True)
    last_error = models.CharField(max_length=255, blank=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['order', 'status']),
            models.Index(fields=['provider', 'status']),
            models.Index(fields=['checkout_request_id']),
            models.Index(fields=['external_reference']),
        ]

    def save(self, *args, **kwargs):
        if not self.reference:
            self.reference = f"PAY-{uuid.uuid4().hex[:12].upper()}"
        super().save(*args, **kwargs)

    def __str__(self):
        return self.reference


class OutboundOrderPush(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_RETRYING = 'retrying'
    STATUS_SUCCEEDED = 'succeeded'
    STATUS_EXHAUSTED = 'exhausted'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_RETRYING, 'Retrying'),
        (STATUS_SUCCEEDED, 'Succeeded'),
        (STATUS_EXHAUSTED, 'Exhausted'),
    ]

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='outbound_pushes')
    action = models.CharField(max_length=20)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    payload = models.JSONField(default=dict, blank=True)
    attempt_count = models.PositiveIntegerField(default=0)
    max_attempts = models.PositiveIntegerField(default=0)
    next_attempt_at = models.DateTimeField(default=timezone.now, db_index=True)
    last_attempt_at = models.DateTimeField(null=True, blank=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    response_status_code = models.IntegerField(null=True, blank=True)
    response_body = models.TextField(blank=True)
    last_error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['next_attempt_at', 'created_at']
        indexes = [
            models.Index(fields=['status', 'next_attempt_at'], name='orders_outb_status_8350b9_idx'),
            models.Index(fields=['order', 'action', 'status'], name='orders_outb_order_i_44b93f_idx'),
        ]

    def __str__(self):
        return f'{self.order.order_number} [{self.action}]'

    @property
    def can_retry(self):
        return self.attempt_count < self.max_attempts


class OrderEvent(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='events')
    actor = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='order_events'
    )
    event_type = models.CharField(max_length=50)
    message = models.TextField()
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['order', '-created_at']),
            models.Index(fields=['event_type', '-created_at']),
        ]

    def __str__(self):
        return f"{self.order.order_number} - {self.event_type}"


class ReturnRequest(models.Model):
    STATUS_REQUESTED = 'requested'
    STATUS_APPROVED = 'approved'
    STATUS_REJECTED = 'rejected'
    STATUS_RECEIVED = 'received'
    STATUS_REFUNDED = 'refunded'
    STATUS_CHOICES = [
        (STATUS_REQUESTED, 'Requested'),
        (STATUS_APPROVED, 'Approved'),
        (STATUS_REJECTED, 'Rejected'),
        (STATUS_RECEIVED, 'Received'),
        (STATUS_REFUNDED, 'Refunded'),
    ]

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='return_requests')
    customer = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL, null=True, related_name='return_requests'
    )
    order_item = models.ForeignKey(
        OrderItem, on_delete=models.SET_NULL, null=True, blank=True, related_name='return_requests'
    )
    request_type = models.CharField(
        max_length=20,
        choices=[('return', 'Return'), ('refund', 'Refund'), ('replacement', 'Replacement')],
        default='return',
    )
    reason = models.TextField()
    requested_refund_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_REQUESTED)
    resolution_notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['customer', 'status']),
            models.Index(fields=['order', 'status']),
        ]

    def __str__(self):
        return f"Return {self.id} - {self.order.order_number}"
