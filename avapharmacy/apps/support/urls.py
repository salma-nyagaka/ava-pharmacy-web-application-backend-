from django.urls import path
from . import views

urlpatterns = [
    path('site-settings/', views.SiteSettingsView.as_view(), name='site-settings'),
    path('compliance/evidence/', views.ComplianceEvidenceListCreateView.as_view(), name='compliance-evidence'),
    path('compliance/evidence/<int:pk>/', views.ComplianceEvidenceDetailView.as_view(), name='compliance-evidence-detail'),
    path('newsletter/subscribe/', views.NewsletterSubscribeView.as_view(), name='newsletter-subscribe'),
    path('support/tickets/', views.SupportTicketListCreateView.as_view(), name='support-tickets'),
    path('support/tickets/<int:pk>/', views.SupportTicketDetailView.as_view(), name='support-ticket-detail'),
    path('support/tickets/<int:pk>/notes/', views.SupportNoteCreateView.as_view(), name='support-ticket-notes'),
]
