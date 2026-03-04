from django.urls import path
from . import views

urlpatterns = [
    # Public
    path('doctors/', views.DoctorListView.as_view(), name='doctors'),
    path('doctors/<int:pk>/', views.DoctorDetailView.as_view(), name='doctor-detail'),
    path('doctors/register/', views.DoctorOnboardingView.as_view(), name='doctor-register'),

    # Patient consultations
    path('consultations/', views.ConsultationListCreateView.as_view(), name='consultations'),
    path('consultations/<int:pk>/', views.ConsultationDetailView.as_view(), name='consultation-detail'),
    path('consultations/<int:pk>/messages/', views.ConsultationMessageListCreateView.as_view(), name='consultation-messages'),
    path('consultations/<int:pk>/consent/', views.GuardianConsentView.as_view(), name='consultation-consent'),

    # Doctor dashboard (serves /doctor frontend route)
    path('doctor/dashboard/', views.DoctorDashboardView.as_view(), name='doctor-dashboard'),
    path('doctor/consultations/', views.DoctorConsultationListView.as_view(), name='doctor-consultations'),
    path('doctor/prescriptions/', views.DoctorPrescriptionListCreateView.as_view(), name='doctor-prescriptions'),
    path('doctor/earnings/', views.DoctorEarningsView.as_view(), name='doctor-earnings'),

    # Pediatrician dashboard (serves /paedetrician frontend route)
    path('pediatrician/dashboard/', views.PediatricianDashboardView.as_view(), name='pediatrician-dashboard'),

    # Admin
    path('admin/dashboard/', views.AdminDashboardView.as_view(), name='admin-dashboard'),
    path('admin/doctors/', views.AdminDoctorListView.as_view(), name='admin-doctors'),
    path('admin/doctors/<int:pk>/', views.AdminDoctorDetailView.as_view(), name='admin-doctor-detail'),
]
