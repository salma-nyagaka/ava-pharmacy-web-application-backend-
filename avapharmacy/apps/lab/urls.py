from django.urls import path
from . import views

urlpatterns = [
    # Public
    path('lab/tests/', views.LabTestListView.as_view(), name='lab-tests'),

    # Patient & lab tech shared
    path('lab/requests/', views.LabRequestListCreateView.as_view(), name='lab-requests'),
    path('lab/requests/<int:pk>/', views.LabRequestDetailView.as_view(), name='lab-request-detail'),
    path('lab/requests/<int:pk>/update/', views.LabRequestUpdateView.as_view(), name='lab-request-update'),
    path('lab/requests/<int:pk>/collection-code/', views.LabCollectionCodeIssueView.as_view(), name='lab-collection-code'),
    path('lab/requests/<int:pk>/verify-collection/', views.LabCollectionCodeVerifyView.as_view(), name='lab-verify-collection'),
    path('lab/requests/<int:pk>/results/', views.LabResultCreateView.as_view(), name='lab-result-create'),
    path('lab/results/<int:pk>/', views.LabResultDetailView.as_view(), name='lab-result-detail'),
    path('lab/results/<int:pk>/download/', views.LabResultDownloadView.as_view(), name='lab-result-download'),

    # Lab tech dashboard (serves /labaratory frontend route)
    path('lab/dashboard/', views.LabTechDashboardView.as_view(), name='lab-dashboard'),
    path('lab/partner/dashboard/', views.LabPartnerDashboardView.as_view(), name='lab-partner-dashboard'),
    path('lab/partner/facilities/', views.LabPartnerFacilityListCreateView.as_view(), name='lab-partner-facilities'),
    path('lab/partner/facilities/<int:pk>/', views.LabPartnerFacilityDetailView.as_view(), name='lab-partner-facility-detail'),
    path('lab/partner/facilities/<int:facility_pk>/documents/', views.LabPartnerFacilityDocumentListCreateView.as_view(), name='lab-partner-facility-documents'),
    path('lab/facility-documents/<int:pk>/download/', views.LaboratoryFacilityDocumentDownloadView.as_view(), name='lab-facility-document-download'),
    path('lab/partner/technicians/', views.LabPartnerTechnicianListCreateView.as_view(), name='lab-partner-techs'),
    path('lab/partner/technicians/<int:pk>/action/', views.LabPartnerTechnicianActionView.as_view(), name='lab-partner-tech-action'),
    path('lab/partner/technicians/<int:pk>/provision-account/', views.LabPartnerTechnicianProvisionAccountView.as_view(), name='lab-partner-tech-provision-account'),

    # Public professional registration
    path('professionals/register/lab-partner/', views.LabPartnerRegistrationView.as_view(), name='lab-partner-register'),

    # Admin
    path('admin/lab/tests/', views.AdminLabTestListCreateView.as_view(), name='admin-lab-tests'),
    path('admin/lab/tests/<int:pk>/', views.AdminLabTestDetailView.as_view(), name='admin-lab-test-detail'),
    path('admin/lab/facilities/', views.AdminLaboratoryFacilityListView.as_view(), name='admin-lab-facilities'),
    path('admin/lab/facilities/<int:pk>/', views.AdminLaboratoryFacilityDetailView.as_view(), name='admin-lab-facility-detail'),
    path('admin/lab/facilities/<int:pk>/action/', views.AdminLaboratoryFacilityActionView.as_view(), name='admin-lab-facility-action'),
    path('admin/lab/partners/', views.AdminLabPartnerListCreateView.as_view(), name='admin-lab-partners'),
    path('admin/lab/partners/<int:pk>/', views.AdminLabPartnerDetailView.as_view(), name='admin-lab-partner-detail'),
    path('admin/lab/partners/<int:pk>/action/', views.AdminLabPartnerActionView.as_view(), name='admin-lab-partner-action'),
    path('admin/lab/partners/<int:pk>/provision-account/', views.AdminLabPartnerProvisionAccountView.as_view(), name='admin-lab-partner-provision-account'),
    path('admin/lab/partners/<int:partner_pk>/technicians/', views.AdminLabTechnicianListCreateView.as_view(), name='admin-lab-partner-techs'),
    path('admin/lab/technicians/<int:pk>/', views.AdminLabTechnicianDetailView.as_view(), name='admin-lab-tech-detail'),
    path('admin/lab/technicians/<int:pk>/action/', views.AdminLabTechnicianActionView.as_view(), name='admin-lab-tech-action'),
    path('admin/lab/technicians/<int:pk>/provision-account/', views.AdminLabTechnicianProvisionAccountView.as_view(), name='admin-lab-tech-provision-account'),
]
