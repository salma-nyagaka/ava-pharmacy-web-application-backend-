import secrets
from datetime import timedelta

from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Count, Q
from django.http import FileResponse
from django.utils import timezone
from django.contrib.auth.hashers import make_password, check_password

from .models import (
    LabPartner, LabPartnerDocument, LabTechnicianProfile, LabTechDocument, LabTest,
    LaboratoryFacility, LaboratoryFacilityDocument, FacilityLabTest,
    LabRequest, LabAuditLog, LabResult,
)
from .serializers import (
    LabPartnerSerializer, LabPartnerCreateSerializer, LabPartnerUpdateSerializer,
    LabPartnerRegistrationSerializer,
    LabTechnicianProfileSerializer, LabTechnicianRegistrationSerializer,
    LabTestSerializer, LaboratoryFacilitySerializer,
    LaboratoryFacilityDocumentSerializer, LaboratoryFacilityDocumentCreateSerializer,
    LabRequestSerializer, LabRequestCreateSerializer,
    LabRequestUpdateSerializer, LabResultSerializer, LabResultCreateSerializer
)
from apps.accounts.permissions import IsAdminUser, IsLabPartner, IsLabTechOrAdmin
from apps.accounts.utils import log_admin_action
from apps.accounts.serializers import (
    ProvisionLabPartnerAccountSerializer, ProvisionLabTechnicianAccountSerializer,
    UserSerializer,
)

ALLOWED_RESULT_TYPES = ['application/pdf', 'image/jpeg', 'image/png']
MAX_RESULT_SIZE = 10 * 1024 * 1024  # 10 MB


def _active_lab_access(user):
    if not user.is_active or user.status != 'active':
        return False
    if user.role == 'lab_partner':
        partner = getattr(user, 'lab_partner_profile', None)
        return bool(partner and partner.status == LabPartner.STATUS_VERIFIED)
    if user.role == 'lab_technician':
        profile = getattr(user, 'lab_tech_profile', None)
        return bool(profile and profile.status == LabTechnicianProfile.STATUS_ACTIVE
                    and profile.partner_id and profile.partner.status == LabPartner.STATUS_VERIFIED
                    and profile.partner.user_id and profile.partner.user.is_active
                    and profile.partner.user.status == 'active')
    return True


def _lab_request_queryset_for_user(user):
    queryset = (
        LabRequest.objects.all()
        .select_related(
            'test', 'patient', 'assigned_partner', 'laboratory__partner',
            'assigned_pharmacist', 'assigned_technician',
        )
        .prefetch_related('audit_logs', 'result')
    )
    if not _active_lab_access(user):
        return queryset.none()
    if user.role == 'admin':
        return queryset
    if user.role == 'pharmacist':
        return queryset.filter(
            Q(assigned_pharmacist=user) | Q(assigned_pharmacist__isnull=True)
        )
    if user.role == 'lab_partner':
        return queryset.filter(
            Q(laboratory__partner__user=user)
            | Q(laboratory__isnull=True, assigned_partner__user=user)
        )
    if user.role == 'lab_technician':
        profile = getattr(user, 'lab_tech_profile', None)
        if not profile:
            return queryset.none()
        return queryset.filter(
            Q(assigned_technician=user) | (Q(assigned_technician__isnull=True) & (
                Q(laboratory_id__in=profile.facilities.values('pk'))
                | Q(laboratory__isnull=True, assigned_partner_id=profile.partner_id)
            ))
        )
    return queryset.filter(patient=user)


def _result_queryset_for_user(user):
    queryset = LabResult.objects.select_related(
        'request__patient', 'request__assigned_partner__user',
        'request__laboratory__partner__user',
        'request__assigned_pharmacist', 'request__assigned_technician',
        'reviewed_by',
    )
    if not _active_lab_access(user):
        return queryset.none()
    if user.role == 'admin':
        return queryset
    if user.role == 'pharmacist':
        return queryset.none()
    if user.role == 'lab_partner':
        return queryset.filter(
            Q(request__laboratory__partner__user=user)
            | Q(request__laboratory__isnull=True, request__assigned_partner__user=user)
        )
    if user.role == 'lab_technician':
        return queryset.filter(request__assigned_technician=user)
    return queryset.filter(request__patient=user)


def _get_lab_partner_or_404(user):
    try:
        return LabPartner.objects.prefetch_related('documents', 'technicians__user', 'technicians__documents').get(user=user)
    except LabPartner.DoesNotExist:
        from django.http import Http404
        raise Http404


# ─── Lab Partners ─────────────────────────────────────────────────────────────

class AdminLabPartnerListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAdminUser]
    parser_classes = [MultiPartParser, FormParser]
    filterset_fields = ['status']
    search_fields = ['name', 'email', 'reference']
    ordering = ['-submitted_at']

    def get_queryset(self):
        return LabPartner.objects.all().prefetch_related('documents', 'technicians__user', 'technicians__documents')

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return LabPartnerCreateSerializer
        return LabPartnerSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        partner = serializer.save(created_by=request.user, updated_by=request.user)
        return Response(LabPartnerSerializer(partner).data, status=status.HTTP_201_CREATED)


class AdminLabPartnerDetailView(generics.RetrieveUpdateAPIView):
    permission_classes = [IsAdminUser]
    queryset = LabPartner.objects.all().prefetch_related('documents', 'technicians__user', 'technicians__documents')

    def get_serializer_class(self):
        if self.request.method in ['PUT', 'PATCH']:
            return LabPartnerUpdateSerializer
        return LabPartnerSerializer

    def update(self, request, *args, **kwargs):
        protected_fields = {'status', 'status_note', 'rejection_note', 'verified_at'}
        attempted_protected_fields = protected_fields.intersection(request.data.keys())
        if attempted_protected_fields:
            raise ValidationError({
                field: 'Use the partner review action to change approval status.'
                for field in attempted_protected_fields
            })
        partial = kwargs.pop('partial', True)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        partner = serializer.save(updated_by=request.user)
        return Response(LabPartnerSerializer(partner).data)


