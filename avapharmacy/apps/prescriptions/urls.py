from django.urls import path
from . import views

urlpatterns = [
    path('prescriptions/', views.PrescriptionListView.as_view(), name='prescriptions'),
    path('prescriptions/upload/', views.PrescriptionUploadView.as_view(), name='prescription-upload'),
    path('prescriptions/<int:pk>/', views.PrescriptionDetailView.as_view(), name='prescription-detail'),
    path('prescriptions/<int:pk>/clarification-replies/', views.PrescriptionClarificationReplyView.as_view(), name='prescription-clarification-reply'),
    path('prescriptions/<int:pk>/update/', views.PrescriptionUpdateView.as_view(), name='prescription-update'),
    path('prescriptions/<int:pk>/resubmit/', views.PrescriptionResubmitView.as_view(), name='prescription-resubmit'),
    path('prescriptions/<int:pk>/audit/', views.PrescriptionAuditView.as_view(), name='prescription-audit'),
    path('prescriptions/<int:pk>/items/<int:item_pk>/add-to-cart/', views.PrescriptionItemAddToCartView.as_view(), name='prescription-item-add-to-cart'),
    path('pharmacist/prescriptions/', views.PharmacistPrescriptionQueueView.as_view(), name='pharmacist-prescriptions'),
    path('pharmacist/prescriptions/<int:pk>/assign/', views.PharmacistPrescriptionAssignView.as_view(), name='pharmacist-prescription-assign'),
    path('pharmacist/prescriptions/<int:pk>/review/', views.PharmacistPrescriptionReviewView.as_view(), name='pharmacist-prescription-review'),
    path('admin/prescriptions/', views.AdminPrescriptionListView.as_view(), name='admin-prescriptions'),
]
