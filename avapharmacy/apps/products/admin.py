"""
Django admin registrations for the products app.

Registers Category, Brand, Product (with image and variant inlines),
VariantReview, Wishlist, Banner, Promotion, and CMSBlock.
"""
from django import forms
from django.contrib import admin
from .models import (
    Banner,
    Brand,
    Category,
    CMSBlock,
    FAQ,
    Product,
    ProductImage,
    Promotion,
    StockMovement,
    Store,
    StoreFulfillmentPolicy,
    StoreVariantListing,
    Variant,
    VariantInventory,
    VariantReview,
    Wishlist,
)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'parent')
    list_filter = ('parent',)
    search_fields = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)}


@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug')
    search_fields = ('name',)
    prepopulated_fields = {'slug': ('name',)}


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1


class VariantInline(admin.TabularInline):
    model = Variant
    extra = 0


class VariantInventoryAdminForm(forms.ModelForm):
    class Meta:
        model = VariantInventory
        fields = '__all__'

    def clean(self):
        cleaned_data = super().clean()
        variant = cleaned_data.get('variant') or getattr(self.instance, 'variant', None)
        listing = cleaned_data.get('store_listing')
        if variant is not None and listing is not None and listing.variant_id != variant.pk:
            self.add_error(
                'store_listing',
                'The selected store listing belongs to a different product variant.',
            )
        return cleaned_data


class VariantInventoryInline(admin.TabularInline):
    model = VariantInventory
    form = VariantInventoryAdminForm
    extra = 0
    fields = (
        'store_listing',
        'location',
        'batch_number',
        'supplier',
        'stock_quantity',
        'reorder_level',
        'low_stock_threshold',
        'expiry_date',
        'shelf_location',
        'status',
    )
    readonly_fields = ('status',)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'display_sku', 'brand', 'family_review_status', 'image_source', 'image_verified', 'category', 'display_price', 'stock_source', 'stock_quantity', 'is_active')
    list_filter = ('is_active', 'family_review_status', 'image_source', 'image_verified')
    search_fields = ('name', 'master_product_id', 'manufacturer', 'variants__sku', 'slug')
    prepopulated_fields = {'slug': ('name',)}
    inlines = [ProductImageInline, VariantInline]
    readonly_fields = ('created_at', 'updated_at')

    @admin.display(description='Lead Variant SKU')
    def display_sku(self, obj):
        return obj.get_display_sku()


@admin.register(Variant)
class VariantAdmin(admin.ModelAdmin):
    list_display = ('name', 'product', 'sku', 'barcode', 'image_source', 'image_verified', 'price', 'display_stock_quantity', 'display_inventory_status', 'is_active')
    list_filter = (
        'is_active', 'requires_prescription', 'prescription_classification',
        'prescription_review_status', 'regulatory_status', 'category', 'image_source', 'image_verified',
    )
    search_fields = (
        'name', 'sku', 'barcode', 'ppb_registration_number',
        'marketing_authorization_number', 'product__name', 'product__brand__name',
    )
    inlines = [VariantInventoryInline]

    @admin.display(description='Stock')
    def display_stock_quantity(self, obj):
        return obj._get_inventory_values()['stock_quantity']

    @admin.display(description='Inventory Status')
    def display_inventory_status(self, obj):
        return obj.inventory_status.replace('_', ' ').title()


@admin.register(VariantInventory)
class VariantInventoryAdmin(admin.ModelAdmin):
    form = VariantInventoryAdminForm
    list_select_related = ('variant', 'variant__product', 'store_listing__store')
    list_display = (
        'variant',
        'display_store',
        'location',
        'batch_number',
        'supplier',
        'stock_quantity',
        'reorder_level',
        'expiry_date',
        'shelf_location',
        'status',
    )
    list_filter = ('store_listing__store', 'location', 'status', 'expiry_date')
    search_fields = (
        'variant__name', 'variant__sku', 'variant__product__name',
        'store_listing__store__name', 'batch_number', 'supplier',
    )

    @admin.display(description='Store', ordering='store_listing__store__name')
    def display_store(self, obj):
        return obj.store_name or 'Unassigned'


