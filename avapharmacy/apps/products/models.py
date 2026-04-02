"""
Database models for the products app.

Defines the product catalog: Category, Brand, Product, ProductImage,
Variant, VariantReview, Wishlist, Banner, Promotion, and CMSBlock.
"""
from decimal import Decimal
import re

from django.conf import settings
from django.db import models
from django.db.models import Q, Value
from django.db.models.functions import Coalesce, Lower
from django.utils import timezone
from django.utils.text import slugify


GENERIC_PRODUCT_SUFFIX_WORDS = {
    'tablet', 'tablets', 'capsule', 'capsules', 'caplet', 'caplets', 'syrup', 'syrups',
    'cream', 'creams', 'ointment', 'gel', 'gels', 'lotion', 'lotions', 'solution',
    'solutions', 'liquid', 'liquids', 'drop', 'drops', 'spray', 'sprays', 'powder',
    'powders', 'softgel', 'softgels', 'lozenge', 'lozenges', 'effervescent',
    'inhaler', 'inhalers', 'mask', 'masks', 'bundle', 'bundles', 'pack', 'packs',
    'sheet', 'sheets', 'starter', 'kit', 'kits', 'monitor', 'monitors',
}

GENERIC_PRODUCT_MODIFIERS = {
    'extra', 'normal', 'original', 'advance', 'advanced', 'plus', 'max', 'flu', 'gone',
    'cough', 'cold', 'day', 'night', 'honey', 'lemon', 'repair', 'protect',
}

DOSAGE_TOKEN_RE = re.compile(
    r'^(?:(?:\d+(?:[./+]\d+)*(?:mg|mcg|g|kg|ml|l|%|iu|spf))(?:/\d+(?:[./+]\d+)*(?:mg|mcg|g|kg|ml|l|%|iu|spf))*|\d+(?:s|pcs|pc))$',
    re.IGNORECASE,
)


def normalize_generic_product_name(name):
    text = re.sub(r'\s+', ' ', str(name or '')).strip()
    if not text:
        return ''

    text = re.sub(r'\([^)]*\)$', '', text).strip()
    tokens = text.split()
    while tokens:
        token = tokens[-1].strip(",").lower()
        if DOSAGE_TOKEN_RE.match(token):
            tokens.pop()
            continue
        if token in GENERIC_PRODUCT_SUFFIX_WORDS:
            tokens.pop()
            continue
        break

    while len(tokens) > 1 and tokens[-1].lower() in GENERIC_PRODUCT_MODIFIERS:
        tokens.pop()

    normalized = ' '.join(tokens).strip()
    return normalized or text


def generate_internal_product_sku(name, *, exclude_pk=None):
    base_slug = slugify(name or 'product').replace('-', '').upper() or 'PRODUCT'
    base_code = f'PRD-{base_slug[:24]}'
    candidate = base_code
    counter = 2

    queryset = Product.objects.all()
    if exclude_pk is not None:
        queryset = queryset.exclude(pk=exclude_pk)

    while queryset.filter(sku=candidate).exists():
        candidate = f'{base_code[:20]}-{counter}'
        counter += 1
    return candidate


