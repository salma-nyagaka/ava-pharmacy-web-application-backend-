from django.urls import path
from . import views

urlpatterns = [
    path('newsletter/subscribe/', views.NewsletterSubscribeView.as_view(), name='newsletter-subscribe'),
    path('support/tickets/', views.SupportTicketListCreateView.as_view(), name='support-tickets'),
    path('support/tickets/<int:pk>/', views.SupportTicketDetailView.as_view(), name='support-ticket-detail'),
    path('support/tickets/<int:pk>/notes/', views.SupportNoteCreateView.as_view(), name='support-ticket-notes'),
]
