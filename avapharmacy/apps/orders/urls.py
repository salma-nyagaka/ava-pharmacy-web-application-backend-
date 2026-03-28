from django.urls import path
from . import views

urlpatterns = [
    # Delivery options (spec: GET /checkout/delivery-options)
    path('shipping-methods/', views.ShippingMethodListView.as_view(), name='shipping-methods'),
    path('checkout/delivery-options/', views.ShippingMethodListView.as_view(), name='delivery-options'),

    # Cart
    path('cart/', views.CartView.as_view(), name='cart'),
    path('cart/items/', views.CartItemCreateView.as_view(), name='cart-items'),
    path('cart/items/<int:pk>/', views.CartItemUpdateView.as_view(), name='cart-item-update'),
    path('cart/items/<int:pk>/delete/', views.CartItemDeleteView.as_view(), name='cart-item-delete'),
    path('cart/clear/', views.CartClearView.as_view(), name='cart-clear'),
    path('cart/merge/', views.CartMergeView.as_view(), name='cart-merge'),
    path('cart/coupon/', views.CartApplyCouponView.as_view(), name='cart-apply-coupon'),
    path('cart/coupon/remove/', views.CartRemoveCouponView.as_view(), name='cart-remove-coupon'),
    # Spec-named promo routes
    path('cart/promo/', views.CartApplyCouponView.as_view(), name='cart-apply-promo'),
    path('cart/promo/remove/', views.CartRemoveCouponView.as_view(), name='cart-remove-promo'),

    # Checkout (2-step legacy flow)
    path('checkout/draft/', views.CheckoutDraftView.as_view(), name='checkout-draft'),
    path('checkout/<int:pk>/finalize/', views.CheckoutFinalizeView.as_view(), name='checkout-finalize'),

    # Payments
    path('payments/intents/', views.PaymentIntentCreateView.as_view(), name='payment-intents'),
    path('payments/intents/<int:pk>/sync/', views.PaymentIntentStatusSyncView.as_view(), name='payment-intent-sync'),
    path('payments/intents/<int:pk>/cancel/', views.PaymentIntentCancelView.as_view(), name='payment-intent-cancel'),
    path('orders/payments/flutterwave/initiate/', views.FlutterwaveInitiateView.as_view(), name='orders-payment-flutterwave-initiate'),
    path('orders/payments/flutterwave/callback/', views.FlutterwaveCallbackView.as_view(), name='orders-payment-flutterwave-callback'),
    path('orders/payments/flutterwave/redirect/', views.FlutterwaveRedirectView.as_view(), name='orders-payment-flutterwave-redirect'),
    path('orders/payments/flutterwave/status/<str:tx_ref>/', views.FlutterwaveStatusView.as_view(), name='orders-payment-flutterwave-status'),
    path('payments/mpesa/initiate/', views.MpesaInitiateView.as_view(), name='payment-mpesa-initiate'),
    path('payments/mpesa/status/<str:checkout_request_id>/', views.MpesaStatusView.as_view(), name='payment-mpesa-status'),
    path('payments/mpesa/callback/', views.MpesaCallbackView.as_view(), name='payment-mpesa-callback'),
    path('payments/mpesa/paybill/validation/', views.MpesaPaybillValidationView.as_view(), name='payment-mpesa-paybill-validation'),
    path('payments/mpesa/paybill/confirmation/', views.MpesaPaybillConfirmationView.as_view(), name='payment-mpesa-paybill-confirmation'),
    path('payments/mpesa/paybill/webhook/', views.PaybillWebhookView.as_view(), name='payment-mpesa-paybill-webhook'),
    path('payments/webhook/', views.PaymentWebhookView.as_view(), name='payment-webhook'),
    path('webhooks/order-status/', views.OrderStatusWebhookView.as_view(), name='order-status-webhook'),

    # Orders (spec: POST /orders = one-step create)
    path('orders/', views.OrderListView.as_view(), name='orders'),
    path('orders/create/', views.OrderCreateView.as_view(), name='order-create'),
    path('orders/<int:pk>/', views.OrderDetailView.as_view(), name='order-detail'),
    path('orders/<int:pk>/cancel/', views.OrderCancelView.as_view(), name='order-cancel'),
    path('orders/<int:pk>/tracking/', views.OrderTrackingView.as_view(), name='order-tracking'),
    path('orders/<int:pk>/return/', views.ReturnRequestListCreateView.as_view(), name='order-return'),

    path('returns/', views.ReturnRequestListCreateView.as_view(), name='return-requests'),

    # Admin
    path('admin/orders/', views.AdminOrderListView.as_view(), name='admin-orders'),
    path('admin/orders/<int:pk>/', views.AdminOrderDetailView.as_view(), name='admin-order-detail'),
    path('admin/orders/<int:pk>/status/', views.AdminOrderStatusView.as_view(), name='admin-order-status'),
    path('admin/order-push/', views.AdminOrderPushListView.as_view(), name='admin-order-push-list'),
    path('admin/order-push/<int:pk>/retry/', views.AdminOrderPushRetryView.as_view(), name='admin-order-push-retry'),
    path('admin/orders/<int:pk>/notes/', views.AdminOrderNoteView.as_view(), name='admin-order-notes'),
    path('admin/orders/<int:pk>/refund/', views.AdminOrderRefundView.as_view(), name='admin-order-refund'),
    path('admin/payments/mpesa/paybill/register-urls/', views.AdminMpesaPaybillRegisterUrlsView.as_view(), name='admin-payment-mpesa-paybill-register-urls'),
    path('admin/payments/intents/<int:pk>/reconcile/', views.AdminPaybillReconcileView.as_view(), name='admin-payment-intent-reconcile'),
    path('admin/shipping-methods/', views.AdminShippingMethodListCreateView.as_view(), name='admin-shipping-methods'),
    path('admin/shipping-methods/<int:pk>/', views.AdminShippingMethodDetailView.as_view(), name='admin-shipping-method-detail'),
    path('admin/returns/', views.AdminReturnRequestListView.as_view(), name='admin-return-requests'),
    path('admin/returns/<int:pk>/', views.AdminReturnRequestDetailView.as_view(), name='admin-return-request-detail'),
    path('admin/reports/', views.AdminReportsView.as_view(), name='admin-reports'),
    path('admin/reports/download/', views.AdminDownloadReportView.as_view(), name='admin-reports-download'),
    path('admin/activity-feed/', views.AdminActivityFeedView.as_view(), name='admin-activity-feed'),
    path('admin/invoices/', views.AdminInvoiceListView.as_view(), name='admin-invoices'),
    path('admin/invoices/<int:pk>/', views.AdminInvoiceDetailView.as_view(), name='admin-invoice-detail'),
]