class Category(models.Model):
    """A product category."""

    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)
    parent = models.ForeignKey(
        'self', null=True, blank=True, on_delete=models.SET_NULL, related_name='child_categories'
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
        db_table = 'prodcut_variants_categories'
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


class Subcategory(models.Model):
    """A subcategory that belongs to a Category."""

    category = models.ForeignKey(
        Category, on_delete=models.CASCADE, related_name='subcategories'
    )
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True, max_length=200)
    image = models.ImageField(upload_to='categories/', blank=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='created_subcategories')
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='updated_subcategories')

    class Meta:
        db_table = 'product_variants_subcategories'
        verbose_name_plural = 'subcategories'
        ordering = ['category__name', 'name']
        indexes = [
            models.Index(fields=['category', 'is_active']),
        ]
        constraints = [
            models.UniqueConstraint(
                Lower('name'),
                models.F('category'),
                name='unique_subcategory_name_per_category_ci',
            ),
        ]

    def __str__(self):
        return f'{self.category.name} / {self.name}'

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(f'{self.category.name}-{self.name}') or 'subcategory'
            slug = base
            counter = 2
            while Subcategory.objects.exclude(pk=self.pk).filter(slug=slug).exists():
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

    Acts as a catalog parent for sellable variants.
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
    LEGACY_VARIANT_FIELD_NAMES = {
        'strength',
        'category',
        'category_id',
        'subcategory',
        'subcategory_id',
        'health_concerns',
        'price',
        'cost_price',
        'short_description',
        'description',
        'features',
        'directions',
        'warnings',
        'dosage_quantity',
        'dosage_unit',
        'dosage_frequency',
        'dosage_notes',
        'requires_prescription',
    }

    sku = models.CharField(max_length=50, unique=True)
    barcode = models.CharField(max_length=64, blank=True)
    pos_product_id = models.CharField(max_length=80, blank=True)
    slug = models.SlugField(unique=True, max_length=200)
    name = models.CharField(max_length=200)
    brand = models.ForeignKey(Brand, on_delete=models.SET_NULL, null=True, blank=True, related_name='products')
    image = models.ImageField(upload_to='products/', blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='created_products')
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='updated_products')

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['brand', 'is_active']),
            models.Index(fields=['is_active', 'created_at']),
        ]

    def __init__(self, *args, **kwargs):
        legacy_variant_values = {}
        for field_name in self.LEGACY_VARIANT_FIELD_NAMES:
            if field_name in kwargs:
                legacy_variant_values[field_name] = kwargs.pop(field_name)
        super().__init__(*args, **kwargs)
        self._pending_variant_seed = legacy_variant_values

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
        rows = []
        for variant in self.get_active_variants():
            rows.extend(variant._get_inventory_rows())
        return rows

    def _get_inventory_map(self):
        location_map = {
            location: self._inventory_defaults(location).copy()
            for location in dict(self.INVENTORY_LOCATION_CHOICES)
        }
        for inventory in self._get_inventory_rows():
            row = location_map.setdefault(inventory.location, self._inventory_defaults(inventory.location).copy())
            row['stock_quantity'] += inventory.stock_quantity
            row['low_stock_threshold'] += inventory.low_stock_threshold
            row['allow_backorder'] = row['allow_backorder'] or inventory.allow_backorder
            row['max_backorder_quantity'] += inventory.max_backorder_quantity
        return location_map

    def _clear_inventory_cache(self):
        if hasattr(self, '_prefetched_objects_cache') and 'variants' in self._prefetched_objects_cache:
            del self._prefetched_objects_cache['variants']

    def _get_location_inventory_values(self):
        values = {
            location: self._inventory_defaults(location).copy()
            for location in dict(self.INVENTORY_LOCATION_CHOICES)
        }
        for location, inventory in self._get_inventory_map().items():
            values[location].update(inventory)
        return values

    def _get_inventory_values(self):
        annotated_total = getattr(self, 'total_stock_quantity', None)
        annotated_threshold = getattr(self, 'total_low_stock_threshold', None)
        annotated_backorder = getattr(self, 'has_backorder_inventory', None)
        annotated_max_backorder = getattr(self, 'total_max_backorder_quantity', None)

        if annotated_total is not None:
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
        return values

    def _set_inventory_value(self, field_name, value):
        # Product-level inventory writes are disabled. Stock is derived from variants only.
        return None

    def _get_variant_seed(self):
        return getattr(self, '_pending_variant_seed', {})

    def _set_variant_seed_value(self, field_name, value):
        pending = self._get_variant_seed().copy()
        pending[field_name] = value
        self._pending_variant_seed = pending

    def _representative_variant_value(self, field_name, default=None):
        variant = self.get_representative_variant()
        if variant is None:
            return default
        return getattr(variant, field_name, default)

    def _variant_relation_id(self, field_name):
        relation = self._representative_variant_value(field_name)
        return getattr(relation, 'id', None) if relation is not None else None

    def _default_variant_name(self):
        strength = (self._get_variant_seed().get('strength') or '').strip()
        return strength or 'Standard'

    def _sync_pending_variant_seed(self):
        pending = self._get_variant_seed().copy()
        if not pending or self.pk is None:
            return

        variant = self.get_representative_variant()
        if variant is None:
            variant = Variant(
                product=self,
                sku=self.sku,
                barcode=self.barcode,
                pos_product_id=self.pos_product_id,
                name=self._default_variant_name(),
                price=pending.get('price') or Decimal('0.00'),
                is_active=self.is_active,
            )

        m2m_health_concerns = pending.pop('health_concerns', None)

        for relation_name in ('category', 'subcategory'):
            relation_id_name = f'{relation_name}_id'
            if relation_id_name in pending and relation_name not in pending:
                setattr(variant, relation_id_name, pending.pop(relation_id_name))

        for field_name, value in pending.items():
            setattr(variant, field_name, value)

        if not variant.name:
            variant.name = self._default_variant_name()
        if not variant.sku:
            variant.sku = self.sku

        variant.save()

        if m2m_health_concerns is not None:
            variant.health_concerns.set(m2m_health_concerns)

        self._pending_variant_seed = {}

    def save(self, *args, **kwargs):
        """Auto-generate slug and persist catalog fields only."""
        self.name = normalize_generic_product_name(self.name)
        if not self.slug:
            self.slug = slugify(self.name)
        if not self.sku:
            self.sku = generate_internal_product_sku(self.name, exclude_pk=self.pk)

        original_update_fields = kwargs.get('update_fields')
        if original_update_fields is not None:
            update_fields = set(original_update_fields)
            kwargs['update_fields'] = [field for field in update_fields if field not in self.INVENTORY_FIELD_NAMES]
            if not kwargs['update_fields']:
                kwargs.pop('update_fields')

        if self.pk is None or original_update_fields is None or bool(kwargs.get('update_fields')):
            super().save(*args, **kwargs)
        self._sync_pending_variant_seed()

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
    def uses_variant_inventory(self):
        """Return True when stock should be managed through variants only."""
        return self.has_variants

    @property
    def average_rating(self):
        """Return the average rating from approved reviews, rounded to 1 decimal."""
        annotated_average = getattr(self, 'approved_average_rating', None)
        if annotated_average is not None:
            return round(annotated_average, 1) if annotated_average else 0.0
        from django.db.models import Avg
        reviews = VariantReview.objects.filter(variant__product=self, is_approved=True)
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
        return VariantReview.objects.filter(variant__product=self, is_approved=True).count()

    def get_active_variants(self):
        """Return active variants ordered for presentation and fallback logic."""
        if hasattr(self, '_prefetched_objects_cache') and 'variants' in self._prefetched_objects_cache:
            variants = [variant for variant in self._prefetched_objects_cache['variants'] if variant.is_active]
            return sorted(variants, key=lambda variant: (variant.sort_order, variant.name, variant.pk or 0))
        return list(self.variants.filter(is_active=True).order_by('sort_order', 'name', 'pk'))

    def get_representative_variant(self):
        """Return the lead active variant used for derived display fields."""
        variants = self.get_active_variants()
        return variants[0] if variants else None

    def get_display_sku(self):
        """Return the lead variant SKU for API/display usage."""
        variant = self.get_representative_variant()
        if variant and variant.sku:
            return variant.sku
        return self.sku

    def get_pricing_variant(self):
        """Return the active variant that drives product-level display pricing."""
        return self.get_representative_variant()

    def has_prescription_required_variant(self):
        active_variants = self.get_active_variants()
        return any(variant.requires_prescription for variant in active_variants)

    def get_health_concerns(self):
        active_variants = self.get_active_variants()
        variant_ids = [variant.id for variant in active_variants if variant.id]
        if variant_ids:
            return HealthConcern.objects.filter(variants__id__in=variant_ids).distinct().order_by('name')
        return HealthConcern.objects.none()

    @property
    def display_price(self):
        variant = self.get_pricing_variant()
        return variant.price if variant and variant.price is not None else Decimal('0.00')

    @property
    def display_cost_price(self):
        variant = self.get_pricing_variant()
        return variant.cost_price if variant else None

    @property
    def strength(self):
        return self._representative_variant_value('strength', '')

    @strength.setter
    def strength(self, value):
        self._set_variant_seed_value('strength', value)

    @property
    def category(self):
        return self._representative_variant_value('category')

    @category.setter
    def category(self, value):
        self._set_variant_seed_value('category', value)

    @property
    def category_id(self):
        return self._variant_relation_id('category')

    @category_id.setter
    def category_id(self, value):
        self._set_variant_seed_value('category_id', value)

    @property
    def subcategory(self):
        return self._representative_variant_value('subcategory')

    @subcategory.setter
    def subcategory(self, value):
        self._set_variant_seed_value('subcategory', value)

    @property
    def subcategory_id(self):
        return self._variant_relation_id('subcategory')

    @subcategory_id.setter
    def subcategory_id(self, value):
        self._set_variant_seed_value('subcategory_id', value)

    @property
    def health_concerns(self):
        return self.get_health_concerns()

    @health_concerns.setter
    def health_concerns(self, value):
        self._set_variant_seed_value('health_concerns', value)

    @property
    def price(self):
        return self.display_price

    @price.setter
    def price(self, value):
        self._set_variant_seed_value('price', value)

    @property
    def cost_price(self):
        return self.display_cost_price

    @cost_price.setter
    def cost_price(self, value):
        self._set_variant_seed_value('cost_price', value)

    @property
    def short_description(self):
        return self._representative_variant_value('short_description', '')

    @short_description.setter
    def short_description(self, value):
        self._set_variant_seed_value('short_description', value)

    @property
    def description(self):
        return self._representative_variant_value('description', '')

    @description.setter
    def description(self, value):
        self._set_variant_seed_value('description', value)

    @property
    def features(self):
        return self._representative_variant_value('features', [])

    @features.setter
    def features(self, value):
        self._set_variant_seed_value('features', value)

    @property
    def directions(self):
        return self._representative_variant_value('directions', '')

    @directions.setter
    def directions(self, value):
        self._set_variant_seed_value('directions', value)

    @property
    def warnings(self):
        return self._representative_variant_value('warnings', '')

    @warnings.setter
    def warnings(self, value):
        self._set_variant_seed_value('warnings', value)

    @property
    def dosage_quantity(self):
        return self._representative_variant_value('dosage_quantity', '')

    @dosage_quantity.setter
    def dosage_quantity(self, value):
        self._set_variant_seed_value('dosage_quantity', value)

    @property
    def dosage_unit(self):
        return self._representative_variant_value('dosage_unit', '')

    @dosage_unit.setter
    def dosage_unit(self, value):
        self._set_variant_seed_value('dosage_unit', value)

    @property
    def dosage_frequency(self):
        return self._representative_variant_value('dosage_frequency', '')

    @dosage_frequency.setter
    def dosage_frequency(self, value):
        self._set_variant_seed_value('dosage_frequency', value)

    @property
    def dosage_notes(self):
        return self._representative_variant_value('dosage_notes', '')

    @dosage_notes.setter
    def dosage_notes(self, value):
        self._set_variant_seed_value('dosage_notes', value)

    @property
    def requires_prescription(self):
        return self.has_prescription_required_variant()

    @requires_prescription.setter
    def requires_prescription(self, value):
        self._set_variant_seed_value('requires_prescription', value)


