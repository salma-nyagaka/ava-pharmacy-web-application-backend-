from decimal import Decimal

from django.db import models
from django.utils import timezone
from django.utils.text import slugify


class Category(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)
    parent = models.ForeignKey(
        'self', null=True, blank=True, on_delete=models.SET_NULL, related_name='subcategories'
    )
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=50, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = 'categories'
        ordering = ['name']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class Brand(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)
    logo = models.ImageField(upload_to='brands/', null=True, blank=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class Product(models.Model):
    STOCK_BRANCH = 'branch'
    STOCK_WAREHOUSE = 'warehouse'
    STOCK_OUT = 'out'
    STOCK_CHOICES = [
        (STOCK_BRANCH, 'In Branch'),
        (STOCK_WAREHOUSE, 'In Warehouse'),
        (STOCK_OUT, 'Out of Stock'),
    ]

    sku = models.CharField(max_length=50, unique=True)
    slug = models.SlugField(unique=True, max_length=200)
    name = models.CharField(max_length=200)
    brand = models.ForeignKey(Brand, on_delete=models.SET_NULL, null=True, blank=True, related_name='products')
    category = models.ForeignKey(
        Category, on_delete=models.SET_NULL, null=True, blank=True, related_name='products'
    )
    price = models.DecimalField(max_digits=10, decimal_places=2)
    original_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    image = models.ImageField(upload_to='products/', blank=True)
    short_description = models.CharField(max_length=500, blank=True)
    description = models.TextField(blank=True)
    features = models.JSONField(default=list)
    directions = models.TextField(blank=True)
    warnings = models.TextField(blank=True)
    badge = models.CharField(max_length=50, blank=True)
    stock_source = models.CharField(max_length=20, choices=STOCK_CHOICES, default=STOCK_BRANCH)
    stock_quantity = models.PositiveIntegerField(default=0)
    low_stock_threshold = models.PositiveIntegerField(default=5)
    allow_backorder = models.BooleanField(default=False)
    max_backorder_quantity = models.PositiveIntegerField(default=0)
    requires_prescription = models.BooleanField(default=False)
    is_featured = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['is_active', 'created_at']),
            models.Index(fields=['category', 'is_active']),
            models.Index(fields=['brand', 'is_active']),
            models.Index(fields=['stock_source', 'is_active']),
        ]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        if self.has_variants:
            super().save(*args, **kwargs)
            return
        if self.stock_quantity == 0 and not self.allow_backorder:
            self.stock_source = self.STOCK_OUT
        elif self.stock_quantity > 0 and self.stock_source == self.STOCK_OUT:
            self.stock_source = self.STOCK_BRANCH
        super().save(*args, **kwargs)

    @property
    def inventory_status(self):
        if self.has_variants:
            statuses = [variant.inventory_status for variant in self.variants.filter(is_active=True)]
            if 'in_stock' in statuses:
                return 'in_stock'
            if 'low_stock' in statuses:
                return 'low_stock'
            if 'backorder' in statuses:
                return 'backorder'
            if statuses:
                return 'out_of_stock'
        if not self.is_active:
            return 'inactive'
        if self.stock_quantity == 0:
            return 'backorder' if self.allow_backorder else 'out_of_stock'
        if self.stock_quantity <= self.low_stock_threshold:
            return 'low_stock'
        return 'in_stock'

    @property
    def available_quantity(self):
        if self.has_variants:
            return sum(variant.available_quantity for variant in self.variants.filter(is_active=True))
        if self.allow_backorder:
            return self.stock_quantity + self.max_backorder_quantity
        return self.stock_quantity

    @property
    def can_purchase(self):
        return self.is_active and self.available_quantity > 0

    @property
    def has_variants(self):
        if hasattr(self, '_prefetched_objects_cache') and 'variants' in self._prefetched_objects_cache:
            return any(variant.is_active for variant in self._prefetched_objects_cache['variants'])
        return self.variants.filter(is_active=True).exists()

    @property
    def average_rating(self):
        from django.db.models import Avg
        reviews = self.reviews.filter(is_approved=True)
        if reviews.exists():
            result = reviews.aggregate(avg=Avg('rating'))['avg']
            return round(result, 1) if result else 0.0
        return 0.0

    @property
    def review_count(self):
        return self.reviews.filter(is_approved=True).count()


