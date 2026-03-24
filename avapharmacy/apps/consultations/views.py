import hashlib
from io import BytesIO

from django.http import Http404, HttpResponse
from rest_framework import generics, permissions, status
from rest_framework.pagination import CursorPagination
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.throttling import UserRateThrottle
from django.db import transaction
from django.utils import timezone
from django.db.models import Sum, Count, Q
from django.db.models.functions import TruncDate
from datetime import timedelta

from .models import (
    ClinicianDocument, ClinicianProfile, ClinicianPrescription, ClinicianEarning,
    Consultation, ConsultationMessage,
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
    DoctorOnboardingAvailabilityStepSerializer,
    DoctorOnboardingPayoutStepSerializer,
    DoctorOnboardingProfileStepSerializer,
    DoctorVerificationActionSerializer,
)
from apps.accounts.permissions import IsAdminUser, IsDoctor, IsDoctorOrAdmin
from apps.accounts.utils import log_admin_action
from apps.accounts.serializers import (
    ProvisionDoctorAccountSerializer, ProvisionPediatricianAccountSerializer, UserSerializer,
)
from apps.notifications.utils import create_notification, notify_doctor_verified


CONSULTATION_SELECT_RELATED = (
    'patient',
    'clinician',
    'clinician__user',
)


def _get_clinician_for_user(user, provider_type=None):
    queryset = ClinicianProfile.objects.filter(user=user)
    if provider_type:
        queryset = queryset.filter(provider_type=provider_type)
    return queryset.first()


def _get_doctor_or_404(user):
    return _get_clinician_for_user(user, ClinicianProfile.TYPE_DOCTOR)


def _get_pediatrician_or_404(user):
    return _get_clinician_for_user(user, ClinicianProfile.TYPE_PEDIATRICIAN)


def _get_provider_for_user(user):
    if getattr(user, 'role', None) == 'pediatrician':
        return _get_pediatrician_or_404(user)
    return _get_doctor_or_404(user)


def _get_or_create_onboarding_profile(user):
    profile, _ = ClinicianProfile.objects.get_or_create(
        user=user,
        defaults={
            'provider_type': ClinicianProfile.TYPE_DOCTOR,
            'name': user.full_name or user.email,
            'email': user.email,
            'phone': user.phone,
            'specialty': '',
            'license_number': '',
            'status': ClinicianProfile.STATUS_PENDING,
        },
    )
    return profile


def _update_availability_summary(profile):
    slots = profile.availability_schedule or []
    if not slots:
        profile.availability = ''
        return
    first = slots[0]
    profile.availability = f"{first.get('day', '')} {first.get('start_time', '')}-{first.get('end_time', '')}".strip()


def _is_controlled_substance_item(item):
    text = ' '.join(
        str(item.get(key, '') or '').lower()
        for key in ('drug_name', 'name', 'dose', 'notes', 'frequency')
    )
    return any(keyword in text for keyword in {
        'morphine', 'codeine', 'diazepam', 'alprazolam', 'tramadol',
        'ketamine', 'fentanyl', 'pethidine', 'methadone', 'clonazepam',
    })


class ConsultationMessageCursorPagination(CursorPagination):
    page_size = 20
    ordering = '-sent_at'


def _broadcast_consultation_event(consultation_id, event_type, payload):
    try:
        from asgiref.sync import async_to_sync
        from channels.layers import get_channel_layer
    except Exception:
        return
    channel_layer = get_channel_layer()
    if not channel_layer:
        return
    async_to_sync(channel_layer.group_send)(
        f'consultation_{consultation_id}',
        {
            'type': 'consultation.event',
            'event_type': event_type,
            'payload': payload,
        },
    )


def _get_clinician_by_identifier(identifier, provider_type):
    queryset = ClinicianProfile.objects.filter(provider_type=provider_type)
    legacy_field = 'legacy_doctor_id' if provider_type == ClinicianProfile.TYPE_DOCTOR else 'legacy_pediatrician_id'
    return queryset.filter(pk=identifier).first() or queryset.filter(**{legacy_field: identifier}).first()


# ─── Public ───────────────────────────────────────────────────────────────────

