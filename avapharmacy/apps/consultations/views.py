from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.throttling import UserRateThrottle
from django.utils import timezone
from django.db.models import Sum, Count, Q

from .models import (
    DoctorProfile, DoctorDocument, PediatricianProfile, PediatricianDocument,
    Consultation, ConsultationMessage,
    DoctorPrescription, PediatricianPrescription,
    DoctorEarning, PediatricianEarning,
)
from .serializers import (
    DoctorProfileSerializer, DoctorProfileListSerializer, DoctorOnboardingSerializer,
    PediatricianProfileSerializer, PediatricianProfileListSerializer, PediatricianOnboardingSerializer,
    AdminDoctorUpdateSerializer, AdminPediatricianUpdateSerializer,
    ConsultationSerializer, ConsultationListSerializer,
    ConsultationCreateSerializer, ConsultationUpdateSerializer,
    ConsultationMessageSerializer,
    DoctorPrescriptionSerializer, PediatricianPrescriptionSerializer,
    DoctorEarningSerializer, PediatricianEarningSerializer,
)
from apps.accounts.permissions import IsAdminUser, IsDoctor, IsDoctorOrAdmin
from apps.accounts.utils import log_admin_action
from apps.accounts.serializers import (
    ProvisionDoctorAccountSerializer, ProvisionPediatricianAccountSerializer, UserSerializer,
)


def _get_doctor_or_404(user):
    try:
        return DoctorProfile.objects.get(user=user)
    except DoctorProfile.DoesNotExist:
        return None


def _get_pediatrician_or_404(user):
    try:
        return PediatricianProfile.objects.get(user=user)
    except PediatricianProfile.DoesNotExist:
        return None


def _get_provider_for_user(user):
    if getattr(user, 'role', None) == 'pediatrician':
        return _get_pediatrician_or_404(user)
    return _get_doctor_or_404(user)


# ─── Public ───────────────────────────────────────────────────────────────────

