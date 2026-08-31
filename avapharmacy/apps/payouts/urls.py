from django.urls import path
from . import views

urlpatterns = [
    path('admin/payouts/', views.PayoutListCreateView.as_view(), name='admin-payouts'),
    path('admin/payouts/<int:pk>/', views.PayoutDetailView.as_view(), name='admin-payout-detail'),
    path('admin/payouts/<int:pk>/actions/', views.PayoutActionView.as_view(), name='admin-payout-action'),
    path('admin/payouts-summary/', views.PayoutSummaryView.as_view(), name='admin-payout-summary'),
    path('admin/payout-rules/', views.PayoutRuleListView.as_view(), name='admin-payout-rules'),
    path('admin/payout-rules/<int:pk>/', views.PayoutRuleDetailView.as_view(), name='admin-payout-rule-detail'),
]
