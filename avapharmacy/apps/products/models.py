"""
Database models for the products app.

Defines the product catalog: Category, Brand, Product, ProductImage,
ProductVariant, ProductReview, Wishlist, Banner, Promotion, and CMSBlock.
"""
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.db.models.functions import Lower
from django.utils import timezone
from django.utils.text import slugify


class Category(models.Model):
    """A product category, optionally nested under a parent category."""

    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)
    parent = models.ForeignKey(
        'self', null=True, blank=True, on_delete=models.SET_NULL, related_name='subcategories'
    )
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=50, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='created_categories')
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='updated_categories')

    class Meta:
        verbose_name_plural = 'categories'
        ordering = ['name']
        constraints = [
            models.UniqueConstraint(
                Lower('name'),
                name='unique_category_name_ci',
            ),
        ]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        """Auto-generate slug from name if not already set."""
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class ProductCategory(models.Model):
    """Top-level product category managed from the admin panel."""

    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=50, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='created_product_categories')
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='updated_product_categories')

    class Meta:
        verbose_name_plural = 'product categories'
        ordering = ['name']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class ProductSubcategory(models.Model):
    """A subcategory that belongs to a ProductCategory."""

    category = models.ForeignKey(
        ProductCategory, on_delete=models.CASCADE, related_name='subcategories'
    )
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='created_product_subcategories')
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='updated_product_subcategories')

    class Meta:
        verbose_name_plural = 'product subcategories'
        ordering = ['category__name', 'name']
        unique_together = [('category', 'name')]

    def __str__(self):
        return f'{self.category.name} / {self.name}'

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(f'{self.category.name}-{self.name}')
            slug = base
            counter = 2
            while ProductSubcategory.objects.exclude(pk=self.pk).filter(slug=slug).exists():
                slug = f'{base}-{counter}'
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)


class HealthConcern(models.Model):
    """A health concern or condition that products address."""

    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=50, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='created_health_concerns')
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='updated_health_concerns')

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.name) or 'concern'
            slug = base
            counter = 2
            while HealthConcern.objects.exclude(pk=self.pk).filter(slug=slug).exists():
                slug = f'{base}-{counter}'
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)


class Brand(models.Model):
    """A product brand (manufacturer or label)."""

    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)
    logo = models.ImageField(upload_to='brands/')
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='created_brands')
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='updated_brands')

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        """Auto-generate slug from name if not already set."""
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class Product(models.Model):
    """A sellable product in the pharmacy catalog.

    Tracks stock levels, prescription requirements, variants, reviews, and
    promotional eligibility. Stock source is automatically updated based on
    the stock quantity when the product is saved.
    """

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
    strength = models.CharField(max_length=50, blank=True, help_text="e.g. 500mg, 10mg/5ml, 2%")
    brand = models.ForeignKey(Brand, on_delete=models.SET_NULL, null=True, blank=True, related_name='products')
    category = models.ForeignKey(
        Category, on_delete=models.SET_NULL, null=True, blank=True, related_name='products'
    )
    subcategory = models.ForeignKey(
        'ProductSubcategory', on_delete=models.SET_NULL, null=True, blank=True, related_name='products'
    )
    health_concerns = models.ManyToManyField(HealthConcern, blank=True, related_name='products')
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
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='created_products')
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='updated_products')

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
        """Auto-generate slug and sync stock_source with stock_quantity."""
        if not self.slug:
            self.slug = slugify(self.name)
        if self.pk and self.has_variants:
            super().save(*args, **kwargs)
            return
        if self.stock_quantity == 0 and not self.allow_backorder:
            self.stock_source = self.STOCK_OUT
        elif self.stock_quantity > 0 and self.stock_source == self.STOCK_OUT:
            self.stock_source = self.STOCK_BRANCH
        super().save(*args, **kwargs)

    @property
    def inventory_status(self):
        """Return a human-readable inventory status string.

        Aggregates variant statuses when variants exist; otherwise derives status
        from stock_quantity and low_stock_threshold.

        Returns:
            str: One of 'in_stock', 'low_stock', 'backorder', 'out_of_stock', 'inactive'.
        """
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
        """Return the total purchasable quantity, including backorder allowance."""
        if self.has_variants:
            return sum(variant.available_quantity for variant in self.variants.filter(is_active=True))
        if self.allow_backorder:
            return self.stock_quantity + self.max_backorder_quantity
        return self.stock_quantity

    @property
    def can_purchase(self):
        """Return True if the product is active and has available stock."""
        return self.is_active and self.available_quantity > 0

    @property
    def has_variants(self):
        """Return True if the product has at least one active variant."""
        if hasattr(self, '_prefetched_objects_cache') and 'variants' in self._prefetched_objects_cache:
            return any(variant.is_active for variant in self._prefetched_objects_cache['variants'])
        return self.variants.filter(is_active=True).exists()

    @property
    def average_rating(self):
        """Return the average rating from approved reviews, rounded to 1 decimal."""
        from django.db.models import Avg
        reviews = self.reviews.filter(is_approved=True)
        if reviews.exists():
            result = reviews.aggregate(avg=Avg('rating'))['avg']
            return round(result, 1) if result else 0.0
        return 0.0

    @property
    def review_count(self):
        """Return the count of approved reviews for this product."""
        return self.reviews.filter(is_approved=True).count()


