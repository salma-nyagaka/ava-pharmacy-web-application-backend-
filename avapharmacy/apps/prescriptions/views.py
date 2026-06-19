import json

from django.db import models
from django.db import transaction
from django.utils import timezone
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, FormParser

from apps.orders.models import Cart, CartItem, Order, OrderItem
from apps.products.models import Variant

from .models import (
    Prescription,
    PrescriptionAuditLog,
    PrescriptionFile,
    PrescriptionItem,
    PrescriptionReviewDecision,
    PrescriptionClarificationMessage,
)
from .serializers import (
    PrescriptionSerializer, PrescriptionUploadSerializer,
    PrescriptionUpdateSerializer, PrescriptionAuditCreateSerializer,
    PharmacistPrescriptionReviewSerializer, PrescriptionResubmitSerializer,
    PrescriptionClarificationReplySerializer,
)
from apps.accounts.permissions import IsAdminUser, IsPharmacist, IsPharmacistOrAdmin, IsPrescriptionReviewPharmacist
from apps.accounts.models import User
from apps.notifications.utils import create_notification
from apps.orders.serializers import CartSerializer

ALLOWED_FILE_TYPES = ['image/jpeg', 'image/png', 'application/pdf']
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB
MAX_PRESCRIPTION_FILES = 5
CONTROLLED_SUBSTANCE_KEYWORDS = {
    'morphine', 'codeine', 'diazepam', 'alprazolam', 'tramadol', 'ketamine',
    'fentanyl', 'pethidine', 'methadone', 'clonazepam',
}


def _get_or_create_cart(user):
    cart, _ = Cart.objects.get_or_create(user=user)
    return cart


def _product_availability_error(product, requested_quantity):
    if not product.is_active:
        return f'{product.name} is no longer active.'

    if hasattr(product, '_get_inventory_values'):
        inventory = product._get_inventory_values()
        stock_quantity = inventory.get('stock_quantity', 0)
        allow_backorder = inventory.get('allow_backorder', False)
        available_quantity = product.available_quantity
    else:
        stock_quantity = product.stock_quantity
        allow_backorder = product.allow_backorder
        available_quantity = product.available_quantity

    if requested_quantity <= stock_quantity:
        return None
    if allow_backorder and requested_quantity <= available_quantity:
        return None
    if stock_quantity == 0 and not allow_backorder:
        return f'{product.name} is out of stock.'
    return f'{product.name} only has {available_quantity} unit(s) available.'


def _is_controlled_substance(*values):
    haystack = ' '.join(str(value or '').lower() for value in values)
    return any(keyword in haystack for keyword in CONTROLLED_SUBSTANCE_KEYWORDS)


def _replace_prescription_items(prescription, items_data):
    if items_data is None:
        return
    prescription.items.all().delete()
    for item_data in items_data:
        variant_id = item_data.get('variant_id')
        product_id = item_data.get('product_id')
        if variant_id and not product_id:
            product_id = Variant.objects.filter(pk=variant_id).values_list('product_id', flat=True).first()
        PrescriptionItem.objects.create(
            prescription=prescription,
            name=item_data['name'],
            product_id=product_id,
            variant_id=variant_id,
            dose=item_data.get('dose', ''),
            frequency=item_data.get('frequency', ''),
            quantity=item_data.get('quantity', 1),
            is_controlled_substance=_is_controlled_substance(
                item_data.get('name', ''),
                item_data.get('dose', ''),
                item_data.get('frequency', ''),
                prescription.notes,
            ),
        )


def _prescription_queryset():
    return Prescription.objects.select_related('patient', 'pharmacist').prefetch_related(
        'files',
        'items__product',
        'items__variant',
        'audit_logs',
        'review_decisions__pharmacist',
        'clarification_messages__sender',
    )


def _sender_role_for_user(user):
    if not user:
        return PrescriptionClarificationMessage.SENDER_SYSTEM
    if getattr(user, 'role', '') == User.PHARMACIST:
        return PrescriptionClarificationMessage.SENDER_PHARMACIST
    if getattr(user, 'role', '') == User.ADMIN:
        return PrescriptionClarificationMessage.SENDER_ADMIN
    return PrescriptionClarificationMessage.SENDER_PATIENT


def _sender_name_for_user(user):
    if not user:
        return ''
    return user.full_name or user.email


def _create_clarification_message(prescription, *, sender=None, message=''):
    if not (message or '').strip():
        return None
    return PrescriptionClarificationMessage.objects.create(
        prescription=prescription,
        sender=sender if getattr(sender, 'is_authenticated', False) else sender,
        sender_role=_sender_role_for_user(sender),
        sender_name=_sender_name_for_user(sender),
        message=message.strip(),
    )


