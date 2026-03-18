"""
Serializers for the products app.

Covers Category, Brand, ProductImage, ProductVariant, ProductReview,
ProductList/Detail, Wishlist, Banner, Promotion, and CMSBlock serializers.
Pricing fields (final_price, discount_total, active_promotions) are computed
via the calculate_product_pricing service.
"""
import json

from rest_framework import serializers
from django.utils.text import slugify
from .models import Category, Brand, CMSBlock, HealthConcern, Product, ProductImage, ProductInventory, ProductReview, ProductVariant, StockMovement, Wishlist, Banner, Promotion
from .image_validators import validate_uploaded_image
from .services import calculate_product_pricing


class CategorySerializer(serializers.ModelSerializer):
    subcategories = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ('id', 'name', 'slug', 'image', 'description', 'icon', 'is_active', 'subcategories')
        extra_kwargs = {
            'slug': {'required': False, 'allow_blank': True},
        }

    def _generate_unique_slug(self, name):
        base_slug = slugify(name) or 'category'
        slug = base_slug
        queryset = Category.objects.all()
        if self.instance is not None:
            queryset = queryset.exclude(pk=self.instance.pk)

        counter = 2
        while queryset.filter(slug=slug).exists():
            slug = f'{base_slug}-{counter}'
            counter += 1
        return slug

    def validate(self, attrs):
        attrs = super().validate(attrs)
        provided_slug = attrs.get('slug')

        if self.instance is None and not provided_slug:
            attrs['slug'] = self._generate_unique_slug(attrs.get('name', ''))
        elif 'slug' in attrs and not provided_slug:
            attrs['slug'] = self._generate_unique_slug(attrs.get('name') or self.instance.name)

        return attrs

    def validate_name(self, value):
        parent = self.instance.parent if self.instance else None
        if hasattr(self, 'initial_data') and 'parent' in self.initial_data:
            parent = Category.objects.filter(pk=self.initial_data.get('parent')).first()
        queryset = Category.objects.filter(name__iexact=value, parent=parent)
        if self.instance is not None:
            queryset = queryset.exclude(pk=self.instance.pk)
        if queryset.exists():
            raise serializers.ValidationError('A category with this name already exists.')
        return value

    def get_subcategories(self, obj):
        if obj.parent is None:
            prefetched = getattr(obj, '_prefetched_objects_cache', {}).get('subcategories')
            subcategories = prefetched if prefetched is not None else obj.subcategories.all()
            return CategorySerializer([item for item in subcategories if item.is_active], many=True).data
        return []


