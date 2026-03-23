from rest_framework import generics, permissions, status
from rest_framework.response import Response

from .models import Payout, PayoutRule
from .serializers import PayoutSerializer, PayoutCreateSerializer, PayoutUpdateSerializer, PayoutRuleSerializer
from apps.accounts.permissions import IsAdminUser


class PayoutListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAdminUser]
    filterset_fields = ['status', 'role', 'method']
    search_fields = ['reference', 'recipient_name']
    ordering = ['-requested_at']

    def get_queryset(self):
        return Payout.objects.all().select_related('recipient', 'created_by')

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return PayoutCreateSerializer
        return PayoutSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payout = serializer.save(created_by=request.user)
        return Response(PayoutSerializer(payout).data, status=status.HTTP_201_CREATED)


class PayoutDetailView(generics.RetrieveUpdateAPIView):
    permission_classes = [IsAdminUser]
    queryset = Payout.objects.all()

    def get_serializer_class(self):
        if self.request.method in ['PUT', 'PATCH']:
            return PayoutUpdateSerializer
        return PayoutSerializer

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', True)
        instance = self.get_object()
        prev_status = instance.status
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        payout = serializer.save()

        # Notify recipient when payout status changes
        if payout.status != prev_status and payout.recipient:
            try:
                from apps.notifications.utils import notify_payout_status
                notify_payout_status(payout)
            except Exception:
                pass

        return Response(PayoutSerializer(payout).data)


class PayoutRuleListView(generics.ListAPIView):
    permission_classes = [IsAdminUser]
    serializer_class = PayoutRuleSerializer
    queryset = PayoutRule.objects.all()


class PayoutRuleDetailView(generics.RetrieveUpdateAPIView):
    permission_classes = [IsAdminUser]
    serializer_class = PayoutRuleSerializer
    queryset = PayoutRule.objects.all()
