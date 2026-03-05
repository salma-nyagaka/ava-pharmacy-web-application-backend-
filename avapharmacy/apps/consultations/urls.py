from django.urls import path
from . import views

urlpatterns = [
    # Public
    path('doctors/', views.DoctorListView.as_view(), name='doctors'),
    path('doctors/<int:pk>/', views.DoctorDetailView.as_view(), name='doctor-detail'),
    path('doctors/register/', views.DoctorOnboardingView.as_view(), name='doctor-register'),
    path('professionals/register/doctor/', views.DoctorOnboardingView.as_view(), name='doctor-register-alt'),
    path('pediatricians/', views.PediatricianListView.as_view(), name='pediatricians'),
    path('pediatricians/<int:pk>/', views.PediatricianDetailView.as_view(), name='pediatrician-detail'),
    path('professionals/register/pediatrician/', views.PediatricianOnboardingView.as_view(), name='pediatrician-register'),

    # Patient consultations
    path('consultations/', views.ConsultationListCreateView.as_view(), name='consultations'),
    path('consultations/<int:pk>/', views.ConsultationDetailView.as_view(), name='consultation-detail'),
    path('consultations/<int:pk>/messages/', views.ConsultationMessageListCreateView.as_view(), name='consultation-messages'),
    path('consultations/<int:pk>/consent/', views.GuardianConsentView.as_view(), name='consultation-consent'),

    # Doctor dashboard (serves /doctor frontend route)
    path('doctor/dashboard/', views.DoctorDashboardView.as_view(), name='doctor-dashboard'),
    path('doctor/consultations/', views.DoctorConsultationListView.as_view(), name='doctor-consultations'),
    path('doctor/prescriptions/', views.ClinicianPrescriptionListCreateView.as_view(), name='doctor-prescriptions'),
    path('doctor/earnings/', views.ClinicianEarningsView.as_view(), name='doctor-earnings'),

    # Pediatrician dashboard (serves /paedetrician frontend route)
    path('pediatrician/dashboard/', views.PediatricianDashboardView.as_view(), name='pediatrician-dashboard'),
    path('pediatrician/prescriptions/', views.ClinicianPrescriptionListCreateView.as_view(), name='pediatrician-prescriptions'),
    path('pediatrician/earnings/', views.ClinicianEarningsView.as_view(), name='pediatrician-earnings'),

    # Shared clinician routes
    path('clinician/prescriptions/', views.ClinicianPrescriptionListCreateView.as_view(), name='clinician-prescriptions'),
    path('clinician/earnings/', views.ClinicianEarningsView.as_view(), name='clinician-earnings'),

    # Admin
    path('admin/dashboard/', views.AdminDashboardView.as_view(), name='admin-dashboard'),
    path('admin/doctors/', views.AdminDoctorListView.as_view(), name='admin-doctors'),
    path('admin/doctors/<int:pk>/', views.AdminDoctorDetailView.as_view(), name='admin-doctor-detail'),
    path('admin/doctors/<int:pk>/action/', views.AdminDoctorActionView.as_view(), name='admin-doctor-action'),
    path('admin/doctors/<int:pk>/provision-account/', views.AdminDoctorProvisionAccountView.as_view(), name='admin-doctor-provision-account'),
    path('admin/pediatricians/', views.AdminPediatricianListView.as_view(), name='admin-pediatricians'),
    path('admin/pediatricians/<int:pk>/', views.AdminPediatricianDetailView.as_view(), name='admin-pediatrician-detail'),
    path('admin/pediatricians/<int:pk>/action/', views.AdminPediatricianActionView.as_view(), name='admin-pediatrician-action'),
    path('admin/pediatricians/<int:pk>/provision-account/', views.AdminPediatricianProvisionAccountView.as_view(), name='admin-pediatrician-provision-account'),
]
