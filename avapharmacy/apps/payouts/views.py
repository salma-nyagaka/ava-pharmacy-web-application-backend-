from decimal import Decimal

from django.db import IntegrityError, models, transaction
from django.db.models import Count, Sum
from django.db.models.functions import Coalesce
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsAdminUser

from .models import Payout, PayoutAuditLog, PayoutRule
from .serializers import PayoutActionSerializer, PayoutCreateSerializer, PayoutRuleSerializer, PayoutSerializer


def _audit(payout, actor, action, previous_status='', reason='', metadata=None):
    PayoutAuditLog.objects.create(
        payout=payout,
        actor=actor,
        action=action,
        from_status=previous_status,
        to_status=payout.status,
        reason=reason,
        metadata=metadata or {},
    )


class PayoutListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAdminUser]
    filterset_fields = ['status', 'role', 'method', 'reconciliation_status', 'source_type']
    search_fields = ['reference', 'recipient_name', 'source_reference', 'payment_reference', 'provider_transaction_id']
    ordering_fields = ['requested_at', 'amount', 'paid_at', 'approved_at']
    ordering = ['-requested_at']

    def get_queryset(self):
        return Payout.objects.select_related(
            'recipient', 'created_by', 'reviewed_by', 'approved_by', 'submitted_by',
        ).prefetch_related('audit_logs__actor')

    def get_serializer_class(self):
        return PayoutCreateSerializer if self.request.method == 'POST' else PayoutSerializer

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            payout = serializer.save(
                created_by=request.user,
                recipient_name=serializer.validated_data.get('recipient_name') or serializer.validated_data.get('recipient').full_name,
                amount=serializer.validated_data['gross_amount'],
                status=Payout.STATUS_DRAFT,
            )
        except IntegrityError:
            return Response({'detail': 'A payout already exists for this source or idempotency key.'}, status=status.HTTP_409_CONFLICT)
        _audit(payout, request.user, 'created', metadata={'source_reference': payout.source_reference})
        return Response(PayoutSerializer(payout, context={'request': request}).data, status=status.HTTP_201_CREATED)


class PayoutDetailView(generics.RetrieveAPIView):
    permission_classes = [IsAdminUser]
    serializer_class = PayoutSerializer
    queryset = Payout.objects.select_related(
        'recipient', 'created_by', 'reviewed_by', 'approved_by', 'submitted_by',
    ).prefetch_related('audit_logs__actor')