@admin.register(Store)
class StoreAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'city', 'is_active', 'updated_at')
    list_filter = ('is_active', 'city')
    search_fields = ('name', 'code', 'city')
    prepopulated_fields = {'code': ('name',)}


@admin.register(StoreFulfillmentPolicy)
class StoreFulfillmentPolicyAdmin(admin.ModelAdmin):
    list_select_related = ('store',)
    list_display = (
        'store', 'online_fulfillment_enabled', 'customer_pickup_enabled',
        'inter_store_transfer_enabled', 'fulfillment_priority',
        'estimated_lead_time_hours', 'daily_order_capacity',
    )
    list_filter = (
        'online_fulfillment_enabled', 'customer_pickup_enabled',
        'inter_store_transfer_enabled',
    )
    search_fields = ('store__name', 'store__code', 'service_areas', 'notes')


@admin.register(StoreVariantListing)
class StoreVariantListingAdmin(admin.ModelAdmin):
    list_select_related = ('variant', 'variant__product', 'store')
    list_display = (
        'variant', 'store', 'external_product_id', 'price', 'cost_price',
        'minimum_price', 'vat_rate', 'status', 'review_status', 'is_active',
    )
    list_filter = ('store', 'is_active', 'status', 'review_status')
    search_fields = (
        'variant__name', 'variant__sku', 'variant__product__name',
        'store__name', 'external_product_id',
    )
    readonly_fields = ('created_at', 'updated_at')


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = (
        'variant',
        'movement_type',
        'batch_number',
        'quantity_change',
        'quantity_before',
        'quantity_after',
        'source_location',
        'destination_location',
        'created_at',
        'created_by',
    )
    list_filter = ('movement_type', 'source', 'source_location', 'destination_location', 'created_at')
    search_fields = ('variant_inventory__variant__name', 'variant_inventory__variant__sku', 'batch_number', 'reference')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(VariantReview)
class VariantReviewAdmin(admin.ModelAdmin):
    list_display = ('product', 'user', 'rating', 'is_approved', 'created_at')
    list_filter = ('is_approved', 'rating')
    search_fields = ('variant__product__name', 'variant__name', 'user__email')


@admin.register(Wishlist)
class WishlistAdmin(admin.ModelAdmin):
    list_display = ('user', 'product', 'added_at')


@admin.register(Banner)
class BannerAdmin(admin.ModelAdmin):
    list_display = ('title', 'category', 'placement', 'status', 'sort_order', 'updated_at')
    list_filter = ('status', 'placement', 'category')
    search_fields = ('title', 'message')
    ordering = ('sort_order', '-updated_at')
    list_editable = ('placement', 'status', 'sort_order')
    readonly_fields = ('created_at', 'updated_at')
    fields = (
        'title',
        'message',
        'link',
        'image',
        'category',
        'placement',
        'sort_order',
        'status',
        'created_at',
        'updated_at',
    )


@admin.register(Promotion)
class PromotionAdmin(admin.ModelAdmin):
    list_display = ('title', 'code', 'scope', 'type', 'value', 'status', 'priority')
    list_filter = ('scope', 'type', 'status', 'is_stackable')
    search_fields = ('title', 'code')


@admin.register(CMSBlock)
class CMSBlockAdmin(admin.ModelAdmin):
    list_display = ('key', 'placement', 'title', 'is_active', 'sort_order')
    list_filter = ('placement', 'is_active')
    search_fields = ('key', 'title')


@admin.register(FAQ)
class FAQAdmin(admin.ModelAdmin):
    list_display = ('question', 'category', 'is_published', 'sort_order', 'updated_at')
    list_filter = ('category', 'is_published')
    search_fields = ('question', 'answer', 'category')
    list_editable = ('is_published', 'sort_order')
    ordering = ('sort_order', 'pk')
