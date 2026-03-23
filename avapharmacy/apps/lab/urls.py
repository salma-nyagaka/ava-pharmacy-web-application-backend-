from django.urls import path
from . import views

urlpatterns = [
    # Public
    path('lab/tests/', views.LabTestListView.as_view(), name='lab-tests'),

    # Patient & lab tech shared
    path('lab/requests/', views.LabRequestListCreateView.as_view(), name='lab-requests'),
    path('lab/requests/<int:pk>/', views.LabRequestDetailView.as_view(), name='lab-request-detail'),
    path('lab/requests/<int:pk>/update/', views.LabRequestUpdateView.as_view(), name='lab-request-update'),
    path('lab/requests/<int:pk>/results/', views.LabResultCreateView.as_view(), name='lab-result-create'),
    path('lab/results/<int:pk>/', views.LabResultDetailView.as_view(), name='lab-result-detail'),

    # Lab tech dashboard (serves /labaratory frontend route)
    path('lab/dashboard/', views.LabTechDashboardView.as_view(), name='lab-dashboard'),

    # Public professional registration
    path('professionals/register/lab-partner/', views.LabPartnerRegistrationView.as_view(), name='lab-partner-register'),
    path('professionals/register/lab-technician/', views.LabTechnicianRegistrationView.as_view(), name='lab-tech-register'),

    # Admin
    path('admin/lab/tests/', views.AdminLabTestListCreateView.as_view(), name='admin-lab-tests'),
    path('admin/lab/tests/<int:pk>/', views.AdminLabTestDetailView.as_view(), name='admin-lab-test-detail'),
    path('admin/lab/partners/', views.AdminLabPartnerListCreateView.as_view(), name='admin-lab-partners'),
    path('admin/lab/partners/<int:pk>/', views.AdminLabPartnerDetailView.as_view(), name='admin-lab-partner-detail'),
    path('admin/lab/partners/<int:pk>/action/', views.AdminLabPartnerActionView.as_view(), name='admin-lab-partner-action'),
    path('admin/lab/partners/<int:pk>/provision-account/', views.AdminLabPartnerProvisionAccountView.as_view(), name='admin-lab-partner-provision-account'),
    path('admin/lab/partners/<int:partner_pk>/technicians/', views.AdminLabTechnicianListCreateView.as_view(), name='admin-lab-partner-techs'),
    path('admin/lab/technicians/<int:pk>/', views.AdminLabTechnicianDetailView.as_view(), name='admin-lab-tech-detail'),
    path('admin/lab/technicians/<int:pk>/action/', views.AdminLabTechnicianActionView.as_view(), name='admin-lab-tech-action'),
    path('admin/lab/technicians/<int:pk>/provision-account/', views.AdminLabTechnicianProvisionAccountView.as_view(), name='admin-lab-tech-provision-account'),
]