def annotate_product_inventory(queryset):
    branch_filter = models.Q(variants__is_active=True, variants__inventories__location=Product.STOCK_BRANCH)
    warehouse_filter = models.Q(variants__is_active=True, variants__inventories__location=Product.STOCK_WAREHOUSE)
    queryset = queryset.annotate(
        branch_stock_quantity=Coalesce(models.Sum('variants__inventories__stock_quantity', filter=branch_filter), 0),
        warehouse_stock_quantity=Coalesce(models.Sum('variants__inventories__stock_quantity', filter=warehouse_filter), 0),
        total_low_stock_threshold=Coalesce(models.Sum('variants__inventories__low_stock_threshold', filter=models.Q(variants__is_active=True)), 0),
        total_max_backorder_quantity=Coalesce(models.Sum('variants__inventories__max_backorder_quantity', filter=models.Q(variants__is_active=True)), 0),
        backorder_inventory_count=Coalesce(
            models.Count('variants__inventories', filter=models.Q(variants__is_active=True, variants__inventories__allow_backorder=True), distinct=True),
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


def annotate_variant_inventory(queryset):
    branch_filter = models.Q(inventories__location=Product.STOCK_BRANCH)
    warehouse_filter = models.Q(inventories__location=Product.STOCK_WAREHOUSE)
    queryset = queryset.annotate(
        branch_stock_quantity=Coalesce(models.Sum('inventories__stock_quantity', filter=branch_filter), 0),
        warehouse_stock_quantity=Coalesce(models.Sum('inventories__stock_quantity', filter=warehouse_filter), 0),
        low_stock_threshold=Coalesce(models.Sum('inventories__low_stock_threshold'), 0),
        max_backorder_quantity=Coalesce(models.Sum('inventories__max_backorder_quantity'), 0),
        backorder_inventory_count=Coalesce(
            models.Count('inventories', filter=models.Q(inventories__allow_backorder=True), distinct=True),
            0,
        ),
    )
    return queryset.annotate(
        stock_quantity=models.F('branch_stock_quantity') + models.F('warehouse_stock_quantity'),
        allow_backorder=models.Case(
            models.When(backorder_inventory_count__gt=0, then=models.Value(True)),
            default=models.Value(False),
            output_field=models.BooleanField(),
        ),
        stock_source=models.Case(
            models.When(branch_stock_quantity__gt=0, then=models.Value(Product.STOCK_BRANCH)),
            models.When(warehouse_stock_quantity__gt=0, then=models.Value(Product.STOCK_WAREHOUSE)),
            default=models.Value(Product.STOCK_OUT),
            output_field=models.CharField(max_length=20),
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


class Variant(models.Model):
    """A specific variant of a product (e.g. size, colour, strength).

    Maintains its own SKU and price.
    """

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='variants')
    sku = models.CharField(max_length=60, unique=True)
    barcode = models.CharField(max_length=64, blank=True)
    pos_product_id = models.CharField(max_length=80, blank=True)
    name = models.CharField(max_length=120)
    strength = models.CharField(max_length=50, blank=True, help_text="e.g. 500mg, 10mg/5ml, 2%")
    category = models.ForeignKey(
        Category, on_delete=models.SET_NULL, null=True, blank=True, related_name='variants'
    )
    subcategory = models.ForeignKey(
        Subcategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='variants_as_subcategory',
    )
    health_concerns = models.ManyToManyField(HealthConcern, blank=True, related_name='variants')
    short_description = models.CharField(max_length=500, blank=True)
    description = models.TextField(blank=True)
    features = models.JSONField(default=list, blank=True)
    dosage_instructions = models.TextField(blank=True)
    directions = models.TextField(blank=True)
    warnings = models.TextField(blank=True)
    dosage_quantity = models.CharField(max_length=20, blank=True, help_text="e.g. 1, 2, 1-2")
    dosage_unit = models.CharField(max_length=30, blank=True, help_text="e.g. tablet, capsule, ml, drop")
    dosage_frequency = models.CharField(max_length=50, blank=True, help_text="e.g. once_daily, twice_daily")
    dosage_notes = models.CharField(max_length=150, blank=True, help_text="e.g. with food, before meals")
    attributes = models.JSONField(default=dict, blank=True)  # e.g. {"size": "500mg"}
    price = models.DecimalField(max_digits=10, decimal_places=2)
    cost_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    original_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    image = models.ImageField(upload_to='products/variants/', blank=True)
    requires_prescription = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'products_variant'
        ordering = ['sort_order', 'name']
        indexes = [
            models.Index(fields=['product', 'is_active']),
            models.Index(fields=['category', 'is_active']),
            models.Index(fields=['subcategory', 'is_active']),
        ]

    INVENTORY_FIELD_NAMES = {
        'stock_source',
        'stock_quantity',
        'low_stock_threshold',
        'allow_backorder',
        'max_backorder_quantity',
    }

    def __str__(self):
        return f"{self.product.name} - {self.name}"

    @property
    def brand(self):
        return self.product.brand

    @property
    def brand_id(self):
        return self.product.brand_id

    def _inventory_defaults(self, location=None):
        return {
            'stock_quantity': 0,
            'low_stock_threshold': 5 if location != Product.STOCK_WAREHOUSE else 0,
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
            VariantInventory(
                variant=self,
                location=location,
                **self._inventory_defaults(location),
            )
            for location in dict(Product.INVENTORY_LOCATION_CHOICES)
            if location not in inventory_map
        ]
        if missing_rows:
            VariantInventory.objects.bulk_create(missing_rows)
            self._clear_inventory_cache()
            inventory_map = self._get_inventory_map()
        return inventory_map

    def _get_location_inventory_values(self):
        values = {
            location: self._inventory_defaults(location).copy()
            for location in dict(Product.INVENTORY_LOCATION_CHOICES)
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
        location_values = self._get_location_inventory_values()
        stock_source = Product.STOCK_OUT
        if location_values[Product.STOCK_BRANCH]['stock_quantity'] > 0:
            stock_source = Product.STOCK_BRANCH
        elif location_values[Product.STOCK_WAREHOUSE]['stock_quantity'] > 0:
            stock_source = Product.STOCK_WAREHOUSE

        values = {
            'stock_source': stock_source,
            'stock_quantity': sum(item['stock_quantity'] for item in location_values.values()),
            'low_stock_threshold': sum(item['low_stock_threshold'] for item in location_values.values()),
            'allow_backorder': any(item['allow_backorder'] for item in location_values.values()),
            'max_backorder_quantity': sum(item['max_backorder_quantity'] for item in location_values.values()),
        }
        if 'stock_source' in pending and pending['stock_source'] in dict(Product.INVENTORY_LOCATION_CHOICES):
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

    def _apply_pending_inventory_updates(self, inventory_map, pending):
        location_choices = dict(Product.INVENTORY_LOCATION_CHOICES)
        target_location = pending.get('stock_source')
        current_source = self._get_inventory_values()['stock_source']
        if target_location not in location_choices:
            target_location = current_source if current_source in location_choices else Product.STOCK_BRANCH

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

    def save(self, *args, **kwargs):
        """Persist variant inventory and keep parent display fields in sync."""
        original_update_fields = kwargs.get('update_fields')
        inventory_update_fields = set()
        if original_update_fields is not None:
            update_fields = set(original_update_fields)
            inventory_update_fields = update_fields & self.INVENTORY_FIELD_NAMES
            model_update_fields = update_fields - self.INVENTORY_FIELD_NAMES
            if model_update_fields:
                kwargs['update_fields'] = list(model_update_fields)
            else:
                kwargs.pop('update_fields')

        pending = getattr(self, '_pending_inventory_updates', {}).copy()
        if not self.pk and not pending:
            pending = {
                'stock_source': Product.STOCK_BRANCH,
                'stock_quantity': 0,
                'low_stock_threshold': 5,
                'allow_backorder': False,
                'max_backorder_quantity': 0,
            }

        should_save_variant = self.pk is None or original_update_fields is None or bool(kwargs.get('update_fields'))
        if should_save_variant:
            super().save(*args, **kwargs)

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

    @property
    def effective_price(self):
        """Return this variant's price."""
        return self.price

    @property
    def inventory_status(self):
        """Return the inventory status string for this variant.

        Returns:
            str: One of 'inactive', 'backorder', 'out_of_stock', 'low_stock', 'in_stock'.
        """
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
        """Return purchasable quantity including backorder allowance."""
        inventory = self._get_inventory_values()
        if inventory['allow_backorder']:
            return inventory['stock_quantity'] + inventory['max_backorder_quantity']
        return inventory['stock_quantity']

    @property
    def inventories_summary(self):
        return self._get_location_inventory_values()


class VariantInventory(models.Model):
    """Current inventory snapshot for a variant location."""

    variant = models.ForeignKey(Variant, on_delete=models.CASCADE, related_name='inventories')
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
        ordering = ['variant_id', 'location']
        constraints = [
            models.UniqueConstraint(fields=['variant', 'location'], name='unique_variant_inventory_location'),
        ]
        indexes = [
            models.Index(fields=['location']),
        ]

    def __str__(self):
        return f"{self.get_location_display()} inventory for {self.variant}"

    @property
    def quantity_on_hand(self):
        return self.stock_quantity

    def save(self, *args, **kwargs):
        if self.location == Product.STOCK_WAREHOUSE and not self.source_name:
            self.source_name = 'POS Store'
        if self.location == Product.STOCK_BRANCH:
            self.source_name = ''
        super().save(*args, **kwargs)


class VariantReview(models.Model):
    """A customer review (1-5 star rating) for a variant."""

    variant = models.ForeignKey(Variant, on_delete=models.CASCADE, related_name='reviews', null=True, blank=True)
    user = models.ForeignKey('accounts.User', on_delete=models.CASCADE, related_name='reviews')
    rating = models.PositiveSmallIntegerField()
    comment = models.TextField(blank=True)
    is_approved = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('variant', 'user')
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.full_name} - {self.variant} ({self.rating})"

    @property
    def product(self):
        return self.variant.product

    @product.setter
    def product(self, value):
        if value is None:
            self.variant = None
            return
        self.variant = value.get_representative_variant()


class Wishlist(models.Model):
    """A saved variant on a user's wishlist."""

    user = models.ForeignKey('accounts.User', on_delete=models.CASCADE, related_name='wishlist')
    variant = models.ForeignKey(Variant, on_delete=models.CASCADE, related_name='wishlisted_by', null=True, blank=True)
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'variant')
        ordering = ['-added_at']

    def __str__(self):
        return f"{self.user.full_name} - {self.variant}"

    @property
    def product(self):
        return self.variant.product

    @product.setter
    def product(self, value):
        if value is None:
            self.variant = None
            return
        self.variant = value.get_representative_variant()


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
            variant_skus = {variant.sku for variant in product.get_active_variants() if variant.sku}
            return (
                str(product.id) in targets
                or product.slug in targets
                or product.get_display_sku() in targets
                or bool(variant_skus.intersection(targets))
            )
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
    """Audit trail for every stock level change on a variant inventory row."""

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

    variant_inventory = models.ForeignKey(VariantInventory, on_delete=models.CASCADE, related_name='stock_movements', null=True, blank=True)
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
            models.Index(fields=['variant_inventory', '-created_at']),
            models.Index(fields=['source', '-created_at']),
        ]

    def __str__(self):
        return f"{self.movement_type} {self.quantity_change:+d} for {self.variant_inventory.variant}"

    @property
    def variant(self):
        return self.variant_inventory.variant

    @property
    def product(self):
        return self.variant_inventory.variant.product
