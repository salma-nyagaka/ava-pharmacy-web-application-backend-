"""
Serializers for the products app.

Covers Category, Brand, ProductImage, ProductVariant, ProductReview,
ProductList/Detail, Wishlist, Banner, Promotion, and CMSBlock serializers.
Pricing fields (final_price, discount_total, active_promotions) are computed
via the calculate_product_pricing service.
"""
from rest_framework import serializers
from django.utils.text import slugify
from .models import Category, Brand, CMSBlock, HealthConcern, Product, ProductCategory, ProductSubcategory, ProductImage, ProductReview, ProductVariant, StockMovement, Wishlist, Banner, Promotion
from .services import calculate_product_pricing


class CategorySerializer(serializers.ModelSerializer):
    subcategories = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ('id', 'name', 'slug', 'description', 'icon', 'is_active', 'subcategories')
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
        if obj.parent is None:
            return CategorySerializer(obj.subcategories.filter(is_active=True), many=True).data
        return []


class ProductSubcategorySerializer(serializers.ModelSerializer):
    category_name = serializers.ReadOnlyField(source='category.name')

    class Meta:
        model = ProductSubcategory
        fields = ('id', 'name', 'slug', 'category', 'category_name', 'description', 'is_active', 'created_at')
        extra_kwargs = {'slug': {'required': False, 'allow_blank': True}}

    def validate_name(self, value):
        category_id = self.initial_data.get('category')
        qs = ProductSubcategory.objects.filter(category_id=category_id, name__iexact=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError('A subcategory with this name already exists in the selected category.')
        return value


class ProductCategorySerializer(serializers.ModelSerializer):
    subcategories = ProductSubcategorySerializer(many=True, read_only=True)

    class Meta:
        model = ProductCategory
        fields = ('id', 'name', 'slug', 'description', 'icon', 'is_active', 'created_at', 'subcategories')
        extra_kwargs = {'slug': {'required': False, 'allow_blank': True}}

    def validate_name(self, value):
        qs = ProductCategory.objects.filter(name__iexact=value)
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
            return obj.created_by.get_full_name() or obj.created_by.email
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
    average_rating = serializers.ReadOnlyField()
    review_count = serializers.ReadOnlyField()
    inventory_status = serializers.ReadOnlyField()
    available_quantity = serializers.ReadOnlyField()
    can_purchase = serializers.ReadOnlyField()
    final_price = serializers.SerializerMethodField()
    discount_total = serializers.SerializerMethodField()
    active_promotions = serializers.SerializerMethodField()
    has_variants = serializers.ReadOnlyField()

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

    def get_discount_total(self, obj):
        return self._pricing(obj)['discount_total']

    def get_active_promotions(self, obj):
        return self._pricing(obj)['promotions']


class ProductDetailSerializer(serializers.ModelSerializer):
    brand = BrandSerializer(read_only=True)
    brand_id = serializers.PrimaryKeyRelatedField(
        queryset=Brand.objects.all(), source='brand', write_only=True, required=False, allow_null=True
    )
    category = CategorySerializer(read_only=True)
    category_id = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.all(), source='category', write_only=True, required=False, allow_null=True
    )
    subcategory_id = serializers.PrimaryKeyRelatedField(
        queryset=ProductSubcategory.objects.all(), source='subcategory', write_only=True, required=False, allow_null=True
    )
    subcategory_name = serializers.ReadOnlyField(source='subcategory.name')
    health_concern_ids = serializers.PrimaryKeyRelatedField(
        queryset=HealthConcern.objects.all(), source='health_concerns', many=True, write_only=True, required=False
    )
    health_concerns = HealthConcernSerializer(many=True, read_only=True)
    gallery = ProductImageSerializer(many=True, read_only=True)
    variants = ProductVariantSerializer(many=True, read_only=True)
    average_rating = serializers.ReadOnlyField()
    review_count = serializers.ReadOnlyField()
    inventory_status = serializers.ReadOnlyField()
    available_quantity = serializers.ReadOnlyField()
    can_purchase = serializers.ReadOnlyField()
    final_price = serializers.SerializerMethodField()
    discount_total = serializers.SerializerMethodField()
    active_promotions = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = (
            'id', 'sku', 'slug', 'name', 'strength', 'brand', 'brand_id', 'category', 'category_id',
            'subcategory_id', 'subcategory_name', 'health_concerns', 'health_concern_ids',
            'price', 'original_price', 'image', 'gallery', 'variants', 'badge', 'stock_source',
            'stock_quantity', 'low_stock_threshold', 'allow_backorder', 'max_backorder_quantity',
            'short_description', 'description', 'features', 'directions', 'warnings',
            'requires_prescription', 'inventory_status', 'available_quantity', 'can_purchase',
            'final_price', 'discount_total', 'active_promotions', 'has_variants', 'is_featured', 'is_active',
            'average_rating', 'review_count', 'created_at', 'updated_at'
        )
        read_only_fields = ('id', 'created_at', 'updated_at')

    def _pricing(self, obj):
        pricing = getattr(obj, '_pricing_cache', None)
        if pricing is None:
            pricing = calculate_product_pricing(obj, promotions=self.context.get('active_promotions'))
            obj._pricing_cache = pricing
        return pricing

    def get_final_price(self, obj):
        return self._pricing(obj)['final_price']

    def get_discount_total(self, obj):
        return self._pricing(obj)['discount_total']

    def get_active_promotions(self, obj):
        return self._pricing(obj)['promotions']

    def validate(self, attrs):
        attrs = super().validate(attrs)
        if self.instance is None and not attrs.get('image'):
            raise serializers.ValidationError({'image': 'Product image is required.'})
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


class CMSBlockSerializer(serializers.ModelSerializer):
    class Meta:
        model = CMSBlock
        fields = (
            'id', 'placement', 'key', 'title', 'subtitle', 'body', 'image',
            'cta_label', 'cta_url', 'content', 'is_active', 'sort_order',
            'created_at', 'updated_at'
        )
        read_only_fields = ('id', 'created_at', 'updated_at')
