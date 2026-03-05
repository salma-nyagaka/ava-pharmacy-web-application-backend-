"""
Serializers for the products app.

Covers Category, Brand, ProductImage, ProductVariant, ProductReview,
ProductList/Detail, Wishlist, Banner, Promotion, and CMSBlock serializers.
Pricing fields (final_price, discount_total, active_promotions) are computed
via the calculate_product_pricing service.
"""
from rest_framework import serializers
from .models import Category, Brand, CMSBlock, Product, ProductImage, ProductReview, ProductVariant, Wishlist, Banner, Promotion
from .services import calculate_product_pricing


class CategorySerializer(serializers.ModelSerializer):
    subcategories = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ('id', 'name', 'slug', 'description', 'icon', 'is_active', 'subcategories')

    def get_subcategories(self, obj):
        if obj.parent is None:
            return CategorySerializer(obj.subcategories.filter(is_active=True), many=True).data
        return []


class BrandSerializer(serializers.ModelSerializer):
    class Meta:
        model = Brand
        fields = ('id', 'name', 'slug', 'logo', 'description', 'is_active')


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
            'id', 'sku', 'slug', 'name', 'brand_name', 'brand_slug',
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
            'id', 'sku', 'slug', 'name', 'brand', 'brand_id', 'category', 'category_id',
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