class LabPartnerDocumentDownloadView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk):
        try:
            document = LabPartnerDocument.objects.select_related('partner__user').get(pk=pk)
        except LabPartnerDocument.DoesNotExist:
            return Response({'detail': 'Document not found.'}, status=status.HTTP_404_NOT_FOUND)
        if request.user.role != 'admin' and document.partner.user_id != request.user.id:
            return Response({'detail': 'Document not found.'}, status=status.HTTP_404_NOT_FOUND)
        response = FileResponse(document.file.open('rb'), as_attachment=True, filename=document.file.name.rsplit('/', 1)[-1])
        response['Cache-Control'] = 'private, no-store'
        return response


class AdminLabTechnicianListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAdminUser]
    serializer_class = LabTechnicianProfileSerializer

    def get_queryset(self):
        return LabTechnicianProfile.objects.filter(
            partner_id=self.kwargs['partner_pk']
        ).select_related('user').prefetch_related('documents')

    def perform_create(self, serializer):
        try:
            partner = LabPartner.objects.get(pk=self.kwargs['partner_pk'])
        except LabPartner.DoesNotExist:
            raise ValidationError({'detail': 'Lab partner not found.'})
        if not partner.facilities.filter(
            status=LaboratoryFacility.STATUS_VERIFIED,
            is_active=True,
        ).exists():
            raise ValidationError({'detail': 'Verify at least one laboratory before adding technicians.'})
        serializer.save(partner=partner, created_by=self.request.user, updated_by=self.request.user)


class AdminLabTechnicianDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAdminUser]
    serializer_class = LabTechnicianProfileSerializer
    queryset = LabTechnicianProfile.objects.all().select_related('user', 'partner').prefetch_related('documents')

    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)


