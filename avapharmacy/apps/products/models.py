"""
Database models for the products app.

Defines the product catalog: Category, Brand, Product, ProductImage,
ProductVariant, ProductReview, Wishlist, Banner, Promotion, and CMSBlock.
"""
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.db.models import Q, Value
from django.db.models.functions import Coalesce, Lower
from django.utils import timezone
from django.utils.text import slugify


class Category(models.Model):
    """A product category, optionally nested under a parent category."""

    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)
    parent = models.ForeignKey(
        'self', null=True, blank=True, on_delete=models.SET_NULL, related_name='subcategories'
    )
    image = models.ImageField(upload_to='categories/', blank=True)
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
        indexes = [
            models.Index(fields=['parent', 'is_active']),
            models.Index(fields=['is_active', 'name']),
        ]
        constraints = [
            models.UniqueConstraint(
                Lower('name'),
                condition=Q(parent__isnull=True),
                name='unique_root_category_name_ci',
            ),
            models.UniqueConstraint(
                Lower('name'),
                Coalesce('parent', Value(0)),
                condition=Q(parent__isnull=False),
                name='unique_category_name_per_parent_ci',
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
    image = models.ImageField(upload_to='categories/')
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
        indexes = [
            models.Index(fields=['is_active', 'name']),
        ]

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
    category_node = models.OneToOneField(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='legacy_product_subcategory',
    )
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True, max_length=200)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='created_product_subcategories')
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='updated_product_subcategories')

    class Meta:
        verbose_name_plural = 'product subcategories'
        ordering = ['category__name', 'name']
        indexes = [
            models.Index(fields=['category', 'is_active']),
        ]
        constraints = [
            models.UniqueConstraint(
                Lower('name'),
                models.F('category'),
                name='unique_product_subcategory_name_per_category_ci',
            ),
        ]

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
    image = models.ImageField(upload_to='health_concerns/', blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='created_health_concerns')
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='updated_health_concerns')

    class Meta:
        ordering = ['name']
        indexes = [
            models.Index(fields=['is_active', 'name']),
        ]

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
        indexes = [
            models.Index(fields=['is_active', 'name']),
        ]

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
        (STOCK_BRANCH, 'Main Shop'),
        (STOCK_WAREHOUSE, 'POS Store'),
        (STOCK_OUT, 'Out of Stock'),
    ]
    INVENTORY_LOCATION_CHOICES = [
        (STOCK_BRANCH, 'Main Shop'),
        (STOCK_WAREHOUSE, 'POS Store'),
    ]

    sku = models.CharField(max_length=50, unique=True)
    barcode = models.CharField(max_length=64, blank=True)
    pos_product_id = models.CharField(max_length=80, blank=True)
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
    catalog_subcategory = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='products_as_subcategory',
    )
    health_concerns = models.ManyToManyField(HealthConcern, blank=True, related_name='products')
    price = models.DecimalField(max_digits=10, decimal_places=2)
    cost_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    image = models.ImageField(upload_to='products/', blank=True)
    short_description = models.CharField(max_length=500, blank=True)
    description = models.TextField(blank=True)
    features = models.JSONField(default=list)
    directions = models.TextField(blank=True)
    warnings = models.TextField(blank=True)
    dosage_quantity = models.CharField(max_length=20, blank=True, help_text="e.g. 1, 2, 1-2")
    dosage_unit = models.CharField(max_length=30, blank=True, help_text="e.g. tablet, capsule, ml, drop")
    dosage_frequency = models.CharField(max_length=50, blank=True, help_text="e.g. once_daily, twice_daily")
    dosage_notes = models.CharField(max_length=150, blank=True, help_text="e.g. with food, before meals")
    requires_prescription = models.BooleanField(default=False)
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
            models.Index(fields=['catalog_subcategory', 'is_active']),
            models.Index(fields=['brand', 'is_active']),
            models.Index(fields=['requires_prescription', 'is_active']),
        ]

    INVENTORY_FIELD_NAMES = {
        'stock_source',
        'stock_quantity',
        'low_stock_threshold',
        'allow_backorder',
        'max_backorder_quantity',
    }

    def __str__(self):
        return self.name

    def _inventory_defaults(self, location=None):
        return {
            'stock_quantity': 0,
            'low_stock_threshold': 5 if location != self.STOCK_WAREHOUSE else 0,
            'allow_backorder': False,
            'max_backorder_quantity': 0,
        }

    def _get_inventory_rows(self):
        if not self.pk:
            return []
        if hasattr(self, '_prefetched_objects_cache') and 'inventories' in self._prefetched_objects_cache:
            return list(self._prefetched_objects_cache['inventories'])
        return list(self.inventories.all())

    def _get_inventory_map(self):
        return {inventory.location: inventory for inventory in self._get_inventory_rows()}

    def _clear_inventory_cache(self):
        if hasattr(self, '_prefetched_objects_cache'):
            self._prefetched_objects_cache.pop('inventories', None)

    def _ensure_inventory_rows(self):
        if not self.pk:
            return {}

        inventory_map = self._get_inventory_map()
        missing_rows = [
            ProductInventory(
                product=self,
                location=location,
                **self._inventory_defaults(location),
            )
            for location in dict(self.INVENTORY_LOCATION_CHOICES)
            if location not in inventory_map
        ]
        if missing_rows:
            ProductInventory.objects.bulk_create(missing_rows)
            self._clear_inventory_cache()
            inventory_map = self._get_inventory_map()
        return inventory_map

    def _get_location_inventory_values(self):
        values = {
            location: self._inventory_defaults(location).copy()
            for location in dict(self.INVENTORY_LOCATION_CHOICES)
        }
        for location, inventory in self._get_inventory_map().items():
            values[location].update({
                'stock_quantity': inventory.stock_quantity,
                'low_stock_threshold': inventory.low_stock_threshold,
                'allow_backorder': inventory.allow_backorder,
                'max_backorder_quantity': inventory.max_backorder_quantity,
            })
        return values

    def _get_inventory_values(self):
        pending = getattr(self, '_pending_inventory_updates', {})
        annotated_total = getattr(self, 'total_stock_quantity', None)
        annotated_threshold = getattr(self, 'total_low_stock_threshold', None)
        annotated_backorder = getattr(self, 'has_backorder_inventory', None)
        annotated_max_backorder = getattr(self, 'total_max_backorder_quantity', None)

        if not pending and annotated_total is not None:
            stock_source = self.STOCK_OUT
            branch_stock = getattr(self, 'branch_stock_quantity', 0) or 0
            warehouse_stock = getattr(self, 'warehouse_stock_quantity', 0) or 0
            if branch_stock > 0:
                stock_source = self.STOCK_BRANCH
            elif warehouse_stock > 0:
                stock_source = self.STOCK_WAREHOUSE
            return {
                'stock_source': stock_source,
                'stock_quantity': annotated_total or 0,
                'low_stock_threshold': annotated_threshold or 0,
                'allow_backorder': bool(annotated_backorder),
                'max_backorder_quantity': annotated_max_backorder or 0,
            }

        location_values = self._get_location_inventory_values()
        stock_source = self.STOCK_OUT
        if location_values[self.STOCK_BRANCH]['stock_quantity'] > 0:
            stock_source = self.STOCK_BRANCH
        elif location_values[self.STOCK_WAREHOUSE]['stock_quantity'] > 0:
            stock_source = self.STOCK_WAREHOUSE

        values = {
            'stock_source': stock_source,
            'stock_quantity': sum(item['stock_quantity'] for item in location_values.values()),
            'low_stock_threshold': sum(item['low_stock_threshold'] for item in location_values.values()),
            'allow_backorder': any(item['allow_backorder'] for item in location_values.values()),
            'max_backorder_quantity': sum(item['max_backorder_quantity'] for item in location_values.values()),
        }
        if 'stock_source' in pending and pending['stock_source'] in dict(self.INVENTORY_LOCATION_CHOICES):
            values['stock_source'] = pending['stock_source']
        if 'stock_quantity' in pending:
            values['stock_quantity'] = max(0, int(pending['stock_quantity']))
        if 'low_stock_threshold' in pending:
            values['low_stock_threshold'] = max(0, int(pending['low_stock_threshold']))
        if 'allow_backorder' in pending:
            values['allow_backorder'] = bool(pending['allow_backorder'])
        if 'max_backorder_quantity' in pending:
            values['max_backorder_quantity'] = max(0, int(pending['max_backorder_quantity']))
        return values

    def _set_inventory_value(self, field_name, value):
        pending = getattr(self, '_pending_inventory_updates', {}).copy()
        pending[field_name] = value
        self._pending_inventory_updates = pending

    def _sync_category_from_subcategory(self):
        subcategory = self.catalog_subcategory
        if subcategory is None and self.subcategory_id:
            subcategory = getattr(self.subcategory, 'category_node', None)
        if not subcategory:
            return False

        source_category = subcategory.parent or subcategory

        if self.category_id != source_category.id:
            self.category = source_category
            return True
        return False

    def save(self, *args, **kwargs):
        """Auto-generate slug and persist any pending inventory updates."""
        if not self.slug:
            self.slug = slugify(self.name)

        category_synced = self._sync_category_from_subcategory()

        original_update_fields = kwargs.get('update_fields')
        inventory_update_fields = set()
        if original_update_fields is not None:
            update_fields = set(original_update_fields)
            if category_synced:
                update_fields.add('category')
            inventory_update_fields = update_fields & self.INVENTORY_FIELD_NAMES
            model_update_fields = update_fields - self.INVENTORY_FIELD_NAMES
            if model_update_fields:
                kwargs['update_fields'] = list(model_update_fields)
            else:
                kwargs.pop('update_fields')

        should_save_product = self.pk is None or original_update_fields is None or bool(kwargs.get('update_fields'))
        if should_save_product:
            super().save(*args, **kwargs)

        pending = getattr(self, '_pending_inventory_updates', {}).copy()
        if original_update_fields is None:
            inventory_update_fields.update(pending.keys())
        else:
            for field_name in inventory_update_fields:
                pending.setdefault(field_name, self._inventory_defaults()[field_name])

        if self.pk is not None:
            inventory_map = self._ensure_inventory_rows()
            if pending:
                self._apply_pending_inventory_updates(inventory_map, pending)

        self._pending_inventory_updates = {}

    def _apply_pending_inventory_updates(self, inventory_map, pending):
        location_choices = dict(self.INVENTORY_LOCATION_CHOICES)
        target_location = pending.get('stock_source')
        current_source = self._get_inventory_values()['stock_source']
        if target_location not in location_choices:
            target_location = current_source if current_source in location_choices else self.STOCK_BRANCH

        changed_inventories = set()
        if 'stock_quantity' in pending:
            desired_total = max(0, int(pending['stock_quantity']))
            current_total = sum(inventory.stock_quantity for inventory in inventory_map.values())
            delta = desired_total - current_total
            if delta > 0:
                inventory_map[target_location].stock_quantity += delta
                changed_inventories.add(target_location)
            elif delta < 0:
                remaining = -delta
                ordered_locations = [target_location] + [
                    location for location in location_choices if location != target_location
                ]
                for location in ordered_locations:
                    if remaining == 0:
                        break
                    inventory = inventory_map[location]
                    deduction = min(inventory.stock_quantity, remaining)
                    if deduction:
                        inventory.stock_quantity -= deduction
                        changed_inventories.add(location)
                        remaining -= deduction

        field_normalizers = {
            'low_stock_threshold': lambda value: max(0, int(value)),
            'allow_backorder': bool,
            'max_backorder_quantity': lambda value: max(0, int(value)),
        }
        for field_name, normalizer in field_normalizers.items():
            if field_name in pending:
                setattr(inventory_map[target_location], field_name, normalizer(pending[field_name]))
                changed_inventories.add(target_location)

        if changed_inventories:
            for location in changed_inventories:
                inventory_map[location].save()
            self._clear_inventory_cache()

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
        inventory = self._get_inventory_values()
        if inventory['stock_quantity'] == 0:
            return 'backorder' if inventory['allow_backorder'] else 'out_of_stock'
        if inventory['stock_quantity'] <= inventory['low_stock_threshold']:
            return 'low_stock'
        return 'in_stock'

    @property
    def available_quantity(self):
        """Return the total purchasable quantity, including backorder allowance."""
        if self.has_variants:
            return sum(variant.available_quantity for variant in self.variants.filter(is_active=True))
        inventory = self._get_inventory_values()
        if inventory['allow_backorder']:
            return inventory['stock_quantity'] + inventory['max_backorder_quantity']
        return inventory['stock_quantity']

    @property
    def can_purchase(self):
        """Return True if the product is active and has available stock."""
        return self.is_active and self.available_quantity > 0

    @property
    def stock_source(self):
        return self._get_inventory_values()['stock_source']

    @stock_source.setter
    def stock_source(self, value):
        self._set_inventory_value('stock_source', value)

    @property
    def stock_quantity(self):
        return self._get_inventory_values()['stock_quantity']

    @stock_quantity.setter
    def stock_quantity(self, value):
        self._set_inventory_value('stock_quantity', max(0, int(value)))

    @property
    def low_stock_threshold(self):
        return self._get_inventory_values()['low_stock_threshold']

    @low_stock_threshold.setter
    def low_stock_threshold(self, value):
        self._set_inventory_value('low_stock_threshold', max(0, int(value)))

    @property
    def allow_backorder(self):
        return self._get_inventory_values()['allow_backorder']

    @allow_backorder.setter
    def allow_backorder(self, value):
        self._set_inventory_value('allow_backorder', bool(value))

    @property
    def max_backorder_quantity(self):
        return self._get_inventory_values()['max_backorder_quantity']

    @max_backorder_quantity.setter
    def max_backorder_quantity(self, value):
        self._set_inventory_value('max_backorder_quantity', max(0, int(value)))

    @property
    def has_variants(self):
        """Return True if the product has at least one active variant."""
        if hasattr(self, '_prefetched_objects_cache') and 'variants' in self._prefetched_objects_cache:
            return any(variant.is_active for variant in self._prefetched_objects_cache['variants'])
        return self.variants.filter(is_active=True).exists()

    @property
    def average_rating(self):
        """Return the average rating from approved reviews, rounded to 1 decimal."""
        annotated_average = getattr(self, 'approved_average_rating', None)
        if annotated_average is not None:
            return round(annotated_average, 1) if annotated_average else 0.0
        from django.db.models import Avg
        reviews = self.reviews.filter(is_approved=True)
        if reviews.exists():
            result = reviews.aggregate(avg=Avg('rating'))['avg']
            return round(result, 1) if result else 0.0
        return 0.0

    @property
    def review_count(self):
        """Return the count of approved reviews for this product."""
        annotated_count = getattr(self, 'approved_review_count', None)
        if annotated_count is not None:
            return annotated_count
        return self.reviews.filter(is_approved=True).count()