class ProductSubcategorySerializer(serializers.ModelSerializer):
    category = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.filter(parent__isnull=True),
        source='parent',
    )
    category_name = serializers.ReadOnlyField(source='parent.name')

    class Meta:
        model = Category
        fields = ('id', 'name', 'slug', 'category', 'category_name', 'image', 'description', 'is_active', 'created_at')
        extra_kwargs = {'slug': {'required': False, 'allow_blank': True}}

    def validate_name(self, value):
        parent_id = self.initial_data.get('category')
        qs = Category.objects.filter(parent_id=parent_id, name__iexact=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError('A subcategory with this name already exists in the selected category.')
        return value


class ProductCategorySerializer(serializers.ModelSerializer):
    subcategories = ProductSubcategorySerializer(many=True, read_only=True)

    class Meta:
        model = Category
        fields = ('id', 'name', 'slug', 'image', 'description', 'icon', 'is_active', 'created_at', 'subcategories')
        extra_kwargs = {'slug': {'required': False, 'allow_blank': True}}

    def validate(self, attrs):
        attrs = super().validate(attrs)
        description = attrs.get('description')

        if self.instance is None and not str(description or '').strip():
            raise serializers.ValidationError({'description': ['Category description is required.']})
        if self.instance is not None and 'description' in attrs and not str(description or '').strip():
            raise serializers.ValidationError({'description': ['Category description is required.']})
        if self.instance is None and not attrs.get('image'):
            raise serializers.ValidationError({'image': ['Category image is required.']})
        if self.instance is not None and 'image' in attrs and not attrs.get('image'):
            raise serializers.ValidationError({'image': ['Category image is required.']})
        if attrs.get('image'):
            validate_uploaded_image(attrs['image'], 'category')
        return attrs

    def validate_name(self, value):
        qs = Category.objects.filter(parent__isnull=True, name__iexact=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError('A category with this name already exists.')
        return value


class HealthConcernSerializer(serializers.ModelSerializer):
    class Meta:
        model = HealthConcern
        fields = ('id', 'name', 'slug', 'description', 'icon', 'is_active', 'created_at')
        extra_kwargs = {'slug': {'required': False, 'allow_blank': True}}

    def validate_name(self, value):
        qs = HealthConcern.objects.filter(name__iexact=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError('A health concern with this name already exists.')
        return value


class StockMovementSerializer(serializers.ModelSerializer):
    created_by_name = serializers.SerializerMethodField()

    class Meta:
        model = StockMovement
        fields = (
            'id', 'movement_type', 'quantity_change', 'quantity_before', 'quantity_after',
            'reason', 'reference', 'created_at', 'updated_at', 'created_by', 'created_by_name',
        )

    def get_created_by_name(self, obj):
        if obj.created_by:
            return getattr(obj.created_by, 'full_name', '') or obj.created_by.email
        return 'system'


class BrandSerializer(serializers.ModelSerializer):
    class Meta:
        model = Brand
        fields = ('id', 'name', 'slug', 'logo', 'description', 'is_active')
        extra_kwargs = {'slug': {'required': False, 'allow_blank': True}}

    def _generate_unique_slug(self, name):
        base_slug = slugify(name) or 'brand'
        slug = base_slug
        queryset = Brand.objects.all()
        if self.instance is not None:
            queryset = queryset.exclude(pk=self.instance.pk)

        counter = 2
        while queryset.filter(slug=slug).exists():
            slug = f'{base_slug}-{counter}'
            counter += 1
        return slug

    def validate(self, attrs):
        attrs = super().validate(attrs)
        provided_slug = attrs.get('slug')
        has_logo_input = hasattr(self, 'initial_data') and 'logo' in self.initial_data

        if self.instance is None and not attrs.get('logo'):
            raise serializers.ValidationError({'logo': ['Brand logo is required.']})
        if self.instance is not None and has_logo_input and not attrs.get('logo'):
            raise serializers.ValidationError({'logo': ['Brand logo is required.']})
        if attrs.get('logo'):
            validate_uploaded_image(attrs['logo'], 'brand')

        if self.instance is None and not provided_slug:
            attrs['slug'] = self._generate_unique_slug(attrs.get('name', ''))
        elif 'slug' in attrs and not provided_slug:
            attrs['slug'] = self._generate_unique_slug(attrs.get('name') or self.instance.name)

        return attrs

    def validate_name(self, value):
        queryset = Brand.objects.filter(name__iexact=value)
        if self.instance is not None:
            queryset = queryset.exclude(pk=self.instance.pk)
        if queryset.exists():
            raise serializers.ValidationError('A brand with this name already exists.')
        return value


class ProductImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductImage
        fields = ('id', 'image', 'alt_text', 'order')


class ProductInventorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductInventory
        fields = (
            'id', 'location', 'source_name', 'stock_quantity', 'low_stock_threshold',
            'allow_backorder', 'max_backorder_quantity', 'is_pos_synced', 'last_synced_at',
            'created_at', 'updated_at',
        )
        read_only_fields = ('id', 'created_at', 'updated_at')


class ProductVariantSerializer(serializers.ModelSerializer):
    effective_price = serializers.ReadOnlyField()
    inventory_status = serializers.ReadOnlyField()
    available_quantity = serializers.ReadOnlyField()

    class Meta:
        model = ProductVariant
        fields = (
            'id', 'sku', 'name', 'attributes', 'price', 'original_price', 'effective_price',
            'image', 'stock_source', 'stock_quantity', 'low_stock_threshold',
            'allow_backorder', 'max_backorder_quantity', 'inventory_status',
            'available_quantity', 'is_active', 'sort_order', 'created_at', 'updated_at'
        )
        read_only_fields = ('id', 'created_at', 'updated_at', 'effective_price', 'inventory_status', 'available_quantity')


class ProductReviewSerializer(serializers.ModelSerializer):
    user_name = serializers.ReadOnlyField(source='user.full_name')

    class Meta:
        model = ProductReview
        fields = ('id', 'user', 'user_name', 'rating', 'comment', 'is_approved', 'created_at')
        read_only_fields = ('id', 'user', 'is_approved', 'created_at')

    def validate_rating(self, value):
        if not 1 <= value <= 5:
            raise serializers.ValidationError('Rating must be between 1 and 5.')
        return value


class ProductListSerializer(serializers.ModelSerializer):
    brand_name = serializers.ReadOnlyField(source='brand.name')
    brand_slug = serializers.ReadOnlyField(source='brand.slug')
    category_name = serializers.ReadOnlyField(source='category.name')
    category_slug = serializers.ReadOnlyField(source='category.slug')
    stock_source = serializers.ReadOnlyField()
    stock_quantity = serializers.ReadOnlyField()
    average_rating = serializers.ReadOnlyField()
    review_count = serializers.ReadOnlyField()
    inventory_status = serializers.ReadOnlyField()
    available_quantity = serializers.ReadOnlyField()
    can_purchase = serializers.ReadOnlyField()
    has_variants = serializers.ReadOnlyField()
    original_price = serializers.SerializerMethodField()
    final_price = serializers.SerializerMethodField()
    discount_total = serializers.SerializerMethodField()
    active_promotions = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = (
            'id', 'sku', 'slug', 'name', 'strength', 'brand_name', 'brand_slug',
            'category_name', 'category_slug', 'price', 'original_price',
            'image', 'badge', 'stock_source', 'stock_quantity',
            'short_description', 'average_rating', 'review_count',
            'requires_prescription', 'inventory_status', 'available_quantity',
            'can_purchase', 'final_price', 'discount_total', 'active_promotions',
            'has_variants', 'is_featured', 'is_active'
        )

    def _pricing(self, obj):
        pricing = getattr(obj, '_pricing_cache', None)
        if pricing is None:
            pricing = calculate_product_pricing(obj, promotions=self.context.get('active_promotions'))
            obj._pricing_cache = pricing
        return pricing

    def get_final_price(self, obj):
        return self._pricing(obj)['final_price']

    def get_original_price(self, obj):
        final_price = self._pricing(obj)['final_price']
        price = obj.price
        if final_price < price:
            return price
        return None

    def get_discount_total(self, obj):
        return self._pricing(obj)['discount_total']

    def get_active_promotions(self, obj):
        return self._pricing(obj)['promotions']


class ProductDetailSerializer(serializers.ModelSerializer):
    created_by_name = serializers.SerializerMethodField()
    brand = BrandSerializer(read_only=True)
    brand_id = serializers.PrimaryKeyRelatedField(
        queryset=Brand.objects.all(), source='brand', write_only=True, required=False, allow_null=True
    )
    category = CategorySerializer(read_only=True)
    category_id = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.filter(parent__isnull=True), source='category', write_only=True, required=False, allow_null=True
    )
    subcategory_id = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.exclude(parent__isnull=True), source='catalog_subcategory', write_only=True, required=False, allow_null=True
    )
    subcategory_name = serializers.ReadOnlyField(source='catalog_subcategory.name')
    health_concern_ids = serializers.PrimaryKeyRelatedField(
        queryset=HealthConcern.objects.all(), source='health_concerns', many=True, write_only=True, required=False
    )
    health_concerns = HealthConcernSerializer(many=True, read_only=True)
    gallery = ProductImageSerializer(many=True, read_only=True)
    inventories = ProductInventorySerializer(many=True, read_only=True)
    branch_inventory = serializers.JSONField(write_only=True, required=False)
    warehouse_inventory = serializers.JSONField(write_only=True, required=False)
    variants = ProductVariantSerializer(many=True, read_only=True)
    stock_source = serializers.ChoiceField(choices=Product.STOCK_CHOICES, required=False)
    stock_quantity = serializers.IntegerField(required=False, min_value=0)
    low_stock_threshold = serializers.IntegerField(required=False, min_value=0)
    allow_backorder = serializers.BooleanField(required=False)
    max_backorder_quantity = serializers.IntegerField(required=False, min_value=0)
    average_rating = serializers.ReadOnlyField()
    review_count = serializers.ReadOnlyField()
    inventory_status = serializers.ReadOnlyField()
    available_quantity = serializers.ReadOnlyField()
    can_purchase = serializers.ReadOnlyField()
    has_variants = serializers.ReadOnlyField()
    original_price = serializers.SerializerMethodField()
    final_price = serializers.SerializerMethodField()
    discount_total = serializers.SerializerMethodField()
    active_promotions = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = (
            'id', 'sku', 'slug', 'name', 'strength', 'brand', 'brand_id', 'category', 'category_id',
            'subcategory_id', 'subcategory_name', 'health_concerns', 'health_concern_ids',
            'price', 'original_price', 'image', 'gallery', 'inventories', 'variants',
            'branch_inventory', 'warehouse_inventory', 'badge', 'stock_source',
            'stock_quantity', 'low_stock_threshold', 'allow_backorder', 'max_backorder_quantity',
            'short_description', 'description', 'features', 'directions', 'warnings',
            'requires_prescription', 'inventory_status', 'available_quantity', 'can_purchase',
            'final_price', 'discount_total', 'active_promotions', 'has_variants', 'is_featured', 'is_active',
            'average_rating', 'review_count', 'created_at', 'updated_at', 'created_by', 'created_by_name'
        )
        read_only_fields = ('id', 'created_at', 'updated_at')
        extra_kwargs = {
            'slug': {'required': False, 'allow_blank': True},
        }

    def _generate_unique_slug(self, name):
        base_slug = slugify(name) or 'product'
        slug = base_slug
        queryset = Product.objects.all()
        if self.instance is not None:
            queryset = queryset.exclude(pk=self.instance.pk)

        counter = 2
        while queryset.filter(slug=slug).exists():
            slug = f'{base_slug}-{counter}'
            counter += 1
        return slug

    def _pricing(self, obj):
        pricing = getattr(obj, '_pricing_cache', None)
        if pricing is None:
            pricing = calculate_product_pricing(obj, promotions=self.context.get('active_promotions'))
            obj._pricing_cache = pricing
        return pricing

    def _inventory_defaults(self, location=None):
        return {
            'stock_quantity': 0,
            'low_stock_threshold': 5 if location != Product.STOCK_WAREHOUSE else 0,
            'allow_backorder': False,
            'max_backorder_quantity': 0,
        }

    def _validate_inventory_payload(self, value, location_label):
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except json.JSONDecodeError:
                raise serializers.ValidationError(f'{location_label} inventory must be a valid JSON object.')
        if not isinstance(value, dict):
            raise serializers.ValidationError(f'{location_label} inventory must be an object.')

        validated = {}
        integer_fields = ('stock_quantity', 'low_stock_threshold', 'max_backorder_quantity')
        for field_name in integer_fields:
            if field_name in value:
                try:
                    coerced = int(value[field_name])
                except (TypeError, ValueError):
                    raise serializers.ValidationError({field_name: ['A valid integer is required.']})
                if coerced < 0:
                    raise serializers.ValidationError({field_name: ['Ensure this value is greater than or equal to 0.']})
                validated[field_name] = coerced

        if 'allow_backorder' in value:
            raw_value = value['allow_backorder']
            if isinstance(raw_value, bool):
                validated['allow_backorder'] = raw_value
            else:
                validated['allow_backorder'] = str(raw_value).lower() in {'true', '1', 'yes', 'on'}

        return validated

    def _pop_inventory_data(self, validated_data):
        locations = {
            Product.STOCK_BRANCH: self._inventory_defaults(Product.STOCK_BRANCH),
            Product.STOCK_WAREHOUSE: self._inventory_defaults(Product.STOCK_WAREHOUSE),
        }

        if self.instance is not None:
            for inventory in self.instance.inventories.all():
                locations[inventory.location] = {
                    'stock_quantity': inventory.stock_quantity,
                    'low_stock_threshold': inventory.low_stock_threshold,
                    'allow_backorder': inventory.allow_backorder,
                    'max_backorder_quantity': inventory.max_backorder_quantity,
                }

        branch_payload = validated_data.pop('branch_inventory', None)
        if branch_payload:
            locations[Product.STOCK_BRANCH].update(branch_payload)

        warehouse_payload = validated_data.pop('warehouse_inventory', None)
        if warehouse_payload:
            locations[Product.STOCK_WAREHOUSE].update(warehouse_payload)

        flat_inventory_data = {}
        for field_name in ('stock_source', 'stock_quantity', 'low_stock_threshold', 'allow_backorder', 'max_backorder_quantity'):
            if field_name in validated_data:
                flat_inventory_data[field_name] = validated_data.pop(field_name)

        target_location = flat_inventory_data.pop('stock_source', None)
        if flat_inventory_data:
            if target_location not in dict(Product.INVENTORY_LOCATION_CHOICES):
                if self.instance is not None and self.instance.stock_source in dict(Product.INVENTORY_LOCATION_CHOICES):
                    target_location = self.instance.stock_source
                else:
                    target_location = Product.STOCK_BRANCH
            locations[target_location].update(flat_inventory_data)

        return locations

    def get_final_price(self, obj):
        return self._pricing(obj)['final_price']

    def get_original_price(self, obj):
        final_price = self._pricing(obj)['final_price']
        price = obj.price
        if final_price < price:
            return price
        return None

    def get_discount_total(self, obj):
        return self._pricing(obj)['discount_total']

    def get_active_promotions(self, obj):
        return self._pricing(obj)['promotions']

    def get_created_by_name(self, obj):
        if obj.created_by:
            return getattr(obj.created_by, 'full_name', '') or obj.created_by.email
        return 'system'

    def validate(self, attrs):
        attrs = super().validate(attrs)
        provided_slug = attrs.get('slug')
        if 'branch_inventory' in attrs:
            attrs['branch_inventory'] = self._validate_inventory_payload(attrs['branch_inventory'], 'Main shop')
        if 'warehouse_inventory' in attrs:
            attrs['warehouse_inventory'] = self._validate_inventory_payload(attrs['warehouse_inventory'], 'POS store')
        if self.instance is None and not provided_slug:
            attrs['slug'] = self._generate_unique_slug(attrs.get('name', ''))
        elif 'slug' in attrs and not provided_slug:
            attrs['slug'] = self._generate_unique_slug(attrs.get('name') or self.instance.name)
        if self.instance is None and not attrs.get('image'):
            raise serializers.ValidationError({'image': 'Product image is required.'})
        if attrs.get('image'):
            validate_uploaded_image(attrs['image'], 'product')
        return attrs

    def create(self, validated_data):
        inventory_data = self._pop_inventory_data(validated_data)
        health_concerns = validated_data.pop('health_concerns', [])
        product = Product.objects.create(**validated_data)
        if health_concerns:
            product.health_concerns.set(health_concerns)
        for location, defaults in inventory_data.items():
            ProductInventory.objects.update_or_create(
                product=product,
                location=location,
                defaults=defaults,
            )
        if hasattr(product, '_clear_inventory_cache'):
            product._clear_inventory_cache()
        return product

    def update(self, instance, validated_data):
        inventory_data = self._pop_inventory_data(validated_data)
        health_concerns = validated_data.pop('health_concerns', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if health_concerns is not None:
            instance.health_concerns.set(health_concerns)
        for location, defaults in inventory_data.items():
            ProductInventory.objects.update_or_create(
                product=instance,
                location=location,
                defaults=defaults,
            )
        if hasattr(instance, '_clear_inventory_cache'):
            instance._clear_inventory_cache()
        return instance


class AdminProductSerializer(ProductDetailSerializer):
    cost_price = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        required=False,
        allow_null=True,
    )
    discount_price = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        required=False,
        allow_null=True,
    )

    class Meta(ProductDetailSerializer.Meta):
        fields = (
            'id', 'sku', 'slug', 'name', 'strength', 'brand', 'brand_id', 'category', 'category_id',
            'subcategory_id', 'subcategory_name', 'health_concerns', 'health_concern_ids',
            'price', 'cost_price', 'discount_price', 'original_price', 'image', 'gallery', 'inventories', 'variants',
            'branch_inventory', 'warehouse_inventory', 'badge', 'stock_source',
            'stock_quantity', 'low_stock_threshold', 'allow_backorder', 'max_backorder_quantity',
            'short_description', 'description', 'features', 'directions', 'warnings',
            'requires_prescription', 'inventory_status', 'available_quantity', 'can_purchase',
            'final_price', 'discount_total', 'active_promotions', 'has_variants', 'is_featured', 'is_active',
            'average_rating', 'review_count', 'created_at', 'updated_at', 'created_by', 'created_by_name'
        )

    def validate(self, attrs):
        attrs = super().validate(attrs)

        price = attrs.get('price', getattr(self.instance, 'price', None))
        cost_price = attrs.get('cost_price', getattr(self.instance, 'cost_price', None))
        discount_price = attrs.get('discount_price', getattr(self.instance, 'discount_price', None))

        if cost_price is not None and price is not None and cost_price < 0:
            raise serializers.ValidationError({'cost_price': ['Ensure this value is greater than or equal to 0.']})

        if discount_price is not None:
            if discount_price < 0:
                raise serializers.ValidationError({'discount_price': ['Ensure this value is greater than or equal to 0.']})
            if price is not None and discount_price >= price:
                raise serializers.ValidationError({'discount_price': ['Discount price must be lower than the selling price.']})

        return attrs

