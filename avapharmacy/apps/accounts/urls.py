"""
URL patterns for the accounts app.

Covers auth endpoints (register, login, logout, token refresh, profile,
password change, addresses) and admin-only user management endpoints.
"""
from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from . import views

urlpatterns = [
    path('auth/register/', views.RegisterView.as_view(), name='register'),
    path('auth/login/', views.LoginView.as_view(), name='login'),
    path('auth/logout/', views.LogoutView.as_view(), name='logout'),
    path('auth/pharmacist/activate/', views.PharmacistActivationSetPasswordView.as_view(), name='pharmacist-activate'),
    path('auth/pharmacist/activate/<str:token>/', views.PharmacistActivationPageView.as_view(), name='pharmacist-activate-page'),
    path('auth/professional/activate/', views.ProfessionalActivationSetPasswordView.as_view(), name='professional-activate'),
    path('auth/professional/activate/<str:token>/', views.ProfessionalActivationPageView.as_view(), name='professional-activate-page'),
    path('auth/token/refresh/', TokenRefreshView.as_view(), name='token-refresh'),
    path('auth/me/', views.MeView.as_view(), name='me'),
    path('auth/me/password/', views.PasswordChangeView.as_view(), name='password-change'),
    path('auth/me/addresses/', views.AddressListCreateView.as_view(), name='addresses'),
    path('auth/me/addresses/<int:pk>/', views.AddressDetailView.as_view(), name='address-detail'),
    path('professionals/register/', views.ProfessionalRegistrationView.as_view(), name='professional-register'),
    path('professionals/lab-partners/', views.PublicLabPartnerListView.as_view(), name='public-lab-partners'),

    path('admin/users/', views.AdminUserListCreateView.as_view(), name='admin-users'),
    path('admin/users/<int:pk>/', views.AdminUserDetailView.as_view(), name='admin-user-detail'),
    path('admin/users/<int:pk>/suspend/', views.AdminUserSuspendView.as_view(), name='admin-user-suspend'),
    path('admin/users/<int:pk>/activate/', views.AdminUserActivateView.as_view(), name='admin-user-activate'),
    path('admin/users/<int:pk>/resend-activation/', views.AdminPharmacistActivationResendView.as_view(), name='admin-user-resend-activation'),
    path('admin/users/<int:pk>/notes/', views.UserNoteListCreateView.as_view(), name='admin-user-notes'),
    path('admin/audit-logs/', views.AdminAuditLogListView.as_view(), name='admin-audit-logs'),
]