class AdminLabPartnerActionView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request, pk):
        try:
            partner = LabPartner.objects.get(pk=pk)
        except LabPartner.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

        action = request.data.get('action')

        if action == 'verify':
            if not partner.documents.exists():
                raise ValidationError({
                    'detail': 'Upload at least one partner licence or accreditation document before verification.'
                })
            if partner.license_expiry and partner.license_expiry < timezone.now().date():
                raise ValidationError({'detail': 'The lab partner licence has expired.'})
            partner.status = LabPartner.STATUS_VERIFIED
            partner.verified_at = timezone.now()
            partner.status_note = ''
            partner.rejection_note = ''
            partner.updated_by = request.user
            partner.save(update_fields=['status', 'verified_at', 'status_note', 'rejection_note', 'updated_by', 'updated_at'])
            log_admin_action(request.user, 'lab_partner_verified', 'lab_partner', partner.id,
                             f'Verified {partner.name}')

        elif action == 'request_docs':
            note = (request.data.get('note') or '').strip()
            if not note:
                return Response({'note': 'Reason is required when requesting additional documents.'}, status=status.HTTP_400_BAD_REQUEST)
            partner.status = LabPartner.STATUS_PENDING
            FacilityLabTest.objects.filter(facility__partner=partner).update(is_active=False)
            partner.technicians.update(status=LabTechnicianProfile.STATUS_SUSPENDED)
            partner.status_note = note
            partner.updated_by = request.user
            partner.save(update_fields=['status', 'status_note', 'updated_by', 'updated_at'])
            log_admin_action(request.user, 'lab_partner_docs_requested', 'lab_partner', partner.id,
                             f'Requested more documents from {partner.name}')

        elif action == 'reject':
            note = (request.data.get('note') or '').strip()
            if not note:
                return Response({'note': 'Rejection reason is required.'}, status=status.HTTP_400_BAD_REQUEST)
            partner.status = LabPartner.STATUS_SUSPENDED
            FacilityLabTest.objects.filter(facility__partner=partner).update(is_active=False)
            partner.technicians.update(status=LabTechnicianProfile.STATUS_SUSPENDED)
            partner.rejection_note = note
            partner.updated_by = request.user
            partner.save(update_fields=['status', 'rejection_note', 'updated_by', 'updated_at'])
            log_admin_action(request.user, 'lab_partner_rejected', 'lab_partner', partner.id,
                             f'Rejected {partner.name}')

        elif action == 'suspend':
            partner.status = LabPartner.STATUS_SUSPENDED
            FacilityLabTest.objects.filter(facility__partner=partner).update(is_active=False)
            partner.technicians.update(status=LabTechnicianProfile.STATUS_SUSPENDED)
            partner.updated_by = request.user
            partner.save(update_fields=['status', 'updated_by', 'updated_at'])
            log_admin_action(request.user, 'lab_partner_suspended', 'lab_partner', partner.id,
                             f'Suspended {partner.name}')

        else:
            return Response(
                {'detail': 'Invalid action. Use: verify, request_docs, reject, suspend.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        return Response(LabPartnerSerializer(partner).data)


class AdminLabTechnicianActionView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request, pk):
        try:
            tech = LabTechnicianProfile.objects.get(pk=pk)
        except LabTechnicianProfile.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

        action = request.data.get('action')

        if action == 'approve':
            tech.status = LabTechnicianProfile.STATUS_ACTIVE
            tech.status_note = ''
            tech.rejection_note = ''
            tech.updated_by = request.user
            tech.save(update_fields=['status', 'status_note', 'rejection_note', 'updated_by', 'updated_at'])
            log_admin_action(request.user, 'lab_technician_approved', 'lab_technician', tech.id,
                             f'Approved {tech.name}')
        elif action == 'request_docs':
            note = (request.data.get('note') or '').strip()
            if not note:
                return Response({'note': 'Reason is required when requesting additional documents.'}, status=status.HTTP_400_BAD_REQUEST)
            tech.status = LabTechnicianProfile.STATUS_PENDING
            tech.status_note = note
            tech.updated_by = request.user
            tech.save(update_fields=['status', 'status_note', 'updated_by', 'updated_at'])
            log_admin_action(request.user, 'lab_technician_docs_requested', 'lab_technician', tech.id,
                             f'Requested more documents from {tech.name}')
        elif action == 'reject':
            note = (request.data.get('note') or '').strip()
            if not note:
                return Response({'note': 'Rejection reason is required.'}, status=status.HTTP_400_BAD_REQUEST)
            tech.status = LabTechnicianProfile.STATUS_SUSPENDED
            tech.rejection_note = note
            tech.updated_by = request.user
            tech.save(update_fields=['status', 'rejection_note', 'updated_by', 'updated_at'])
            log_admin_action(request.user, 'lab_technician_rejected', 'lab_technician', tech.id,
                             f'Rejected {tech.name}')
        else:
            return Response(
                {'detail': 'Invalid action. Use: approve, request_docs, reject.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        return Response(LabTechnicianProfileSerializer(tech).data)


class AdminLabPartnerProvisionAccountView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request, pk):
        try:
            partner = LabPartner.objects.get(pk=pk)
        except LabPartner.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = ProvisionLabPartnerAccountSerializer(
            data=request.data,
            context={'partner': partner, 'request': request},
        )
        serializer.is_valid(raise_exception=True)
        partner, user, _ = serializer.save()

        log_admin_action(
            request.user,
            'lab_partner_account_provisioned',
            'lab_partner',
            partner.id,
            f'Provisioned login account for lab partner {partner.name}',
            metadata={'user_id': user.id, 'role': user.role},
        )

        response_data = {
            'detail': 'Professional account provisioned successfully.',
            'application': LabPartnerSerializer(partner).data,
            'user': UserSerializer(user).data,
            'activation_email': getattr(serializer, 'activation_email_meta', None),
        }
        return Response(response_data, status=status.HTTP_201_CREATED)


class AdminLabTechnicianProvisionAccountView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request, pk):
        try:
            tech = LabTechnicianProfile.objects.select_related('partner').get(pk=pk)
        except LabTechnicianProfile.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = ProvisionLabTechnicianAccountSerializer(
            data=request.data,
            context={'tech': tech, 'request': request},
        )
        serializer.is_valid(raise_exception=True)
        tech, user, _ = serializer.save()

        log_admin_action(
            request.user,
            'lab_technician_account_provisioned',
            'lab_technician',
            tech.id,
            f'Provisioned login account for lab technician {tech.name}',
            metadata={'user_id': user.id, 'role': user.role},
        )

        response_data = {
            'detail': 'Professional account provisioned successfully.',
            'application': LabTechnicianProfileSerializer(tech).data,
            'user': UserSerializer(user).data,
            'activation_email': getattr(serializer, 'activation_email_meta', None),
        }
        return Response(response_data, status=status.HTTP_201_CREATED)


class LabPartnerDashboardView(APIView):
    permission_classes = [IsLabPartner]

    def get(self, request):
        partner = _get_lab_partner_or_404(request.user)
        request_qs = _lab_request_queryset_for_user(request.user)

        pending_statuses = [
            LabRequest.STATUS_AWAITING,
            LabRequest.STATUS_COLLECTED,
            LabRequest.STATUS_PROCESSING,
            LabRequest.STATUS_READY,
        ]

        return Response({
            'partner': LabPartnerSerializer(partner).data,
            'facilities': LaboratoryFacilitySerializer(
                partner.facilities.prefetch_related('offerings__test', 'technicians__user', 'documents'),
                many=True,
                context={'request': request},
            ).data,
            'stats': {
                'facilities_total': partner.facilities.count(),
                'facilities_verified': partner.facilities.filter(
                    status=LaboratoryFacility.STATUS_VERIFIED,
                    is_active=True,
                ).count(),
                'technicians_total': partner.technicians.count(),
                'technicians_active': partner.technicians.filter(status=LabTechnicianProfile.STATUS_ACTIVE).count(),
                'technicians_pending': partner.technicians.filter(status=LabTechnicianProfile.STATUS_PENDING).count(),
                'requests_total': request_qs.count(),
                'requests_pending': request_qs.filter(status__in=pending_statuses).count(),
                'requests_completed': request_qs.filter(status=LabRequest.STATUS_COMPLETED).count(),
            },
            'recent_requests': LabRequestSerializer(
                request_qs.order_by('-requested_at')[:10],
                many=True, context={'request': request},
            ).data,
        })


class LabPartnerFacilityListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsLabPartner]
    serializer_class = LaboratoryFacilitySerializer

    def get_partner(self):
        return _get_lab_partner_or_404(self.request.user)

    def get_queryset(self):
        return self.get_partner().facilities.prefetch_related(
            'offerings__test', 'technicians__user', 'documents'
        )

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['partner'] = self.get_partner()
        return context

    def perform_create(self, serializer):
        partner = self.get_partner()
        if partner.status != LabPartner.STATUS_VERIFIED:
            raise ValidationError({'detail': 'Only verified lab partners can register laboratories.'})
        serializer.save(partner=partner)


