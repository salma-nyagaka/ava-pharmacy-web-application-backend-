from django.urls import path
from . import views

urlpatterns = [
    path('catalog/summary/', views.CatalogSummaryView.as_view(), name='catalog-summary'),
    path('categories/', views.CategoryListView.as_view(), name='categories'),
    path('brands/', views.BrandListView.as_view(), name='brands'),
    path('products/', views.ProductListView.as_view(), name='products'),
    path('products/featured/', views.FeaturedProductListView.as_view(), name='featured-products'),
    path('products/<slug:slug>/', views.ProductDetailView.as_view(), name='product-detail'),
    path('products/<int:pk>/reviews/', views.ProductReviewListCreateView.as_view(), name='product-reviews'),
    path('wishlist/', views.WishlistView.as_view(), name='wishlist'),
    path('wishlist/<int:pk>/', views.WishlistItemDeleteView.as_view(), name='wishlist-item'),
    path('banners/', views.BannerListView.as_view(), name='banners'),
    path('promotions/', views.PromotionListView.as_view(), name='promotions'),
    path('admin/categories/', views.AdminCategoryListCreateView.as_view(), name='admin-categories'),
    path('admin/categories/<int:pk>/', views.AdminCategoryDetailView.as_view(), name='admin-category-detail'),
    path('admin/brands/', views.AdminBrandListCreateView.as_view(), name='admin-brands'),
    path('admin/brands/<int:pk>/', views.AdminBrandDetailView.as_view(), name='admin-brand-detail'),
    path('admin/products/', views.AdminProductListCreateView.as_view(), name='admin-products'),
    path('admin/products/<int:pk>/', views.AdminProductDetailView.as_view(), name='admin-product-detail'),
    path('admin/inventory/', views.AdminInventoryListView.as_view(), name='admin-inventory'),
    path('admin/inventory/<int:pk>/', views.AdminInventoryAdjustView.as_view(), name='admin-inventory-adjust'),
    path('admin/banners/', views.AdminBannerListCreateView.as_view(), name='admin-banners'),
    path('admin/banners/<int:pk>/', views.AdminBannerDetailView.as_view(), name='admin-banner-detail'),
    path('admin/promotions/', views.AdminPromotionListCreateView.as_view(), name='admin-promotions'),
    path('admin/promotions/<int:pk>/', views.AdminPromotionDetailView.as_view(), name='admin-promotion-detail'),
]
