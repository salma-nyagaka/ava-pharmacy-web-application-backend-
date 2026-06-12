"""
Django admin registrations for the products app.

Registers Category, Brand, Product (with image and variant inlines),
VariantReview, Wishlist, Banner, Promotion, and CMSBlock.
"""
from django.contrib import admin
from .models import (
    Banner,
    Brand,
    Category,
    CMSBlock,
    Product,
    ProductImage,
    Promotion,
    StockMovement,
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


class VariantInventoryInline(admin.TabularInline):
    model = VariantInventory
    extra = 0
    fields = (
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
    list_display = ('name', 'display_sku', 'brand', 'category', 'display_price', 'stock_source', 'stock_quantity', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name', 'variants__sku', 'slug')
    prepopulated_fields = {'slug': ('name',)}
    inlines = [ProductImageInline, VariantInline]
    readonly_fields = ('created_at', 'updated_at')

    @admin.display(description='Lead Variant SKU')
    def display_sku(self, obj):
        return obj.get_display_sku()


@admin.register(Variant)
class VariantAdmin(admin.ModelAdmin):
    list_display = ('name', 'product', 'sku', 'barcode', 'price', 'display_stock_quantity', 'display_inventory_status', 'is_active')
    list_filter = ('is_active', 'requires_prescription', 'category')
    search_fields = ('name', 'sku', 'barcode', 'product__name', 'product__brand__name')
    inlines = [VariantInventoryInline]

    @admin.display(description='Stock')
    def display_stock_quantity(self, obj):
        return obj._get_inventory_values()['stock_quantity']

    @admin.display(description='Inventory Status')
    def display_inventory_status(self, obj):
        return obj.inventory_status.replace('_', ' ').title()


@admin.register(VariantInventory)
class VariantInventoryAdmin(admin.ModelAdmin):
    list_display = (
        'variant',
        'location',
        'batch_number',
        'supplier',
        'stock_quantity',
        'reorder_level',
        'expiry_date',
        'shelf_location',
        'status',
    )
    list_filter = ('location', 'status', 'expiry_date')
    search_fields = ('variant__name', 'variant__sku', 'variant__product__name', 'batch_number', 'supplier')


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
    list_display = ('title', 'placement', 'status', 'sort_order', 'updated_at')
    list_filter = ('status', 'placement')
    search_fields = ('title', 'message')


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
