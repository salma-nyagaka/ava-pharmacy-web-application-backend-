from django.contrib import admin
from .models import Banner, Brand, Category, CMSBlock, Product, ProductImage, ProductReview, ProductVariant, Promotion, Wishlist


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


class ProductVariantInline(admin.TabularInline):
    model = ProductVariant
    extra = 0


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'sku', 'brand', 'category', 'price', 'stock_source', 'stock_quantity', 'is_active')
    list_filter = ('brand', 'category', 'stock_source', 'is_active', 'requires_prescription')
    search_fields = ('name', 'sku', 'slug')
    prepopulated_fields = {'slug': ('name',)}
    inlines = [ProductImageInline, ProductVariantInline]
    readonly_fields = ('created_at', 'updated_at')


@admin.register(ProductReview)
class ProductReviewAdmin(admin.ModelAdmin):
    list_display = ('product', 'user', 'rating', 'is_approved', 'created_at')
    list_filter = ('is_approved', 'rating')
    search_fields = ('product__name', 'user__email')


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
