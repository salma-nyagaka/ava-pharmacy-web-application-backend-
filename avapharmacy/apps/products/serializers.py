"""
Serializers for the products app.

Covers Category, Brand, ProductImage, Variant, VariantReview,
ProductList/Detail, Wishlist, Banner, Promotion, and CMSBlock serializers.
Pricing fields (final_price, discount_total, active_promotions) are computed
via the representative variant pricing service.
"""
import json
from decimal import Decimal

from django.conf import settings
from rest_framework import serializers
from django.utils.text import slugify
from .models import Banner, Brand, Category, CMSBlock, HealthConcern, Product, ProductImage, Promotion, StockMovement, Subcategory, Variant, VariantInventory, VariantReview, Wishlist
from .image_validators import validate_uploaded_image
from .services import calculate_product_pricing


class ProductImageWithBrandFallbackField(serializers.ImageField):
    """Return the product image, falling back to a representative variant image, then brand."""

    def to_representation(self, value):
        if self._has_usable_file(value):
            return super().to_representation(value)

        instance = getattr(value, 'instance', None)
        variant_image = self._representative_variant_image(instance)
        if self._has_usable_file(variant_image):
            return super().to_representation(variant_image)

        brand_logo = getattr(getattr(instance, 'brand', None), 'logo', None)
        if self._has_usable_file(brand_logo):
            return super().to_representation(brand_logo)

        return None

    def _representative_variant_image(self, instance):
        if instance is None:
            return None

        representative = None
        get_variant = getattr(instance, 'get_representative_variant', None)
        if callable(get_variant):
            representative = get_variant()
        elif hasattr(instance, 'variants'):
            representative = instance.variants.filter(is_active=True).order_by('sort_order', 'name', 'pk').first()
        return getattr(representative, 'image', None)

    @staticmethod
    def _has_usable_file(value):
        name = getattr(value, 'name', '')
        if not name:
            return False

        storage = getattr(value, 'storage', None)
        if storage is None:
            return False

        try:
            return storage.exists(name)
        except Exception:
            return False


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
        queryset = Category.objects.filter(name__iexact=value)
        if self.instance is not None:
            queryset = queryset.exclude(pk=self.instance.pk)
        if queryset.exists():
            raise serializers.ValidationError('A category with this name already exists.')
        return value

    def get_subcategories(self, obj):
        prefetched = getattr(obj, '_prefetched_objects_cache', {}).get('subcategories')
        subcategories = prefetched if prefetched is not None else obj.subcategories.all()
        return SubcategorySerializer([item for item in subcategories if item.is_active], many=True).data