class ProductInventory(models.Model):
    """Current inventory snapshot for a product location."""

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='inventories')
    location = models.CharField(max_length=20, choices=Product.INVENTORY_LOCATION_CHOICES, default=Product.STOCK_BRANCH)
    source_name = models.CharField(max_length=120, blank=True)
    stock_quantity = models.PositiveIntegerField(default=0)
    low_stock_threshold = models.PositiveIntegerField(default=0)
    allow_backorder = models.BooleanField(default=False)
    max_backorder_quantity = models.PositiveIntegerField(default=0)
    next_restock_date = models.DateField(null=True, blank=True)
    is_pos_synced = models.BooleanField(default=False)
    last_synced_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['product_id', 'location']
        constraints = [
            models.UniqueConstraint(fields=['product', 'location'], name='unique_product_inventory_location'),
        ]
        indexes = [
            models.Index(fields=['location']),
        ]

    def __str__(self):
        return f"{self.get_location_display()} inventory for {self.product.name}"

    @property
    def quantity_on_hand(self):
        return self.stock_quantity

    def save(self, *args, **kwargs):
        """Persist a location inventory row."""
        if self.location == Product.STOCK_WAREHOUSE and not self.source_name:
            self.source_name = 'POS Store'
        if self.location == Product.STOCK_BRANCH:
            self.source_name = ''
        super().save(*args, **kwargs)