class LabPartnerFacilityDetailView(generics.RetrieveUpdateAPIView):
    permission_classes = [IsLabPartner]
    serializer_class = LaboratoryFacilitySerializer

    def get_partner(self):
        return _get_lab_partner_or_404(self.request.user)

    def get_queryset(self):
        return self.get_partner().facilities.prefetch_related(
            'offerings__test', 'technicians__user', 'documents'
        )

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['partner'] = self.get_partner()
        return context

    def perform_update(self, serializer):
        facility = serializer.save()
        verification_fields = {
            'name', 'county', 'address', 'accreditation', 'license_number',
            'license_expiry', 'supported_counties', 'home_collection_enabled',
            'physical_result_pickup_enabled', 'test_ids', 'technician_ids',
            'test_offerings',
        }
        if facility.status == LaboratoryFacility.STATUS_VERIFIED and (
            verification_fields & set(self.request.data.keys())
        ):
            facility.status = LaboratoryFacility.STATUS_PENDING
            facility.status_note = 'Facility details changed; Ava re-verification is required.'
            facility.verified_at = None
            facility.verified_by = None
            facility.save(update_fields=[
                'status', 'status_note', 'verified_at', 'verified_by', 'updated_at',
            ])


class LabPartnerFacilityDocumentListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsLabPartner]
    parser_classes = [MultiPartParser, FormParser]

    def get_facility(self):
        partner = _get_lab_partner_or_404(self.request.user)
        try:
            return partner.facilities.get(pk=self.kwargs['facility_pk'])
        except LaboratoryFacility.DoesNotExist:
            from django.http import Http404
            raise Http404

    def get_queryset(self):
        return self.get_facility().documents.all()

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return LaboratoryFacilityDocumentCreateSerializer
        return LaboratoryFacilityDocumentSerializer

    def perform_create(self, serializer):
        uploaded_file = self.request.FILES.get('file')
        if uploaded_file and uploaded_file.size > MAX_RESULT_SIZE:
            raise ValidationError({'file': 'File too large. Maximum size is 10 MB.'})
        if uploaded_file and uploaded_file.content_type not in ALLOWED_RESULT_TYPES:
            raise ValidationError({'file': 'Use a PDF, JPEG, or PNG document.'})
        facility = self.get_facility()
        serializer.save(facility=facility)
        if facility.status == LaboratoryFacility.STATUS_VERIFIED:
            facility.status = LaboratoryFacility.STATUS_PENDING
            facility.status_note = 'A new facility document requires Ava verification.'
            facility.verified_at = None
            facility.verified_by = None
            facility.save(update_fields=[
                'status', 'status_note', 'verified_at', 'verified_by', 'updated_at',
            ])


class LaboratoryFacilityDocumentDownloadView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk):
        queryset = LaboratoryFacilityDocument.objects.select_related('facility__partner__user')
        if request.user.role != 'admin':
            queryset = queryset.filter(facility__partner__user=request.user)
        try:
            document = queryset.get(pk=pk)
        except LaboratoryFacilityDocument.DoesNotExist:
            return Response({'detail': 'Document not found.'}, status=status.HTTP_404_NOT_FOUND)
        response = FileResponse(document.file.open('rb'), as_attachment=True, filename=document.file.name.rsplit('/', 1)[-1])
        response['Cache-Control'] = 'private, no-store'
        return response


class AdminLaboratoryFacilityListView(generics.ListAPIView):
    permission_classes = [IsAdminUser]
    serializer_class = LaboratoryFacilitySerializer
    filterset_fields = ['status', 'partner', 'county', 'is_active']
    search_fields = ['name', 'reference', 'partner__name', 'license_number', 'county']

    def get_queryset(self):
        return LaboratoryFacility.objects.select_related('partner').prefetch_related(
            'offerings__test', 'technicians__user', 'documents'
        )


class AdminLabApprovalQueueView(APIView):
    """Expose only records that require an administrator's next approval action."""
    permission_classes = [IsAdminUser]

    def get(self, request):
        partner_applications = LabPartner.objects.filter(
            status=LabPartner.STATUS_PENDING,
        ).prefetch_related('documents').order_by('-submitted_at')
        laboratory_applications = LaboratoryFacility.objects.filter(
            status=LaboratoryFacility.STATUS_PENDING,
            partner__status=LabPartner.STATUS_VERIFIED,
        ).select_related('partner').prefetch_related('documents').order_by('-submitted_at')
        return Response({
            'partner_applications': LabPartnerSerializer(partner_applications, many=True, context={'request': request}).data,
            'laboratory_applications': LaboratoryFacilitySerializer(laboratory_applications, many=True, context={'request': request}).data,
            'counts': {
                'partners': partner_applications.count(),
                'laboratories': laboratory_applications.count(),
            },
        })


class AdminLaboratoryFacilityDetailView(generics.RetrieveUpdateAPIView):
    permission_classes = [IsAdminUser]
    serializer_class = LaboratoryFacilitySerializer
    queryset = LaboratoryFacility.objects.select_related('partner').prefetch_related(
        'offerings__test', 'technicians__user', 'documents'
    )