class SubcategorySerializer(serializers.ModelSerializer):
    category = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.all(),
    )
    category_name = serializers.ReadOnlyField(source='category.name')

    class Meta:
        model = Subcategory
        fields = ('id', 'name', 'slug', 'category', 'category_name', 'image', 'description', 'is_active', 'created_at')
        extra_kwargs = {'slug': {'required': False, 'allow_blank': True}}

    def validate_name(self, value):
        parent_id = self.initial_data.get('category')
        qs = Subcategory.objects.filter(category_id=parent_id, name__iexact=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError('A subcategory with this name already exists in the selected category.')
        return value

class CatalogCategorySerializer(serializers.ModelSerializer):
    subcategories = SubcategorySerializer(many=True, read_only=True)

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
        qs = Category.objects.filter(name__iexact=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError('A category with this name already exists.')
        return value


class HealthConcernSerializer(serializers.ModelSerializer):
    class Meta:
        model = HealthConcern
        fields = ('id', 'name', 'slug', 'description', 'icon', 'image', 'is_active', 'created_at')
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
    image = serializers.SerializerMethodField()

    class Meta:
        model = Brand
        fields = ('id', 'name', 'slug', 'logo', 'image', 'description', 'is_active')
        extra_kwargs = {'slug': {'required': False, 'allow_blank': True}}

    def to_internal_value(self, data):
        if hasattr(data, 'copy'):
            data = data.copy()
        else:
            data = dict(data)

        if 'image' in data and 'logo' not in data:
            data['logo'] = data.get('image')

        return super().to_internal_value(data)

    def get_image(self, obj):
        return self.fields['logo'].to_representation(obj.logo)

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
        has_logo_input = hasattr(self, 'initial_data') and (
            'logo' in self.initial_data or 'image' in self.initial_data
        )

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


class VariantInventorySerializer(serializers.ModelSerializer):
    class Meta:
        model = VariantInventory
        fields = (
            'id', 'location', 'source_name', 'stock_quantity', 'low_stock_threshold',
            'allow_backorder', 'max_backorder_quantity', 'is_pos_synced', 'last_synced_at',
            'created_at', 'updated_at',
        )
        read_only_fields = ('id', 'created_at', 'updated_at')


class VariantSerializer(serializers.ModelSerializer):
    brand = BrandSerializer(source='product.brand', read_only=True)
    brand_id = serializers.IntegerField(source='product.brand_id', read_only=True)
    category = CategorySerializer(read_only=True)
    category_id = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.all(), source='category', write_only=True, required=False, allow_null=True
    )
    subcategory_id = serializers.PrimaryKeyRelatedField(
        queryset=Subcategory.objects.all(), source='subcategory', write_only=True, required=False, allow_null=True
    )
    subcategory_name = serializers.ReadOnlyField(source='subcategory.name')
    health_concern_ids = serializers.PrimaryKeyRelatedField(
        queryset=HealthConcern.objects.all(), source='health_concerns', many=True, write_only=True, required=False
    )
    health_concerns = HealthConcernSerializer(many=True, read_only=True)
    effective_price = serializers.ReadOnlyField()
    inventory_status = serializers.ReadOnlyField()
    available_quantity = serializers.ReadOnlyField()
    stock_source = serializers.SerializerMethodField()
    stock_quantity = serializers.SerializerMethodField()
    low_stock_threshold = serializers.SerializerMethodField()
    allow_backorder = serializers.SerializerMethodField()
    max_backorder_quantity = serializers.SerializerMethodField()
    inventories = VariantInventorySerializer(many=True, read_only=True)

    class Meta:
        model = Variant
        fields = (
            'id', 'sku', 'name', 'strength', 'brand', 'brand_id', 'category', 'category_id',
            'subcategory_id', 'subcategory_name', 'health_concerns', 'health_concern_ids',
            'short_description', 'description', 'features', 'dosage_instructions', 'directions',
            'warnings', 'dosage_quantity', 'dosage_unit', 'dosage_frequency', 'dosage_notes',
            'attributes', 'price', 'cost_price', 'original_price', 'effective_price',
            'image', 'requires_prescription', 'inventories', 'stock_source', 'stock_quantity', 'low_stock_threshold',
            'allow_backorder', 'max_backorder_quantity', 'inventory_status',
            'available_quantity', 'is_active', 'sort_order', 'created_at', 'updated_at'
        )
        read_only_fields = ('id', 'created_at', 'updated_at', 'effective_price', 'inventory_status', 'available_quantity')

    def _inventory_values(self, obj):
        getter = getattr(obj, '_get_inventory_values', None)
        if callable(getter):
            return getter()
        return {
            'stock_source': getattr(obj, 'stock_source', Product.STOCK_OUT),
            'stock_quantity': getattr(obj, 'stock_quantity', 0),
            'low_stock_threshold': getattr(obj, 'low_stock_threshold', 0),
            'allow_backorder': getattr(obj, 'allow_backorder', False),
            'max_backorder_quantity': getattr(obj, 'max_backorder_quantity', 0),
        }

    def get_stock_source(self, obj):
        return self._inventory_values(obj)['stock_source']

    def get_stock_quantity(self, obj):
        return self._inventory_values(obj)['stock_quantity']

    def get_low_stock_threshold(self, obj):
        return self._inventory_values(obj)['low_stock_threshold']

    def get_allow_backorder(self, obj):
        return self._inventory_values(obj)['allow_backorder']

    def get_max_backorder_quantity(self, obj):
        return self._inventory_values(obj)['max_backorder_quantity']


class AdminVariantSerializer(VariantSerializer):
    barcode = serializers.CharField(required=False, allow_blank=True)
    pos_product_id = serializers.CharField(required=False, allow_blank=True)
    branch_inventory = serializers.JSONField(write_only=True, required=False)
    warehouse_inventory = serializers.JSONField(write_only=True, required=False)

    class Meta(VariantSerializer.Meta):
        fields = (
            'id', 'sku', 'barcode', 'pos_product_id', 'name', 'strength', 'brand', 'brand_id',
            'category', 'category_id', 'subcategory_id', 'subcategory_name', 'health_concerns',
            'health_concern_ids', 'short_description', 'description', 'features',
            'dosage_instructions', 'directions', 'warnings', 'dosage_quantity', 'dosage_unit',
            'dosage_frequency', 'dosage_notes', 'attributes', 'price', 'cost_price',
            'original_price', 'effective_price',
            'image', 'requires_prescription', 'inventories', 'branch_inventory', 'warehouse_inventory', 'stock_source', 'stock_quantity', 'low_stock_threshold',
            'allow_backorder', 'max_backorder_quantity', 'inventory_status',
            'available_quantity', 'is_active', 'sort_order', 'created_at', 'updated_at'
        )

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
        else:
            locations[Product.STOCK_BRANCH].update({
                'stock_quantity': validated_data.get('stock_quantity', 0),
                'low_stock_threshold': validated_data.get('low_stock_threshold', 5),
                'allow_backorder': validated_data.get('allow_backorder', False),
                'max_backorder_quantity': validated_data.get('max_backorder_quantity', 0),
            })

        branch_payload = validated_data.pop('branch_inventory', None)
        if branch_payload:
            locations[Product.STOCK_BRANCH].update(branch_payload)

        warehouse_payload = validated_data.pop('warehouse_inventory', None)
        if warehouse_payload:
            locations[Product.STOCK_WAREHOUSE].update(warehouse_payload)

        validated_data.pop('stock_source', None)
        validated_data.pop('stock_quantity', None)
        validated_data.pop('low_stock_threshold', None)
        validated_data.pop('allow_backorder', None)
        validated_data.pop('max_backorder_quantity', None)
        return locations

    def validate(self, attrs):
        attrs = super().validate(attrs)
        if 'branch_inventory' in attrs:
            attrs['branch_inventory'] = self._validate_inventory_payload(attrs['branch_inventory'], 'Main shop')
        if 'warehouse_inventory' in attrs:
            attrs['warehouse_inventory'] = self._validate_inventory_payload(attrs['warehouse_inventory'], 'POS store')
        price = attrs.get('price', getattr(self.instance, 'price', None))
        cost_price = attrs.get('cost_price', getattr(self.instance, 'cost_price', None))

        if price is None:
            raise serializers.ValidationError({'price': ['Selling price is required for each variant.']})
        if cost_price is not None and cost_price < 0:
            raise serializers.ValidationError({'cost_price': ['Ensure this value is greater than or equal to 0.']})
        if attrs.get('image'):
            validate_uploaded_image(attrs['image'], 'product')

        strategy = getattr(settings, 'POS_LINK_STRATEGY', 'sku')
        sku = attrs.get('sku', getattr(self.instance, 'sku', None))
        pos_product_id = attrs.get('pos_product_id', getattr(self.instance, 'pos_product_id', None))
        barcode = attrs.get('barcode', getattr(self.instance, 'barcode', None))

        if isinstance(pos_product_id, str):
            attrs['pos_product_id'] = pos_product_id.strip()
            pos_product_id = attrs['pos_product_id']
        if isinstance(barcode, str):
            attrs['barcode'] = barcode.strip()
            barcode = attrs['barcode']
        if isinstance(attrs.get('strength'), str):
            attrs['strength'] = attrs['strength'].strip()
        if isinstance(attrs.get('short_description'), str):
            attrs['short_description'] = attrs['short_description'].strip()
        if isinstance(attrs.get('description'), str):
            attrs['description'] = attrs['description'].strip()
        if isinstance(attrs.get('dosage_instructions'), str):
            attrs['dosage_instructions'] = attrs['dosage_instructions'].strip()
        if isinstance(attrs.get('directions'), str):
            attrs['directions'] = attrs['directions'].strip()
        if isinstance(attrs.get('warnings'), str):
            attrs['warnings'] = attrs['warnings'].strip()
        if isinstance(attrs.get('dosage_quantity'), str):
            attrs['dosage_quantity'] = attrs['dosage_quantity'].strip()
        if isinstance(attrs.get('dosage_unit'), str):
            attrs['dosage_unit'] = attrs['dosage_unit'].strip()
        if isinstance(attrs.get('dosage_frequency'), str):
            attrs['dosage_frequency'] = attrs['dosage_frequency'].strip()
        if isinstance(attrs.get('dosage_notes'), str):
            attrs['dosage_notes'] = attrs['dosage_notes'].strip()

        strategy = (strategy or 'sku').strip().lower()
        if strategy == 'pos_product_id' and not pos_product_id:
            raise serializers.ValidationError({'pos_product_id': ['POS product ID is required for this POS link strategy.']})
        if strategy == 'barcode' and not barcode:
            raise serializers.ValidationError({'barcode': ['Barcode is required for this POS link strategy.']})
        if strategy == 'barcode_and_pos_id' and (not barcode or not pos_product_id):
            raise serializers.ValidationError({'barcode': ['Barcode and POS product ID are required for this POS link strategy.']})
        if strategy == 'sku_or_pos_id' and not (sku or pos_product_id):
            raise serializers.ValidationError({'pos_product_id': ['Provide a SKU or POS product ID to link with the POS.']})
        if strategy == 'sku_or_barcode' and not (sku or barcode):
            raise serializers.ValidationError({'barcode': ['Provide a SKU or barcode to link with the POS.']})
        if strategy == 'any' and not (sku or pos_product_id or barcode):
            raise serializers.ValidationError({'sku': ['Provide a SKU, POS product ID, or barcode to link with the POS.']})

        return attrs

    def create(self, validated_data):
        health_concerns = validated_data.pop('health_concerns', None)
        inventory_data = self._pop_inventory_data(validated_data)
        variant = Variant.objects.create(**validated_data)
        if health_concerns is not None:
            variant.health_concerns.set(health_concerns)
        for location, defaults in inventory_data.items():
            VariantInventory.objects.update_or_create(
                variant=variant,
                location=location,
                defaults=defaults,
            )
        if hasattr(variant, '_clear_inventory_cache'):
            variant._clear_inventory_cache()
        variant.save()
        return variant

    def update(self, instance, validated_data):
        health_concerns = validated_data.pop('health_concerns', None)
        inventory_data = self._pop_inventory_data(validated_data)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if health_concerns is not None:
            instance.health_concerns.set(health_concerns)
        for location, defaults in inventory_data.items():
            VariantInventory.objects.update_or_create(
                variant=instance,
                location=location,
                defaults=defaults,
            )
        if hasattr(instance, '_clear_inventory_cache'):
            instance._clear_inventory_cache()
        instance.save()
        return instance


class VariantReviewSerializer(serializers.ModelSerializer):
    user_name = serializers.ReadOnlyField(source='user.full_name')
    is_verified_purchase = serializers.SerializerMethodField()

    class Meta:
        model = VariantReview
        fields = ('id', 'user', 'user_name', 'rating', 'comment', 'is_approved', 'is_verified_purchase', 'created_at')
        read_only_fields = ('id', 'user', 'is_approved', 'created_at')

    def validate_rating(self, value):
        if not 1 <= value <= 5:
            raise serializers.ValidationError('Rating must be between 1 and 5.')
        return value

    def get_is_verified_purchase(self, obj):
        from apps.orders.models import Order

        return Order.objects.filter(
            customer=obj.user,
            status=Order.STATUS_DELIVERED,
            items__variant=obj.variant,
        ).exists()


class ProductListSerializer(serializers.ModelSerializer):
    sku = serializers.SerializerMethodField()
    image = ProductImageWithBrandFallbackField(read_only=True)
    price = serializers.SerializerMethodField()
    requires_prescription = serializers.SerializerMethodField()
    brand_name = serializers.ReadOnlyField(source='brand.name')
    brand_slug = serializers.ReadOnlyField(source='brand.slug')
    brand_image = serializers.ImageField(source='brand.logo', read_only=True)
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
    badge = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = (
            'id', 'sku', 'slug', 'name', 'strength', 'brand_name', 'brand_slug', 'brand_image',
            'category_name', 'category_slug', 'price', 'original_price',
            'image', 'badge', 'stock_source', 'stock_quantity',
            'short_description', 'average_rating', 'review_count',
            'requires_prescription', 'inventory_status', 'available_quantity',
            'can_purchase', 'final_price', 'discount_total', 'active_promotions',
            'has_variants', 'is_active'
        )

    def get_badge(self, obj):
        promotions = self._pricing(obj).get('promotions') or []
        if promotions:
            promotion_badge = promotions[0].get('badge')
            if promotion_badge:
                return promotion_badge
        return ''

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
        price = self.get_price(obj)
        if final_price < price:
            return price
        return None

    def get_price(self, obj):
        return obj.display_price

    def get_sku(self, obj):
        return obj.get_display_sku()

    def get_discount_total(self, obj):
        return self._pricing(obj)['discount_total']

    def get_active_promotions(self, obj):
        return self._pricing(obj)['promotions']

    def get_requires_prescription(self, obj):
        return obj.has_prescription_required_variant()


class PublicInventoryItemSerializer(serializers.ModelSerializer):
    product_id = serializers.IntegerField(source='product.id', read_only=True)
    product_slug = serializers.CharField(source='product.slug', read_only=True)
    sku = serializers.CharField(read_only=True)
    slug = serializers.CharField(source='product.slug', read_only=True)
    name = serializers.SerializerMethodField()
    image = serializers.SerializerMethodField()
    price = serializers.SerializerMethodField()
    requires_prescription = serializers.ReadOnlyField()
    brand_name = serializers.ReadOnlyField(source='product.brand.name')
    brand_slug = serializers.ReadOnlyField(source='product.brand.slug')
    brand_image = serializers.ImageField(source='product.brand.logo', read_only=True)
    category_name = serializers.ReadOnlyField(source='product.category.name')
    category_slug = serializers.ReadOnlyField(source='product.category.slug')
    stock_source = serializers.ReadOnlyField()
    stock_quantity = serializers.ReadOnlyField()
    average_rating = serializers.ReadOnlyField(source='approved_average_rating')
    review_count = serializers.ReadOnlyField(source='approved_review_count')
    inventory_status = serializers.ReadOnlyField()
    available_quantity = serializers.ReadOnlyField()
    can_purchase = serializers.SerializerMethodField()
    has_variants = serializers.SerializerMethodField()
    original_price = serializers.SerializerMethodField()
    final_price = serializers.SerializerMethodField()
    discount_total = serializers.SerializerMethodField()
    active_promotions = serializers.SerializerMethodField()
    badge = serializers.SerializerMethodField()
    short_description = serializers.ReadOnlyField(source='product.short_description')
    is_active = serializers.ReadOnlyField()

    class Meta:
        model = Variant
        fields = (
            'id', 'product_id', 'product_slug', 'sku', 'slug', 'name', 'brand_name', 'brand_slug', 'brand_image',
            'category_name', 'category_slug', 'price', 'original_price', 'image', 'badge', 'stock_source',
            'stock_quantity', 'short_description', 'average_rating', 'review_count', 'requires_prescription',
            'inventory_status', 'available_quantity', 'can_purchase', 'final_price', 'discount_total',
            'active_promotions', 'has_variants', 'is_active',
        )

    def get_name(self, obj):
        return (obj.name or '').strip() or obj.product.name

    def get_image(self, obj):
        variant_image = getattr(obj, 'image', None)
        if ProductImageWithBrandFallbackField._has_usable_file(variant_image):
            return self.fields['brand_image'].to_representation(variant_image)

        product_image = getattr(obj.product, 'image', None)
        if ProductImageWithBrandFallbackField._has_usable_file(product_image):
            return self.fields['brand_image'].to_representation(product_image)

        brand_logo = getattr(getattr(obj.product, 'brand', None), 'logo', None)
        if ProductImageWithBrandFallbackField._has_usable_file(brand_logo):
            return self.fields['brand_image'].to_representation(brand_logo)

        return None

    def _pricing(self, obj):
        pricing = getattr(obj, '_pricing_cache', None)
        if pricing is None:
            product_pricing = calculate_product_pricing(obj.product, promotions=self.context.get('active_promotions'))
            base_price = obj.price
            base_product_price = product_pricing.get('base_price')
            if base_product_price and base_product_price > 0:
                ratio = obj.price / base_product_price
                discount_total = (product_pricing['discount_total'] * ratio).quantize(Decimal('0.01'))
            else:
                discount_total = Decimal('0.00')
            final_price = max(Decimal('0.00'), obj.price - discount_total)
            pricing = {
                'base_price': obj.price,
                'discount_total': discount_total,
                'final_price': final_price,
                'promotions': product_pricing.get('promotions', []),
            }
            obj._pricing_cache = pricing
        return pricing

    def get_badge(self, obj):
        promotions = self._pricing(obj).get('promotions') or []
        if promotions:
            promotion_badge = promotions[0].get('badge')
            if promotion_badge:
                return promotion_badge
        return ''

    def get_price(self, obj):
        return obj.price

    def get_original_price(self, obj):
        final_price = self._pricing(obj)['final_price']
        if final_price < obj.price:
            return obj.price
        if obj.original_price and obj.original_price > obj.price:
            return obj.original_price
        return None

    def get_final_price(self, obj):
        return self._pricing(obj)['final_price']

    def get_discount_total(self, obj):
        return self._pricing(obj)['discount_total']

    def get_active_promotions(self, obj):
        return self._pricing(obj)['promotions']

    def get_can_purchase(self, obj):
        return obj.is_active and obj.available_quantity > 0

    def get_has_variants(self, obj):
        active_variants = getattr(obj.product, '_active_variant_count', None)
        if active_variants is None:
            active_variants = obj.product.variants.filter(is_active=True).count()
            obj.product._active_variant_count = active_variants
        return active_variants > 1


class AdminInventoryItemSerializer(AdminVariantSerializer):
    product_id = serializers.IntegerField(source='product.id', read_only=True)
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_sku = serializers.CharField(source='product.sku', read_only=True)
    product_slug = serializers.CharField(source='product.slug', read_only=True)
    brand_name = serializers.ReadOnlyField(source='product.brand.name')
    brand_slug = serializers.ReadOnlyField(source='product.brand.slug')
    category_name = serializers.ReadOnlyField(source='product.category.name')
    category_slug = serializers.ReadOnlyField(source='product.category.slug')
    short_description = serializers.ReadOnlyField(source='product.short_description')

    class Meta(AdminVariantSerializer.Meta):
        fields = (
            'id', 'product_id', 'product_name', 'product_sku', 'product_slug',
            'brand_name', 'brand_slug', 'category_name', 'category_slug',
            'short_description',
            'sku', 'barcode', 'pos_product_id', 'name', 'strength',
            'health_concerns', 'health_concern_ids', 'dosage_instructions',
            'directions', 'warnings', 'attributes', 'price', 'cost_price',
            'original_price', 'effective_price', 'image', 'requires_prescription',
            'inventories', 'branch_inventory', 'warehouse_inventory', 'stock_source',
            'stock_quantity', 'low_stock_threshold', 'allow_backorder',
            'max_backorder_quantity', 'inventory_status', 'available_quantity',
            'is_active', 'sort_order', 'created_at', 'updated_at',
        )


class ProductDetailSerializer(serializers.ModelSerializer):
    sku = serializers.SerializerMethodField()
    image = ProductImageWithBrandFallbackField(required=False, allow_null=True)
    price = serializers.SerializerMethodField()
    requires_prescription = serializers.SerializerMethodField()
    created_by_name = serializers.SerializerMethodField()
    updated_by_name = serializers.SerializerMethodField()
    brand = BrandSerializer(read_only=True)
    brand_id = serializers.PrimaryKeyRelatedField(
        queryset=Brand.objects.all(), source='brand', write_only=True, required=False, allow_null=True
    )
    category = CategorySerializer(read_only=True)
    category_id = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.all(), source='category', write_only=True, required=False, allow_null=True
    )
    subcategory_id = serializers.PrimaryKeyRelatedField(
        queryset=Subcategory.objects.all(), source='subcategory', write_only=True, required=False, allow_null=True
    )
    subcategory_name = serializers.ReadOnlyField(source='subcategory.name')
    health_concern_ids = serializers.PrimaryKeyRelatedField(
        queryset=HealthConcern.objects.all(), source='health_concerns', many=True, write_only=True, required=False
    )
    health_concerns = HealthConcernSerializer(many=True, read_only=True)
    gallery = ProductImageSerializer(many=True, read_only=True)
    variants = VariantSerializer(many=True, read_only=True)
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
    badge = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = (
            'id', 'sku', 'slug', 'name', 'strength', 'brand', 'brand_id', 'category', 'category_id',
            'subcategory_id', 'subcategory_name', 'health_concerns', 'health_concern_ids',
            'price', 'original_price', 'image', 'gallery', 'variants', 'badge', 'stock_source',
            'stock_quantity', 'low_stock_threshold', 'allow_backorder', 'max_backorder_quantity',
            'short_description', 'description', 'features', 'directions', 'warnings',
            'requires_prescription', 'inventory_status', 'available_quantity', 'can_purchase',
            'final_price', 'discount_total', 'active_promotions', 'has_variants', 'is_active',
            'average_rating', 'review_count', 'created_at', 'updated_at', 'created_by', 'created_by_name', 'updated_by', 'updated_by_name'
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

    def get_badge(self, obj):
        promotions = self._pricing(obj).get('promotions') or []
        if promotions:
            promotion_badge = promotions[0].get('badge')
            if promotion_badge:
                return promotion_badge
        return ''

    def get_final_price(self, obj):
        return self._pricing(obj)['final_price']

    def get_original_price(self, obj):
        final_price = self._pricing(obj)['final_price']
        price = self.get_price(obj)
        if final_price < price:
            return price
        return None

    def get_price(self, obj):
        return obj.display_price

    def get_sku(self, obj):
        return obj.get_display_sku()

    def get_discount_total(self, obj):
        return self._pricing(obj)['discount_total']

    def get_active_promotions(self, obj):
        return self._pricing(obj)['promotions']

    def get_requires_prescription(self, obj):
        return obj.has_prescription_required_variant()

    def get_created_by_name(self, obj):
        if obj.created_by:
            return getattr(obj.created_by, 'full_name', '') or obj.created_by.email
        return 'system'

    def get_updated_by_name(self, obj):
        if obj.updated_by:
            return getattr(obj.updated_by, 'full_name', '') or obj.updated_by.email
        return 'system'

    def _resolved_health_concerns(self, obj):
        cached = getattr(obj, '_variant_health_concerns_cache', None)
        if cached is None:
            cached = list(obj.get_health_concerns())
            obj._variant_health_concerns_cache = cached
        return cached

    def get_health_concerns(self, obj):
        return HealthConcernSerializer(self._resolved_health_concerns(obj), many=True, context=self.context).data

    def get_health_concern_ids(self, obj):
        return [concern.id for concern in self._resolved_health_concerns(obj)]

    def validate(self, attrs):
        attrs = super().validate(attrs)
        provided_slug = attrs.get('slug')
        inventory_fields = {'branch_inventory', 'warehouse_inventory', 'stock_source', 'stock_quantity', 'low_stock_threshold', 'allow_backorder', 'max_backorder_quantity'}
        initial_data = getattr(self, 'initial_data', {}) or {}
        supplied_inventory_fields = [field for field in inventory_fields if field in initial_data]
        if supplied_inventory_fields:
            raise serializers.ValidationError({
                'detail': 'Product-level inventory writes are disabled. Create or update stock on variants instead.'
            })
        if self.instance is None and not provided_slug:
            attrs['slug'] = self._generate_unique_slug(attrs.get('name', ''))
        elif 'slug' in attrs and not provided_slug:
            attrs['slug'] = self._generate_unique_slug(attrs.get('name') or self.instance.name)
        if attrs.get('image'):
            validate_uploaded_image(attrs['image'], 'product')
        return attrs

    def create(self, validated_data):
        product = Product.objects.create(**validated_data)
        return product

    def update(self, instance, validated_data):
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance


class AdminProductSerializer(ProductDetailSerializer):
    cost_price = serializers.SerializerMethodField()
    barcode = serializers.CharField(required=False, allow_blank=True)
    pos_product_id = serializers.CharField(required=False, allow_blank=True)

    class Meta(ProductDetailSerializer.Meta):
        fields = (
            'id', 'sku', 'barcode', 'pos_product_id', 'slug', 'name', 'strength', 'brand', 'brand_id', 'category', 'category_id',
            'subcategory_id', 'subcategory_name', 'health_concerns', 'health_concern_ids',
            'price', 'cost_price', 'original_price', 'image', 'gallery', 'variants', 'stock_source',
            'stock_quantity', 'low_stock_threshold', 'allow_backorder', 'max_backorder_quantity',
            'short_description', 'description', 'features', 'directions', 'warnings',
            'dosage_quantity', 'dosage_unit', 'dosage_frequency', 'dosage_notes',
            'requires_prescription', 'inventory_status', 'available_quantity', 'can_purchase',
            'final_price', 'discount_total', 'active_promotions', 'has_variants', 'is_active',
            'average_rating', 'review_count', 'created_at', 'updated_at', 'created_by', 'created_by_name', 'updated_by', 'updated_by_name'
        )

    def validate(self, attrs):
        attrs = super().validate(attrs)

        strategy = getattr(settings, 'POS_LINK_STRATEGY', 'sku')
        sku = None
        pos_product_id = attrs.get('pos_product_id', getattr(self.instance, 'pos_product_id', None))
        barcode = attrs.get('barcode', getattr(self.instance, 'barcode', None))

        if isinstance(pos_product_id, str):
            attrs['pos_product_id'] = pos_product_id.strip()
            pos_product_id = attrs['pos_product_id']
        if isinstance(barcode, str):
            attrs['barcode'] = barcode.strip()
            barcode = attrs['barcode']

        strategy = (strategy or 'sku').strip().lower()
        if strategy == 'pos_product_id' and not pos_product_id:
            raise serializers.ValidationError({'pos_product_id': ['POS product ID is required for this POS link strategy.']})
        if strategy == 'barcode' and not barcode:
            raise serializers.ValidationError({'barcode': ['Barcode is required for this POS link strategy.']})
        if strategy == 'barcode_and_pos_id' and (not barcode or not pos_product_id):
            raise serializers.ValidationError({'barcode': ['Barcode and POS product ID are required for this POS link strategy.']})
        if strategy == 'sku_or_pos_id' and not pos_product_id:
            attrs['pos_product_id'] = ''
        if strategy == 'sku_or_barcode' and not barcode:
            attrs['barcode'] = attrs.get('barcode', '')

        return attrs

    def get_cost_price(self, obj):
        return obj.display_cost_price


class WishlistSerializer(serializers.ModelSerializer):
    product = ProductListSerializer(source='variant.product', read_only=True)
    variant = VariantSerializer(read_only=True)
    variant_id = serializers.PrimaryKeyRelatedField(
        queryset=Variant.objects.all(), source='variant', write_only=True
    )

    class Meta:
        model = Wishlist
        fields = ('id', 'product', 'variant', 'variant_id', 'added_at')
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
            'id', 'title', 'code', 'description', 'image', 'type', 'value', 'scope', 'targets', 'badge',
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

    def validate(self, attrs):
        attrs = super().validate(attrs)
        has_image_input = hasattr(self, 'initial_data') and 'image' in self.initial_data
        existing_image = getattr(self.instance, 'image', None)
        if attrs.get('code', None) == '':
            attrs['code'] = None

        if self.instance is None and not attrs.get('image'):
            raise serializers.ValidationError({'image': ['Offer image is required.']})
        if self.instance is not None and has_image_input and not attrs.get('image') and not existing_image:
            raise serializers.ValidationError({'image': ['Offer image is required.']})
        if attrs.get('image'):
            validate_uploaded_image(attrs['image'], 'promotion')

        return attrs


class CMSBlockSerializer(serializers.ModelSerializer):
    class Meta:
        model = CMSBlock
        fields = (
            'id', 'placement', 'key', 'title', 'subtitle', 'body', 'image',
            'cta_label', 'cta_url', 'content', 'is_active', 'sort_order',
            'created_at', 'updated_at'
        )
        read_only_fields = ('id', 'created_at', 'updated_at')
