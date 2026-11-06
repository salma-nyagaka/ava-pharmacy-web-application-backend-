from .compliance_audit import LockedUpdateMixin
from django.db import transaction
from django.http import FileResponse
from rest_framework.exceptions import PermissionDenied
from rest_framework.throttling import AnonRateThrottle
from django.utils import timezone
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import ComplianceEvidence, NewsletterSubscriber, SiteSettings, SupportTicket, SupportNote
from .serializers import (
    SiteSettingsSerializer,
    NewsletterSubscriptionRequestSerializer,
    NewsletterSubscriberSerializer,
    ComplianceEvidenceSerializer,
    SupportTicketSerializer, SupportTicketCreateSerializer,
    SupportTicketUpdateSerializer, SupportNoteCreateSerializer
)
from apps.accounts.permissions import IsAdminOrPPBInspector, IsAdminUser
from .utils import send_newsletter_subscription_email


class ActiveAccount(permissions.IsAuthenticated):
    def has_permission(self, request, view):
        return super().has_permission(request, view) and request.user.is_active and request.user.status == 'active'


class ActiveEvidenceAccess(IsAdminOrPPBInspector):
    def has_permission(self, request, view):
        return super().has_permission(request, view) and request.user.status == 'active'


class NewsletterThrottle(AnonRateThrottle):
    scope = 'newsletter'
    rate = '5/min'

    def get_cache_key(self, request, view):
        return self.cache_format % {'scope': self.scope, 'ident': self.get_ident(request)}


class SiteSettingsView(generics.RetrieveUpdateAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = SiteSettingsSerializer

    def get_object(self):
        return SiteSettings.get_solo()

    def update(self, request, *args, **kwargs):
        if not (IsAdminUser().has_permission(request, self) and request.user.is_active and request.user.status == 'active'):
            return Response({'detail': 'Only admins can update site settings.'}, status=status.HTTP_403_FORBIDDEN)
        return super().update(request, *args, **kwargs)


class NewsletterSubscribeView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [NewsletterThrottle]

    def post(self, request):
        serializer = NewsletterSubscriptionRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated = serializer.validated_data

        delivered = True
        with transaction.atomic():
            subscriber, created = NewsletterSubscriber.objects.get_or_create(
                email=validated['email'],
                defaults={
                    'source': validated.get('source', 'website'),
                    'is_active': True,
                },
            )

            subscriber = NewsletterSubscriber.objects.select_for_update().get(pk=subscriber.pk)
            update_fields = []
            next_source = validated.get('source', subscriber.source)
            if subscriber.source != next_source:
                subscriber.source = next_source
                update_fields.append('source')
            if not subscriber.is_active:
                subscriber.is_active = True
                subscriber.last_confirmation_sent_at = None
                update_fields.extend(['is_active', 'last_confirmation_sent_at'])

            should_send = created or not subscriber.last_confirmation_sent_at or 'is_active' in update_fields
            if update_fields:
                subscriber.save(update_fields=update_fields)

            if should_send:
                try:
                    if send_newsletter_subscription_email(subscriber.email) == 0:
                        raise RuntimeError('The email backend did not accept the confirmation.')
                    subscriber.last_confirmation_sent_at = timezone.now()
                    subscriber.save(update_fields=['last_confirmation_sent_at'])
                except Exception:
                    delivered = False

        response_serializer = NewsletterSubscriberSerializer(subscriber)
        return Response(
            {
                'subscriber': response_serializer.data,
                'message': ('You are subscribed. Check your inbox for confirmation.' if should_send and delivered else 'You are already subscribed.' if delivered else 'Your subscription is saved. Confirmation delivery is delayed; please try again later.'),
            },
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class ComplianceEvidenceListCreateView(generics.ListCreateAPIView):
    permission_classes = [ActiveEvidenceAccess]
    serializer_class = ComplianceEvidenceSerializer
    filterset_fields = ['evidence_type', 'status']
    search_fields = ['title', 'reference_number', 'issuing_authority', 'notes']
    ordering_fields = ['created_at', 'expires_at', 'evidence_type']
    ordering = ['evidence_type', 'expires_at', 'title']
    queryset = ComplianceEvidence.objects.all().select_related('created_by', 'updated_by')

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user, updated_by=self.request.user)


class ComplianceEvidenceDetailView(LockedUpdateMixin, generics.RetrieveUpdateAPIView):
    permission_classes = [ActiveEvidenceAccess]
    serializer_class = ComplianceEvidenceSerializer
    queryset = ComplianceEvidence.objects.all().select_related('created_by', 'updated_by')

    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user, verified_by=None, verified_at=None, verification_reference='')