class AdminLaboratoryFacilityActionView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request, pk):
        try:
            facility = LaboratoryFacility.objects.select_related('partner').prefetch_related(
                'offerings__test', 'technicians__user', 'documents'
            ).get(pk=pk)
        except LaboratoryFacility.DoesNotExist:
            return Response({'detail': 'Laboratory not found.'}, status=status.HTTP_404_NOT_FOUND)

        action = request.data.get('action')
        note = (request.data.get('note') or '').strip()
        if action == 'verify':
            if facility.partner.status != LabPartner.STATUS_VERIFIED:
                raise ValidationError({'detail': 'Verify the legal lab partner before its laboratory.'})
            if not facility.license_expiry:
                raise ValidationError({'detail': 'Provide the laboratory licence expiry date before verification.'})
            if facility.license_expiry < timezone.now().date():
                raise ValidationError({'detail': 'The laboratory licence has expired.'})
            if not facility.documents.exists():
                raise ValidationError({'detail': 'Upload at least one facility licence or accreditation document.'})
            facility.status = LaboratoryFacility.STATUS_VERIFIED
            facility.status_note = ''
            facility.verified_at = timezone.now()
            facility.verified_by = request.user
            facility.is_active = True
            facility.documents.filter(status=LaboratoryFacilityDocument.STATUS_SUBMITTED).update(
                status=LaboratoryFacilityDocument.STATUS_VERIFIED
            )
            facility._prefetched_objects_cache.pop('documents', None)
        elif action == 'request_changes':
            if not note:
                raise ValidationError({'note': 'Describe the required changes.'})
            facility.status = LaboratoryFacility.STATUS_PENDING
            facility.status_note = note
            facility.offerings.update(is_active=False)
        elif action == 'suspend':
            if not note:
                raise ValidationError({'note': 'Provide a suspension reason.'})
            facility.status = LaboratoryFacility.STATUS_SUSPENDED
            facility.status_note = note
            facility.is_active = False
            facility.offerings.update(is_active=False)
        else:
            raise ValidationError({'detail': 'Use verify, request_changes, or suspend.'})
        facility.save()
        log_admin_action(
            request.user,
            f'laboratory_facility_{action}',
            'laboratory_facility',
            facility.id,
            f'{action.replace("_", " ").title()}: {facility.name}',
            metadata={'partner_id': facility.partner_id, 'note': note},
        )
        return Response(LaboratoryFacilitySerializer(facility, context={'request': request}).data)


class LabPartnerTechnicianListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsLabPartner]
    serializer_class = LabTechnicianProfileSerializer

    def get_partner(self):
        return _get_lab_partner_or_404(self.request.user)

    def get_queryset(self):
        partner = self.get_partner()
        return (
            LabTechnicianProfile.objects.filter(partner=partner)
            .select_related('user', 'partner')
            .prefetch_related('documents')
        )

    def perform_create(self, serializer):
        partner = self.get_partner()
        if partner.status != LabPartner.STATUS_VERIFIED:
            from rest_framework.exceptions import ValidationError
            raise ValidationError({'detail': 'Only verified lab partners can add lab technicians.'})
        if not partner.facilities.filter(
            status=LaboratoryFacility.STATUS_VERIFIED,
            is_active=True,
        ).exists():
            from rest_framework.exceptions import ValidationError
            raise ValidationError({'detail': 'Verify at least one laboratory before adding technicians.'})
        serializer.save(
            partner=partner,
            status=LabTechnicianProfile.STATUS_ACTIVE,
            created_by=self.request.user,
            updated_by=self.request.user,
        )


class LabPartnerTechnicianActionView(APIView):
    permission_classes = [IsLabPartner]

    def post(self, request, pk):
        partner = _get_lab_partner_or_404(request.user)
        try:
            tech = LabTechnicianProfile.objects.get(pk=pk, partner=partner)
        except LabTechnicianProfile.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

        action = request.data.get('action')
        if action == 'activate':
            tech.status = LabTechnicianProfile.STATUS_ACTIVE
            tech.status_note = ''
            tech.rejection_note = ''
        elif action == 'suspend':
            tech.status = LabTechnicianProfile.STATUS_SUSPENDED
            tech.status_note = (request.data.get('note') or '').strip()
        else:
            return Response({'detail': 'Invalid action. Use: activate or suspend.'}, status=status.HTTP_400_BAD_REQUEST)

        tech.updated_by = request.user
        tech.save(update_fields=['status', 'status_note', 'rejection_note', 'updated_by', 'updated_at'])
        return Response(LabTechnicianProfileSerializer(tech).data)


