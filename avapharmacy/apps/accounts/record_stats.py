"""Unpaginated database aggregates for admin KPI cards.

Table search, status filters and pagination are deliberately not accepted here.
Only an explicit menu role/provider scope may narrow a total.
"""
from django.apps import apps
from django.db.models import Count, Q, Sum
from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView
from .permissions import IsAdminUser


def counts(queryset, **conditions):
    return queryset.aggregate(total=Count('pk'), **{key: Count('pk', filter=value) for key, value in conditions.items()})


class AdminRecordStatsView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        section = request.query_params.get('section', '')
        scope = request.query_params.get('scope', 'all')
        model = apps.get_model
        if section in {'categories', 'brands', 'health_concerns'}:
            name = {'categories': 'Category', 'brands': 'Brand', 'health_concerns': 'HealthConcern'}[section]
            result = counts(model('products', name).objects.all(), active=Q(is_active=True), inactive=Q(is_active=False))
            if section == 'categories':
                sub = counts(model('products', 'Subcategory').objects.all(), active=Q(is_active=True), inactive=Q(is_active=False))
                result.update({f'subcategories_{key}': value for key, value in sub.items()})
        elif section == 'users':
            User = model('accounts', 'User')
            if scope != 'all' and scope not in dict(User.ROLE_CHOICES):
                return Response({'detail': 'Unknown user role.'}, status=400)
            qs = User.objects.all() if scope == 'all' else User.objects.filter(role=scope)
            result = counts(qs, active=Q(status='active', is_active=True), pending=Q(status='pending_verification') | (Q(is_active=False) & ~Q(status='suspended')), suspended=Q(status='suspended'))
        elif section == 'doctors':
            if scope not in {'all', 'doctor', 'pediatrician'}:
                return Response({'detail': 'Unknown clinician type.'}, status=400)
            qs = model('consultations', 'ClinicianProfile').objects.all()
            if scope != 'all': qs = qs.filter(provider_type=scope)
            result = counts(qs, active=Q(status='active'), pending=Q(status='pending'), pendingActivation=Q(status='approved_pending_activation'), blocked=Q(status__in=['suspended', 'rejected', 'deactivated']))
        elif section == 'prescriptions':
            result = counts(model('prescriptions', 'Prescription').objects.all(), pending=Q(status='pending'), approved=Q(status='approved'), clarification=Q(status='clarification'), rejected=Q(status='rejected'), inTransit=Q(status='approved', dispatch_status__in=['queued','packed','dispatched']))
        elif section == 'deals':
            today = timezone.localdate()
            result = counts(model('products', 'Promotion').objects.all(), active=Q(status='active', start_date__lte=today, end_date__gte=today), scheduled=Q(status='active', start_date__gt=today), expired=Q(status='active', end_date__lt=today), draft=Q(status='draft'))
        elif section in {'orders', 'invoices'}:
            qs = model('orders', 'Order').objects.all()
            if section == 'invoices': qs = qs.exclude(status='draft')
            result = counts(qs, pending=Q(status='pending'), shipped=Q(status='shipped'), delivered=Q(status='delivered'), paid=Q(payment_status='paid'), unpaid=Q(payment_status__in=['pending', 'requires_action', 'failed']))
        elif section == 'support':
            result = counts(model('support', 'SupportTicket').objects.all(), open=Q(status='open'), inProgress=Q(status='in_progress'), unassigned=Q(assigned_to__isnull=True), highPriority=Q(priority='high'))
        elif section == 'lab_requests':
            result = counts(model('lab', 'LabRequest').objects.all(), unassigned=Q(laboratory__isnull=True) | Q(assigned_technician__isnull=True), home=Q(channel='collection'), processing=Q(status='processing'), ready=Q(status='result_ready'))
        elif section == 'lab_tests':
            LabTest = model('lab', 'LabTest')
            result = {'total': LabTest.objects.count()}
            labels = dict(LabTest.CATEGORY_CHOICES)
            for row in LabTest.objects.values('category').annotate(count=Count('pk')):
                result['category:' + labels.get(row['category'], row['category'])] = row['count']
        elif section == 'payouts':
            qs = model('payouts', 'Payout').objects.all()
            payable = Q(status__in=['draft','pending','approved','processing','on_hold'])
            result = counts(qs, pending=payable, paid=Q(status='paid'), failed=Q(status='failed'))
            sums = qs.aggregate(totalAmount=Sum('amount', filter=Q(status='paid')), pendingAmount=Sum('amount', filter=payable), failedAmount=Sum('amount', filter=Q(status='failed')))
            result.update({key: value or 0 for key, value in sums.items()})
        else:
            return Response({'detail': 'Unknown KPI section.'}, status=400)
        return Response(result)