class ProductImage(models.Model):
    """An additional gallery image for a product."""

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='gallery')
    image = models.ImageField(upload_to='products/gallery/')
    alt_text = models.CharField(max_length=200, blank=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"{self.product.name} - Image {self.order}"


class ProductVariant(models.Model):
    """A specific variant of a product (e.g. size, colour, strength).

    Maintains its own SKU, price (falls back to parent product price if null),
    stock levels, and inventory status.
    """

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='variants')
    sku = models.CharField(max_length=60, unique=True)
    name = models.CharField(max_length=120)
    attributes = models.JSONField(default=dict, blank=True)  # e.g. {"size": "500mg"}
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
        """Sync stock_source with stock_quantity on save."""
        if self.stock_quantity == 0 and not self.allow_backorder:
            self.stock_source = Product.STOCK_OUT
        elif self.stock_quantity > 0 and self.stock_source == Product.STOCK_OUT:
            self.stock_source = Product.STOCK_BRANCH
        super().save(*args, **kwargs)

    @property
    def effective_price(self):
        """Return this variant's price, falling back to the parent product's price."""
        return self.price if self.price is not None else self.product.price

    @property
    def inventory_status(self):
        """Return the inventory status string for this variant.

        Returns:
            str: One of 'inactive', 'backorder', 'out_of_stock', 'low_stock', 'in_stock'.
        """
        if not self.is_active:
            return 'inactive'
        if self.stock_quantity == 0:
            return 'backorder' if self.allow_backorder else 'out_of_stock'
        if self.stock_quantity <= self.low_stock_threshold:
            return 'low_stock'
        return 'in_stock'

    @property
    def available_quantity(self):
        """Return purchasable quantity including backorder allowance."""
        if self.allow_backorder:
            return self.stock_quantity + self.max_backorder_quantity
        return self.stock_quantity


class ProductReview(models.Model):
    """A customer review (1-5 star rating) for a product.

    One review per user per product (enforced by unique_together).
    """

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
    """A saved product on a user's wishlist."""

    user = models.ForeignKey('accounts.User', on_delete=models.CASCADE, related_name='wishlist')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='wishlisted_by')
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'product')
        ordering = ['-added_at']

    def __str__(self):
        return f"{self.user.full_name} - {self.product.name}"


class Banner(models.Model):
    """A promotional banner displayed on the storefront."""

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
    """A discount promotion that can apply to all products, a category, brand, or specific product.

    Supports percentage and fixed-amount discounts, stackable/non-stackable
    behaviour, coupon codes, priority ordering, and date-range activation.
    """

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
    targets = models.JSONField(default=list)  # IDs/slugs/SKUs of targeted entities
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
        """Return True if the promotion is active and within its date range."""
        today = timezone.now().date()
        return (
            self.status == self.STATUS_ACTIVE
            and self.start_date <= today <= self.end_date
        )

    def applies_to_product(self, product):
        """Check whether this promotion applies to the given product.

        Args:
            product: A Product instance to test.

        Returns:
            bool: True if the promotion's scope and targets match the product.
        """
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
        """Compute the discount amount for a given price.

        Args:
            amount: The base price to apply the discount to.

        Returns:
            Decimal: The discount value, capped at the full amount.
        """
        amount = Decimal(amount)
        if amount <= 0:
            return Decimal('0.00')
        if self.type == self.TYPE_PERCENTAGE:
            discount = (amount * self.value) / Decimal('100')
        else:
            discount = self.value
        return min(discount, amount)


class CMSBlock(models.Model):
    """A configurable content block used for dynamic storefront sections."""

    placement = models.CharField(max_length=60)   # e.g. 'home_hero', 'sidebar'
    key = models.CharField(max_length=80, unique=True)
    title = models.CharField(max_length=180)
    subtitle = models.CharField(max_length=255, blank=True)
    body = models.TextField(blank=True)
    image = models.ImageField(upload_to='cms/', blank=True)
    cta_label = models.CharField(max_length=80, blank=True)
    cta_url = models.URLField(blank=True)
    content = models.JSONField(default=dict, blank=True)  # Arbitrary structured content
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


class StockMovement(models.Model):
    """Audit trail for every stock level change on a product."""

    TYPE_SALE = 'sale'
    TYPE_ADJUSTMENT = 'adjustment'
    TYPE_RETURN = 'return'
    TYPE_RESERVE = 'reserve'
    TYPE_RELEASE = 'release'
    TYPE_INITIAL = 'initial'
    TYPE_CHOICES = [
        (TYPE_SALE, 'Sale'),
        (TYPE_ADJUSTMENT, 'Adjustment'),
        (TYPE_RETURN, 'Return'),
        (TYPE_RESERVE, 'Reserve'),
        (TYPE_RELEASE, 'Release'),
        (TYPE_INITIAL, 'Initial'),
    ]

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='stock_movements')
    movement_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    quantity_change = models.IntegerField()
    quantity_before = models.PositiveIntegerField()
    quantity_after = models.PositiveIntegerField()
    reason = models.CharField(max_length=255, blank=True)
    reference = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='created_stock_movements'
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='updated_stock_movements'
    )

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['product', '-created_at']),
        ]

    def __str__(self):
        return f"{self.movement_type} {self.quantity_change:+d} for {self.product.name}"
