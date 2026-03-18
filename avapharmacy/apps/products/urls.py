"""
URL patterns for the products app.

Covers public catalog endpoints (categories, brands, products, reviews,
wishlist, banners, CMS blocks, promotions) and admin endpoints for CRUD
operations on all catalog entities and inventory management.
"""
from django.urls import path
from . import views

urlpatterns = [
    path('catalog/summary/', views.CatalogSummaryView.as_view(), name='catalog-summary'),
    path('categories/', views.CategoryListView.as_view(), name='categories'),
    path('brands/', views.BrandListView.as_view(), name='brands'),
    path('health-concerns/', views.HealthConcernListView.as_view(), name='health-concerns'),
    path('product-categories/', views.ProductCategoryListView.as_view(), name='product-categories'),
    path('products/', views.ProductListView.as_view(), name='products'),
    path('products/featured/', views.FeaturedProductListView.as_view(), name='featured-products'),
    # Search must come before slug route to avoid conflict
    path('products/search/suggestions/', views.ProductSuggestionsView.as_view(), name='product-suggestions'),
    path('products/search/', views.ProductSearchView.as_view(), name='product-search'),
    path('products/availability/', views.ProductAvailabilityView.as_view(), name='product-availability'),
    # Product by numeric ID (spec: GET /products/:id)
    path('products/<int:pk>/', views.ProductDetailByIdView.as_view(), name='product-detail-by-id'),
    # Product by slug (SEO URLs)
    path('products/slug/<slug:slug>/', views.ProductDetailView.as_view(), name='product-detail-by-slug'),
    path('products/<slug:slug>/', views.ProductDetailView.as_view(), name='product-detail'),
    path('products/<int:pk>/reviews/', views.ProductReviewListCreateView.as_view(), name='product-reviews'),
    path('wishlist/', views.WishlistView.as_view(), name='wishlist'),
    path('wishlist/<int:pk>/', views.WishlistItemDeleteView.as_view(), name='wishlist-item'),
    path('wishlist/<int:pk>/move-to-cart/', views.WishlistItemMoveToCartView.as_view(), name='wishlist-item-move-to-cart'),
    path('cart/items/<int:pk>/move-to-wishlist/', views.CartItemMoveToWishlistView.as_view(), name='cart-item-move-to-wishlist'),
    path('banners/', views.BannerListView.as_view(), name='banners'),
    path('cms/', views.CMSBlockListView.as_view(), name='cms-blocks'),
    path('promotions/', views.PromotionListView.as_view(), name='promotions'),
    path('admin/categories/', views.AdminCategoryListCreateView.as_view(), name='admin-categories'),
    path('admin/categories/<int:pk>/', views.AdminCategoryDetailView.as_view(), name='admin-category-detail'),
    path('admin/product-categories/', views.AdminProductCategoryListCreateView.as_view(), name='admin-product-categories'),
    path('admin/product-categories/<int:pk>/', views.AdminProductCategoryDetailView.as_view(), name='admin-product-category-detail'),
    path('admin/product-subcategories/', views.AdminProductSubcategoryListCreateView.as_view(), name='admin-product-subcategories'),
    path('admin/product-subcategories/<int:pk>/', views.AdminProductSubcategoryDetailView.as_view(), name='admin-product-subcategory-detail'),
    path('admin/brands/', views.AdminBrandListCreateView.as_view(), name='admin-brands'),
    path('admin/brands/<int:pk>/', views.AdminBrandDetailView.as_view(), name='admin-brand-detail'),
    path('admin/products/', views.AdminProductListCreateView.as_view(), name='admin-products'),
    path('admin/products/<int:pk>/', views.AdminProductDetailView.as_view(), name='admin-product-detail'),
    path('admin/products/<int:product_pk>/images/', views.AdminProductImageListCreateView.as_view(), name='admin-product-images'),
    path('admin/products/<int:product_pk>/images/<int:pk>/', views.AdminProductImageDetailView.as_view(), name='admin-product-image-detail'),
    path('admin/products/<int:product_pk>/variants/', views.AdminProductVariantListCreateView.as_view(), name='admin-product-variants'),
    path('admin/products/<int:product_pk>/variants/<int:pk>/', views.AdminProductVariantDetailView.as_view(), name='admin-product-variant-detail'),
    path('admin/inventory/', views.AdminInventoryListView.as_view(), name='admin-inventory'),
    path('admin/inventory/pos-sync/', views.AdminInventoryPosSyncView.as_view(), name='admin-inventory-pos-sync'),
    path('admin/inventory/bulk-update/', views.AdminInventoryBulkUpdateView.as_view(), name='admin-inventory-bulk-update'),
    path('admin/inventory/reserve/', views.AdminInventoryReserveView.as_view(), name='admin-inventory-reserve'),
    path('admin/inventory/release/', views.AdminInventoryReleaseView.as_view(), name='admin-inventory-release'),
    path('admin/inventory/deduct/', views.AdminInventoryDeductView.as_view(), name='admin-inventory-deduct'),
    path('admin/inventory/<int:pk>/movements/', views.AdminInventoryMovementsView.as_view(), name='admin-inventory-movements'),
    path('admin/inventory/<int:pk>/', views.AdminInventoryAdjustView.as_view(), name='admin-inventory-adjust'),
    path('admin/banners/', views.AdminBannerListCreateView.as_view(), name='admin-banners'),
    path('admin/banners/<int:pk>/', views.AdminBannerDetailView.as_view(), name='admin-banner-detail'),
    path('admin/cms/', views.AdminCMSBlockListCreateView.as_view(), name='admin-cms-blocks'),
    path('admin/cms/<int:pk>/', views.AdminCMSBlockDetailView.as_view(), name='admin-cms-block-detail'),
    path('admin/promotions/', views.AdminPromotionListCreateView.as_view(), name='admin-promotions'),
    path('admin/promotions/<int:pk>/', views.AdminPromotionDetailView.as_view(), name='admin-promotion-detail'),
    path('admin/health-concerns/', views.AdminHealthConcernListCreateView.as_view(), name='admin-health-concerns'),
    path('admin/health-concerns/<int:pk>/', views.AdminHealthConcernDetailView.as_view(), name='admin-health-concern-detail'),
    path('admin/badges/', views.AdminProductBadgeListCreateView.as_view(), name='admin-product-badges'),
    path('admin/badges/<int:pk>/', views.AdminProductBadgeDetailView.as_view(), name='admin-product-badge-detail'),
]
