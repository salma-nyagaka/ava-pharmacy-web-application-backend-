from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, FormParser
from django.db.models import Count
from django.utils import timezone

from .models import LabPartner, LabTechnicianProfile, LabTest, LabRequest, LabAuditLog, LabResult
from .serializers import (
    LabPartnerSerializer, LabPartnerCreateSerializer, LabPartnerUpdateSerializer,
    LabTechnicianProfileSerializer,
    LabTestSerializer, LabRequestSerializer, LabRequestCreateSerializer,
    LabRequestUpdateSerializer, LabResultSerializer, LabResultCreateSerializer
)
from apps.accounts.permissions import IsAdminUser, IsLabTechOrAdmin

ALLOWED_RESULT_TYPES = ['application/pdf', 'image/jpeg', 'image/png']
MAX_RESULT_SIZE = 10 * 1024 * 1024  # 10 MB


# ─── Lab Partners ─────────────────────────────────────────────────────────────

class AdminLabPartnerListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAdminUser]
    filterset_fields = ['status']
    search_fields = ['name', 'email', 'reference']
    ordering = ['-submitted_at']

    def get_queryset(self):
        return LabPartner.objects.all().prefetch_related('documents', 'technicians__user')

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return LabPartnerCreateSerializer
        return LabPartnerSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        partner = serializer.save()
        return Response(LabPartnerSerializer(partner).data, status=status.HTTP_201_CREATED)


class AdminLabPartnerDetailView(generics.RetrieveUpdateAPIView):
    permission_classes = [IsAdminUser]
    queryset = LabPartner.objects.all().prefetch_related('documents', 'technicians__user')

    def get_serializer_class(self):
        if self.request.method in ['PUT', 'PATCH']:
            return LabPartnerUpdateSerializer
        return LabPartnerSerializer

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', True)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        if request.data.get('status') == LabPartner.STATUS_VERIFIED and not instance.verified_at:
            from django.utils import timezone as tz
            instance.verified_at = tz.now()
            instance.save(update_fields=['verified_at'])
        partner = serializer.save()
        return Response(LabPartnerSerializer(partner).data)


class AdminLabTechnicianListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAdminUser]
    serializer_class = LabTechnicianProfileSerializer

    def get_queryset(self):
        return LabTechnicianProfile.objects.filter(
            partner_id=self.kwargs['partner_pk']
        ).select_related('user')

    def perform_create(self, serializer):
        serializer.save(partner_id=self.kwargs['partner_pk'])


# ─── Lab Tech Dashboard ───────────────────────────────────────────────────────

class LabTechDashboardView(APIView):
    """Aggregated stats for the /labaratory frontend route."""
    permission_classes = [IsLabTechOrAdmin]

    def get(self, request):
        today = timezone.now().date()
        month_start = today.replace(day=1)

        pending_statuses = [
            LabRequest.STATUS_AWAITING, LabRequest.STATUS_COLLECTED, LabRequest.STATUS_PROCESSING
        ]

        all_qs = LabRequest.objects.all()
        mine_qs = LabRequest.objects.filter(assigned_technician=request.user)

        by_category = list(
            LabRequest.objects.filter(status__in=pending_statuses)
            .values('test__category')
            .annotate(count=Count('id'))
        )

        by_status = list(
            LabRequest.objects.values('status').annotate(count=Count('id'))
        )

        recent = LabRequestSerializer(
            all_qs.select_related('test', 'assigned_technician').order_by('-requested_at')[:10],
            many=True
        ).data

        return Response({
            'stats': {
                'total': all_qs.count(),
                'pending': all_qs.filter(status__in=pending_statuses).count(),
                'awaiting_sample': all_qs.filter(status=LabRequest.STATUS_AWAITING).count(),
                'sample_collected': all_qs.filter(status=LabRequest.STATUS_COLLECTED).count(),
                'processing': all_qs.filter(status=LabRequest.STATUS_PROCESSING).count(),
                'result_ready': all_qs.filter(status=LabRequest.STATUS_READY).count(),
                'completed_today': all_qs.filter(
                    status=LabRequest.STATUS_COMPLETED, updated_at__date=today
                ).count(),
                'completed_this_month': all_qs.filter(
                    status=LabRequest.STATUS_COMPLETED, updated_at__date__gte=month_start
                ).count(),
                'assigned_to_me': mine_qs.filter(status__in=pending_statuses).count(),
                'today_requests': all_qs.filter(requested_at__date=today).count(),
                'priority_pending': all_qs.filter(
                    priority=LabRequest.PRIORITY_PRIORITY, status__in=pending_statuses
                ).count(),
            },
            'by_category': by_category,
            'by_status': by_status,
            'recent_requests': recent,
        })