class DoctorListView(generics.ListAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = DoctorProfileListSerializer
    filterset_fields = ['specialty']
    search_fields = ['name', 'specialty', 'facility']

    def get_queryset(self):
        return ClinicianProfile.objects.doctors().filter(status=ClinicianProfile.STATUS_ACTIVE).select_related('user')


class PediatricianListView(generics.ListAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = PediatricianProfileListSerializer
    filterset_fields = ['specialty']
    search_fields = ['name', 'specialty', 'facility']

    def get_queryset(self):
        return ClinicianProfile.objects.pediatricians().filter(status=ClinicianProfile.STATUS_ACTIVE).select_related('user')


class DoctorDetailView(generics.RetrieveAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = DoctorProfileSerializer
    queryset = ClinicianProfile.objects.doctors().select_related('user').prefetch_related('documents')

    def get_object(self):
        clinician = _get_clinician_by_identifier(self.kwargs['pk'], ClinicianProfile.TYPE_DOCTOR)
        if not clinician:
            from django.http import Http404
            raise Http404
        return clinician


class PediatricianDetailView(generics.RetrieveAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = PediatricianProfileSerializer
    queryset = ClinicianProfile.objects.pediatricians().select_related('user').prefetch_related('documents')

    def get_object(self):
        clinician = _get_clinician_by_identifier(self.kwargs['pk'], ClinicianProfile.TYPE_PEDIATRICIAN)
        if not clinician:
            from django.http import Http404
            raise Http404
        return clinician


# ─── Doctor / Pediatrician Onboarding ─────────────────────────────────────────

class DoctorOnboardingView(APIView):
    permission_classes = [permissions.AllowAny]
    parser_classes = [JSONParser, MultiPartParser, FormParser]
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


class DoctorOnboardingProfileStepView(APIView):
    permission_classes = [IsDoctor]

    def patch(self, request):
        profile = _get_or_create_onboarding_profile(request.user)
        serializer = DoctorOnboardingProfileStepSerializer(profile, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save(email=request.user.email or profile.email, updated_by=request.user)
        if 'phone' in serializer.validated_data and request.user.phone != serializer.validated_data['phone']:
            request.user.phone = serializer.validated_data['phone']
            request.user.save(update_fields=['phone', 'updated_at'])
        return Response(DoctorProfileSerializer(profile).data)


class DoctorOnboardingDocumentsStepView(APIView):
    permission_classes = [IsDoctor]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        profile = _get_or_create_onboarding_profile(request.user)
        medical_license_number = (request.data.get('medical_license_number') or '').strip()
        specialty = (request.data.get('specialty') or '').strip()
        years_of_experience = request.data.get('years_of_experience')
        if medical_license_number:
            profile.license_number = medical_license_number
        if specialty:
            profile.specialty = specialty
        if years_of_experience not in (None, ''):
            profile.years_experience = int(years_of_experience)
        profile.updated_by = request.user
        profile.save(update_fields=['license_number', 'specialty', 'years_experience', 'updated_by', 'updated_at'])

        files = request.FILES.getlist('documents') or request.FILES.getlist('files')
        document_names = request.data.getlist('document_names') or []
        created = []
        for index, file_obj in enumerate(files):
            document = ClinicianDocument.objects.create(
                clinician=profile,
                name=document_names[index] if index < len(document_names) else file_obj.name,
                file=file_obj,
            )
            created.append(document.id)
        return Response({'created_document_ids': created, 'profile': DoctorProfileSerializer(profile).data}, status=status.HTTP_201_CREATED)


class DoctorOnboardingAvailabilityStepView(APIView):
    permission_classes = [IsDoctor]

    def patch(self, request):
        profile = _get_or_create_onboarding_profile(request.user)
        serializer = DoctorOnboardingAvailabilityStepSerializer(profile, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save(updated_by=request.user)
        _update_availability_summary(profile)
        profile.save(update_fields=['availability', 'updated_at'])
        return Response(DoctorProfileSerializer(profile).data)


class DoctorOnboardingPayoutStepView(APIView):
    permission_classes = [IsDoctor]

    def patch(self, request):
        profile = _get_or_create_onboarding_profile(request.user)
        serializer = DoctorOnboardingPayoutStepSerializer(profile, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        payout_account_number = serializer.validated_data['payout_account_number']
        serializer.save(
            payout_account=payout_account_number[-4:],
            updated_by=request.user,
        )
        return Response(DoctorProfileSerializer(profile).data)


# ─── Doctor Dashboard ─────────────────────────────────────────────────────────

class DoctorDashboardView(APIView):
    permission_classes = [IsDoctor]

    def get(self, request):
        doctor = _get_doctor_or_404(request.user)
        if not doctor:
            return Response({'detail': 'Doctor profile not found.'}, status=status.HTTP_404_NOT_FOUND)

        today = timezone.now().date()
        month_start = today.replace(day=1)
        qs = Consultation.objects.filter(clinician=doctor).select_related(*CONSULTATION_SELECT_RELATED)

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

        earnings = ClinicianEarning.objects.filter(clinician=doctor)
        stats['monthly_earnings'] = float(
            earnings.filter(earned_at__date__gte=month_start).aggregate(t=Sum('amount'))['t'] or 0
        )
        stats['total_earnings'] = float(
            earnings.aggregate(t=Sum('amount'))['t'] or 0
        )

        recent = ConsultationListSerializer(
            qs.order_by('-created_at')[:5], many=True
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

        qs = Consultation.objects.filter(clinician=pediatrician, is_pediatric=True).select_related(*CONSULTATION_SELECT_RELATED)

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
                    ClinicianEarning.objects.filter(
                        clinician=pediatrician, earned_at__date__gte=month_start
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
        return Consultation.objects.filter(patient=self.request.user).select_related(*CONSULTATION_SELECT_RELATED)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        consultation = serializer.save(
            patient=request.user,
            patient_name=request.user.full_name,
            patient_email=request.user.email,
            patient_phone=request.user.phone,
        )

        # Notify doctor of new consultation
        provider = consultation.provider_profile
        provider_user = None
        if provider and provider.user:
            provider_user = provider.user
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
            return Consultation.objects.all().select_related(*CONSULTATION_SELECT_RELATED).prefetch_related('messages')
        return Consultation.objects.filter(patient=user).select_related(*CONSULTATION_SELECT_RELATED).prefetch_related('messages')

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
    parser_classes = [JSONParser, MultiPartParser, FormParser]
    pagination_class = ConsultationMessageCursorPagination

    def get_queryset(self):
        consultation = Consultation.objects.select_related('clinician', 'patient').filter(pk=self.kwargs['pk']).first()
        if consultation is None:
            return ConsultationMessage.objects.none()
        user = self.request.user
        provider = consultation.provider_profile
        is_provider = bool(provider and provider.user_id == user.id)
        if consultation.patient_id != user.id and not is_provider and user.role != 'admin':
            return ConsultationMessage.objects.none()
        return ConsultationMessage.objects.filter(consultation_id=self.kwargs['pk']).select_related('sender')

    def perform_create(self, serializer):
        try:
            consultation = Consultation.objects.get(pk=self.kwargs['pk'])
        except Consultation.DoesNotExist:
            from rest_framework.exceptions import NotFound
            raise NotFound('Consultation not found.')

        # Validate the user is a participant
        user = self.request.user
        provider = consultation.provider_profile
        is_doctor = bool(provider and provider.provider_type == ClinicianProfile.TYPE_DOCTOR and provider.user == user)
        is_pediatrician = bool(provider and provider.provider_type == ClinicianProfile.TYPE_PEDIATRICIAN and provider.user == user)
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
            if is_patient and provider and provider.user:
                create_notification(
                    recipient=provider.user,
                    notification_type='consultation_message',
                    title=f'New message from {user.full_name}',
                    message=f'New message in consultation {consultation.reference}',
                    data={'reference': consultation.reference, 'consultation_id': consultation.id},
                )
            elif (is_doctor or is_pediatrician) and consultation.patient:
                create_notification(
                    recipient=consultation.patient,
                    notification_type='consultation_message',
                    title=f'New message from {user.full_name}',
                    message=f'New message in consultation {consultation.reference}',
                    data={'reference': consultation.reference, 'consultation_id': consultation.id},
                )
        except Exception:
            pass
        _broadcast_consultation_event(
            consultation.id,
            'message.new',
            ConsultationMessageSerializer(msg).data,
        )


# ─── Doctor-Specific Views ────────────────────────────────────────────────────

class DoctorConsultationListView(generics.ListAPIView):
    serializer_class = ConsultationListSerializer
    permission_classes = [IsDoctor]
    filterset_fields = ['status', 'priority', 'is_pediatric']

    def get_queryset(self):
        provider = _get_provider_for_user(self.request.user)
        if not provider:
            return Consultation.objects.none()
        filter_kwargs = {'clinician': provider}
        return Consultation.objects.filter(**filter_kwargs).select_related(*CONSULTATION_SELECT_RELATED)


class ConsultationEndView(APIView):
    permission_classes = [IsDoctor]

    def post(self, request, pk):
        try:
            consultation = Consultation.objects.select_related('clinician', 'patient').get(pk=pk)
        except Consultation.DoesNotExist:
            return Response({'detail': 'Consultation not found.'}, status=status.HTTP_404_NOT_FOUND)

        provider = _get_provider_for_user(request.user)
        if not provider or consultation.clinician_id != provider.id:
            return Response({'detail': 'You are not assigned to this consultation.'}, status=status.HTTP_403_FORBIDDEN)

        if consultation.status == Consultation.STATUS_COMPLETED:
            return Response({'detail': 'Consultation already completed.'})

        consultation.status = Consultation.STATUS_COMPLETED
        consultation.ended_at = timezone.now()
        consultation.save(update_fields=['status', 'ended_at', 'updated_at'])

        ClinicianEarning.objects.get_or_create(
            clinician=provider,
            consultation=consultation,
            defaults={
                'amount': provider.consult_fee,
                'description': f'Consultation fee for {consultation.reference}',
            },
        )
        if consultation.patient:
            create_notification(
                recipient=consultation.patient,
                notification_type='consultation_status',
                title='Consultation completed',
                message=f'Consultation {consultation.reference} has been completed.',
                data={'consultation_id': consultation.id, 'reference': consultation.reference},
            )
        _broadcast_consultation_event(
            consultation.id,
            'consultation.status_changed',
            {'status': consultation.status, 'ended_at': consultation.ended_at.isoformat()},
        )
        return Response(ConsultationSerializer(consultation).data)


class ClinicianPrescriptionListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsDoctor]

    def get_serializer_class(self):
        if self.request.user.role == 'pediatrician':
            return PediatricianPrescriptionSerializer
        return DoctorPrescriptionSerializer

    def get_queryset(self):
        provider = _get_provider_for_user(self.request.user)
        if not provider:
            return ClinicianPrescription.objects.none()
        if self.request.user.role == 'pediatrician':
            return ClinicianPrescription.objects.filter(clinician=provider).select_related('consultation')
        return ClinicianPrescription.objects.filter(clinician=provider).select_related('consultation')

    def perform_create(self, serializer):
        provider = _get_provider_for_user(self.request.user)
        if not provider:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('No clinician profile found.')
        consultation = serializer.validated_data.get('consultation')
        patient_name = serializer.validated_data.get('patient_name')
        if consultation and not patient_name:
            patient_name = consultation.patient_name
        serializer.save(clinician=provider, patient_name=patient_name or '')


class ClinicianPrescriptionSendView(APIView):
    permission_classes = [IsDoctor]

    @transaction.atomic
    def post(self, request, pk):
        provider = _get_provider_for_user(request.user)
        if not provider:
            return Response({'detail': 'No clinician profile found.'}, status=status.HTTP_403_FORBIDDEN)

        try:
            prescription = ClinicianPrescription.objects.select_for_update().select_related(
                'consultation', 'consultation__patient'
            ).get(pk=pk, clinician=provider)
        except ClinicianPrescription.DoesNotExist:
            return Response({'detail': 'Prescription not found.'}, status=status.HTTP_404_NOT_FOUND)

        patient = prescription.consultation.patient if prescription.consultation else None
        if not patient:
            return Response({'detail': 'Prescription must be linked to a consultation with a patient.'}, status=status.HTTP_400_BAD_REQUEST)
        if not prescription.items:
            return Response({'detail': 'Prescription must contain at least one item.'}, status=status.HTTP_400_BAD_REQUEST)

        from apps.prescriptions.models import Prescription as DispensingPrescription, PrescriptionItem as DispensingPrescriptionItem

        linked = getattr(prescription, 'linked_prescriptions', None)
        existing = linked.order_by('-created_at').first() if linked is not None else None
        if existing is None:
            existing = DispensingPrescription.objects.create(
                patient=patient,
                patient_name=patient.full_name,
                doctor_name=provider.name,
                source=DispensingPrescription.SOURCE_E_PRESCRIPTION,
                clinician_prescription=prescription,
                status=DispensingPrescription.STATUS_APPROVED,
                notes=prescription.notes,
            )
        else:
            existing.status = DispensingPrescription.STATUS_APPROVED
            existing.notes = prescription.notes
            existing.doctor_name = provider.name
            existing.save(update_fields=['status', 'notes', 'doctor_name', 'updated_at'])
            existing.items.all().delete()

        for item in prescription.items:
            DispensingPrescriptionItem.objects.create(
                prescription=existing,
                name=item.get('drug_name') or item.get('name') or 'Medication',
                dose=item.get('dose', ''),
                frequency=item.get('frequency', ''),
                quantity=item.get('quantity') or 1,
                is_controlled_substance=_is_controlled_substance_item(item),
            )

        signature_material = f'{provider.license_number}:{timezone.now().isoformat()}'
        prescription.digital_signature = hashlib.sha256(signature_material.encode('utf-8')).hexdigest()
        prescription.status = ClinicianPrescription.STATUS_SENT
        prescription.sent_at = timezone.now()
        prescription.save(update_fields=['digital_signature', 'status', 'sent_at', 'updated_at'])

        create_notification(
            recipient=patient,
            notification_type='prescription_status',
            title='New e-prescription',
            message=f'Your clinician sent prescription {prescription.reference}.',
            data={'prescription_id': existing.id, 'reference': existing.reference},
            send_email=True,
        )
        return Response(self._serialize_response(prescription, request.user))

    @staticmethod
    def _serialize_response(prescription, user):
        serializer_class = PediatricianPrescriptionSerializer if user.role == 'pediatrician' else DoctorPrescriptionSerializer
        return serializer_class(prescription).data


class ClinicianPrescriptionPDFView(APIView):
    permission_classes = [IsDoctor]

    def get(self, request, pk):
        provider = _get_provider_for_user(request.user)
        if not provider:
            return Response({'detail': 'No clinician profile found.'}, status=status.HTTP_403_FORBIDDEN)
        try:
            prescription = ClinicianPrescription.objects.select_related('consultation').get(pk=pk, clinician=provider)
        except ClinicianPrescription.DoesNotExist:
            return Response({'detail': 'Prescription not found.'}, status=status.HTTP_404_NOT_FOUND)

        try:  # pragma: no cover - optional dependency in local dev
            from reportlab.lib.pagesizes import A4
            from reportlab.pdfgen import canvas
        except ImportError:
            return Response({'detail': 'PDF generation dependency is not installed.'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        buffer = BytesIO()
        pdf = canvas.Canvas(buffer, pagesize=A4)
        pdf.setTitle(f'{prescription.reference}.pdf')
        y = 800
        rows = [
            'AvaPharma Clinic',
            f'Prescription: {prescription.reference}',
            f'Clinician: {provider.name} ({provider.license_number})',
            f'Patient: {prescription.patient_name}',
            f'Status: {prescription.get_status_display()}',
            '',
        ]
        for row in rows:
            pdf.drawString(40, y, row)
            y -= 22
        for item in prescription.items:
            text = f"- {item.get('drug_name') or item.get('name')} | {item.get('dose', '')} | {item.get('frequency', '')} | {item.get('duration', '')}"
            pdf.drawString(40, y, text[:110])
            y -= 18
            if item.get('notes'):
                pdf.drawString(55, y, f"Notes: {item['notes']}"[:105])
                y -= 18
        y -= 8
        pdf.drawString(40, y, f'Digital signature: {prescription.digital_signature or "Pending"}')
        pdf.showPage()
        pdf.save()
        buffer.seek(0)

        response = HttpResponse(buffer.read(), content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{prescription.reference}.pdf"'
        return response


class ClinicianEarningsView(generics.ListAPIView):
    permission_classes = [IsDoctor]

    def get_serializer_class(self):
        if self.request.user.role == 'pediatrician':
            return PediatricianEarningSerializer
        return DoctorEarningSerializer

    def get_queryset(self):
        provider = _get_provider_for_user(self.request.user)
        if not provider:
            return ClinicianEarning.objects.none()
        return ClinicianEarning.objects.filter(clinician=provider).select_related('consultation')


# ─── Admin Doctor Management ──────────────────────────────────────────────────

class AdminDoctorListView(generics.ListAPIView):
    permission_classes = [IsAdminUser]
    serializer_class = DoctorProfileSerializer
    filterset_fields = ['status']
    search_fields = ['name', 'email', 'license_number']
    ordering = ['-submitted_at']
    queryset = ClinicianProfile.objects.doctors().select_related('user', 'created_by', 'updated_by').prefetch_related('documents')


class AdminDoctorDetailView(generics.RetrieveUpdateAPIView):
    permission_classes = [IsAdminUser]
    queryset = ClinicianProfile.objects.doctors().select_related('user', 'created_by', 'updated_by').prefetch_related('documents')

    def get_serializer_class(self):
        if self.request.method in ['PUT', 'PATCH']:
            return AdminDoctorUpdateSerializer
        return DoctorProfileSerializer

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', True)
        instance = self.get_object()
        was_pending = instance.status == ClinicianProfile.STATUS_PENDING
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)

        if request.data.get('status') == ClinicianProfile.STATUS_ACTIVE and not instance.verified_at:
            instance.verified_at = timezone.now()
            instance.is_verified = True
            instance.save(update_fields=['verified_at', 'is_verified'])

        doctor = serializer.save(updated_by=request.user)

        # Notify doctor if newly verified
        if was_pending and doctor.status == ClinicianProfile.STATUS_ACTIVE and doctor.user:
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
            doctor = ClinicianProfile.objects.doctors().get(pk=pk)
        except ClinicianProfile.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

        action = request.data.get('action')

        if action == 'approve':
            doctor.status = ClinicianProfile.STATUS_ACTIVE
            doctor.is_verified = True
            doctor.verified_at = timezone.now()
            doctor.status_note = ''
            doctor.updated_by = request.user
            doctor.save(update_fields=['status', 'is_verified', 'verified_at', 'status_note', 'updated_by', 'updated_at'])
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
            doctor.status = ClinicianProfile.STATUS_SUSPENDED
            doctor.is_verified = False
            doctor.rejection_note = note
            doctor.updated_by = request.user
            doctor.save(update_fields=['status', 'is_verified', 'rejection_note', 'updated_by', 'updated_at'])
            log_admin_action(request.user, 'doctor_rejected', 'doctor_profile', doctor.id,
                             f'Rejected {doctor.name}')

        else:
            return Response(
                {'detail': 'Invalid action. Use: approve, request_docs, reject.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        return Response(DoctorProfileSerializer(doctor).data)


class AdminDoctorVerifyView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request, pk):
        try:
            doctor = ClinicianProfile.objects.doctors().select_related('user').get(pk=pk)
        except ClinicianProfile.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

        doctor.status = ClinicianProfile.STATUS_ACTIVE
        doctor.is_verified = True
        doctor.verified_at = timezone.now()
        doctor.suspension_reason = ''
        doctor.updated_by = request.user
        doctor.save(update_fields=['status', 'is_verified', 'verified_at', 'suspension_reason', 'updated_by', 'updated_at'])
        if doctor.user:
            doctor.user.status = doctor.user.STATUS_ACTIVE
            doctor.user.is_active = True
            doctor.user.save(update_fields=['status', 'is_active', 'updated_at'])
            notify_doctor_verified(doctor)
        return Response(DoctorProfileSerializer(doctor).data)


class AdminDoctorSuspendView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request, pk):
        try:
            doctor = ClinicianProfile.objects.doctors().select_related('user').get(pk=pk)
        except ClinicianProfile.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = DoctorVerificationActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        reason = serializer.validated_data.get('reason', '').strip()
        if not reason:
            return Response({'reason': 'Suspension reason is required.'}, status=status.HTTP_400_BAD_REQUEST)

        doctor.status = ClinicianProfile.STATUS_SUSPENDED
        doctor.is_verified = False
        doctor.suspension_reason = reason
        doctor.updated_by = request.user
        doctor.save(update_fields=['status', 'is_verified', 'suspension_reason', 'updated_by', 'updated_at'])
        if doctor.user:
            doctor.user.status = doctor.user.STATUS_SUSPENDED
            doctor.user.is_active = False
            doctor.user.save(update_fields=['status', 'is_active', 'updated_at'])
            create_notification(
                recipient=doctor.user,
                notification_type='doctor_verified',
                title='Doctor account suspended',
                message=reason,
                data={'doctor_id': doctor.id},
                send_email=True,
            )
        return Response(DoctorProfileSerializer(doctor).data)


class AdminDoctorProvisionAccountView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request, pk):
        try:
            doctor = ClinicianProfile.objects.doctors().get(pk=pk)
        except ClinicianProfile.DoesNotExist:
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
    queryset = ClinicianProfile.objects.pediatricians().select_related('user', 'created_by', 'updated_by').prefetch_related('documents')


class AdminPediatricianDetailView(generics.RetrieveUpdateAPIView):
    permission_classes = [IsAdminUser]
    queryset = ClinicianProfile.objects.pediatricians().select_related('user', 'created_by', 'updated_by').prefetch_related('documents')

    def get_serializer_class(self):
        if self.request.method in ['PUT', 'PATCH']:
            return AdminPediatricianUpdateSerializer
        return PediatricianProfileSerializer

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', True)
        instance = self.get_object()
        was_pending = instance.status == ClinicianProfile.STATUS_PENDING
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)

        if request.data.get('status') == ClinicianProfile.STATUS_ACTIVE and not instance.verified_at:
            instance.verified_at = timezone.now()
            instance.save(update_fields=['verified_at'])

        pediatrician = serializer.save(updated_by=request.user)

        if was_pending and pediatrician.status == ClinicianProfile.STATUS_ACTIVE and pediatrician.user:
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
            pediatrician = ClinicianProfile.objects.pediatricians().get(pk=pk)
        except ClinicianProfile.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

        action = request.data.get('action')

        if action == 'approve':
            pediatrician.status = ClinicianProfile.STATUS_ACTIVE
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
            pediatrician.status = ClinicianProfile.STATUS_SUSPENDED
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
            pediatrician = ClinicianProfile.objects.pediatricians().get(pk=pk)
        except ClinicianProfile.DoesNotExist:
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
        summary_start = today - timedelta(days=13)

        users_by_role = list(User.objects.values('role').annotate(count=Count('id')))
        orders_by_status = list(Order.objects.values('status').annotate(count=Count('id')))
        revenue_data = Order.objects.filter(payment_status='paid').aggregate(
            revenue_total=Sum('total'), revenue_monthly=Sum('total', filter=Q(created_at__date__gte=month_start))
        )

        daily_orders = list(
            Order.objects.exclude(status='draft')
            .filter(created_at__date__gte=summary_start)
            .annotate(day=TruncDate('created_at'))
            .values('day')
            .annotate(
                orders=Count('id'),
                revenue=Sum('total', filter=Q(payment_status='paid')),
            )
            .order_by('day')
        )

        new_customers_by_day = list(
            User.objects.filter(date_joined__date__gte=summary_start)
            .annotate(day=TruncDate('date_joined'))
            .values('day')
            .annotate(count=Count('id'))
            .order_by('day')
        )
        nc_map = {str(d['day']): d['count'] for d in new_customers_by_day}

        daily_summary = [
            {
                'date': str(d['day']),
                'orders': d['orders'],
                'revenue': float(d['revenue'] or 0),
                'new_customers': nc_map.get(str(d['day']), 0),
            }
            for d in daily_orders
        ]

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
                'pending_doctor_verification': ClinicianProfile.objects.doctors().filter(status='pending').count(),
                'pending_pediatrician_verification': ClinicianProfile.objects.pediatricians().filter(status='pending').count(),
            },
            'daily_summary': daily_summary,
        })