def annotate_product_inventory(queryset):
    branch_filter = models.Q(inventories__location=Product.STOCK_BRANCH)
    warehouse_filter = models.Q(inventories__location=Product.STOCK_WAREHOUSE)
    queryset = queryset.annotate(
        branch_stock_quantity=Coalesce(models.Sum('inventories__stock_quantity', filter=branch_filter), 0),
        warehouse_stock_quantity=Coalesce(models.Sum('inventories__stock_quantity', filter=warehouse_filter), 0),
        total_low_stock_threshold=Coalesce(models.Sum('inventories__low_stock_threshold'), 0),
        total_max_backorder_quantity=Coalesce(models.Sum('inventories__max_backorder_quantity'), 0),
        backorder_inventory_count=Coalesce(
            models.Count('inventories', filter=models.Q(inventories__allow_backorder=True), distinct=True),
            0,
        ),
    )
    return queryset.annotate(
        total_stock_quantity=models.F('branch_stock_quantity') + models.F('warehouse_stock_quantity'),
        has_backorder_inventory=models.Case(
            models.When(backorder_inventory_count__gt=0, then=models.Value(True)),
            default=models.Value(False),
            output_field=models.BooleanField(),
        ),
    )


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
    barcode = models.CharField(max_length=64, blank=True)
    pos_product_id = models.CharField(max_length=80, blank=True)
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
    image = models.ImageField(upload_to='promotions/', blank=True, null=True)
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

    @staticmethod
    def format_badge_value(value):
        normalized = Decimal(value)
        if normalized == normalized.to_integral():
            return str(int(normalized))
        return format(normalized.normalize(), 'f').rstrip('0').rstrip('.')

    def build_badge(self):
        value = self.format_badge_value(self.value)
        if self.type == self.TYPE_PERCENTAGE:
            return f'{value}% Off'
        return f'KSh {value} Off'

    def save(self, *args, **kwargs):
        self.badge = self.build_badge()
        super().save(*args, **kwargs)

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

    SOURCE_MANUAL = 'manual'
    SOURCE_POS_SYNC = 'pos_sync'
    SOURCE_WEBHOOK = 'webhook'
    SOURCE_ORDER = 'order'
    SOURCE_SYSTEM = 'system'
    SOURCE_CHOICES = [
        (SOURCE_MANUAL, 'Manual'),
        (SOURCE_POS_SYNC, 'POS Sync'),
        (SOURCE_WEBHOOK, 'Webhook'),
        (SOURCE_ORDER, 'Order'),
        (SOURCE_SYSTEM, 'System'),
    ]

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='stock_movements')
    movement_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default=SOURCE_MANUAL)
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
            models.Index(fields=['source', '-created_at']),
        ]

    def __str__(self):
        return f"{self.movement_type} {self.quantity_change:+d} for {self.product.name}"