# ─── Lab Tests (public) ───────────────────────────────────────────────────────

class LabTestListView(generics.ListAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = LabTestSerializer
    filterset_fields = ['category', 'is_active']
    search_fields = ['name', 'sample_type']

    def get_queryset(self):
        return LabTest.objects.filter(is_active=True)


# ─── Admin Lab Test Management ────────────────────────────────────────────────

class AdminLabTestListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAdminUser]
    serializer_class = LabTestSerializer
    queryset = LabTest.objects.all()


class AdminLabTestDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAdminUser]
    serializer_class = LabTestSerializer
    queryset = LabTest.objects.all()


# ─── Lab Requests ─────────────────────────────────────────────────────────────

class LabRequestListCreateView(generics.ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return LabRequestCreateSerializer
        return LabRequestSerializer

    def get_queryset(self):
        user = self.request.user
        if user.role in ['lab_technician', 'admin']:
            return (
                LabRequest.objects.all()
                .select_related('test', 'assigned_technician', 'patient')
                .prefetch_related('audit_logs')
            )
        return (
            LabRequest.objects.filter(patient=user)
            .select_related('test')
            .prefetch_related('audit_logs')
        )

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        patient = request.user if request.user.is_authenticated else None
        req = serializer.save(patient=patient)

        LabAuditLog.objects.create(
            request=req,
            action='Lab request created',
            performed_by=request.user,
        )
        return Response(LabRequestSerializer(req).data, status=status.HTTP_201_CREATED)


class LabRequestDetailView(generics.RetrieveAPIView):
    serializer_class = LabRequestSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.role in ['lab_technician', 'admin']:
            return LabRequest.objects.all().prefetch_related('audit_logs', 'result')
        return LabRequest.objects.filter(patient=user).prefetch_related('audit_logs', 'result')


class LabRequestUpdateView(generics.UpdateAPIView):
    serializer_class = LabRequestUpdateSerializer
    permission_classes = [IsLabTechOrAdmin]
    queryset = LabRequest.objects.all()

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', True)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        req = serializer.save()

        LabAuditLog.objects.create(
            request=req,
            action=f"Status updated to '{req.get_status_display()}'",
            performed_by=request.user,
        )

        # Notify patient of status change
        if req.patient:
            try:
                from apps.notifications.utils import create_notification
                create_notification(
                    recipient=req.patient,
                    notification_type='lab_status',
                    title=f"Lab Request {req.reference} Updated",
                    message=f"Your lab request is now: {req.get_status_display()}",
                    data={'url': f'/lab/requests/{req.id}', 'reference': req.reference, 'status': req.status},
                )
            except Exception:
                pass

        return Response(LabRequestSerializer(req).data)


# ─── Lab Results ──────────────────────────────────────────────────────────────

class LabResultCreateView(APIView):
    permission_classes = [IsLabTechOrAdmin]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, pk):
        try:
            lab_request = LabRequest.objects.get(pk=pk)
        except LabRequest.DoesNotExist:
            return Response({'detail': 'Lab request not found.'}, status=status.HTTP_404_NOT_FOUND)

        if hasattr(lab_request, 'result'):
            return Response(
                {'detail': 'Result already exists. Update it instead.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Validate file type and size
        uploaded_file = request.FILES.get('file')
        if uploaded_file:
            if uploaded_file.size > MAX_RESULT_SIZE:
                return Response(
                    {'detail': f'File too large. Max size is {MAX_RESULT_SIZE // (1024*1024)} MB.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            content_type = uploaded_file.content_type
            if content_type not in ALLOWED_RESULT_TYPES:
                return Response(
                    {'detail': 'Invalid file type. Allowed: PDF, JPEG, PNG.'},
                    status=status.HTTP_400_BAD_REQUEST
                )

        serializer = LabResultCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = serializer.save(
            request=lab_request,
            reviewed_by=request.user,
            filename=uploaded_file.name if uploaded_file else '',
        )

        lab_request.status = LabRequest.STATUS_READY
        lab_request.save(update_fields=['status', 'updated_at'])

        LabAuditLog.objects.create(
            request=lab_request,
            action='Result uploaded',
            performed_by=request.user,
        )

        # Notify patient result is ready
        if lab_request.patient:
            try:
                from apps.notifications.utils import notify_lab_result_ready
                notify_lab_result_ready(lab_request)
            except Exception:
                pass

        return Response(LabResultSerializer(result).data, status=status.HTTP_201_CREATED)


class LabResultDetailView(generics.RetrieveAPIView):
    serializer_class = LabResultSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = LabResult.objects.all()