class LabPartnerTechnicianProvisionAccountView(APIView):
    permission_classes = [IsLabPartner]

    def post(self, request, pk):
        partner = _get_lab_partner_or_404(request.user)
        if partner.status != LabPartner.STATUS_VERIFIED:
            return Response({'detail': 'Only verified lab partners can provision technician accounts.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            tech = LabTechnicianProfile.objects.select_related('partner').get(pk=pk, partner=partner)
        except LabTechnicianProfile.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = ProvisionLabTechnicianAccountSerializer(
            data=request.data,
            context={'tech': tech, 'request': request},
        )
        serializer.is_valid(raise_exception=True)
        tech, user, _ = serializer.save()

        response_data = {
            'detail': 'Professional account provisioned successfully.',
            'application': LabTechnicianProfileSerializer(tech).data,
            'user': UserSerializer(user).data,
            'activation_email': getattr(serializer, 'activation_email_meta', None),
        }
        return Response(response_data, status=status.HTTP_201_CREATED)


# ─── Public Professional Registration ────────────────────────────────────────

class LabPartnerRegistrationView(APIView):
    permission_classes = [permissions.AllowAny]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        serializer = LabPartnerRegistrationSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        partner = serializer.save()
        return Response(LabPartnerSerializer(partner).data, status=status.HTTP_201_CREATED)


class LabTechnicianRegistrationView(APIView):
    permission_classes = [permissions.AllowAny]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        serializer = LabTechnicianRegistrationSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        tech = serializer.save()
        return Response(LabTechnicianProfileSerializer(tech).data, status=status.HTTP_201_CREATED)


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

        all_qs = _lab_request_queryset_for_user(request.user)
        mine_qs = all_qs.filter(assigned_technician=request.user)

        by_category = list(
            all_qs.filter(status__in=pending_statuses)
            .values('test__category')
            .annotate(count=Count('id'))
        )

        by_status = list(
            all_qs.values('status').annotate(count=Count('id'))
        )

        recent = LabRequestSerializer(
            all_qs.select_related('test', 'assigned_technician').order_by('-requested_at')[:10],
            many=True, context={'request': request}
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
        return LabTest.objects.filter(is_active=True, facility_offerings__is_active=True, facility_offerings__facility__status='verified', facility_offerings__facility__is_active=True, facility_offerings__facility__partner__status='verified', facility_offerings__facility__partner__user__is_active=True, facility_offerings__facility__partner__user__status='active').distinct()


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
        return _lab_request_queryset_for_user(self.request.user)

    def create(self, request, *args, **kwargs):
        if request.user.role not in ('customer', 'admin'):
            raise PermissionDenied('Only patients or administrators can create lab requests.')
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        patient = request.user if request.user.is_authenticated else None
        req = serializer.save(patient=patient)

        LabAuditLog.objects.create(
            request=req,
            action='Lab request created',
            performed_by=request.user,
        )
        return Response(LabRequestSerializer(req, context={'request': request}).data, status=status.HTTP_201_CREATED)


class LabRequestDetailView(generics.RetrieveAPIView):
    serializer_class = LabRequestSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return _lab_request_queryset_for_user(self.request.user)


class LabRequestUpdateView(generics.UpdateAPIView):
    serializer_class = LabRequestUpdateSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return _lab_request_queryset_for_user(self.request.user).select_for_update(of=('self',))

    @transaction.atomic
    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', True)
        instance = self.get_object()

        role = request.user.role
        editable_fields = {
            'customer': {'status'},
            'admin': {
                'status', 'payment_status', 'priority', 'assigned_partner', 'laboratory',
                'assigned_pharmacist', 'assigned_technician', 'scheduled_at',
                'collection_address', 'collection_instructions',
                'result_pickup_location', 'notes',
            },
            'pharmacist': {
                'priority', 'assigned_partner', 'laboratory', 'assigned_pharmacist',
                'assigned_technician', 'scheduled_at',
                'collection_address', 'collection_instructions',
                'result_pickup_location', 'notes',
            },
            'lab_partner': {'assigned_technician', 'scheduled_at', 'notes'},
            'lab_technician': {'status', 'assigned_technician', 'notes'},
        }.get(role, set())
        requested_fields = set(request.data.keys())
        disallowed = requested_fields - editable_fields
        if disallowed:
            raise PermissionDenied(
                f"Your role cannot update: {', '.join(sorted(disallowed))}."
            )

        if role == 'customer' and (request.data.get('status') != LabRequest.STATUS_CANCELLED or instance.status != LabRequest.STATUS_AWAITING or instance.payment_status != LabRequest.PAYMENT_PENDING):
            raise ValidationError({'status': 'Only unpaid requests awaiting sample collection can be cancelled by the patient. Contact your coordinator for other cancellations.'})

        if role == 'pharmacist':
            requested_pharmacist = request.data.get('assigned_pharmacist')
            if requested_pharmacist not in (None, '', request.user.pk, str(request.user.pk)):
                raise PermissionDenied('Pharmacists can only assign requests to themselves.')

        if role == 'lab_partner' and instance.assigned_partner_id != getattr(
            getattr(request.user, 'lab_partner_profile', None), 'id', None
        ):
            raise PermissionDenied('This request is not assigned to your laboratory.')

        if role == 'lab_technician':
            requested_technician = request.data.get('assigned_technician')
            if requested_technician not in (None, '', request.user.pk, str(request.user.pk)):
                raise PermissionDenied('Technicians can only assign requests to themselves.')
            if instance.assigned_technician_id not in (None, request.user.pk):
                raise PermissionDenied('This request is assigned to another technician.')

        next_status = request.data.get('status')
        if next_status and next_status != instance.status:
            allowed_transitions = {
                LabRequest.STATUS_AWAITING: {LabRequest.STATUS_COLLECTED, LabRequest.STATUS_CANCELLED},
                LabRequest.STATUS_COLLECTED: {LabRequest.STATUS_PROCESSING, LabRequest.STATUS_CANCELLED},
                LabRequest.STATUS_PROCESSING: {LabRequest.STATUS_CANCELLED},
                LabRequest.STATUS_READY: {LabRequest.STATUS_COMPLETED},
                LabRequest.STATUS_COMPLETED: set(),
                LabRequest.STATUS_CANCELLED: set(),
            }
            if next_status == LabRequest.STATUS_COMPLETED and not hasattr(instance, 'result'):
                raise ValidationError({'status': 'A result must be released before completing this request.'})
            if next_status not in allowed_transitions.get(instance.status, set()):
                raise ValidationError({
                    'status': f'Cannot move from {instance.status} to {next_status}.'
                })
            if (
                next_status == LabRequest.STATUS_COLLECTED
                and instance.channel == LabRequest.CHANNEL_COLLECTION
                and instance.collection_verified_at is None
            ):
                raise ValidationError({
                    'status': 'Verify the patient collection code before marking the sample collected.'
                })

        previous = {
            'status': instance.status,
            'payment_status': instance.payment_status,
            'assigned_partner_id': instance.assigned_partner_id,
            'laboratory_id': instance.laboratory_id,
            'assigned_pharmacist_id': instance.assigned_pharmacist_id,
            'assigned_technician_id': instance.assigned_technician_id,
            'scheduled_at': instance.scheduled_at,
        }
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        if instance.status != LabRequest.STATUS_AWAITING and any(
            field in serializer.validated_data and getattr(serializer.validated_data[field], 'pk', None) != getattr(instance, f'{field}_id')
            for field in ('assigned_partner', 'laboratory', 'assigned_technician')
        ):
            raise ValidationError({'assignment': 'Assignments cannot change after sample collection.'})
        assignment_changed = any(
            field in serializer.validated_data and getattr(serializer.validated_data[field], 'pk', None) != getattr(instance, f'{field}_id')
            for field in ('assigned_partner', 'laboratory', 'assigned_technician')
        )
        req = serializer.save()
        if assignment_changed or req.status == LabRequest.STATUS_CANCELLED:
            req.collection_verification_code_hash = ''
            req.collection_code_expires_at = None
            req.collection_verification_attempts = 0
            req.save(update_fields=['collection_verification_code_hash', 'collection_code_expires_at', 'collection_verification_attempts', 'updated_at'])

        actions = []
        if previous['payment_status'] != req.payment_status:
            actions.append(f"Payment status recorded as '{req.get_payment_status_display()}' (administrative record)")
        if previous['status'] != req.status:
            actions.append(f"Status updated to '{req.get_status_display()}'")
        if previous['assigned_partner_id'] != req.assigned_partner_id:
            actions.append(f"Laboratory assigned: {req.assigned_partner.name}" if req.assigned_partner else 'Laboratory assignment removed')
        if previous['laboratory_id'] != req.laboratory_id:
            actions.append(f"Facility assigned: {req.laboratory.name}" if req.laboratory else 'Facility assignment removed')
        if previous['assigned_pharmacist_id'] != req.assigned_pharmacist_id:
            actions.append(f"Pharmacist coordinator assigned: {req.assigned_pharmacist.full_name}" if req.assigned_pharmacist else 'Pharmacist coordinator removed')
        if previous['assigned_technician_id'] != req.assigned_technician_id:
            actions.append(f"Technician assigned: {req.assigned_technician.full_name}" if req.assigned_technician else 'Technician assignment removed')
        if previous['scheduled_at'] != req.scheduled_at:
            actions.append('Collection appointment updated')

        for action in actions:
            LabAuditLog.objects.create(
                request=req,
                action=action,
                performed_by=request.user,
            )

        # Notify patient of status change
        if req.patient and previous['status'] != req.status:
            try:
                from apps.notifications.utils import create_notification
                create_notification(
                    recipient=req.patient,
                    notification_type='lab_status',
                    title=f"Lab Request {req.reference} Updated",
                    message=f"Your lab request is now: {req.get_status_display()}",
                    data={'url': '/account/lab-tests', 'reference': req.reference, 'status': req.status},
                )
            except Exception:
                pass

        req._prefetched_objects_cache = {}
        return Response(LabRequestSerializer(req, context={'request': request}).data)


class LabCollectionCodeIssueView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @transaction.atomic
    def post(self, request, pk):
        try:
            lab_request = _lab_request_queryset_for_user(request.user).select_for_update(of=('self',)).get(pk=pk, patient=request.user)
        except LabRequest.DoesNotExist:
            return Response({'detail': 'Lab request not found.'}, status=status.HTTP_404_NOT_FOUND)
        if lab_request.channel != LabRequest.CHANNEL_COLLECTION:
            raise ValidationError({'detail': 'A collection code is only used for home sample collection.'})
        if lab_request.status != LabRequest.STATUS_AWAITING:
            raise ValidationError({'detail': 'A collection code can only be generated while awaiting the sample.'})
        if not lab_request.assigned_technician_id:
            raise ValidationError({'detail': 'A collector must be assigned before generating the code.'})

        code = f'{secrets.randbelow(1_000_000):06d}'
        now = timezone.now()
        lab_request.collection_verification_code_hash = make_password(code)
        lab_request.collection_code_requested_at = now
        lab_request.collection_code_expires_at = now + timedelta(hours=4)
        lab_request.collection_verification_attempts = 0
        lab_request.collection_verified_at = None
        lab_request.collection_verified_by = None
        lab_request.save(update_fields=[
            'collection_verification_code_hash', 'collection_code_requested_at',
            'collection_code_expires_at', 'collection_verification_attempts',
            'collection_verified_at', 'collection_verified_by', 'updated_at',
        ])
        LabAuditLog.objects.create(
            request=lab_request,
            action='Patient generated a home-collection verification code',
            performed_by=request.user,
        )
        return Response({
            'code': code,
            'expires_at': lab_request.collection_code_expires_at,
            'laboratory_name': lab_request.laboratory.name if lab_request.laboratory else '',
            'technician_name': lab_request.assigned_technician.full_name,
        })


class LabCollectionCodeVerifyView(APIView):
    permission_classes = [IsLabTechOrAdmin]

    @transaction.atomic
    def post(self, request, pk):
        try:
            lab_request = _lab_request_queryset_for_user(request.user).select_for_update(of=('self',)).get(pk=pk)
        except LabRequest.DoesNotExist:
            return Response({'detail': 'Lab request not found.'}, status=status.HTTP_404_NOT_FOUND)
        if request.user.role != 'admin' and lab_request.laboratory_id and (lab_request.laboratory.status != LaboratoryFacility.STATUS_VERIFIED or not lab_request.laboratory.is_active):
            raise PermissionDenied('This laboratory is not active and approved. Contact the coordinator.')
        if request.user.role != 'admin' and lab_request.assigned_technician_id != request.user.id:
            raise PermissionDenied('Only the assigned collector can verify this collection.')
        if lab_request.channel != LabRequest.CHANNEL_COLLECTION or lab_request.status != LabRequest.STATUS_AWAITING:
            raise ValidationError({'detail': 'This request is not awaiting home sample collection.'})
        if lab_request.collection_verification_attempts >= 5:
            return Response(
                {'detail': 'Too many attempts. Ask the patient to generate a new code.'},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )
        if (
            not lab_request.collection_verification_code_hash
            or not lab_request.collection_code_expires_at
            or lab_request.collection_code_expires_at <= timezone.now()
        ):
            raise ValidationError({'code': 'The code is missing or expired. Ask the patient for a new code.'})

        code = str(request.data.get('code', '')).strip()
        lab_request.collection_verification_attempts += 1
        if not code or not check_password(code, lab_request.collection_verification_code_hash):
            lab_request.save(update_fields=['collection_verification_attempts', 'updated_at'])
            return Response({'detail': 'The verification code is incorrect.'}, status=status.HTTP_400_BAD_REQUEST)

        now = timezone.now()
        lab_request.collection_verified_at = now
        lab_request.collection_verified_by = request.user
        lab_request.status = LabRequest.STATUS_COLLECTED
        lab_request.collection_verification_code_hash = ''
        lab_request.save(update_fields=[
            'collection_verified_at', 'collection_verified_by', 'status',
            'collection_verification_code_hash', 'collection_verification_attempts',
            'updated_at',
        ])
        LabAuditLog.objects.create(
            request=lab_request,
            action=f'Home collection verified with patient code by {request.user.full_name}',
            performed_by=request.user,
        )
        if lab_request.patient:
            try:
                from apps.notifications.utils import create_notification
                create_notification(
                    recipient=lab_request.patient,
                    notification_type='lab_status',
                    title='Sample collection confirmed',
                    message=f'Your sample for {lab_request.test.name} was collected successfully.',
                    data={'url': '/account/lab-tests', 'reference': lab_request.reference},
                )
            except Exception:
                pass
        lab_request._prefetched_objects_cache = {}
        return Response(LabRequestSerializer(lab_request, context={'request': request}).data)


# ─── Lab Results ──────────────────────────────────────────────────────────────

class LabResultCreateView(APIView):
    permission_classes = [IsLabTechOrAdmin]
    parser_classes = [MultiPartParser, FormParser]

    @transaction.atomic
    def post(self, request, pk):
        try:
            lab_request = _lab_request_queryset_for_user(request.user).select_for_update(of=('self',)).get(pk=pk)
        except LabRequest.DoesNotExist:
            return Response({'detail': 'Lab request not found.'}, status=status.HTTP_404_NOT_FOUND)

        if request.user.role != 'admin' and lab_request.laboratory_id and (lab_request.laboratory.status != LaboratoryFacility.STATUS_VERIFIED or not lab_request.laboratory.is_active):
            raise PermissionDenied('This laboratory is not active and approved. Contact the coordinator.')
        if request.user.role != 'admin' and lab_request.assigned_technician_id != request.user.id:
            raise PermissionDenied('Only the assigned technician can upload this result.')

        if lab_request.status != LabRequest.STATUS_PROCESSING:
            return Response(
                {'detail': 'Results can only be uploaded while the request is processing.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

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

        if uploaded_file:
            header = uploaded_file.read(8)
            uploaded_file.seek(0)
            valid = ((content_type == 'application/pdf' and header.startswith(b'%PDF-'))
                     or (content_type == 'image/png' and header == b'\x89PNG\r\n\x1a\n')
                     or (content_type == 'image/jpeg' and header.startswith(b'\xff\xd8\xff')))
            if not valid:
                raise ValidationError({'file': 'The file content does not match a supported PDF, JPEG or PNG.'})

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

        return Response(
            LabResultSerializer(result, context={'request': request}).data,
            status=status.HTTP_201_CREATED,
        )


class LabResultDetailView(generics.RetrieveAPIView):
    serializer_class = LabResultSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return _result_queryset_for_user(self.request.user)


class LabResultDownloadView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk):
        try:
            result = _result_queryset_for_user(request.user).get(pk=pk)
        except LabResult.DoesNotExist:
            return Response({'detail': 'Result not found.'}, status=status.HTTP_404_NOT_FOUND)
        if not result.file:
            return Response({'detail': 'No result file is available.'}, status=status.HTTP_404_NOT_FOUND)
        LabAuditLog.objects.create(
            request=result.request,
            action='Result file downloaded',
            performed_by=request.user,
        )
        response = FileResponse(
            result.file.open('rb'),
            as_attachment=True,
            filename=result.filename or f'{result.reference}.pdf',
        )
        response['Cache-Control'] = 'private, no-store'
        return response


class LabTechDocumentDownloadView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk):
        if not request.user.is_active or request.user.status != 'active':
            raise PermissionDenied('Account is not active.')
        documents = LabTechDocument.objects.select_related('tech__user', 'tech__partner__user')
        if request.user.role != 'admin':
            documents = documents.filter(Q(tech__user=request.user) | Q(tech__partner__user=request.user))
        try:
            document = documents.get(pk=pk)
        except LabTechDocument.DoesNotExist:
            return Response({'detail': 'Document not found.'}, status=status.HTTP_404_NOT_FOUND)
        response = FileResponse(document.file.open('rb'), as_attachment=True, filename=document.file.name.rsplit('/', 1)[-1])
        response['Cache-Control'] = 'private, no-store'
        return response
