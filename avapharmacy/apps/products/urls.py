"""
URL patterns for the products app.

Covers public catalog endpoints (categories, brands, products, reviews,
wishlist, banners, CMS blocks, promotions) and admin endpoints for CRUD
operations on all catalog entities and inventory management.
"""
from django.urls import path
from . import views


def _admin_crud_patterns(route, list_view, detail_view, list_name, detail_name):
    return [
        path(f'admin/{route}/', list_view.as_view(), name=f'admin-{list_name}'),
        path(f'admin/{route}/<int:pk>/', detail_view.as_view(), name=f'admin-{detail_name}-detail'),
    ]


urlpatterns = [
    path('catalog/summary/', views.CatalogSummaryView.as_view(), name='catalog-summary'),
    path('categories/', views.CategoryListView.as_view(), name='categories'),
    path('brands/', views.BrandListView.as_view(), name='brands'),
    path('health-concerns/', views.HealthConcernListView.as_view(), name='health-concerns'),
    path('catalog-categories/', views.CatalogCategoryListView.as_view(), name='catalog-categories'),
    path('products/', views.ProductListView.as_view(), name='products'),
    path('inventory-items/', views.InventoryItemListView.as_view(), name='inventory-items'),
    path('products/featured/', views.FeaturedProductListView.as_view(), name='featured-products'),
    # Search must come before slug route to avoid conflict
    path('products/search/suggestions/', views.ProductSuggestionsView.as_view(), name='product-suggestions'),
    path('products/search/', views.ProductSearchView.as_view(), name='product-search'),
    path('products/availability/', views.ProductAvailabilityView.as_view(), name='product-availability'),
    path('products/<int:pk>/availability/', views.ProductAvailabilityDetailView.as_view(), name='product-availability-detail'),
    path('products/id/<int:pk>/', views.ProductDetailByIdView.as_view(), name='product-detail-by-id-alias'),
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
    path('webhooks/inventory/', views.InventoryWebhookView.as_view(), name='inventory-webhook'),
    *_admin_crud_patterns(
        'categories',
        views.AdminCategoryListCreateView,
        views.AdminCategoryDetailView,
        'categories',
        'category',
    ),
    *_admin_crud_patterns(
        'sub-categories',
        views.AdminSubCategoryListCreateView,
        views.AdminSubCategoryDetailView,
        'sub-categories',
        'sub-category',
    ),
    *_admin_crud_patterns(
        'brands',
        views.AdminBrandListCreateView,
        views.AdminBrandDetailView,
        'brands',
        'brand',
    ),
    path('admin/products/', views.AdminProductListCreateView.as_view(), name='admin-products'),
    path('admin/products/meta/', views.AdminProductFormMetaView.as_view(), name='admin-product-form-meta'),
    path('admin/products/pos-options/', views.AdminPosProductOptionListView.as_view(), name='admin-pos-product-options'),
    path('admin/products/<int:pk>/', views.AdminProductDetailView.as_view(), name='admin-product-detail'),
    path('admin/products/<int:product_pk>/images/', views.AdminProductImageListCreateView.as_view(), name='admin-product-images'),
    path('admin/products/<int:product_pk>/images/<int:pk>/', views.AdminProductImageDetailView.as_view(), name='admin-product-image-detail'),
    path('admin/products/<int:product_pk>/variants/', views.AdminProductVariantListCreateView.as_view(), name='admin-product-variants'),
    path('admin/products/<int:product_pk>/variants/<int:pk>/', views.AdminProductVariantDetailView.as_view(), name='admin-product-variant-detail'),
    path('admin/inventory/', views.AdminInventoryListView.as_view(), name='admin-inventory'),
    path('admin/inventory/variant-pos-refresh/', views.AdminInventoryVariantPosRefreshView.as_view(), name='admin-inventory-variant-pos-refresh'),
    path('admin/inventory/pos-sync/', views.AdminInventoryPosSyncView.as_view(), name='admin-inventory-pos-sync'),
    path('admin/inventory/pos-refresh/', views.AdminInventoryPosRefreshView.as_view(), name='admin-inventory-pos-refresh'),
    path('admin/inventory/bulk-update/', views.AdminInventoryBulkUpdateView.as_view(), name='admin-inventory-bulk-update'),
    path('admin/inventory/reserve/', views.AdminInventoryReserveView.as_view(), name='admin-inventory-reserve'),
    path('admin/inventory/release/', views.AdminInventoryReleaseView.as_view(), name='admin-inventory-release'),
    path('admin/inventory/deduct/', views.AdminInventoryDeductView.as_view(), name='admin-inventory-deduct'),
    path('admin/inventory/<int:pk>/movements/', views.AdminInventoryMovementsView.as_view(), name='admin-inventory-movements'),
    path('admin/inventory/<int:pk>/', views.AdminInventoryAdjustView.as_view(), name='admin-inventory-adjust'),
    *_admin_crud_patterns(
        'banners',
        views.AdminBannerListCreateView,
        views.AdminBannerDetailView,
        'banners',
        'banner',
    ),
    *_admin_crud_patterns(
        'cms',
        views.AdminCMSBlockListCreateView,
        views.AdminCMSBlockDetailView,
        'cms-blocks',
        'cms-block',
    ),
    *_admin_crud_patterns(
        'promotions',
        views.AdminPromotionListCreateView,
        views.AdminPromotionDetailView,
        'promotions',
        'promotion',
    ),
    *_admin_crud_patterns(
        'health-concerns',
        views.AdminHealthConcernListCreateView,
        views.AdminHealthConcernDetailView,
        'health-concerns',
        'health-concern',
    ),
]