class SupportTicketListCreateView(generics.ListCreateAPIView):
    permission_classes = [ActiveAccount]

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return SupportTicketCreateSerializer
        return SupportTicketSerializer

    def get_queryset(self):
        user = self.request.user
        if user.role == 'admin':
            return (
                SupportTicket.objects.all()
                .select_related('customer', 'assigned_to')
                .prefetch_related('notes')
            )
        return SupportTicket.objects.filter(customer=user).select_related('customer', 'assigned_to').prefetch_related('notes')

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ticket = serializer.save(
            customer=request.user,
            customer_name=request.user.full_name,
            customer_email=request.user.email,
        )
        return Response(SupportTicketSerializer(ticket, context={'request': request}).data, status=status.HTTP_201_CREATED)


class SupportTicketDetailView(generics.RetrieveUpdateAPIView):
    permission_classes = [ActiveAccount]

    def get_queryset(self):
        user = self.request.user
        if user.role == 'admin':
            return SupportTicket.objects.all().select_related('customer', 'assigned_to').prefetch_related('notes')
        return SupportTicket.objects.filter(customer=user).select_related('customer', 'assigned_to').prefetch_related('notes')

    def get_serializer_class(self):
        if self.request.method in ['PUT', 'PATCH']:
            return SupportTicketUpdateSerializer
        return SupportTicketSerializer

    def update(self, request, *args, **kwargs):
        if request.user.role != 'admin':
            return Response({'detail': 'Only admins can update tickets.'}, status=status.HTTP_403_FORBIDDEN)

        with transaction.atomic():
            ticket = self.get_object()
            ticket = SupportTicket.objects.select_for_update().get(pk=ticket.pk)
            previous = ticket.status
            serializer = self.get_serializer(ticket, data=request.data, partial=kwargs.get('partial', False))
            serializer.is_valid(raise_exception=True)
            ticket = serializer.save()
            if ticket.status != previous:
                SupportNote.objects.create(ticket=ticket, author=request.user, author_name=request.user.full_name, message=f'Status changed from {previous} to {ticket.status}.', is_internal=False)
                from apps.notifications.utils import notify_support_update
                transaction.on_commit(lambda: notify_support_update(ticket), robust=True)
            ticket._prefetched_objects_cache = {}
        return Response(SupportTicketSerializer(ticket, context={'request': request}).data)



class SupportNoteCreateView(APIView):
    permission_classes = [ActiveAccount]

    def post(self, request, pk):
        try:
            ticket = SupportTicket.objects.get(pk=pk)
        except SupportTicket.DoesNotExist:
            return Response({'detail': 'Ticket not found.'}, status=status.HTTP_404_NOT_FOUND)

        user = self.request.user
        is_admin = user.role == 'admin'
        is_owner = ticket.customer == user
        if not (is_admin or is_owner):
            return Response({'detail': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)

        serializer = SupportNoteCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if serializer.validated_data.get('is_internal') and not is_admin:
            raise PermissionDenied('Only support administrators can add internal notes.')
        SupportNote.objects.create(
            ticket=ticket,
            author=user,
            author_name=user.full_name,
            message=serializer.validated_data['message'],
            is_internal=serializer.validated_data['is_internal'],
        )

        if is_owner and not is_admin and ticket.status == SupportTicket.STATUS_RESOLVED:
            ticket.status = SupportTicket.STATUS_OPEN
            ticket.save(update_fields=['status', 'updated_at'])
            SupportNote.objects.create(ticket=ticket, author=user, author_name=user.full_name, message='Ticket reopened after customer reply.', is_internal=False)

        # Notify customer if admin left a note
        if is_admin and ticket.customer and not serializer.validated_data['is_internal']:
            try:
                from apps.notifications.utils import create_notification
                create_notification(
                    recipient=ticket.customer,
                    notification_type='support_update',
                    title=f"New reply on ticket {ticket.reference}",
                    message="Support has replied to your ticket.",
                    data={'url': f'/account/support?ticket={ticket.id}', 'reference': ticket.reference},
                )
            except Exception:
                pass

        return Response(SupportTicketSerializer(ticket, context={'request': request}).data)


class ComplianceEvidenceDownloadView(APIView):
    permission_classes = [ActiveEvidenceAccess]

    def get(self, request, pk):
        from django.shortcuts import get_object_or_404
        evidence = get_object_or_404(ComplianceEvidence, pk=pk)
        if not evidence.file:
            return Response({'detail': 'No document attached.'}, status=404)
        try:
            response = FileResponse(evidence.file.open('rb'), as_attachment=True, filename=evidence.file.name.rsplit('/', 1)[-1])
        except FileNotFoundError:
            return Response({'detail': 'The stored document is unavailable.'}, status=404)
        response['Cache-Control'] = 'private, no-store'
        response['X-Content-Type-Options'] = 'nosniff'
        return response