class ProductImage(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='gallery')
    image = models.ImageField(upload_to='products/gallery/')
    alt_text = models.CharField(max_length=200, blank=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"{self.product.name} - Image {self.order}"


class ProductVariant(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='variants')
    sku = models.CharField(max_length=60, unique=True)
    name = models.CharField(max_length=120)
    attributes = models.JSONField(default=dict, blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    original_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    image = models.ImageField(upload_to='products/variants/', blank=True)
    stock_source = models.CharField(max_length=20, choices=Product.STOCK_CHOICES, default=Product.STOCK_BRANCH)
    stock_quantity = models.PositiveIntegerField(default=0)
    low_stock_threshold = models.PositiveIntegerField(default=5)
    allow_backorder = models.BooleanField(default=False)
    max_backorder_quantity = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['sort_order', 'name']
        indexes = [
            models.Index(fields=['product', 'is_active']),
            models.Index(fields=['stock_source', 'is_active']),
        ]

    def __str__(self):
        return f"{self.product.name} - {self.name}"

    def save(self, *args, **kwargs):
        if self.stock_quantity == 0 and not self.allow_backorder:
            self.stock_source = Product.STOCK_OUT
        elif self.stock_quantity > 0 and self.stock_source == Product.STOCK_OUT:
            self.stock_source = Product.STOCK_BRANCH
        super().save(*args, **kwargs)

    @property
    def effective_price(self):
        return self.price if self.price is not None else self.product.price

    @property
    def inventory_status(self):
        if not self.is_active:
            return 'inactive'
        if self.stock_quantity == 0:
            return 'backorder' if self.allow_backorder else 'out_of_stock'
        if self.stock_quantity <= self.low_stock_threshold:
            return 'low_stock'
        return 'in_stock'

    @property
    def available_quantity(self):
        if self.allow_backorder:
            return self.stock_quantity + self.max_backorder_quantity
        return self.stock_quantity


class ProductReview(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='reviews')
    user = models.ForeignKey('accounts.User', on_delete=models.CASCADE, related_name='reviews')
    rating = models.PositiveSmallIntegerField()
    comment = models.TextField(blank=True)
    is_approved = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('product', 'user')
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.full_name} - {self.product.name} ({self.rating})"


class Wishlist(models.Model):
    user = models.ForeignKey('accounts.User', on_delete=models.CASCADE, related_name='wishlist')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='wishlisted_by')
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'product')
        ordering = ['-added_at']

    def __str__(self):
        return f"{self.user.full_name} - {self.product.name}"


class Banner(models.Model):
    title = models.CharField(max_length=120, blank=True)
    message = models.TextField()
    link = models.URLField(blank=True)
    image = models.ImageField(upload_to='banners/', blank=True)
    placement = models.CharField(max_length=50, default='home_hero')
    sort_order = models.PositiveIntegerField(default=0)
    status = models.CharField(
        max_length=20,
        choices=[('active', 'Active'), ('inactive', 'Inactive')],
        default='active'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['sort_order', '-created_at']

    def __str__(self):
        return self.message[:60]


class Promotion(models.Model):
    TYPE_PERCENTAGE = 'percentage'
    TYPE_AMOUNT = 'amount'
    TYPE_CHOICES = [
        (TYPE_PERCENTAGE, 'Percentage'),
        (TYPE_AMOUNT, 'Amount'),
    ]

    SCOPE_ALL = 'all'
    SCOPE_CATEGORY = 'category'
    SCOPE_BRAND = 'brand'
    SCOPE_PRODUCT = 'product'
    SCOPE_CHOICES = [
        (SCOPE_ALL, 'All Products'),
        (SCOPE_CATEGORY, 'Category'),
        (SCOPE_BRAND, 'Brand'),
        (SCOPE_PRODUCT, 'Product'),
    ]

    STATUS_ACTIVE = 'active'
    STATUS_DRAFT = 'draft'
    STATUS_CHOICES = [
        (STATUS_ACTIVE, 'Active'),
        (STATUS_DRAFT, 'Draft'),
    ]

    title = models.CharField(max_length=200)
    code = models.CharField(max_length=40, blank=True, null=True, unique=True)
    description = models.TextField(blank=True)
    type = models.CharField(max_length=20, choices=TYPE_CHOICES, default=TYPE_PERCENTAGE)
    value = models.DecimalField(max_digits=10, decimal_places=2)
    scope = models.CharField(max_length=20, choices=SCOPE_CHOICES, default=SCOPE_ALL)
    targets = models.JSONField(default=list)
    badge = models.CharField(max_length=50, blank=True)
    priority = models.PositiveIntegerField(default=0)
    is_stackable = models.BooleanField(default=False)
    minimum_order_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    start_date = models.DateField()
    end_date = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-priority', '-created_at']
        indexes = [
            models.Index(fields=['status', 'start_date', 'end_date']),
            models.Index(fields=['scope', 'status']),
        ]

    def __str__(self):
        return self.title

    @property
    def is_currently_active(self):
        today = timezone.now().date()
        return (
            self.status == self.STATUS_ACTIVE
            and self.start_date <= today <= self.end_date
        )

    def applies_to_product(self, product):
        if self.scope == self.SCOPE_ALL:
            return True

        targets = {str(value) for value in self.targets}
        if self.scope == self.SCOPE_CATEGORY and product.category:
            return str(product.category_id) in targets or product.category.slug in targets
        if self.scope == self.SCOPE_BRAND and product.brand:
            return str(product.brand_id) in targets or product.brand.slug in targets
        if self.scope == self.SCOPE_PRODUCT:
            return str(product.id) in targets or product.slug in targets or product.sku in targets
        return False

    def calculate_discount(self, amount):
        amount = Decimal(amount)
        if amount <= 0:
            return Decimal('0.00')
        if self.type == self.TYPE_PERCENTAGE:
            discount = (amount * self.value) / Decimal('100')
        else:
            discount = self.value
        return min(discount, amount)


class CMSBlock(models.Model):
    placement = models.CharField(max_length=60)
    key = models.CharField(max_length=80, unique=True)
    title = models.CharField(max_length=180)
    subtitle = models.CharField(max_length=255, blank=True)
    body = models.TextField(blank=True)
    image = models.ImageField(upload_to='cms/', blank=True)
    cta_label = models.CharField(max_length=80, blank=True)
    cta_url = models.URLField(blank=True)
    content = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['placement', 'sort_order', 'title']
        indexes = [
            models.Index(fields=['placement', 'is_active']),
        ]

    def __str__(self):
        return f"{self.placement} - {self.key}"
