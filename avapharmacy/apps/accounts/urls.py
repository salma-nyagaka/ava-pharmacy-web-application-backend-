from . import credential_api
"""
URL patterns for the accounts app.

Covers auth endpoints (register, login, logout, token refresh, profile,
password change, addresses) and admin-only user management endpoints.
"""
from django.urls import path
from . import views
from .record_stats import AdminRecordStatsView

urlpatterns = [
    path('auth/confirm-email-change/', views.ConfirmEmailChangeView.as_view(), name='confirm-email-change'),
    path('admin/users/<int:pk>/documents/', credential_api.PharmacistDocumentsView.as_view(), name='pharmacist-documents'),
    path('admin/users/<int:pk>/documents/<int:document_pk>/', credential_api.PharmacistDocumentDeleteView.as_view(), name='pharmacist-document-delete'),
    path('admin/record-stats/', AdminRecordStatsView.as_view(), name='admin-record-stats'),
    path('compliance/pharmacist-credential-subjects/', credential_api.CredentialSubjectListView.as_view(), name='pharmacist-credential-subjects'),
    path('compliance/pharmacist-credentials/', credential_api.PharmacistCredentialListView.as_view(), name='pharmacist-credentials'),
    path('compliance/pharmacist-credentials/me/', credential_api.MyPharmacistCredentialView.as_view(), name='my-pharmacist-credential'),
    path('compliance/pharmacist-credentials/<int:pk>/', credential_api.PharmacistCredentialDetailView.as_view(), name='pharmacist-credential-detail'),
    path('compliance/pharmacist-credentials/<int:pk>/verify/', credential_api.PharmacistCredentialVerifyView.as_view(), name='pharmacist-credential-verify'),
    path('compliance/pharmacist-credentials/<int:pk>/suspend/', credential_api.PharmacistCredentialSuspendView.as_view(), name='pharmacist-credential-suspend'),
    path('auth/register/', views.RegisterView.as_view(), name='register'),
    path('auth/login/', views.LoginView.as_view(), name='login'),
    path('auth/logout/', views.LogoutView.as_view(), name='logout'),
    path('auth/verify-email/', views.VerifyEmailView.as_view(), name='verify-email'),
    path('auth/resend-verification/', views.ResendVerificationView.as_view(), name='resend-verification'),
    path('auth/forgot-password/', views.ForgotPasswordView.as_view(), name='forgot-password'),
    path('auth/reset-password/', views.ResetPasswordView.as_view(), name='reset-password'),
    path('auth/pharmacist/activate/', views.PharmacistActivationSetPasswordView.as_view(), name='pharmacist-activate'),
    path('auth/pharmacist/activate/<str:token>/', views.PharmacistActivationPageView.as_view(), name='pharmacist-activate-page'),
    path('auth/professional/activate/', views.ProfessionalActivationSetPasswordView.as_view(), name='professional-activate'),
    path('auth/professional/activate/<str:token>/', views.ProfessionalActivationPageView.as_view(), name='professional-activate-page'),
    path('auth/token/refresh/', views.ActiveUserTokenRefreshView.as_view(), name='token-refresh'),
    path('auth/refresh/', views.ActiveUserTokenRefreshView.as_view(), name='token-refresh-alias'),
    path('auth/me/', views.MeView.as_view(), name='me'),
    path('auth/me/password/', views.PasswordChangeView.as_view(), name='password-change'),
    path('auth/me/addresses/', views.AddressListCreateView.as_view(), name='addresses'),
    path('auth/me/addresses/<int:pk>/', views.AddressDetailView.as_view(), name='address-detail'),
    path('auth/me/payment-methods/', views.PaymentMethodListCreateView.as_view(), name='payment-methods'),
    path('auth/me/payment-methods/<int:pk>/', views.PaymentMethodDetailView.as_view(), name='payment-method-detail'),
    path('professionals/register/', views.ProfessionalRegistrationView.as_view(), name='professional-register'),
    path('professionals/lab-partners/', views.PublicLabPartnerListView.as_view(), name='public-lab-partners'),

    # Account management (spec-named routes)
    path('account/profile/', views.AccountProfileView.as_view(), name='account-profile'),
    path('account/change-password/', views.PasswordChangeView.as_view(), name='account-change-password'),
    path('account/', views.AccountDeleteView.as_view(), name='account-delete'),

    path('admin/users/', views.AdminUserListCreateView.as_view(), name='admin-users'),
    path('admin/users/<int:pk>/', views.AdminUserDetailView.as_view(), name='admin-user-detail'),
    path('admin/users/<int:pk>/suspend/', views.AdminUserSuspendView.as_view(), name='admin-user-suspend'),
    path('admin/users/<int:pk>/activate/', views.AdminUserActivateView.as_view(), name='admin-user-activate'),
    path('admin/users/<int:pk>/resend-activation/', views.AdminPharmacistActivationResendView.as_view(), name='admin-user-resend-activation'),
    path('admin/users/<int:pk>/notes/', views.UserNoteListCreateView.as_view(), name='admin-user-notes'),
    path('admin/customers/', views.AdminCustomerListCreateView.as_view(), name='admin-customers'),
    path('admin/customers/stats/', views.AdminCustomerStatsView.as_view(), name='admin-customer-stats'),
    path('admin/customers/<int:pk>/', views.AdminCustomerDetailView.as_view(), name='admin-customer-detail'),
    path('admin/customers/<int:pk>/suspend/', views.AdminCustomerSuspendView.as_view(), name='admin-customer-suspend'),
    path('admin/customers/<int:pk>/activate/', views.AdminCustomerActivateView.as_view(), name='admin-customer-activate'),
    path('admin/customers/<int:pk>/notes/', views.UserNoteListCreateView.as_view(), name='admin-customer-notes'),
    path('admin/audit-logs/', views.AdminAuditLogListView.as_view(), name='admin-audit-logs'),
]
