from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import SupportTicket, SupportNote
from .serializers import (
    SupportTicketSerializer, SupportTicketCreateSerializer,
    SupportTicketUpdateSerializer, SupportNoteCreateSerializer
)
from apps.accounts.permissions import IsAdminUser


class SupportTicketListCreateView(generics.ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticated]

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
        return Response(SupportTicketSerializer(ticket).data, status=status.HTTP_201_CREATED)


class SupportTicketDetailView(generics.RetrieveUpdateAPIView):
    permission_classes = [permissions.IsAuthenticated]

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

        prev_status = self.get_object().status
        response = super().update(request, *args, **kwargs)

        # Notify customer if status changed
        ticket = self.get_object()
        if ticket.status != prev_status and ticket.customer:
            try:
                from apps.notifications.utils import notify_support_update
                notify_support_update(ticket)
            except Exception:
                pass

        return response


class SupportNoteCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

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
        SupportNote.objects.create(
            ticket=ticket,
            author=user,
            author_name=user.full_name,
            message=serializer.validated_data['message'],
        )

        # Notify customer if admin left a note
        if is_admin and ticket.customer:
            try:
                from apps.notifications.utils import create_notification
                create_notification(
                    recipient=ticket.customer,
                    notification_type='support_update',
                    title=f"New reply on ticket {ticket.reference}",
                    message="Support has replied to your ticket.",
                    data={'url': f'/support/tickets/{ticket.id}', 'reference': ticket.reference},
                )
            except Exception:
                pass

        return Response(SupportTicketSerializer(ticket).data)
