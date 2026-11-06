from django.db import transaction
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Notification, NotificationDelivery
from .serializers import NotificationDeliverySerializer, NotificationPreferenceSerializer, NotificationSerializer
from .utils import get_notification_preferences


class ActiveNotificationAccount(permissions.IsAuthenticated):
    def has_permission(self, request, view):
        return super().has_permission(request, view) and request.user.is_active and request.user.status == 'active'


class NotificationListView(generics.ListAPIView):
    serializer_class = NotificationSerializer
    permission_classes = [ActiveNotificationAccount]
    filterset_fields = ['is_read', 'type']
    search_fields = ['title', 'message']
    ordering = ['-created_at']

    def get_queryset(self):
        return Notification.objects.filter(recipient=self.request.user)


class NotificationDetailView(generics.RetrieveDestroyAPIView):
    serializer_class = NotificationSerializer
    permission_classes = [ActiveNotificationAccount]

    def get_queryset(self):
        return Notification.objects.filter(recipient=self.request.user)


class NotificationMarkReadView(APIView):
    permission_classes = [ActiveNotificationAccount]

    def post(self, request, pk):
        updated = Notification.objects.filter(pk=pk, recipient=request.user).update(is_read=True)
        if not updated:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        return Response({'detail': 'Marked as read.'})


class NotificationMarkAllReadView(APIView):
    permission_classes = [ActiveNotificationAccount]

    def post(self, request):
        Notification.objects.filter(recipient=request.user, is_read=False).update(is_read=True)
        return Response({'detail': 'All notifications marked as read.'})


class NotificationUnreadCountView(APIView):
    permission_classes = [ActiveNotificationAccount]

    def get(self, request):
        count = Notification.objects.filter(recipient=request.user, is_read=False).count()
        return Response({'unread_count': count})


class NotificationPreferenceView(APIView):
    permission_classes = [ActiveNotificationAccount]

    def get(self, request):
        preferences = get_notification_preferences(request.user)
        return Response(NotificationPreferenceSerializer(preferences).data)

    def patch(self, request):
        preferences = get_notification_preferences(request.user)
        serializer = NotificationPreferenceSerializer(preferences, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class NotificationDeliveryListView(generics.ListAPIView):
    serializer_class = NotificationDeliverySerializer
    permission_classes = [ActiveNotificationAccount]
    filterset_fields = ['channel', 'status']
    ordering = ['-created_at']

    def get_queryset(self):
        return NotificationDelivery.objects.filter(recipient=self.request.user)


class NotificationDeliveryRetryView(APIView):
    permission_classes = [ActiveNotificationAccount]

    @transaction.atomic
    def post(self, request, pk):
        from django.shortcuts import get_object_or_404
        from .utils import deliver_email, deliver_sms
        delivery = get_object_or_404(NotificationDelivery.objects.select_for_update(), pk=pk, recipient=request.user)
        if delivery.status != 'failed':
            return Response({'detail': 'Only failed deliveries can be retried.'}, status=409)
        if len((delivery.metadata or {}).get('attempts', [])) >= 3:
            return Response({'detail': 'Maximum delivery attempts reached. Contact support.'}, status=429)
        current_destination = request.user.email if delivery.channel == 'email' else request.user.phone
        if (delivery.destination or '').casefold() != (current_destination or '').casefold():
            return Response({'detail': 'The delivery destination has changed. Contact support instead of resending to an old address.'}, status=400)
        if not delivery.notification_id:
            return Response({'detail': 'The original notification is unavailable.'}, status=400)
        if not (delivery.metadata or {}).get('attempts'):
            delivery.metadata = {**(delivery.metadata or {}), 'attempts': [{'number': 1, 'status': 'failed', 'at': delivery.created_at.isoformat(), 'error': delivery.error_message}]}
        preferences = get_notification_preferences(request.user)
        allowed = preferences.email_enabled if delivery.channel == 'email' else preferences.sms_enabled if delivery.channel == 'sms' else False
        if delivery.notification and delivery.notification.type == 'order_status':
            allowed = allowed and (preferences.order_updates_email if delivery.channel == 'email' else preferences.order_updates_sms)
        if delivery.notification.type == 'marketing':
            allowed = allowed and preferences.marketing_enabled
        if not allowed:
            return Response({'detail': 'This channel is disabled in your preferences.'}, status=400)
        if delivery.channel == 'email':
            deliver_email(delivery.notification, delivery.destination, delivery.subject, delivery.message, delivery=delivery)
        else:
            deliver_sms(delivery.notification, delivery.destination, delivery.message, delivery=delivery)
        return Response(NotificationDeliverySerializer(delivery).data)
