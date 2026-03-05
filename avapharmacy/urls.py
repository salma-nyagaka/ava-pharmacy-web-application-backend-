"""
Root URL configuration for the AvaPharma backend.

Registers the Django admin site, OpenAPI schema/docs endpoints, and includes
all app URL modules under four base prefixes for frontend compatibility:
``api/``, ``api/v1/``, ``avapharmacy/api/``, and ``avapharmacy/api/v1/``.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView

handler400 = 'django.views.defaults.bad_request'
handler403 = 'django.views.defaults.permission_denied'
handler404 = 'django.views.defaults.page_not_found'
handler500 = 'django.views.defaults.server_error'

urlpatterns = [
    path('admin/', admin.site.urls),

    # API schema / docs
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),

    # App routes — registered under four prefixes so the frontend can hit any variant
    path('api/', include('apps.accounts.urls')),
    path('api/', include('apps.products.urls')),
    path('api/', include('apps.orders.urls')),
    path('api/', include('apps.prescriptions.urls')),
    path('api/', include('apps.consultations.urls')),
    path('api/', include('apps.lab.urls')),
    path('api/', include('apps.support.urls')),
    path('api/', include('apps.payouts.urls')),
    path('api/', include('apps.notifications.urls')),
    path('api/v1/', include('apps.accounts.urls')),
    path('api/v1/', include('apps.products.urls')),
    path('api/v1/', include('apps.orders.urls')),
    path('api/v1/', include('apps.prescriptions.urls')),
    path('api/v1/', include('apps.consultations.urls')),
    path('api/v1/', include('apps.lab.urls')),
    path('api/v1/', include('apps.support.urls')),
    path('api/v1/', include('apps.payouts.urls')),
    path('api/v1/', include('apps.notifications.urls')),
    path('avapharmacy/api/', include('apps.accounts.urls')),
    path('avapharmacy/api/', include('apps.products.urls')),
    path('avapharmacy/api/', include('apps.orders.urls')),
    path('avapharmacy/api/', include('apps.prescriptions.urls')),
    path('avapharmacy/api/', include('apps.consultations.urls')),
    path('avapharmacy/api/', include('apps.lab.urls')),
    path('avapharmacy/api/', include('apps.support.urls')),
    path('avapharmacy/api/', include('apps.payouts.urls')),
    path('avapharmacy/api/', include('apps.notifications.urls')),
    path('avapharmacy/api/v1/', include('apps.accounts.urls')),
    path('avapharmacy/api/v1/', include('apps.products.urls')),
    path('avapharmacy/api/v1/', include('apps.orders.urls')),
    path('avapharmacy/api/v1/', include('apps.prescriptions.urls')),
    path('avapharmacy/api/v1/', include('apps.consultations.urls')),
    path('avapharmacy/api/v1/', include('apps.lab.urls')),
    path('avapharmacy/api/v1/', include('apps.support.urls')),
    path('avapharmacy/api/v1/', include('apps.payouts.urls')),
    path('avapharmacy/api/v1/', include('apps.notifications.urls')),
]

# Serve uploaded media and static files in debug mode
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