class PrescriptionListView(generics.ListAPIView):
    serializer_class = PrescriptionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        queryset = _prescription_queryset().filter(patient=self.request.user)
        source_value = self.request.query_params.get('source')
        if source_value:
            queryset = queryset.filter(source=source_value)
        return queryset.order_by('-submitted_at', '-id')


class PrescriptionUploadView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    @transaction.atomic
    def post(self, request):
        serializer = PrescriptionUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        uploaded_files = data.get('files', [])
        if not uploaded_files:
            return Response({'files': 'At least one file is required.'}, status=status.HTTP_400_BAD_REQUEST)
        if len(uploaded_files) > MAX_PRESCRIPTION_FILES:
            return Response({'files': f'You can upload up to {MAX_PRESCRIPTION_FILES} files.'}, status=status.HTTP_400_BAD_REQUEST)

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
            source=Prescription.SOURCE_UPLOAD,
        )

        for f in uploaded_files:
            PrescriptionFile.objects.create(
                prescription=prescription,
                file=f,
                filename=f.name,
            )

        items_data = data.get('items')
        if not items_data:
            raw_items = request.data.get('items_json') or request.data.get('items')
            if isinstance(raw_items, str):
                try:
                    items_data = json.loads(raw_items)
                except json.JSONDecodeError:
                    items_data = None
        _replace_prescription_items(prescription, items_data)

        PrescriptionAuditLog.objects.create(
            prescription=prescription,
            action='Prescription submitted by patient',
            notes=data.get('notes', ''),
            performed_by=request.user,
        )
        requested_items = ', '.join(
            item.get('name', '').strip()
            for item in (items_data or [])
            if item.get('name', '').strip()
        )
        if requested_items:
            PrescriptionAuditLog.objects.create(
                prescription=prescription,
                action='Catalog item requested by patient',
                notes=requested_items,
                performed_by=request.user,
            )

        return Response(PrescriptionSerializer(prescription).data, status=status.HTTP_201_CREATED)


class PrescriptionDetailView(generics.RetrieveAPIView):
    serializer_class = PrescriptionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.role in ['pharmacist', 'admin']:
            return _prescription_queryset()
        return _prescription_queryset().filter(patient=user)


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
            notes=serializer.validated_data.get('notes', ''),
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
        return _prescription_queryset().order_by('-submitted_at', '-id')


class PharmacistVariantSearchView(APIView):
    permission_classes = [IsPharmacistOrAdmin]

    def get(self, request):
        query = str(request.query_params.get('q') or '').strip()
        try:
            limit = min(max(int(request.query_params.get('limit', 500)), 1), 500)
        except (TypeError, ValueError):
            limit = 500

        variants = Variant.objects.select_related(
            'product',
            'product__brand',
        ).prefetch_related('inventories').filter(
            is_active=True,
            product__is_active=True,
        )
        if query:
            variants = variants.filter(
                models.Q(product__name__icontains=query)
                | models.Q(name__icontains=query)
                | models.Q(sku__icontains=query)
                | models.Q(product__brand__name__icontains=query)
                | models.Q(strength__icontains=query)
            )

        return Response({
            'results': [
                {
                    'id': variant.id,
                    'product_id': variant.product_id,
                    'product_name': variant.product.name,
                    'variant_name': variant.name,
                    'display_name': f'{variant.product.name} {variant.name}'.strip(),
                    'brand_name': variant.product.brand.name if variant.product.brand else '',
                    'sku': variant.sku,
                    'price': str(variant.price),
                    'requires_prescription': variant.requires_prescription,
                    'inventory_status': variant.inventory_status,
                    'available_quantity': variant.available_quantity,
                    'can_select': variant.available_quantity > 0,
                }
                for variant in variants.order_by('product__name', 'sort_order', 'name')[:limit]
            ]
        })