class PayoutActionView(APIView):
    permission_classes = [IsAdminUser]

    @transaction.atomic
    def post(self, request, pk):
        try:
            payout = Payout.objects.select_for_update().get(pk=pk)
        except Payout.DoesNotExist:
            return Response({'detail': 'Payout not found.'}, status=status.HTTP_404_NOT_FOUND)
        serializer = PayoutActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        action = data['action']
        reason = data.get('reason', '').strip()
        previous = payout.status
        now = timezone.now()

        allowed = {
            'submit': {Payout.STATUS_DRAFT, Payout.STATUS_FAILED},
            'approve': {Payout.STATUS_PENDING},
            'hold': {Payout.STATUS_PENDING, Payout.STATUS_APPROVED, Payout.STATUS_PROCESSING},
            'release': {Payout.STATUS_ON_HOLD},
            'process': {Payout.STATUS_APPROVED},
            'mark_paid': {Payout.STATUS_APPROVED, Payout.STATUS_PROCESSING},
            'mark_failed': {Payout.STATUS_APPROVED, Payout.STATUS_PROCESSING},
            'retry': {Payout.STATUS_FAILED},
            'reverse': {Payout.STATUS_PAID},
            'cancel': {Payout.STATUS_DRAFT, Payout.STATUS_PENDING, Payout.STATUS_APPROVED, Payout.STATUS_FAILED, Payout.STATUS_ON_HOLD},
        }
        if action in allowed and payout.status not in allowed[action]:
            return Response({'detail': f'Cannot {action.replace("_", " ")} a {payout.get_status_display().lower()} payout.'}, status=status.HTTP_409_CONFLICT)
        if action in {'reconcile', 'unmatch', 'flag_exception'} and payout.status not in {Payout.STATUS_PAID, Payout.STATUS_REVERSED}:
            return Response({'detail': 'Only paid or reversed payouts can be reconciled.'}, status=status.HTTP_409_CONFLICT)

        if action == 'submit':
            payout.status = Payout.STATUS_PENDING
            payout.reviewed_by = request.user
            payout.reviewed_at = now
        elif action == 'approve':
            if payout.created_by_id == request.user.id:
                return Response({'detail': 'Maker-checker control: the payout creator cannot approve it.'}, status=status.HTTP_403_FORBIDDEN)
            payout.status = Payout.STATUS_APPROVED
            payout.approved_by = request.user
            payout.approved_at = now
        elif action == 'hold':
            if not reason:
                return Response({'reason': 'A hold reason is required.'}, status=status.HTTP_400_BAD_REQUEST)
            payout.status = Payout.STATUS_ON_HOLD
            payout.hold_reason = reason
        elif action == 'release':
            payout.status = Payout.STATUS_PENDING
            payout.hold_reason = ''
        elif action == 'process':
            payout.status = Payout.STATUS_PROCESSING
            payout.submitted_by = request.user
            payout.submitted_at = now
            payout.batch_reference = data.get('batch_reference', '') or payout.batch_reference
        elif action == 'mark_paid':
            reference = data.get('payment_reference', '').strip() or data.get('provider_transaction_id', '').strip()
            if not reference:
                return Response({'payment_reference': 'A verified payment reference is required.'}, status=status.HTTP_400_BAD_REQUEST)
            provider_reference = data.get('provider_transaction_id', '').strip()
            reference_query = models.Q(payment_reference=reference)
            if provider_reference:
                reference_query |= models.Q(provider_transaction_id=provider_reference)
            if Payout.objects.exclude(pk=payout.pk).filter(reference_query).exists():
                return Response({'detail': 'This payment reference is already assigned to another payout.'}, status=status.HTTP_409_CONFLICT)
            payout.status = Payout.STATUS_PAID
            payout.payment_reference = data.get('payment_reference', '').strip() or reference
            payout.provider_transaction_id = provider_reference or payout.provider_transaction_id
            payout.method = data.get('method', payout.method)
            payout.paid_at = data.get('paid_at', now)
            payout.failure_code = ''
            payout.failure_message = ''
        elif action == 'mark_failed':
            if not (data.get('failure_message', '').strip() or reason):
                return Response({'reason': 'A failure reason is required.'}, status=status.HTTP_400_BAD_REQUEST)
            payout.status = Payout.STATUS_FAILED
            payout.failure_code = data.get('failure_code', '')
            payout.failure_message = data.get('failure_message', '') or reason
        elif action == 'retry':
            payout.status = Payout.STATUS_APPROVED if payout.approved_by_id else Payout.STATUS_PENDING
            payout.retry_count += 1
            payout.failure_code = ''
            payout.failure_message = ''
        elif action == 'reverse':
            if not reason:
                return Response({'reason': 'A reversal reason is required.'}, status=status.HTTP_400_BAD_REQUEST)
            payout.status = Payout.STATUS_REVERSED
            payout.reconciliation_status = Payout.RECON_EXCEPTION
        elif action == 'cancel':
            if not reason:
                return Response({'reason': 'A cancellation reason is required.'}, status=status.HTTP_400_BAD_REQUEST)
            payout.status = Payout.STATUS_CANCELLED
        elif action == 'reconcile':
            payout.reconciliation_status = Payout.RECON_MATCHED
        elif action == 'unmatch':
            payout.reconciliation_status = Payout.RECON_UNMATCHED
        elif action == 'flag_exception':
            payout.reconciliation_status = Payout.RECON_EXCEPTION

        payout.save()
        _audit(payout, request.user, action, previous_status=previous, reason=reason, metadata={
            'payment_reference': payout.payment_reference,
            'provider_transaction_id': payout.provider_transaction_id,
            'reconciliation_status': payout.reconciliation_status,
        })
        if payout.status != previous and payout.recipient:
            try:
                from apps.notifications.utils import notify_payout_status
                notify_payout_status(payout)
            except Exception:
                pass
        return Response(PayoutSerializer(payout, context={'request': request}).data)


class PayoutSummaryView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        queryset = Payout.objects.all()
        role = request.query_params.get('role')
        if role:
            queryset = queryset.filter(role=role)
        totals = queryset.aggregate(
            gross=Coalesce(Sum('gross_amount'), Decimal('0.00')),
            net=Coalesce(Sum('amount'), Decimal('0.00')),
            paid=Coalesce(Sum('amount', filter=models.Q(status=Payout.STATUS_PAID)), Decimal('0.00')),
            payable=Coalesce(Sum('amount', filter=models.Q(status__in=[Payout.STATUS_PENDING, Payout.STATUS_APPROVED, Payout.STATUS_PROCESSING])), Decimal('0.00')),
            held=Coalesce(Sum('amount', filter=models.Q(status=Payout.STATUS_ON_HOLD)), Decimal('0.00')),
        )
        by_status = list(queryset.values('status').annotate(count=Count('id'), amount=Coalesce(Sum('amount'), Decimal('0.00'))).order_by('status'))
        by_role = list(queryset.values('role').annotate(count=Count('id'), amount=Coalesce(Sum('amount'), Decimal('0.00'))).order_by('role'))
        return Response({**totals, 'count': queryset.count(), 'by_status': by_status, 'by_role': by_role})


class PayoutRuleListView(generics.ListCreateAPIView):
    permission_classes = [IsAdminUser]
    serializer_class = PayoutRuleSerializer
    queryset = PayoutRule.objects.all()


class PayoutRuleDetailView(generics.RetrieveUpdateAPIView):
    permission_classes = [IsAdminUser]
    serializer_class = PayoutRuleSerializer
    queryset = PayoutRule.objects.all()