class DoctorListView(generics.ListAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = DoctorProfileListSerializer
    filterset_fields = ['type', 'specialty']
    search_fields = ['name', 'specialty', 'facility']

    def get_queryset(self):
        return DoctorProfile.objects.filter(status=DoctorProfile.STATUS_ACTIVE)


class PediatricianListView(generics.ListAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = PediatricianProfileListSerializer
    filterset_fields = ['specialty']
    search_fields = ['name', 'specialty', 'facility']

    def get_queryset(self):
        return PediatricianProfile.objects.filter(status=PediatricianProfile.STATUS_ACTIVE)


class DoctorDetailView(generics.RetrieveAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = DoctorProfileSerializer
    queryset = DoctorProfile.objects.all()


class PediatricianDetailView(generics.RetrieveAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = PediatricianProfileSerializer
    queryset = PediatricianProfile.objects.all()


# ─── Doctor / Pediatrician Onboarding ─────────────────────────────────────────

class DoctorOnboardingView(APIView):
    permission_classes = [permissions.AllowAny]
    parser_classes = [MultiPartParser, FormParser]
    throttle_classes = [UserRateThrottle]

    def post(self, request):
        serializer = DoctorOnboardingSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        profile = serializer.save()
        return Response(DoctorProfileSerializer(profile).data, status=status.HTTP_201_CREATED)


class PediatricianOnboardingView(APIView):
    permission_classes = [permissions.AllowAny]
    parser_classes = [MultiPartParser, FormParser]
    throttle_classes = [UserRateThrottle]

    def post(self, request):
        serializer = PediatricianOnboardingSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        profile = serializer.save()
        return Response(PediatricianProfileSerializer(profile).data, status=status.HTTP_201_CREATED)


# ─── Doctor Dashboard ─────────────────────────────────────────────────────────

class DoctorDashboardView(APIView):
    permission_classes = [IsDoctor]

    def get(self, request):
        doctor = _get_doctor_or_404(request.user)
        if not doctor:
            return Response({'detail': 'Doctor profile not found.'}, status=status.HTTP_404_NOT_FOUND)

        today = timezone.now().date()
        month_start = today.replace(day=1)
        qs = Consultation.objects.filter(doctor=doctor)

        stats = {
            'today': qs.filter(created_at__date=today).count(),
            'waiting': qs.filter(status=Consultation.STATUS_WAITING).count(),
            'in_progress': qs.filter(status=Consultation.STATUS_IN_PROGRESS).count(),
            'completed_this_month': qs.filter(
                status=Consultation.STATUS_COMPLETED,
                created_at__date__gte=month_start
            ).count(),
            'total_completed': qs.filter(status=Consultation.STATUS_COMPLETED).count(),
        }

        earnings = DoctorEarning.objects.filter(doctor=doctor)
        stats['monthly_earnings'] = float(
            earnings.filter(earned_at__date__gte=month_start).aggregate(t=Sum('amount'))['t'] or 0
        )
        stats['total_earnings'] = float(
            earnings.aggregate(t=Sum('amount'))['t'] or 0
        )

        recent = ConsultationListSerializer(
            qs.select_related('patient').order_by('-created_at')[:5], many=True
        ).data

        return Response({
            'profile': DoctorProfileSerializer(doctor).data,
            'stats': stats,
            'recent_consultations': recent,
        })


# ─── Pediatrician Dashboard ───────────────────────────────────────────────────

class PediatricianDashboardView(APIView):
    """Dedicated endpoint for the /pediatrician frontend route."""
    permission_classes = [IsDoctor]

    def get(self, request):
        pediatrician = _get_pediatrician_or_404(request.user)
        if not pediatrician:
            return Response({'detail': 'Profile not found.'}, status=status.HTTP_404_NOT_FOUND)

        today = timezone.now().date()
        month_start = today.replace(day=1)

        qs = Consultation.objects.filter(pediatrician=pediatrician, is_pediatric=True)

        return Response({
            'profile': PediatricianProfileSerializer(pediatrician).data,
            'stats': {
                'today': qs.filter(created_at__date=today).count(),
                'waiting': qs.filter(status=Consultation.STATUS_WAITING).count(),
                'in_progress': qs.filter(status=Consultation.STATUS_IN_PROGRESS).count(),
                'consent_pending': qs.filter(consent_status='pending').count(),
                'dosage_alerts': qs.filter(
                    dosage_alert=True,
                    status__in=[Consultation.STATUS_WAITING, Consultation.STATUS_IN_PROGRESS]
                ).count(),
                'completed_this_month': qs.filter(
                    status=Consultation.STATUS_COMPLETED,
                    created_at__date__gte=month_start
                ).count(),
                'monthly_earnings': float(
                    PediatricianEarning.objects.filter(
                        pediatrician=pediatrician, earned_at__date__gte=month_start
                    ).aggregate(t=Sum('amount'))['t'] or 0
                ),
            },
            'recent_consultations': ConsultationListSerializer(
                qs.order_by('-created_at')[:5], many=True
            ).data,
        })


# ─── Guardian Consent ─────────────────────────────────────────────────────────

class GuardianConsentView(APIView):
    """Patient/guardian grants consent for pediatric consultation."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        try:
            consultation = Consultation.objects.get(pk=pk, patient=request.user, is_pediatric=True)
        except Consultation.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

        if consultation.consent_status == 'granted':
            return Response({'detail': 'Consent already granted.'})

        consultation.consent_status = 'granted'
        consultation.save(update_fields=['consent_status'])
        return Response({'detail': 'Consent granted.', 'reference': consultation.reference})


# ─── Patient Consultations ────────────────────────────────────────────────────

class ConsultationListCreateView(generics.ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return ConsultationCreateSerializer
        return ConsultationListSerializer

    def get_queryset(self):
        return Consultation.objects.filter(patient=self.request.user).select_related('doctor')

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        consultation = serializer.save(
            patient=request.user,
            patient_name=request.user.full_name,
        )

        # Notify doctor of new consultation
        doctor = consultation.doctor
        pediatrician = consultation.pediatrician
        provider_user = None
        if doctor and doctor.user:
            provider_user = doctor.user
        elif pediatrician and pediatrician.user:
            provider_user = pediatrician.user
        if provider_user:
            try:
                from apps.notifications.utils import notify_new_consultation
                notify_new_consultation(provider_user, consultation)
            except Exception:
                pass

        return Response(ConsultationSerializer(consultation).data, status=status.HTTP_201_CREATED)


class ConsultationDetailView(generics.RetrieveUpdateAPIView):
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.role in ['doctor', 'pediatrician', 'admin']:
            return Consultation.objects.all().prefetch_related('messages')
        return Consultation.objects.filter(patient=user).prefetch_related('messages')

    def get_serializer_class(self):
        if self.request.method in ['PUT', 'PATCH']:
            return ConsultationUpdateSerializer
        return ConsultationSerializer

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', True)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        consultation = serializer.save()

        # Notify patient of status change
        if 'status' in request.data and consultation.patient:
            try:
                from apps.notifications.utils import create_notification
                create_notification(
                    recipient=consultation.patient,
                    notification_type='consultation_status',
                    title=f"Consultation {consultation.reference} Updated",
                    message=f"Your consultation status is now: {consultation.get_status_display()}",
                    data={'url': f'/consultations/{consultation.id}', 'reference': consultation.reference},
                )
            except Exception:
                pass

        return Response(ConsultationSerializer(consultation).data)


# ─── Consultation Messages ────────────────────────────────────────────────────

class ConsultationMessageListCreateView(generics.ListCreateAPIView):
    serializer_class = ConsultationMessageSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return ConsultationMessage.objects.filter(consultation_id=self.kwargs['pk'])

    def perform_create(self, serializer):
        try:
            consultation = Consultation.objects.get(pk=self.kwargs['pk'])
        except Consultation.DoesNotExist:
            from rest_framework.exceptions import NotFound
            raise NotFound('Consultation not found.')

        # Validate the user is a participant
        user = self.request.user
        is_doctor = bool(consultation.doctor and consultation.doctor.user == user)
        is_pediatrician = bool(consultation.pediatrician and consultation.pediatrician.user == user)
        is_patient = consultation.patient == user
        is_admin = user.role == 'admin'
        if not (is_doctor or is_pediatrician or is_patient or is_admin):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('You are not a participant in this consultation.')

        msg = serializer.save(
            consultation=consultation,
            sender=user,
            sender_name=user.full_name,
        )
        consultation.last_message_at = msg.sent_at
        consultation.save(update_fields=['last_message_at'])

        # Notify the other participant
        try:
            from apps.notifications.utils import notify_consultation_message
            if is_patient and consultation.doctor and consultation.doctor.user:
                notify_consultation_message(consultation.doctor.user, consultation, user.full_name)
            elif is_patient and consultation.pediatrician and consultation.pediatrician.user:
                notify_consultation_message(consultation.pediatrician.user, consultation, user.full_name)
            elif (is_doctor or is_pediatrician) and consultation.patient:
                notify_consultation_message(consultation.patient, consultation, user.full_name)
        except Exception:
            pass


# ─── Doctor-Specific Views ────────────────────────────────────────────────────

class DoctorConsultationListView(generics.ListAPIView):
    serializer_class = ConsultationListSerializer
    permission_classes = [IsDoctor]
    filterset_fields = ['status', 'priority', 'is_pediatric']

    def get_queryset(self):
        provider = _get_provider_for_user(self.request.user)
        if not provider:
            return Consultation.objects.none()
        filter_kwargs = {'pediatrician': provider} if self.request.user.role == 'pediatrician' else {'doctor': provider}
        return Consultation.objects.filter(**filter_kwargs).select_related('patient')


class ClinicianPrescriptionListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsDoctor]

    def get_serializer_class(self):
        if self.request.user.role == 'pediatrician':
            return PediatricianPrescriptionSerializer
        return DoctorPrescriptionSerializer

    def get_queryset(self):
        provider = _get_provider_for_user(self.request.user)
        if not provider:
            return PediatricianPrescription.objects.none() if self.request.user.role == 'pediatrician' else DoctorPrescription.objects.none()
        if self.request.user.role == 'pediatrician':
            return PediatricianPrescription.objects.filter(pediatrician=provider)
        return DoctorPrescription.objects.filter(doctor=provider)

    def perform_create(self, serializer):
        provider = _get_provider_for_user(self.request.user)
        if not provider:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('No clinician profile found.')
        if self.request.user.role == 'pediatrician':
            serializer.save(pediatrician=provider)
        else:
            serializer.save(doctor=provider)


class ClinicianEarningsView(generics.ListAPIView):
    permission_classes = [IsDoctor]

    def get_serializer_class(self):
        if self.request.user.role == 'pediatrician':
            return PediatricianEarningSerializer
        return DoctorEarningSerializer

    def get_queryset(self):
        provider = _get_provider_for_user(self.request.user)
        if not provider:
            return PediatricianEarning.objects.none() if self.request.user.role == 'pediatrician' else DoctorEarning.objects.none()
        if self.request.user.role == 'pediatrician':
            return PediatricianEarning.objects.filter(pediatrician=provider)
        return DoctorEarning.objects.filter(doctor=provider)


# ─── Admin Doctor Management ──────────────────────────────────────────────────

class AdminDoctorListView(generics.ListAPIView):
    permission_classes = [IsAdminUser]
    serializer_class = DoctorProfileSerializer
    filterset_fields = ['status']
    search_fields = ['name', 'email', 'license_number']
    ordering = ['-submitted_at']
    queryset = DoctorProfile.objects.all().prefetch_related('documents')


class AdminDoctorDetailView(generics.RetrieveUpdateAPIView):
    permission_classes = [IsAdminUser]
    queryset = DoctorProfile.objects.all()

    def get_serializer_class(self):
        if self.request.method in ['PUT', 'PATCH']:
            return AdminDoctorUpdateSerializer
        return DoctorProfileSerializer

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', True)
        instance = self.get_object()
        was_pending = instance.status == DoctorProfile.STATUS_PENDING
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)

        if request.data.get('status') == DoctorProfile.STATUS_ACTIVE and not instance.verified_at:
            instance.verified_at = timezone.now()
            instance.save(update_fields=['verified_at'])

        doctor = serializer.save(updated_by=request.user)

        # Notify doctor if newly verified
        if was_pending and doctor.status == DoctorProfile.STATUS_ACTIVE and doctor.user:
            try:
                from apps.notifications.utils import notify_doctor_verified
                notify_doctor_verified(doctor)
            except Exception:
                pass

        return Response(DoctorProfileSerializer(doctor).data)


class AdminDoctorActionView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request, pk):
        try:
            doctor = DoctorProfile.objects.get(pk=pk)
        except DoctorProfile.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

        action = request.data.get('action')

        if action == 'approve':
            doctor.status = DoctorProfile.STATUS_ACTIVE
            doctor.verified_at = timezone.now()
            doctor.status_note = ''
            doctor.updated_by = request.user
            doctor.save(update_fields=['status', 'verified_at', 'status_note', 'updated_by', 'updated_at'])
            log_admin_action(request.user, 'doctor_approved', 'doctor_profile', doctor.id,
                             f'Approved {doctor.name}')
            if doctor.user:
                try:
                    from apps.notifications.utils import notify_doctor_verified
                    notify_doctor_verified(doctor)
                except Exception:
                    pass

        elif action == 'request_docs':
            note = request.data.get('note', '')
            doctor.status_note = note
            doctor.updated_by = request.user
            doctor.save(update_fields=['status_note', 'updated_by', 'updated_at'])
            log_admin_action(request.user, 'doctor_docs_requested', 'doctor_profile', doctor.id,
                             f'Requested documents from {doctor.name}')

        elif action == 'reject':
            note = (request.data.get('note') or '').strip()
            if not note:
                return Response({'note': 'Rejection reason is required.'}, status=status.HTTP_400_BAD_REQUEST)
            doctor.status = DoctorProfile.STATUS_SUSPENDED
            doctor.rejection_note = note
            doctor.updated_by = request.user
            doctor.save(update_fields=['status', 'rejection_note', 'updated_by', 'updated_at'])
            log_admin_action(request.user, 'doctor_rejected', 'doctor_profile', doctor.id,
                             f'Rejected {doctor.name}')

        else:
            return Response(
                {'detail': 'Invalid action. Use: approve, request_docs, reject.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        return Response(DoctorProfileSerializer(doctor).data)


class AdminDoctorProvisionAccountView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request, pk):
        try:
            doctor = DoctorProfile.objects.get(pk=pk)
        except DoctorProfile.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = ProvisionDoctorAccountSerializer(
            data=request.data,
            context={'doctor': doctor, 'request': request},
        )
        serializer.is_valid(raise_exception=True)
        doctor, user, _ = serializer.save()

        log_admin_action(
            request.user,
            'doctor_account_provisioned',
            'doctor_profile',
            doctor.id,
            f'Provisioned login account for {doctor.name}',
            metadata={'user_id': user.id, 'role': user.role},
        )

        response_data = {
            'detail': 'Professional account provisioned successfully.',
            'application': DoctorProfileSerializer(doctor).data,
            'user': UserSerializer(user).data,
            'activation_email': getattr(serializer, 'activation_email_meta', None),
        }
        try:
            from apps.notifications.utils import notify_doctor_verified
            notify_doctor_verified(doctor)
        except Exception:
            pass
        return Response(response_data, status=status.HTTP_201_CREATED)


class AdminPediatricianListView(generics.ListAPIView):
    permission_classes = [IsAdminUser]
    serializer_class = PediatricianProfileSerializer
    filterset_fields = ['status']
    search_fields = ['name', 'email', 'license_number']
    ordering = ['-submitted_at']
    queryset = PediatricianProfile.objects.all().prefetch_related('documents')


class AdminPediatricianDetailView(generics.RetrieveUpdateAPIView):
    permission_classes = [IsAdminUser]
    queryset = PediatricianProfile.objects.all()

    def get_serializer_class(self):
        if self.request.method in ['PUT', 'PATCH']:
            return AdminPediatricianUpdateSerializer
        return PediatricianProfileSerializer

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', True)
        instance = self.get_object()
        was_pending = instance.status == PediatricianProfile.STATUS_PENDING
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)

        if request.data.get('status') == PediatricianProfile.STATUS_ACTIVE and not instance.verified_at:
            instance.verified_at = timezone.now()
            instance.save(update_fields=['verified_at'])

        pediatrician = serializer.save(updated_by=request.user)

        if was_pending and pediatrician.status == PediatricianProfile.STATUS_ACTIVE and pediatrician.user:
            try:
                from apps.notifications.utils import notify_doctor_verified
                notify_doctor_verified(pediatrician)
            except Exception:
                pass

        return Response(PediatricianProfileSerializer(pediatrician).data)


class AdminPediatricianActionView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request, pk):
        try:
            pediatrician = PediatricianProfile.objects.get(pk=pk)
        except PediatricianProfile.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

        action = request.data.get('action')

        if action == 'approve':
            pediatrician.status = PediatricianProfile.STATUS_ACTIVE
            pediatrician.verified_at = timezone.now()
            pediatrician.status_note = ''
            pediatrician.updated_by = request.user
            pediatrician.save(update_fields=['status', 'verified_at', 'status_note', 'updated_by', 'updated_at'])
            log_admin_action(request.user, 'pediatrician_approved', 'pediatrician_profile', pediatrician.id,
                             f'Approved {pediatrician.name}')
        elif action == 'request_docs':
            note = request.data.get('note', '')
            pediatrician.status_note = note
            pediatrician.updated_by = request.user
            pediatrician.save(update_fields=['status_note', 'updated_by', 'updated_at'])
            log_admin_action(request.user, 'pediatrician_docs_requested', 'pediatrician_profile', pediatrician.id,
                             f'Requested documents from {pediatrician.name}')
        elif action == 'reject':
            note = (request.data.get('note') or '').strip()
            if not note:
                return Response({'note': 'Rejection reason is required.'}, status=status.HTTP_400_BAD_REQUEST)
            pediatrician.status = PediatricianProfile.STATUS_SUSPENDED
            pediatrician.rejection_note = note
            pediatrician.updated_by = request.user
            pediatrician.save(update_fields=['status', 'rejection_note', 'updated_by', 'updated_at'])
            log_admin_action(request.user, 'pediatrician_rejected', 'pediatrician_profile', pediatrician.id,
                             f'Rejected {pediatrician.name}')
        else:
            return Response(
                {'detail': 'Invalid action. Use: approve, request_docs, reject.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        return Response(PediatricianProfileSerializer(pediatrician).data)


class AdminPediatricianProvisionAccountView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request, pk):
        try:
            pediatrician = PediatricianProfile.objects.get(pk=pk)
        except PediatricianProfile.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = ProvisionPediatricianAccountSerializer(
            data=request.data,
            context={'pediatrician': pediatrician, 'request': request},
        )
        serializer.is_valid(raise_exception=True)
        pediatrician, user, _ = serializer.save()

        log_admin_action(
            request.user,
            'pediatrician_account_provisioned',
            'pediatrician_profile',
            pediatrician.id,
            f'Provisioned login account for {pediatrician.name}',
            metadata={'user_id': user.id, 'role': user.role},
        )

        response_data = {
            'detail': 'Professional account provisioned successfully.',
            'application': PediatricianProfileSerializer(pediatrician).data,
            'user': UserSerializer(user).data,
            'activation_email': getattr(serializer, 'activation_email_meta', None),
        }
        try:
            from apps.notifications.utils import notify_doctor_verified
            notify_doctor_verified(pediatrician)
        except Exception:
            pass
        return Response(response_data, status=status.HTTP_201_CREATED)


# ─── Admin Dashboard ──────────────────────────────────────────────────────────

class AdminDashboardView(APIView):
    """Aggregated stats for the /admin frontend route."""
    permission_classes = [IsAdminUser]

    def get(self, request):
        from apps.accounts.models import User
        from apps.orders.models import Order
        from apps.prescriptions.models import Prescription
        from apps.lab.models import LabRequest
        from apps.support.models import SupportTicket

        today = timezone.now().date()
        month_start = today.replace(day=1)

        users_by_role = list(User.objects.values('role').annotate(count=Count('id')))
        orders_by_status = list(Order.objects.values('status').annotate(count=Count('id')))
        revenue_data = Order.objects.filter(payment_status='paid').aggregate(
            revenue_total=Sum('total'), revenue_monthly=Sum('total', filter=Q(created_at__date__gte=month_start))
        )

        return Response({
            'users': {
                'total': User.objects.count(),
                'active': User.objects.filter(status='active').count(),
                'suspended': User.objects.filter(status='suspended').count(),
                'by_role': users_by_role,
                'new_today': User.objects.filter(date_joined__date=today).count(),
            },
            'orders': {
                'total': Order.objects.count(),
                'pending': Order.objects.filter(status='pending').count(),
                'today': Order.objects.filter(created_at__date=today).count(),
                'total_revenue': float(revenue_data['revenue_total'] or 0),
                'monthly_revenue': float(revenue_data['revenue_monthly'] or 0),
                'by_status': orders_by_status,
            },
            'prescriptions': {
                'total': Prescription.objects.count(),
                'pending': Prescription.objects.filter(status='pending').count(),
                'approved_today': Prescription.objects.filter(
                    status='approved', updated_at__date=today
                ).count(),
            },
            'lab': {
                'total_requests': LabRequest.objects.count(),
                'pending': LabRequest.objects.filter(
                    status__in=['awaiting_sample', 'sample_collected', 'processing']
                ).count(),
                'results_ready': LabRequest.objects.filter(status='result_ready').count(),
            },
            'support': {
                'open': SupportTicket.objects.filter(status='open').count(),
                'in_progress': SupportTicket.objects.filter(status='in_progress').count(),
                'high_priority': SupportTicket.objects.filter(
                    priority='high', status__in=['open', 'in_progress']
                ).count(),
            },
            'consultations': {
                'total': Consultation.objects.count(),
                'waiting': Consultation.objects.filter(status='waiting').count(),
                'in_progress': Consultation.objects.filter(status='in_progress').count(),
                'pending_doctor_verification': DoctorProfile.objects.filter(status='pending').count(),
                'pending_pediatrician_verification': PediatricianProfile.objects.filter(status='pending').count(),
            },
        })