class PrescriptionItemAddToCartView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk, item_pk):
        try:
            prescription = Prescription.objects.prefetch_related('items__product', 'items__variant').get(
                pk=pk,
                patient=request.user,
                status=Prescription.STATUS_APPROVED,
            )
        except Prescription.DoesNotExist:
            return Response(
                {'detail': 'Approved prescription not found for this account.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        item = prescription.items.filter(pk=item_pk).select_related('product', 'variant', 'variant__product').first()
        if not item:
            return Response({'detail': 'Prescription item not found.'}, status=status.HTTP_404_NOT_FOUND)
        if OrderItem.objects.filter(
            prescription=prescription,
            prescription_item=item,
            order__customer=request.user,
            order__payment_status=Order.PAYMENT_STATUS_PAID,
        ).exclude(order__status__in=[Order.STATUS_CANCELLED, Order.STATUS_REFUNDED]).exists():
            return Response(
                {'detail': 'This prescription item has already been paid for and cannot be added again.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not item.product or not item.product.is_active:
            return Response(
                {'detail': 'This prescription item has not been mapped to an active product yet.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if item.variant_id and (not item.variant.is_active or not item.variant.product.is_active):
            return Response(
                {'detail': 'The selected prescription variant is no longer active.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            quantity = int(request.data.get('quantity', item.quantity or 1))
        except (TypeError, ValueError):
            return Response({'quantity': 'Invalid quantity.'}, status=status.HTTP_400_BAD_REQUEST)

        if quantity < 1:
            return Response({'quantity': 'Must be at least 1.'}, status=status.HTTP_400_BAD_REQUEST)

        cart = _get_or_create_cart(request.user)
        variant = item.variant or item.product.get_representative_variant()
        if variant is None:
            return Response(
                {'detail': f'No active variant is available for {item.product.name}.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        existing_item = CartItem.objects.filter(
            cart=cart,
            variant=variant,
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

        error = _product_availability_error(variant, requested_total)
        if error:
            return Response({'detail': error}, status=status.HTTP_400_BAD_REQUEST)

        if existing_item:
            existing_item.quantity = requested_total
            existing_item.save(update_fields=['quantity'])
        else:
            CartItem.objects.create(
                cart=cart,
                variant=variant,
                quantity=quantity,
                prescription_reference=prescription.reference,
                prescription=prescription,
                prescription_item=item,
            )

        PrescriptionAuditLog.objects.create(
            prescription=prescription,
            action=f'Added {item.product.name} x{quantity} to cart from approved prescription',
            notes='Prescription item moved to cart.',
            performed_by=request.user,
        )
        return Response(CartSerializer(cart).data, status=status.HTTP_201_CREATED)


class PharmacistPrescriptionQueueView(generics.ListAPIView):
    serializer_class = PrescriptionSerializer
    permission_classes = [IsPrescriptionReviewPharmacist]

    def get_queryset(self):
        queryset = _prescription_queryset().filter(
            models.Q(pharmacist=self.request.user) | models.Q(pharmacist__isnull=True)
        )
        status_value = self.request.query_params.get('status')
        if status_value:
            queryset = queryset.filter(status=status_value)
        return queryset.order_by('pharmacist_id', '-submitted_at', '-id')


class PharmacistPrescriptionAssignView(APIView):
    permission_classes = [IsPrescriptionReviewPharmacist]

    @transaction.atomic
    def post(self, request, pk):
        try:
            prescription = Prescription.objects.select_for_update().get(pk=pk)
        except Prescription.DoesNotExist:
            return Response({'detail': 'Prescription not found.'}, status=status.HTTP_404_NOT_FOUND)

        if prescription.pharmacist_id and prescription.pharmacist_id != request.user.id:
            return Response({'detail': 'Prescription is already assigned to another pharmacist.'}, status=status.HTTP_400_BAD_REQUEST)

        prescription.pharmacist = request.user
        prescription.save(update_fields=['pharmacist', 'updated_at'])
        PrescriptionAuditLog.objects.create(
            prescription=prescription,
            action='Prescription assigned',
            notes=f'Assigned to {request.user.full_name}',
            performed_by=request.user,
        )
        return Response(PrescriptionSerializer(prescription).data)


class PharmacistPrescriptionReviewView(APIView):
    permission_classes = [IsPrescriptionReviewPharmacist]

    @transaction.atomic
    def post(self, request, pk):
        try:
            prescription = Prescription.objects.select_for_update().get(pk=pk)
        except Prescription.DoesNotExist:
            return Response({'detail': 'Prescription not found.'}, status=status.HTTP_404_NOT_FOUND)

        if prescription.pharmacist_id and prescription.pharmacist_id != request.user.id:
            return Response({'detail': 'Prescription is assigned to another pharmacist.'}, status=status.HTTP_400_BAD_REQUEST)

        serializer = PharmacistPrescriptionReviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        action = data['action']
        notes = data.get('notes', '').strip()
        items_data = data.get('items')
        previous_status = prescription.status

        prescription.pharmacist = request.user
        prescription.pharmacist_notes = notes

        if items_data is not None:
            _replace_prescription_items(prescription, items_data)

        if action == PharmacistPrescriptionReviewSerializer.ACTION_APPROVE:
            if not prescription.items.exists():
                return Response({'items': 'At least one prescription item is required for approval.'}, status=status.HTTP_400_BAD_REQUEST)
            unmapped = list(prescription.items.filter(product__isnull=True, variant__isnull=True).values_list('name', flat=True))
            if unmapped:
                return Response({'items': f'All approved items must be mapped to products. Missing: {", ".join(unmapped)}.'}, status=status.HTTP_400_BAD_REQUEST)
            prescription.status = Prescription.STATUS_APPROVED
            prescription.clarification_message = ''
        elif action == PharmacistPrescriptionReviewSerializer.ACTION_REJECT:
            prescription.status = Prescription.STATUS_REJECTED
            prescription.clarification_message = notes
        else:
            prescription.status = Prescription.STATUS_CLARIFICATION
            prescription.clarification_message = notes
            _create_clarification_message(prescription, sender=request.user, message=notes)

        prescription.save(update_fields=[
            'pharmacist', 'pharmacist_notes', 'status', 'clarification_message', 'updated_at',
        ])
        PrescriptionReviewDecision.objects.create(
            prescription=prescription,
            pharmacist=request.user,
            action=action,
            from_status=previous_status,
            to_status=prescription.status,
            notes=notes,
        )
        PrescriptionAuditLog.objects.create(
            prescription=prescription,
            action=f'Prescription review: {action}',
            notes=notes,
            performed_by=request.user,
        )
        return Response(PrescriptionSerializer(prescription).data)


class PrescriptionResubmitView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    @transaction.atomic
    def patch(self, request, pk):
        try:
            prescription = Prescription.objects.select_for_update().get(pk=pk, patient=request.user)
        except Prescription.DoesNotExist:
            return Response({'detail': 'Prescription not found.'}, status=status.HTTP_404_NOT_FOUND)

        if prescription.status != Prescription.STATUS_CLARIFICATION:
            return Response({'detail': 'Only prescriptions awaiting clarification can be resubmitted.'}, status=status.HTTP_400_BAD_REQUEST)

        serializer = PrescriptionResubmitSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        files = serializer.validated_data.get('files', [])
        if prescription.files.count() + len(files) > MAX_PRESCRIPTION_FILES:
            return Response({'files': f'You can keep at most {MAX_PRESCRIPTION_FILES} files on a prescription.'}, status=status.HTTP_400_BAD_REQUEST)

        for f in files:
            if f.size > MAX_FILE_SIZE:
                return Response({'files': f'File "{f.name}" exceeds 5 MB limit.'}, status=status.HTTP_400_BAD_REQUEST)
            if f.content_type not in ALLOWED_FILE_TYPES:
                return Response({'files': f'File "{f.name}" has unsupported type.'}, status=status.HTTP_400_BAD_REQUEST)
            PrescriptionFile.objects.create(prescription=prescription, file=f, filename=f.name)

        notes = serializer.validated_data.get('notes', '').strip()
        if notes:
            prescription.notes = f'{prescription.notes}\n\nResubmission: {notes}'.strip()
            _create_clarification_message(prescription, sender=request.user, message=notes)
        prescription.status = Prescription.STATUS_PENDING
        prescription.pharmacist = None
        prescription.clarification_message = ''
        prescription.resubmitted_at = timezone.now()
        prescription.save(update_fields=[
            'notes', 'status', 'pharmacist', 'clarification_message', 'resubmitted_at', 'updated_at',
        ])
        PrescriptionAuditLog.objects.create(
            prescription=prescription,
            action='Prescription resubmitted by patient',
            notes=notes,
            performed_by=request.user,
        )
        return Response(PrescriptionSerializer(prescription).data)


class PrescriptionClarificationReplyView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @transaction.atomic
    def post(self, request, pk):
        try:
            prescription = (
                Prescription.objects.select_for_update()
                .get(pk=pk, patient=request.user)
            )
        except Prescription.DoesNotExist:
            return Response({'detail': 'Prescription not found.'}, status=status.HTTP_404_NOT_FOUND)

        if prescription.status != Prescription.STATUS_CLARIFICATION:
            return Response(
                {'detail': 'This prescription is not awaiting clarification right now.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = PrescriptionClarificationReplySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        message = serializer.validated_data['message']

        _create_clarification_message(prescription, sender=request.user, message=message)
        prescription.status = Prescription.STATUS_PENDING
        prescription.clarification_message = ''
        prescription.resubmitted_at = timezone.now()
        prescription.save(update_fields=['status', 'clarification_message', 'resubmitted_at', 'updated_at'])

        PrescriptionAuditLog.objects.create(
            prescription=prescription,
            action='Clarification response sent by patient',
            notes=message,
            performed_by=request.user,
        )

        recipients = []
        if prescription.pharmacist:
            recipients = [prescription.pharmacist]
        else:
            recipients = list(
                User.objects.filter(role=User.PHARMACIST, status=User.STATUS_ACTIVE, is_active=True)
            )
        for pharmacist in recipients:
            create_notification(
                recipient=pharmacist,
                notification_type='prescription_status',
                title=f'Clarification response for {prescription.reference}',
                message=f'{request.user.full_name or request.user.email} replied to the clarification request.',
                data={
                    'reference': prescription.reference,
                    'prescription_id': prescription.id,
                    'status': prescription.status,
                },
            )

        return Response(PrescriptionSerializer(prescription).data, status=status.HTTP_201_CREATED)
