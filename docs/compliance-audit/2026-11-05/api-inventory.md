# Current API inventory — 5 November 2026

316 canonical routes: 314 REST/documentation routes plus two server-rendered activation routes. Versioned/base aliases share handlers. Static permission names below do not replace the handler’s dynamic account/ownership/role checks.

| Route | Methods | Handler / declared permissions |
|---|---|---|
| `/api/schema/` | GET | [SpectacularAPIView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/venv/lib/python3.11/site-packages/drf_spectacular/views.py:44) — AllowAny |
| `/api/docs/` | GET | [SpectacularSwaggerView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/venv/lib/python3.11/site-packages/drf_spectacular/views.py:122) — AllowAny |
| `/api/redoc/` | GET | [SpectacularRedocView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/venv/lib/python3.11/site-packages/drf_spectacular/views.py:234) — AllowAny |
| `/api/auth/register/` | POST | [RegisterView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/accounts/views.py:93) — AllowAny |
| `/api/auth/login/` | POST | [LoginView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/accounts/views.py:200) — AllowAny |
| `/api/auth/logout/` | POST | [LogoutView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/accounts/views.py:279) — IsAuthenticated |
| `/api/auth/verify-email/` | POST | [VerifyEmailView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/accounts/views.py:888) — AllowAny |
| `/api/auth/resend-verification/` | POST | [ResendVerificationView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/accounts/views.py:911) — AllowAny |
| `/api/auth/forgot-password/` | POST | [ForgotPasswordView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/accounts/views.py:810) — AllowAny |
| `/api/auth/reset-password/` | POST | [ResetPasswordView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/accounts/views.py:846) — AllowAny |
| `/api/auth/pharmacist/activate/` | POST | [PharmacistActivationSetPasswordView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/accounts/views.py:334) — AllowAny |
| `/api/auth/pharmacist/activate/<str:token>/` | GET, POST | [PharmacistActivationPageView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/accounts/views.py:363) — Django activation view |
| `/api/auth/professional/activate/` | POST | [ProfessionalActivationSetPasswordView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/accounts/views.py:413) — AllowAny |
| `/api/auth/professional/activate/<str:token>/` | GET, POST | [ProfessionalActivationPageView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/accounts/views.py:417) — Django activation view |
| `/api/auth/token/refresh/` | POST | [ActiveUserTokenRefreshView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/accounts/views.py:89) —  |
| `/api/auth/refresh/` | POST | [ActiveUserTokenRefreshView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/accounts/views.py:89) —  |
| `/api/auth/me/` | GET, PUT, PATCH | [MeView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/accounts/views.py:293) — IsAuthenticated |
| `/api/auth/me/password/` | POST | [PasswordChangeView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/accounts/views.py:316) — IsAuthenticated |
| `/api/auth/me/addresses/` | GET, POST | [AddressListCreateView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/accounts/views.py:694) — IsAuthenticated |
| `/api/auth/me/addresses/<int:pk>/` | GET, PUT, PATCH, DELETE | [AddressDetailView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/accounts/views.py:712) — IsAuthenticated |
| `/api/auth/me/payment-methods/` | GET, POST | [PaymentMethodListCreateView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/accounts/views.py:739) — IsAuthenticated |
| `/api/auth/me/payment-methods/<int:pk>/` | GET, PUT, PATCH, DELETE | [PaymentMethodDetailView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/accounts/views.py:758) — IsAuthenticated |
| `/api/professionals/register/` | POST | [ProfessionalRegistrationView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/accounts/views.py:134) — AllowAny |
| `/api/professionals/lab-partners/` | GET | [PublicLabPartnerListView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/accounts/views.py:188) — AllowAny |
| `/api/account/profile/` | GET, PUT, PATCH | [AccountProfileView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/accounts/views.py:930) — IsAuthenticated |
| `/api/account/change-password/` | POST | [PasswordChangeView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/accounts/views.py:316) — IsAuthenticated |
| `/api/account/` | DELETE | [AccountDeleteView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/accounts/views.py:934) — IsAuthenticated |
| `/api/admin/users/` | GET, POST | [AdminUserListCreateView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/accounts/views.py:421) — IsAdminUser |
| `/api/admin/users/<int:pk>/` | GET, PUT, PATCH, DELETE | [AdminUserDetailView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/accounts/views.py:486) — IsAdminUser |
| `/api/admin/users/<int:pk>/suspend/` | POST | [AdminUserSuspendView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/accounts/views.py:585) — IsAdminUser |
| `/api/admin/users/<int:pk>/activate/` | POST | [AdminUserActivateView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/accounts/views.py:610) — IsAdminUser |
| `/api/admin/users/<int:pk>/resend-activation/` | POST | [AdminPharmacistActivationResendView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/accounts/views.py:652) — IsAdminUser |
| `/api/admin/users/<int:pk>/notes/` | GET, POST | [UserNoteListCreateView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/accounts/views.py:783) — IsAdminUser |
| `/api/admin/customers/` | GET, POST | [AdminCustomerListCreateView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/accounts/views.py:467) — IsAdminUser |
| `/api/admin/customers/stats/` | GET | [AdminCustomerStatsView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/accounts/views.py:547) — IsAdminUser |
| `/api/admin/customers/<int:pk>/` | GET, PUT, PATCH, DELETE | [AdminCustomerDetailView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/accounts/views.py:531) — IsAdminUser |
| `/api/admin/customers/<int:pk>/suspend/` | POST | [AdminCustomerSuspendView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/accounts/views.py:634) — IsAdminUser |
| `/api/admin/customers/<int:pk>/activate/` | POST | [AdminCustomerActivateView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/accounts/views.py:643) — IsAdminUser |
| `/api/admin/customers/<int:pk>/notes/` | GET, POST | [UserNoteListCreateView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/accounts/views.py:783) — IsAdminUser |
| `/api/admin/audit-logs/` | GET | [AdminAuditLogListView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/accounts/views.py:798) — IsAdminOrPPBInspector |
| `/api/catalog/summary/` | GET | [CatalogSummaryView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/products/views.py:1315) — AllowAny |
| `/api/categories/` | GET | [CategoryListView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/products/views.py:225) — AllowAny |
| `/api/product-categories/` | GET | [CategoryListView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/products/views.py:225) — AllowAny |
| `/api/products/categories/` | GET | [CategoryListView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/products/views.py:225) — AllowAny |
| `/api/brands/` | GET | [BrandListView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/products/views.py:263) — AllowAny |
| `/api/stores/` | GET | [StoreListView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/products/views.py:269) — AllowAny |
| `/api/health-concerns/` | GET | [HealthConcernListView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/products/views.py:275) — AllowAny |
| `/api/catalog-categories/` | GET | [CatalogCategoryListView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/products/views.py:281) — AllowAny |
| `/api/products/` | GET | [ProductListView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/products/views.py:292) — AllowAny |
| `/api/inventory-items/` | GET | [InventoryItemListView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/products/views.py:317) — AllowAny |
| `/api/products/featured/` | GET | [FeaturedProductListView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/products/views.py:395) — AllowAny |
| `/api/products/search/suggestions/` | GET | [ProductSuggestionsView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/products/views.py:1465) — AllowAny |
| `/api/products/search/` | GET | [ProductSearchView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/products/views.py:1385) — AllowAny |
| `/api/products/availability/` | GET | [ProductAvailabilityView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/products/views.py:1499) — AllowAny |
| `/api/products/<int:pk>/availability/` | GET | [ProductAvailabilityDetailView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/products/views.py:1536) — AllowAny |
| `/api/products/id/<int:pk>/` | GET | [ProductDetailByIdView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/products/views.py:1348) — AllowAny |
| `/api/products/<int:pk>/` | GET | [ProductDetailByIdView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/products/views.py:1348) — AllowAny |
| `/api/products/slug/<slug:slug>/` | GET | [ProductDetailView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/products/views.py:431) — AllowAny |
| `/api/products/<slug:slug>/` | GET | [ProductDetailView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/products/views.py:431) — AllowAny |
| `/api/products/<int:pk>/reviews/` | GET, POST | [ProductReviewListCreateView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/products/views.py:703) — IsAuthenticated |
| `/api/variants/<int:variant_pk>/reviews/` | GET, POST | [ProductReviewListCreateView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/products/views.py:703) — IsAuthenticated |
| `/api/wishlist/` | GET, POST | [WishlistView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/products/views.py:764) — IsAuthenticated |
| `/api/wishlist/<int:pk>/` | DELETE | [WishlistItemDeleteView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/products/views.py:811) — IsAuthenticated |
| `/api/wishlist/<int:pk>/move-to-cart/` | POST | [WishlistItemMoveToCartView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/products/views.py:818) — IsAuthenticated |
| `/api/cart/items/<int:pk>/move-to-wishlist/` | POST | [CartItemMoveToWishlistView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/products/views.py:865) — IsAuthenticated |
| `/api/banners/` | GET | [BannerListView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/products/views.py:886) — AllowAny |
| `/api/cms/` | GET | [CMSBlockListView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/products/views.py:899) — AllowAny |
| `/api/faqs/` | GET | [FAQListView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/products/views.py:912) — AllowAny |
| `/api/promotions/` | GET | [PromotionListView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/products/views.py:957) — AllowAny |
| `/api/webhooks/inventory/` | POST | [InventoryWebhookView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/products/views.py:1585) — AllowAny |
| `/api/admin/categories/` | GET, POST | [AdminCategoryListCreateView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/products/views.py:450) — IsAdminOrInventoryStaff |
| `/api/admin/categories/<int:pk>/` | GET, PUT, PATCH, DELETE | [AdminCategoryDetailView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/products/views.py:471) — IsAdminOrInventoryStaff |
| `/api/admin/sub-categories/` | GET, POST | [AdminSubCategoryListCreateView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/products/views.py:489) — IsAdminOrInventoryStaff |
| `/api/admin/sub-categories/<int:pk>/` | GET, PUT, PATCH, DELETE | [AdminSubCategoryDetailView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/products/views.py:503) — IsAdminOrInventoryStaff |
| `/api/admin/brands/` | GET, POST | [AdminBrandListCreateView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/products/views.py:513) — IsAdminOrInventoryStaff |
| `/api/admin/brands/<int:pk>/` | GET, PUT, PATCH, DELETE | [AdminBrandDetailView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/products/views.py:531) — IsAdminOrInventoryStaff |
| `/api/admin/stores/` | GET, POST | [AdminStoreListCreateView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/products/views.py:547) — IsAdminOrInventoryStaff |
| `/api/admin/stores/<int:pk>/` | GET, PUT, PATCH, DELETE | [AdminStoreDetailView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/products/views.py:555) — IsAdminOrInventoryStaff |
| `/api/admin/store-listings/` | GET, POST | [AdminStoreVariantListingListCreateView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/products/views.py:561) — IsAdminOrInventoryStaff |
| `/api/admin/store-listings/<int:pk>/` | GET, PUT, PATCH, DELETE | [AdminStoreVariantListingDetailView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/products/views.py:577) — IsAdminOrInventoryStaff |
| `/api/admin/products/` | GET, POST | [AdminProductListCreateView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/products/views.py:585) — IsAdminOrInventoryStaff |
| `/api/admin/products/meta/` | GET | [AdminProductFormMetaView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/products/views.py:618) — IsAdminOrInventoryStaff |
| `/api/admin/products/pos-options/` | GET | [AdminPosProductOptionListView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/products/views.py:632) — IsAdminOrInventoryStaff |
| `/api/admin/products/<int:pk>/` | GET, PUT, PATCH, DELETE | [AdminProductDetailView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/products/views.py:672) — IsAdminOrInventoryStaff |
| `/api/admin/products/<int:product_pk>/images/` | GET, POST | [AdminProductImageListCreateView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/products/views.py:1027) — IsAdminOrInventoryStaff |
| `/api/admin/products/<int:product_pk>/images/<int:pk>/` | GET, PUT, PATCH, DELETE | [AdminProductImageDetailView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/products/views.py:1046) — IsAdminOrInventoryStaff |
| `/api/admin/products/<int:product_pk>/variants/` | GET, POST | [AdminProductVariantListCreateView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/products/views.py:1054) — IsAdminOrInventoryStaff |
| `/api/admin/products/<int:product_pk>/variants/<int:pk>/` | GET, PUT, PATCH, DELETE | [AdminProductVariantDetailView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/products/views.py:1079) — IsAdminOrInventoryStaff |
| `/api/admin/inventory/` | GET | [AdminInventoryListView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/products/views.py:1167) — IsAdminOrInventoryStaff |
| `/api/admin/inventory/variant-pos-refresh/` | POST | [AdminInventoryVariantPosRefreshView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/products/views.py:1250) — IsAdminOrInventoryStaff |
| `/api/admin/inventory/pos-sync/` | POST | [AdminInventoryPosSyncView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/products/views.py:1665) — IsAdminOrInventoryStaff |
| `/api/admin/inventory/pos-refresh/` | POST | [AdminInventoryPosRefreshView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/products/views.py:1199) — IsAdminOrInventoryStaff |
| `/api/admin/inventory/bulk-update/` | POST | [AdminInventoryBulkUpdateView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/products/views.py:1598) — IsAdminOrInventoryStaff |
| `/api/admin/inventory/reserve/` | POST | [AdminInventoryReserveView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/products/views.py:1781) — IsAdminOrInventoryStaff |
| `/api/admin/inventory/release/` | POST | [AdminInventoryReleaseView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/products/views.py:1812) — IsAdminOrInventoryStaff |
| `/api/admin/inventory/deduct/` | POST | [AdminInventoryDeductView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/products/views.py:1834) — IsAdminOrInventoryStaff |
| `/api/admin/inventory/<int:pk>/movements/` | GET | [AdminInventoryMovementsView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/products/views.py:1765) — IsAdminOrInventoryStaff |
| `/api/admin/inventory/<int:pk>/` | PATCH | [AdminInventoryAdjustView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/products/views.py:1298) — IsAdminOrInventoryStaff |
| `/api/admin/banners/` | GET, POST | [AdminBannerListCreateView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/products/views.py:925) — IsAdminUser |
| `/api/admin/banners/<int:pk>/` | GET, PUT, PATCH, DELETE | [AdminBannerDetailView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/products/views.py:941) — IsAdminUser |
| `/api/admin/cms/` | GET, POST | [AdminCMSBlockListCreateView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/products/views.py:1087) — IsAdminUser |
| `/api/admin/cms/<int:pk>/` | GET, PUT, PATCH, DELETE | [AdminCMSBlockDetailView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/products/views.py:1105) — IsAdminUser |
| `/api/admin/faqs/` | GET, POST | [AdminFAQListCreateView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/products/views.py:1121) — IsAdminUser |
| `/api/admin/faqs/<int:pk>/` | GET, PUT, PATCH, DELETE | [AdminFAQDetailView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/products/views.py:1140) — IsAdminUser |
| `/api/admin/promotions/` | GET, POST | [AdminPromotionListCreateView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/products/views.py:974) — IsAdminUser |
| `/api/admin/promotions/<int:pk>/` | GET, PUT, PATCH, DELETE | [AdminPromotionDetailView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/products/views.py:991) — IsAdminUser |
| `/api/admin/health-concerns/` | GET, POST | [AdminHealthConcernListCreateView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/products/views.py:1007) — IsAdminOrInventoryStaff |
| `/api/admin/health-concerns/<int:pk>/` | GET, PUT, PATCH, DELETE | [AdminHealthConcernDetailView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/products/views.py:1018) — IsAdminOrInventoryStaff |
| `/api/shipping-methods/` | GET | [ShippingMethodListView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/orders/views.py:2651) — AllowAny |
| `/api/checkout/delivery-options/` | GET | [ShippingMethodListView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/orders/views.py:2651) — AllowAny |
| `/api/cart/` | GET | [CartView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/orders/views.py:1185) — IsAuthenticated |
| `/api/cart/items/` | POST | [CartItemCreateView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/orders/views.py:1193) — IsAuthenticated |
| `/api/cart/items/<int:pk>/` | PATCH | [CartItemUpdateView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/orders/views.py:1332) — IsAuthenticated |
| `/api/cart/items/<int:pk>/delete/` | DELETE | [CartItemDeleteView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/orders/views.py:1380) — IsAuthenticated |
| `/api/cart/clear/` | DELETE | [CartClearView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/orders/views.py:1393) — IsAuthenticated |
| `/api/cart/merge/` | POST | [CartMergeView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/orders/views.py:3460) — IsAuthenticated |
| `/api/cart/coupon/` | POST | [CartApplyCouponView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/orders/views.py:1404) — IsAuthenticated |
| `/api/cart/coupon/remove/` | DELETE | [CartRemoveCouponView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/orders/views.py:1427) — IsAuthenticated |
| `/api/cart/promo/` | POST | [CartApplyCouponView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/orders/views.py:1404) — IsAuthenticated |
| `/api/cart/promo/remove/` | DELETE | [CartRemoveCouponView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/orders/views.py:1427) — IsAuthenticated |
| `/api/checkout/draft/` | POST | [CheckoutDraftView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/orders/views.py:1437) — IsAuthenticated |
| `/api/checkout/<int:pk>/finalize/` | POST | [CheckoutFinalizeView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/orders/views.py:2493) — IsAuthenticated |
| `/api/payments/intents/` | POST | [PaymentIntentCreateView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/orders/views.py:1523) — IsAuthenticated |
| `/api/payments/intents/<int:pk>/sync/` | POST | [PaymentIntentStatusSyncView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/orders/views.py:1946) — IsAuthenticated |
| `/api/payments/intents/<int:pk>/cancel/` | POST | [PaymentIntentCancelView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/orders/views.py:2073) — IsAuthenticated |
| `/api/orders/payments/flutterwave/initiate/` | POST | [FlutterwaveInitiateView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/orders/views.py:1739) — IsAuthenticated |
| `/api/orders/payments/flutterwave/callback/` | POST | [FlutterwaveCallbackView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/orders/views.py:1863) — AllowAny |
| `/api/orders/payments/flutterwave/redirect/` | GET | [FlutterwaveRedirectView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/orders/views.py:1746) — AllowAny |
| `/api/orders/payments/flutterwave/status/<str:tx_ref>/` | GET | [FlutterwaveStatusView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/orders/views.py:1826) — IsAuthenticated |
| `/api/payments/mpesa/initiate/` | POST | [MpesaInitiateView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/orders/views.py:3673) — IsAuthenticated |
| `/api/payments/mpesa/status/<str:checkout_request_id>/` | GET | [MpesaStatusView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/orders/views.py:3759) — IsAuthenticated |
| `/api/payments/mpesa/callback/` | POST | [MpesaCallbackView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/orders/views.py:1906) — AllowAny |
| `/api/payments/mpesa/paybill/validation/` | POST | [MpesaPaybillValidationView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/orders/views.py:2117) — AllowAny |
| `/api/payments/mpesa/paybill/confirmation/` | POST | [MpesaPaybillConfirmationView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/orders/views.py:2167) — AllowAny |
| `/api/payments/mpesa/paybill/webhook/` | POST | [PaybillWebhookView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/orders/views.py:2277) — AllowAny |
| `/api/payments/webhook/` | POST | [PaymentWebhookView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/orders/views.py:2207) — AllowAny |
| `/api/webhooks/order-status/` | POST | [OrderStatusWebhookView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/orders/views.py:2894) — AllowAny |
| `/api/orders/` | GET | [OrderListView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/orders/views.py:2571) — IsAuthenticated |
| `/api/orders/create/` | POST | [OrderCreateView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/orders/views.py:3515) — IsAuthenticated |
| `/api/orders/tracking/lookup/` | POST | [PublicOrderTrackingLookupView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/orders/views.py:3641) — AllowAny |
| `/api/orders/<int:pk>/` | GET | [OrderDetailView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/orders/views.py:2581) — IsAuthenticated |
| `/api/orders/<int:pk>/cancel/` | POST | [OrderCancelView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/orders/views.py:2591) — IsAuthenticated |
| `/api/orders/<int:pk>/tracking/` | GET | [OrderTrackingView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/orders/views.py:3623) — IsAuthenticated |
| `/api/orders/<int:pk>/return/` | GET, POST | [ReturnRequestListCreateView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/orders/views.py:2618) — IsAuthenticated |
| `/api/returns/` | GET, POST | [ReturnRequestListCreateView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/orders/views.py:2618) — IsAuthenticated |
| `/api/admin/orders/` | GET | [AdminOrderListView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/orders/views.py:2691) — IsPharmacistAdminOrPPBInspector |
| `/api/admin/orders/<int:pk>/` | GET, PUT, PATCH | [AdminOrderDetailView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/orders/views.py:2705) — IsPharmacistAdminOrPPBInspector |
| `/api/admin/orders/<int:pk>/delivery-audits/` | GET, POST | [AdminOrderDeliveryAuditListCreateView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/orders/views.py:3434) — IsPharmacistAdminOrPPBInspector |
| `/api/admin/orders/<int:pk>/status/` | PUT | [AdminOrderStatusView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/orders/views.py:3792) — IsAdminUser |
| `/api/admin/order-push/` | GET | [AdminOrderPushListView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/orders/views.py:2861) — IsAdminUser |
| `/api/admin/order-push/<int:pk>/retry/` | POST | [AdminOrderPushRetryView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/orders/views.py:2871) — IsAdminUser |
| `/api/admin/orders/<int:pk>/notes/` | POST | [AdminOrderNoteView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/orders/views.py:2775) — IsPharmacistOrAdmin |
| `/api/admin/orders/<int:pk>/refund/` | POST | [AdminOrderRefundView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/orders/views.py:2795) — IsAdminUser |
| `/api/admin/finance/` | GET | [AdminFinanceDashboardView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/orders/views.py:3277) — IsAdminUser |
| `/api/admin/finance/reports/` | GET | [AdminReportsView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/orders/views.py:2958) — IsAdminUser |
| `/api/admin/finance/reports/download/` | GET | [AdminDownloadReportView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/orders/views.py:3355) — IsAdminUser |
| `/api/admin/finance/payments/` | GET | [AdminPaymentIntentListView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/orders/views.py:2836) — IsAdminUser |
| `/api/admin/finance/payments/<int:pk>/` | GET | [AdminPaymentIntentDetailView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/orders/views.py:2853) — IsAdminUser |
| `/api/admin/finance/payments/<int:pk>/reconcile/` | POST | [AdminPaybillReconcileView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/orders/views.py:2392) — IsAdminUser |
| `/api/admin/finance/invoices/` | GET | [AdminInvoiceListView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/orders/views.py:3327) — IsAdminUser |
| `/api/admin/finance/invoices/<int:pk>/` | GET | [AdminInvoiceDetailView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/orders/views.py:3343) — IsAdminUser |
| `/api/admin/finance/returns/` | GET | [AdminReturnRequestListView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/orders/views.py:2921) — IsAdminOrPPBInspector |
| `/api/admin/finance/returns/<int:pk>/` | GET, PUT, PATCH | [AdminReturnRequestDetailView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/orders/views.py:2931) — IsAdminOrPPBInspector |
| `/api/admin/payments/mpesa/paybill/register-urls/` | POST | [AdminMpesaPaybillRegisterUrlsView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/orders/views.py:2451) — IsAdminUser |
| `/api/admin/payments/intents/<int:pk>/reconcile/` | POST | [AdminPaybillReconcileView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/orders/views.py:2392) — IsAdminUser |
| `/api/admin/shipping-methods/` | GET, POST | [AdminShippingMethodListCreateView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/orders/views.py:2657) — IsAdminUser |
| `/api/admin/shipping-methods/<int:pk>/` | GET, PUT, PATCH, DELETE | [AdminShippingMethodDetailView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/orders/views.py:2675) — IsAdminUser |
| `/api/admin/returns/` | GET | [AdminReturnRequestListView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/orders/views.py:2921) — IsAdminOrPPBInspector |
| `/api/admin/returns/<int:pk>/` | GET, PUT, PATCH | [AdminReturnRequestDetailView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/orders/views.py:2931) — IsAdminOrPPBInspector |
| `/api/admin/reports/` | GET | [AdminReportsView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/orders/views.py:2958) — IsAdminUser |
| `/api/admin/reports/download/` | GET | [AdminDownloadReportView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/orders/views.py:3355) — IsAdminUser |
| `/api/admin/activity-feed/` | GET | [AdminActivityFeedView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/orders/views.py:3281) — IsAdminUser |
| `/api/admin/invoices/` | GET | [AdminInvoiceListView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/orders/views.py:3327) — IsAdminUser |
| `/api/admin/invoices/<int:pk>/` | GET | [AdminInvoiceDetailView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/orders/views.py:3343) — IsAdminUser |
| `/api/prescriptions/<int:pk>/files/<int:file_pk>/download/<str:filename>` | GET | [PrescriptionFileDownloadView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/prescriptions/views.py:732) — AllowAny |
| `/api/prescriptions/<int:pk>/files/<int:file_pk>/download/` | GET | [PrescriptionFileDownloadView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/prescriptions/views.py:732) — AllowAny |
| `/api/prescriptions/` | GET | [PrescriptionListView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/prescriptions/views.py:166) — IsAuthenticated |
| `/api/prescriptions/upload/` | POST | [PrescriptionUploadView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/prescriptions/views.py:178) — IsAuthenticated |
| `/api/prescriptions/<int:pk>/` | GET | [PrescriptionDetailView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/prescriptions/views.py:266) — IsAuthenticated |
| `/api/prescriptions/<int:pk>/clarification-replies/` | POST | [PrescriptionClarificationReplyView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/prescriptions/views.py:673) — IsAuthenticated |
| `/api/prescriptions/<int:pk>/update/` | PUT, PATCH | [PrescriptionUpdateView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/prescriptions/views.py:277) — CanReviewPrescriptionsOrAdmin |
| `/api/prescriptions/<int:pk>/resubmit/` | PATCH | [PrescriptionResubmitView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/prescriptions/views.py:625) — IsAuthenticated |
| `/api/prescriptions/<int:pk>/audit/` | POST | [PrescriptionAuditView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/prescriptions/views.py:318) — CanReviewPrescriptionsOrAdmin |
| `/api/prescriptions/<int:pk>/items/<int:item_pk>/add-to-cart/` | POST | [PrescriptionItemAddToCartView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/prescriptions/views.py:403) — IsAuthenticated |
| `/api/pharmacist/prescriptions/` | GET | [PharmacistPrescriptionQueueView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/prescriptions/views.py:510) — IsPrescriptionReviewPharmacist |
| `/api/pharmacist/catalog/variants/` | GET | [PharmacistVariantSearchView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/prescriptions/views.py:356) — IsPharmacistOrAdmin |
| `/api/pharmacist/prescriptions/<int:pk>/assign/` | POST | [PharmacistPrescriptionAssignView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/prescriptions/views.py:524) — IsPrescriptionReviewPharmacist |
| `/api/pharmacist/prescriptions/<int:pk>/review/` | POST | [PharmacistPrescriptionReviewView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/prescriptions/views.py:548) — IsPrescriptionReviewPharmacist |
| `/api/admin/prescriptions/` | GET | [AdminPrescriptionListView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/prescriptions/views.py:345) — CanReadPrescriptionRegister |
| `/api/doctors/` | GET | [DoctorListView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/consultations/views.py:562) — AllowAny |
| `/api/doctors/<int:pk>/` | GET | [DoctorDetailView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/consultations/views.py:582) — AllowAny |
| `/api/doctors/register/` | POST | [DoctorOnboardingView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/consultations/views.py:610) — AllowAny |
| `/api/professionals/register/doctor/` | POST | [DoctorOnboardingView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/consultations/views.py:610) — AllowAny |
| `/api/professionals/applications/resubmissions/<path:token>/` | GET, POST | [ProfessionalDocumentResubmissionView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/consultations/views.py:634) — AllowAny |
| `/api/doctor/onboarding/profile/` | PATCH | [DoctorOnboardingProfileStepView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/consultations/views.py:712) — IsDoctor |
| `/api/doctor/onboarding/documents/` | POST | [DoctorOnboardingDocumentsStepView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/consultations/views.py:726) — IsDoctor |
| `/api/doctor/onboarding/availability/` | PATCH | [DoctorOnboardingAvailabilityStepView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/consultations/views.py:757) — IsDoctor |
| `/api/doctor/onboarding/payout/` | PATCH | [DoctorOnboardingPayoutStepView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/consultations/views.py:770) — IsDoctor |
| `/api/pediatricians/` | GET | [PediatricianListView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/consultations/views.py:572) — AllowAny |
| `/api/pediatricians/<int:pk>/` | GET | [PediatricianDetailView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/consultations/views.py:595) — AllowAny |
| `/api/professionals/register/pediatrician/` | POST | [PediatricianOnboardingView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/consultations/views.py:622) — AllowAny |
| `/api/consultations/` | GET, POST | [ConsultationListCreateView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/consultations/views.py:1017) — IsAuthenticated |
| `/api/consultations/<int:pk>/` | GET, PUT, PATCH | [ConsultationDetailView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/consultations/views.py:1305) — IsAuthenticated |
| `/api/consultations/<int:pk>/messages/` | GET, POST | [ConsultationMessageListCreateView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/consultations/views.py:1401) — IsAuthenticated |
| `/api/consultations/messages/<int:pk>/attachment/` | GET | [ConsultationMessageAttachmentView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/consultations/views.py:1904) — IsAuthenticated |
| `/api/consultations/<int:pk>/end/` | POST | [ConsultationEndView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/consultations/views.py:1528) — IsDoctor |
| `/api/consultations/<int:pk>/consent/` | POST | [GuardianConsentView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/consultations/views.py:876) — IsAuthenticated |
| `/api/consultations/payments/intents/` | POST | [ConsultationPaymentIntentCreateView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/consultations/views.py:1072) — IsAuthenticated |
| `/api/consultations/payments/intents/<int:pk>/sync/` | POST | [ConsultationPaymentIntentStatusView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/consultations/views.py:1179) — IsAuthenticated |
| `/api/consultations/payments/finalize/` | POST | [ConsultationPaymentFinalizeView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/consultations/views.py:1234) — IsAuthenticated |
| `/api/consultations/payments/mpesa/callback/` | POST | [ConsultationMpesaCallbackView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/consultations/views.py:1256) — AllowAny |
| `/api/guardian/children/` | GET, POST | [GuardianChildPatientListCreateView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/consultations/views.py:894) — IsAuthenticated |
| `/api/guardian/children/<int:pk>/` | GET, PUT, PATCH, DELETE | [GuardianChildPatientDetailView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/consultations/views.py:905) — IsAuthenticated |
| `/api/doctor/dashboard/` | GET | [DoctorDashboardView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/consultations/views.py:787) — IsDoctor |
| `/api/doctor/consultations/` | GET | [DoctorConsultationListView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/consultations/views.py:1514) — IsDoctor |
| `/api/doctor/catalog/variants/` | GET | [ClinicianVariantSearchView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/consultations/views.py:1647) — IsDoctor |
| `/api/doctor/prescriptions/` | GET, POST | [ClinicianPrescriptionListCreateView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/consultations/views.py:1586) — IsDoctor |
| `/api/doctor/prescriptions/<int:pk>/send/` | POST | [ClinicianPrescriptionSendView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/consultations/views.py:1694) — IsDoctor |
| `/api/doctor/prescriptions/<int:pk>/pdf/` | GET | [ClinicianPrescriptionPDFView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/consultations/views.py:1833) — IsDoctor |
| `/api/doctor/earnings/` | GET | [ClinicianEarningsView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/consultations/views.py:1935) — IsDoctor |
| `/api/pediatrician/dashboard/` | GET | [PediatricianDashboardView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/consultations/views.py:831) — IsDoctor |
| `/api/pediatrician/consultations/` | GET | [DoctorConsultationListView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/consultations/views.py:1514) — IsDoctor |
| `/api/pediatrician/catalog/variants/` | GET | [ClinicianVariantSearchView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/consultations/views.py:1647) — IsDoctor |
| `/api/pediatrician/patients/` | GET | [PediatricianPatientListView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/consultations/views.py:917) — IsDoctor |
| `/api/pediatrician/patients/<int:child_id>/` | GET | [PediatricianPatientDetailView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/consultations/views.py:956) — IsDoctor |
| `/api/pediatrician/prescriptions/` | GET, POST | [ClinicianPrescriptionListCreateView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/consultations/views.py:1586) — IsDoctor |
| `/api/pediatrician/prescriptions/<int:pk>/send/` | POST | [ClinicianPrescriptionSendView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/consultations/views.py:1694) — IsDoctor |
| `/api/pediatrician/prescriptions/<int:pk>/pdf/` | GET | [ClinicianPrescriptionPDFView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/consultations/views.py:1833) — IsDoctor |
| `/api/pediatrician/earnings/` | GET | [ClinicianEarningsView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/consultations/views.py:1935) — IsDoctor |
| `/api/clinician/prescriptions/` | GET, POST | [ClinicianPrescriptionListCreateView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/consultations/views.py:1586) — IsDoctor |
| `/api/clinician/earnings/` | GET | [ClinicianEarningsView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/consultations/views.py:1935) — IsDoctor |
| `/api/admin/dashboard/` | GET | [AdminDashboardView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/consultations/views.py:2309) — IsAdminUser |
| `/api/admin/doctors/` | GET | [AdminDoctorListView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/consultations/views.py:1952) — IsAdminUser |
| `/api/admin/doctors/<int:pk>/` | GET, PUT, PATCH | [AdminDoctorDetailView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/consultations/views.py:1961) — IsAdminUser |
| `/api/admin/doctors/<int:pk>/action/` | POST | [AdminDoctorActionView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/consultations/views.py:2001) — IsAdminUser |
| `/api/admin/doctors/<int:pk>/verify/` | POST | [AdminDoctorVerifyView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/consultations/views.py:2071) — IsAdminUser |
| `/api/admin/doctors/<int:pk>/suspend/` | POST | [AdminDoctorSuspendView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/consultations/views.py:2093) — IsAdminUser |
| `/api/admin/doctors/<int:pk>/provision-account/` | POST | [AdminDoctorProvisionAccountView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/consultations/views.py:2128) — IsAdminUser |
| `/api/admin/pediatricians/` | GET | [AdminPediatricianListView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/consultations/views.py:2167) — IsAdminUser |
| `/api/admin/pediatricians/<int:pk>/` | GET, PUT, PATCH | [AdminPediatricianDetailView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/consultations/views.py:2176) — IsAdminUser |
| `/api/admin/pediatricians/<int:pk>/action/` | POST | [AdminPediatricianActionView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/consultations/views.py:2208) — IsAdminUser |
| `/api/admin/pediatricians/<int:pk>/provision-account/` | POST | [AdminPediatricianProvisionAccountView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/consultations/views.py:2268) — IsAdminUser |
| `/api/lab/technician-documents/<int:pk>/download/` | GET | [LabTechDocumentDownloadView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/lab/views.py:1267) — IsAuthenticated |
| `/api/lab/tests/` | GET | [LabTestListView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/lab/views.py:832) — AllowAny |
| `/api/lab/requests/` | GET, POST | [LabRequestListCreateView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/lab/views.py:858) — IsAuthenticated |
| `/api/lab/requests/<int:pk>/` | GET | [LabRequestDetailView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/lab/views.py:886) — IsAuthenticated |
| `/api/lab/requests/<int:pk>/update/` | PUT, PATCH | [LabRequestUpdateView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/lab/views.py:894) — IsAuthenticated |
| `/api/lab/requests/<int:pk>/collection-code/` | POST | [LabCollectionCodeIssueView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/lab/views.py:1044) — IsAuthenticated |
| `/api/lab/requests/<int:pk>/verify-collection/` | POST | [LabCollectionCodeVerifyView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/lab/views.py:1086) — IsLabTechOrAdmin |
| `/api/lab/requests/<int:pk>/results/` | POST | [LabResultCreateView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/lab/views.py:1152) — IsLabTechOrAdmin |
| `/api/lab/results/<int:pk>/` | GET | [LabResultDetailView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/lab/views.py:1235) — IsAuthenticated |
| `/api/lab/results/<int:pk>/download/` | GET | [LabResultDownloadView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/lab/views.py:1243) — IsAuthenticated |
| `/api/lab/dashboard/` | GET | [LabTechDashboardView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/lab/views.py:774) — IsLabTechOrAdmin |
| `/api/lab/partner/dashboard/` | GET | [LabPartnerDashboardView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/lab/views.py:403) — IsLabPartner |
| `/api/lab/partner/facilities/` | GET, POST | [LabPartnerFacilityListCreateView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/lab/views.py:444) — IsLabPartner |
| `/api/lab/partner/facilities/<int:pk>/` | GET, PUT, PATCH | [LabPartnerFacilityDetailView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/lab/views.py:468) — IsLabPartner |
| `/api/lab/partner/facilities/<int:facility_pk>/documents/` | GET, POST | [LabPartnerFacilityDocumentListCreateView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/lab/views.py:505) — IsLabPartner |
| `/api/lab/partner-documents/<int:pk>/download/` | GET | [LabPartnerDocumentDownloadView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/lab/views.py:170) — IsAuthenticated |
| `/api/lab/facility-documents/<int:pk>/download/` | GET | [LaboratoryFacilityDocumentDownloadView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/lab/views.py:543) — IsAuthenticated |
| `/api/lab/partner/technicians/` | GET, POST | [LabPartnerTechnicianListCreateView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/lab/views.py:659) — IsLabPartner |
| `/api/lab/partner/technicians/<int:pk>/action/` | POST | [LabPartnerTechnicianActionView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/lab/views.py:693) — IsLabPartner |
| `/api/lab/partner/technicians/<int:pk>/provision-account/` | POST | [LabPartnerTechnicianProvisionAccountView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/lab/views.py:719) — IsLabPartner |
| `/api/professionals/register/lab-partner/` | POST | [LabPartnerRegistrationView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/lab/views.py:750) — AllowAny |
| `/api/admin/lab/tests/` | GET, POST | [AdminLabTestListCreateView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/lab/views.py:844) — IsAdminUser |
| `/api/admin/lab/tests/<int:pk>/` | GET, PUT, PATCH, DELETE | [AdminLabTestDetailView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/lab/views.py:850) — IsAdminUser |
| `/api/admin/lab/approval-queue/` | GET | [AdminLabApprovalQueueView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/lab/views.py:571) — IsAdminUser |
| `/api/admin/lab/facilities/` | GET | [AdminLaboratoryFacilityListView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/lab/views.py:559) — IsAdminUser |
| `/api/admin/lab/facilities/<int:pk>/` | GET, PUT, PATCH | [AdminLaboratoryFacilityDetailView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/lab/views.py:593) — IsAdminUser |
| `/api/admin/lab/facilities/<int:pk>/action/` | POST | [AdminLaboratoryFacilityActionView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/lab/views.py:601) — IsAdminUser |
| `/api/admin/lab/partners/` | GET, POST | [AdminLabPartnerListCreateView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/lab/views.py:123) — IsAdminUser |
| `/api/admin/lab/partners/<int:pk>/` | GET, PUT, PATCH | [AdminLabPartnerDetailView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/lab/views.py:145) — IsAdminUser |
| `/api/admin/lab/partners/<int:pk>/action/` | POST | [AdminLabPartnerActionView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/lab/views.py:216) — IsAdminUser |
| `/api/admin/lab/partners/<int:pk>/provision-account/` | POST | [AdminLabPartnerProvisionAccountView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/lab/views.py:335) — IsAdminUser |
| `/api/admin/lab/partners/<int:partner_pk>/technicians/` | GET, POST | [AdminLabTechnicianListCreateView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/lab/views.py:185) — IsAdminUser |
| `/api/admin/lab/technicians/<int:pk>/` | GET, PUT, PATCH, DELETE | [AdminLabTechnicianDetailView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/lab/views.py:207) — IsAdminUser |
| `/api/admin/lab/technicians/<int:pk>/action/` | POST | [AdminLabTechnicianActionView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/lab/views.py:287) — IsAdminUser |
| `/api/admin/lab/technicians/<int:pk>/provision-account/` | POST | [AdminLabTechnicianProvisionAccountView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/lab/views.py:369) — IsAdminUser |
| `/api/compliance/catalogue/` | GET | [CurationListView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/support/compliance_api.py:288) — ReviewerAccess |
| `/api/compliance/catalogue/<int:pk>/` | GET, PUT, PATCH | [CurationDetailView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/support/compliance_api.py:297) — ReviewerAccess |
| `/api/compliance/assessment-queue/` | GET | [AssessmentQueueView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/support/compliance_api.py:254) — ReviewerAccess |
| `/api/compliance/evidence/<int:pk>/verify/` | POST | [EvidenceVerifyView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/support/compliance_api.py:234) — ActiveEvidenceAccess |
| `/api/compliance/readiness/` | GET | [ReadinessView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/support/compliance_api.py:218) — ActiveEvidenceAccess |
| `/api/compliance/medicine-assessments/` | GET, POST | [AssessmentView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/support/compliance_api.py:37) — ReviewerAccess |
| `/api/compliance/recalls/` | GET, POST | [RecallListView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/support/compliance_api.py:75) — ReviewerAccess |
| `/api/compliance/recalls/<int:pk>/` | GET, PUT, PATCH | [RecallDetailView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/support/compliance_api.py:94) — ReviewerAccess |
| `/api/compliance/recalls/<int:pk>/affected-orders/` | GET | [RecallAffectedListView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/support/compliance_api.py:119) — ReviewerAccess |
| `/api/compliance/recall-orders/<int:pk>/` | GET, PUT, PATCH | [RecallAffectedDetailView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/support/compliance_api.py:126) — ReviewerAccess |
| `/api/privacy/requests/` | GET, POST | [PrivacyListView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/support/compliance_api.py:158) — ActiveAccount |
| `/api/privacy/requests/<int:pk>/` | GET, PUT, PATCH | [PrivacyDetailView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/support/compliance_api.py:168) — ActiveAccount |
| `/api/privacy/requests/<int:pk>/verify/` | POST | [PrivacyVerifyView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/support/compliance_api.py:178) — ActiveEvidenceAccess |
| `/api/compliance/reviews/` | GET, POST | [OperationalListView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/support/compliance_api.py:206) — ActiveEvidenceAccess |
| `/api/compliance/reviews/<int:pk>/` | GET, PUT, PATCH | [OperationalDetailView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/support/compliance_api.py:212) — ActiveEvidenceAccess |
| `/api/compliance/evidence/<int:pk>/download/` | GET | [ComplianceEvidenceDownloadView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/support/views.py:242) — ActiveEvidenceAccess |
| `/api/site-settings/` | GET, PUT, PATCH | [SiteSettingsView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/support/views.py:42) — AllowAny |
| `/api/compliance/evidence/` | GET, POST | [ComplianceEvidenceListCreateView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/support/views.py:108) — ActiveEvidenceAccess |
| `/api/compliance/evidence/<int:pk>/` | GET, PUT, PATCH | [ComplianceEvidenceDetailView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/support/views.py:121) — ActiveEvidenceAccess |
| `/api/newsletter/subscribe/` | POST | [NewsletterSubscribeView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/support/views.py:55) — AllowAny |
| `/api/support/tickets/` | GET, POST | [SupportTicketListCreateView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/support/views.py:130) — ActiveAccount |
| `/api/support/tickets/<int:pk>/` | GET, PUT, PATCH | [SupportTicketDetailView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/support/views.py:159) — ActiveAccount |
| `/api/support/tickets/<int:pk>/notes/` | POST | [SupportNoteCreateView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/support/views.py:193) — ActiveAccount |
| `/api/admin/payout-recipients/` | GET | [PayoutRecipientListView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/payouts/views.py:244) — ActiveFinanceAdmin |
| `/api/payouts/mine/` | GET | [MyPayoutListView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/payouts/views.py:253) — IsAuthenticated |
| `/api/admin/payouts/` | GET, POST | [PayoutListCreateView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/payouts/views.py:34) — ActiveFinanceAdmin |
| `/api/admin/payouts/<int:pk>/` | GET | [PayoutDetailView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/payouts/views.py:67) — ActiveFinanceAdmin |
| `/api/admin/payouts/<int:pk>/actions/` | POST | [PayoutActionView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/payouts/views.py:75) — ActiveFinanceAdmin |
| `/api/admin/payouts-summary/` | GET | [PayoutSummaryView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/payouts/views.py:212) — ActiveFinanceAdmin |
| `/api/admin/payout-rules/` | GET, POST | [PayoutRuleListView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/payouts/views.py:232) — ActiveFinanceAdmin |
| `/api/admin/payout-rules/<int:pk>/` | GET, PUT, PATCH | [PayoutRuleDetailView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/payouts/views.py:238) — ActiveFinanceAdmin |
| `/api/notifications/deliveries/<int:pk>/retry/` | POST | [NotificationDeliveryRetryView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/notifications/views.py:86) — ActiveNotificationAccount |
| `/api/notifications/` | GET | [NotificationListView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/notifications/views.py:16) — ActiveNotificationAccount |
| `/api/notifications/preferences/` | GET, PATCH | [NotificationPreferenceView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/notifications/views.py:61) — ActiveNotificationAccount |
| `/api/notifications/deliveries/` | GET | [NotificationDeliveryListView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/notifications/views.py:76) — ActiveNotificationAccount |
| `/api/notifications/unread/` | GET | [NotificationUnreadCountView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/notifications/views.py:53) — ActiveNotificationAccount |
| `/api/notifications/mark-all-read/` | POST | [NotificationMarkAllReadView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/notifications/views.py:45) — ActiveNotificationAccount |
| `/api/notifications/<int:pk>/` | GET, DELETE | [NotificationDetailView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/notifications/views.py:27) — ActiveNotificationAccount |
| `/api/notifications/<int:pk>/read/` | POST | [NotificationMarkReadView](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/notifications/views.py:35) — ActiveNotificationAccount |
