from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, FormParser

from apps.orders.models import Cart, CartItem

from .models import Prescription, PrescriptionFile, PrescriptionAuditLog
from .serializers import (
    PrescriptionSerializer, PrescriptionUploadSerializer,
    PrescriptionUpdateSerializer, PrescriptionAuditCreateSerializer
)
from apps.accounts.permissions import IsAdminUser, IsPharmacistOrAdmin
from apps.orders.serializers import CartSerializer

ALLOWED_FILE_TYPES = ['image/jpeg', 'image/png', 'application/pdf']
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB


def _get_or_create_cart(user):
    cart, _ = Cart.objects.get_or_create(user=user)
    return cart


def _product_availability_error(product, requested_quantity):
    if not product.is_active:
        return f'{product.name} is no longer active.'
    if requested_quantity <= product.stock_quantity:
        return None
    if product.allow_backorder and requested_quantity <= product.available_quantity:
        return None
    if product.stock_quantity == 0 and not product.allow_backorder:
        return f'{product.name} is out of stock.'
    return f'{product.name} only has {product.available_quantity} unit(s) available.'


class PrescriptionListView(generics.ListAPIView):
    serializer_class = PrescriptionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Prescription.objects.filter(
            patient=self.request.user
        ).prefetch_related('files', 'items__product', 'audit_logs')


class PrescriptionUploadView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        serializer = PrescriptionUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        uploaded_files = data.get('files', [])
        if not uploaded_files:
            return Response({'files': 'At least one file is required.'}, status=status.HTTP_400_BAD_REQUEST)

        # Validate each file
        for f in uploaded_files:
            if f.size > MAX_FILE_SIZE:
                return Response(
                    {'files': f'File "{f.name}" exceeds 5 MB limit.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            if f.content_type not in ALLOWED_FILE_TYPES:
                return Response(
                    {'files': f'File "{f.name}" has unsupported type. Allowed: PDF, JPEG, PNG.'},
                    status=status.HTTP_400_BAD_REQUEST
                )

        prescription = Prescription.objects.create(
            patient=request.user,
            patient_name=data['patient_name'],
            doctor_name=data.get('doctor_name', ''),
            notes=data.get('notes', ''),
        )

        for f in uploaded_files:
            PrescriptionFile.objects.create(
                prescription=prescription,
                file=f,
                filename=f.name,
            )

        PrescriptionAuditLog.objects.create(
            prescription=prescription,
            action='Prescription submitted by patient',
            performed_by=request.user,
        )

        return Response(PrescriptionSerializer(prescription).data, status=status.HTTP_201_CREATED)


class PrescriptionDetailView(generics.RetrieveAPIView):
    serializer_class = PrescriptionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.role in ['pharmacist', 'admin']:
            return Prescription.objects.all().prefetch_related('files', 'items__product', 'audit_logs')
        return Prescription.objects.filter(patient=user).prefetch_related('files', 'items__product', 'audit_logs')


class PrescriptionUpdateView(generics.UpdateAPIView):
    serializer_class = PrescriptionUpdateSerializer
    permission_classes = [IsPharmacistOrAdmin]

    def get_queryset(self):
        return Prescription.objects.all()

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', True)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)

        prev_status = instance.status
        prescription = serializer.save(pharmacist=request.user)

        action = f"Status updated to '{prescription.get_status_display()}' by {request.user.full_name}"
        PrescriptionAuditLog.objects.create(
            prescription=prescription,
            action=action,
            performed_by=request.user,
        )

        # Notify patient when status changes
        if prescription.status != prev_status and prescription.patient:
            try:
                from apps.notifications.utils import notify_prescription_status
                notify_prescription_status(prescription)
            except Exception:
                pass

        return Response(PrescriptionSerializer(prescription).data)


class PrescriptionAuditView(APIView):
    permission_classes = [IsPharmacistOrAdmin]

    def post(self, request, pk):
        try:
            prescription = Prescription.objects.get(pk=pk)
        except Prescription.DoesNotExist:
            return Response({'detail': 'Prescription not found.'}, status=status.HTTP_404_NOT_FOUND)
        serializer = PrescriptionAuditCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        PrescriptionAuditLog.objects.create(
            prescription=prescription,
            action=serializer.validated_data['action'],
            performed_by=request.user,
        )
        return Response(PrescriptionSerializer(prescription).data)


class AdminPrescriptionListView(generics.ListAPIView):
    serializer_class = PrescriptionSerializer
    permission_classes = [IsPharmacistOrAdmin]
    filterset_fields = ['status', 'dispatch_status']
    search_fields = ['reference', 'patient_name', 'doctor_name']
    ordering = ['-submitted_at']

    def get_queryset(self):
        return Prescription.objects.all().select_related(
            'patient', 'pharmacist'
        ).prefetch_related('files', 'items__product', 'audit_logs')


class PrescriptionItemAddToCartView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk, item_pk):
        try:
            prescription = Prescription.objects.prefetch_related('items__product').get(
                pk=pk,
                patient=request.user,
                status=Prescription.STATUS_APPROVED,
            )
        except Prescription.DoesNotExist:
            return Response(
                {'detail': 'Approved prescription not found for this account.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        item = prescription.items.filter(pk=item_pk).select_related('product').first()
        if not item:
            return Response({'detail': 'Prescription item not found.'}, status=status.HTTP_404_NOT_FOUND)
        if not item.product or not item.product.is_active:
            return Response(
                {'detail': 'This prescription item has not been mapped to an active product yet.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            quantity = int(request.data.get('quantity', item.quantity or 1))
        except (TypeError, ValueError):
            return Response({'quantity': 'Invalid quantity.'}, status=status.HTTP_400_BAD_REQUEST)

        if quantity < 1:
            return Response({'quantity': 'Must be at least 1.'}, status=status.HTTP_400_BAD_REQUEST)

        cart = _get_or_create_cart(request.user)
        existing_item = CartItem.objects.filter(
            cart=cart,
            product=item.product,
            product_variant__isnull=True,
            prescription=prescription,
            prescription_item=item,
        ).first()
        requested_total = quantity + (existing_item.quantity if existing_item else 0)
        if requested_total > item.quantity:
            return Response(
                {
                    'detail': (
                        f'You can only request up to {item.quantity} unit(s) for '
                        f'{item.product.name} from this prescription.'
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        error = _product_availability_error(item.product, requested_total)
        if error:
            return Response({'detail': error}, status=status.HTTP_400_BAD_REQUEST)

        if existing_item:
            existing_item.quantity = requested_total
            existing_item.save(update_fields=['quantity'])
        else:
            CartItem.objects.create(
                cart=cart,
                product=item.product,
                quantity=quantity,
                prescription_reference=prescription.reference,
                prescription=prescription,
                prescription_item=item,
            )

        PrescriptionAuditLog.objects.create(
            prescription=prescription,
            action=f'Added {item.product.name} x{quantity} to cart from approved prescription',
            performed_by=request.user,
        )
        return Response(CartSerializer(cart).data, status=status.HTTP_201_CREATED)
