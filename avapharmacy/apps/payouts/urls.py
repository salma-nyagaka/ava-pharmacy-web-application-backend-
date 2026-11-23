from django.urls import path
from . import views

urlpatterns = [
    path('admin/payouts/sync-consultations/', views.SyncConsultationPayoutsView.as_view(), name='admin-sync-consultation-payouts'),
    path('admin/lab-revenue-agreements/', views.LabRevenueAgreementListView.as_view(), name='admin-lab-revenue-agreements'),
    path('admin/lab-revenue-agreements/<int:pk>/', views.LabRevenueAgreementDetailView.as_view(), name='admin-lab-revenue-agreement-detail'),
    path('admin/payout-recipients/', views.PayoutRecipientListView.as_view(), name='admin-payout-recipients'),
    path('payouts/mine/', views.MyPayoutListView.as_view(), name='my-payouts'),
    path('admin/payouts/', views.PayoutListCreateView.as_view(), name='admin-payouts'),
    path('admin/payouts/<int:pk>/', views.PayoutDetailView.as_view(), name='admin-payout-detail'),
    path('admin/payouts/<int:pk>/actions/', views.PayoutActionView.as_view(), name='admin-payout-action'),
    path('admin/payouts-summary/', views.PayoutSummaryView.as_view(), name='admin-payout-summary'),
    path('admin/payout-rules/', views.PayoutRuleListView.as_view(), name='admin-payout-rules'),
    path('admin/payout-rules/<int:pk>/', views.PayoutRuleDetailView.as_view(), name='admin-payout-rule-detail'),
]
