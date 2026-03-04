from django.urls import path
from . import views

urlpatterns = [
    path('notifications/', views.NotificationListView.as_view(), name='notifications'),
    path('notifications/preferences/', views.NotificationPreferenceView.as_view(), name='notification-preferences'),
    path('notifications/deliveries/', views.NotificationDeliveryListView.as_view(), name='notification-deliveries'),
    path('notifications/unread/', views.NotificationUnreadCountView.as_view(), name='notifications-unread'),
    path('notifications/mark-all-read/', views.NotificationMarkAllReadView.as_view(), name='notifications-mark-all-read'),
    path('notifications/<int:pk>/', views.NotificationDetailView.as_view(), name='notification-detail'),
    path('notifications/<int:pk>/read/', views.NotificationMarkReadView.as_view(), name='notification-read'),
]