class WishlistSerializer(serializers.ModelSerializer):
    product = ProductListSerializer(read_only=True)
    product_id = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.all(), source='product', write_only=True
    )

    class Meta:
        model = Wishlist
        fields = ('id', 'product', 'product_id', 'added_at')
        read_only_fields = ('id', 'added_at')


class BannerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Banner
        fields = (
            'id', 'title', 'message', 'link', 'image', 'placement', 'sort_order',
            'status', 'created_at', 'updated_at'
        )
        read_only_fields = ('id', 'created_at', 'updated_at')


class PromotionSerializer(serializers.ModelSerializer):
    is_currently_active = serializers.ReadOnlyField()

    class Meta:
        model = Promotion
        fields = (
            'id', 'title', 'code', 'description', 'type', 'value', 'scope', 'targets', 'badge',
            'priority', 'is_stackable', 'minimum_order_amount',
            'start_date', 'end_date', 'status', 'is_currently_active',
            'created_at', 'updated_at'
        )
        read_only_fields = ('id', 'created_at', 'updated_at')
        extra_kwargs = {
            'badge': {'read_only': True},
            'is_stackable': {'read_only': True},
            'priority': {'read_only': True},
        }


class CMSBlockSerializer(serializers.ModelSerializer):
    class Meta:
        model = CMSBlock
        fields = (
            'id', 'placement', 'key', 'title', 'subtitle', 'body', 'image',
            'cta_label', 'cta_url', 'content', 'is_active', 'sort_order',
            'created_at', 'updated_at'
        )
        read_only_fields = ('id', 'created_at', 'updated_at')
