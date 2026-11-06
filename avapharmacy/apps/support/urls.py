from django.urls import path
from . import views, compliance_api as compliance

urlpatterns = [
    path('compliance/catalogue/', compliance.CurationListView.as_view()),
    path('compliance/catalogue/<int:pk>/', compliance.CurationDetailView.as_view()),
    path('compliance/assessment-queue/', compliance.AssessmentQueueView.as_view()),
    path('compliance/evidence/<int:pk>/verify/', compliance.EvidenceVerifyView.as_view()),
    path('compliance/readiness/', compliance.ReadinessView.as_view()),
    path('compliance/medicine-assessments/', compliance.AssessmentView.as_view()),
    path('privacy/requests/', compliance.PrivacyListView.as_view()),
    path('privacy/requests/<int:pk>/', compliance.PrivacyDetailView.as_view()),
    path('privacy/requests/<int:pk>/verify/', compliance.PrivacyVerifyView.as_view()),
    path('compliance/reviews/', compliance.OperationalListView.as_view()),
    path('compliance/reviews/<int:pk>/', compliance.OperationalDetailView.as_view()),
    path('compliance/evidence/<int:pk>/download/', views.ComplianceEvidenceDownloadView.as_view(), name='compliance-evidence-download'),
    path('site-settings/', views.SiteSettingsView.as_view(), name='site-settings'),
    path('compliance/evidence/', views.ComplianceEvidenceListCreateView.as_view(), name='compliance-evidence'),
    path('compliance/evidence/<int:pk>/', views.ComplianceEvidenceDetailView.as_view(), name='compliance-evidence-detail'),
    path('newsletter/subscribe/', views.NewsletterSubscribeView.as_view(), name='newsletter-subscribe'),
    path('support/tickets/', views.SupportTicketListCreateView.as_view(), name='support-tickets'),
    path('support/tickets/<int:pk>/', views.SupportTicketDetailView.as_view(), name='support-ticket-detail'),
    path('support/tickets/<int:pk>/notes/', views.SupportNoteCreateView.as_view(), name='support-ticket-notes'),
]
