from django.urls import path
from . import views

urlpatterns = [
    path('prescriptions/', views.PrescriptionListView.as_view(), name='prescriptions'),
    path('prescriptions/upload/', views.PrescriptionUploadView.as_view(), name='prescription-upload'),
    path('prescriptions/<int:pk>/', views.PrescriptionDetailView.as_view(), name='prescription-detail'),
    path('prescriptions/<int:pk>/update/', views.PrescriptionUpdateView.as_view(), name='prescription-update'),
    path('prescriptions/<int:pk>/audit/', views.PrescriptionAuditView.as_view(), name='prescription-audit'),
    path('prescriptions/<int:pk>/items/<int:item_pk>/add-to-cart/', views.PrescriptionItemAddToCartView.as_view(), name='prescription-item-add-to-cart'),
    path('admin/prescriptions/', views.AdminPrescriptionListView.as_view(), name='admin-prescriptions'),
]
