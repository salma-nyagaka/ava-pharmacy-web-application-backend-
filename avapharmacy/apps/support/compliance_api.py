from .compliance_audit import AuditedSerializerMixin, LockedUpdateMixin, record_change
"""Private, role-scoped compliance workflows with attributed decisions."""
from datetime import timedelta
from django.db import transaction
from django.utils import timezone
from rest_framework import serializers, generics, permissions
from rest_framework.exceptions import PermissionDenied
from .models import (MedicineAssessment, PrivacyRequest, OperationalReview, ComplianceEvidence, SiteSettings)
from .views import ActiveAccount, ActiveEvidenceAccess
from .compliance import screening_digest
from apps.prescriptions.access import can_review
from apps.orders.models import CartItem, OrderItem


class ReviewerAccess(ActiveAccount):
    def has_permission(self, request, view):
        return super().has_permission(request, view) and (can_review(request.user) or (request.method in permissions.SAFE_METHODS and request.user.role == 'ppb_inspector'))


class AssessmentSerializer(AuditedSerializerMixin, serializers.ModelSerializer):
    class Meta:
        model = MedicineAssessment
        fields = '__all__'
        read_only_fields = ['id', 'customer', 'variant', 'quantity', 'screening_digest', 'reviewed_by', 'created_at', 'expires_at']

    def validate(self, attrs):
        item = attrs.get('cart_item')
        if not item or not item.cart.user_id or not item.variant_id:
            raise serializers.ValidationError('Select an authenticated customer cart item.')
        if not attrs.get('suitability', '').strip() or not attrs.get('counselling', '').strip():
            raise serializers.ValidationError('Document suitability and counselling, including safe use, storage and disposal.')
        if attrs['decision'] != 'approved' and not attrs.get('intervention', '').strip():
            raise serializers.ValidationError('Explain the refusal or referral and next steps.')
        return attrs


class AssessmentView(generics.ListCreateAPIView):
    permission_classes = [ReviewerAccess]
    serializer_class = AssessmentSerializer
    queryset = MedicineAssessment.objects.all().order_by('-created_at')

    @transaction.atomic
    def perform_create(self, serializer):
        from apps.products.models import Variant
        item = serializer.validated_data['cart_item']
        Variant.objects.select_for_update().get(pk=item.variant_id)
        item = CartItem.objects.select_for_update().get(pk=item.pk)
        serializer.save(customer=item.cart.user, variant=item.variant, quantity=item.quantity,
            screening_digest=screening_digest(item.otc_screening), reviewed_by=self.request.user,
            expires_at=timezone.now()+timedelta(hours=24))


class PrivacySerializer(AuditedSerializerMixin, serializers.ModelSerializer):
    class Meta:
        model = PrivacyRequest
        fields = '__all__'
        read_only_fields = ['id', 'customer', 'handled_by', 'identity_verified_by', 'created_at', 'resolved_at']

    def validate(self, attrs):
        user = self.context['request'].user
        if self.instance is None:
            if set(attrs)-{'request_type', 'details'}:
                raise serializers.ValidationError('Only request type and details can be submitted.')
        else:
            if user.role != 'admin':
                raise PermissionDenied('Only the privacy administrator can process requests.')
            if set(attrs)-{'status', 'response', 'lawful_basis'}:
                raise serializers.ValidationError('The original request is immutable.')
            if attrs.get('status') in {'resolved', 'refused'}:
                if not attrs.get('response', '').strip() or not attrs.get('lawful_basis', '').strip():
                    raise serializers.ValidationError('A response and lawful basis, including any retention restriction, are required.')
                if not self.instance.identity_verified_by_id:
                    raise serializers.ValidationError('Verify the requester identity before resolving or refusing.')
        return attrs


class PrivacyListView(generics.ListCreateAPIView):
    permission_classes = [ActiveAccount]
    serializer_class = PrivacySerializer
    def get_queryset(self):
        qs = PrivacyRequest.objects.all().order_by('-created_at')
        return qs if self.request.user.role == 'admin' else qs.filter(customer=self.request.user)
    def perform_create(self, serializer):
        serializer.save(customer=self.request.user)


class PrivacyDetailView(LockedUpdateMixin, generics.RetrieveUpdateAPIView):
    permission_classes = [ActiveAccount]
    serializer_class = PrivacySerializer
    def get_queryset(self):
        qs = PrivacyRequest.objects.all()
        return qs if self.request.user.role == 'admin' else qs.filter(customer=self.request.user)
    def perform_update(self, serializer):
        serializer.save(handled_by=self.request.user, resolved_at=timezone.now() if serializer.validated_data.get('status') in {'resolved', 'refused'} else None)


class PrivacyVerifyView(generics.GenericAPIView):
    permission_classes = [ActiveEvidenceAccess]
    serializer_class = serializers.Serializer
    def post(self, request, pk):
        from rest_framework.response import Response
        obj = generics.get_object_or_404(PrivacyRequest, pk=pk)
        if not str(request.data.get('verification_reference', '')).strip():
            raise serializers.ValidationError('Provide a reference to the securely stored identity verification, without uploading identity documents here.')
        obj.identity_verified_by = request.user
        obj.lawful_basis = 'Identity verification reference: '+str(request.data['verification_reference'])
        obj.save(update_fields=['identity_verified_by', 'lawful_basis'])
        record_change(obj, request.user, 'identity_verified')
        return Response(PrivacySerializer(obj).data)


class OperationalSerializer(AuditedSerializerMixin, serializers.ModelSerializer):
    class Meta:
        model = OperationalReview
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']
    def validate(self, attrs):
        owner = attrs.get('owner', getattr(self.instance, 'owner', None))
        if owner and (not owner.is_active or owner.status != 'active' or owner.role not in {'admin','pharmacist','doctor','pediatrician','inventory_staff','lab_technician','lab_partner'}):
            raise serializers.ValidationError({'owner': 'Assign an active accountable internal professional or operations owner.'})
        if attrs.get('completed_at'):
            evidence = attrs.get('evidence', getattr(self.instance, 'evidence', None))
            if not evidence or not evidence.verified_at or evidence.status != 'active' or not evidence.expires_at or evidence.expires_at < timezone.localdate() or not attrs.get('findings', '').strip() or attrs['completed_at'] > timezone.now():
                raise serializers.ValidationError('Completion requires reviewed evidence and findings; an uploaded file is insufficient.')
        return attrs


class OperationalListView(generics.ListCreateAPIView):
    permission_classes = [ActiveEvidenceAccess]
    serializer_class = OperationalSerializer
    queryset = OperationalReview.objects.all().order_by('due_on')


class OperationalDetailView(LockedUpdateMixin, generics.RetrieveUpdateAPIView):
    permission_classes = [ActiveEvidenceAccess]
    serializer_class = OperationalSerializer
    queryset = OperationalReview.objects.all()


class ReadinessView(generics.GenericAPIView):
    permission_classes = [ActiveEvidenceAccess]
    serializer_class = serializers.Serializer
    def get(self, request):
        from .checks import REQUIRED_COMPLIANCE_FIELDS, _is_missing
        from rest_framework.response import Response
        site = SiteSettings.get_solo()
        required = [x[0] for x in ComplianceEvidence.TYPE_CHOICES]
        valid = set(ComplianceEvidence.objects.filter(verified_at__isnull=False, expires_at__gte=timezone.localdate(), status='active').values_list('evidence_type', flat=True))
        from apps.accounts.models import Pharmacist
        operators = Pharmacist.objects.filter(user__is_active=True, user__status='active', user__role__in=['pharmacist', 'admin']).select_related('user','credential_evidence')
        return Response({'pharmacist_credentials_pending': sum(not p.credential_is_current for p in operators), 'software_report_is_not_regulatory_approval': True,
            'missing_disclosures': [f for f in REQUIRED_COMPLIANCE_FIELDS if _is_missing(getattr(site, f, ''))],
            'missing_current_verified_evidence': sorted(set(required)-valid),
            'overdue_operational_reviews': OperationalReview.objects.filter(due_on__lt=timezone.localdate(), completed_at__isnull=True).count(),
            'external_verification_required': ['production TLS and private media', 'Kenya hosting and processor contracts', 'backup restore drill', 'professional practice and premises inspection']})


class EvidenceVerifyView(generics.GenericAPIView):
    permission_classes = [ActiveEvidenceAccess]
    serializer_class = serializers.Serializer
    @transaction.atomic
    def post(self, request, pk):
        from rest_framework.response import Response
        obj = generics.get_object_or_404(ComplianceEvidence.objects.select_for_update(), pk=pk)
        if obj.created_by_id == request.user.pk or obj.updated_by_id == request.user.pk:
            raise serializers.ValidationError('Independent review is required; a different administrator must verify this evidence.')
        reference = str(request.data.get('verification_reference', '')).strip()
        if not reference or not (obj.file or obj.external_url) or not obj.expires_at or obj.expires_at < timezone.localdate():
            raise serializers.ValidationError('Current evidence, expiry/review date and external verification reference are required.')
        obj.verified_by = request.user
        obj.verified_at = timezone.now()
        obj.verification_reference = reference
        obj.save(update_fields=['verified_by', 'verified_at', 'verification_reference'])
        record_change(obj, request.user, 'evidence_verified')
        return Response({'id': obj.pk, 'verified_at': obj.verified_at, 'verified_by': obj.verified_by_id})


class AssessmentQueueView(generics.GenericAPIView):
    permission_classes = [ReviewerAccess]
    serializer_class = serializers.Serializer
    def get(self, request):
        from rest_framework.response import Response
        items = CartItem.objects.filter(variant__regulatory_scope='medicine', cart__user__isnull=False).select_related('cart__user', 'variant')[:100]
        return Response([{'id': item.pk, 'customer': item.cart.user.full_name,
            'variant': str(item.variant), 'quantity': item.quantity, 'screening': item.otc_screening}
            for item in items])


class CurationSerializer(AuditedSerializerMixin, serializers.ModelSerializer):
    from apps.products.models import Variant
    class Meta:
        from apps.products.models import Variant
        model = Variant
        fields = ['id', 'name', 'sku', 'regulatory_scope', 'prescription_classification', 'requires_prescription',
            'prescription_review_status', 'regulatory_status', 'ppb_registration_number', 'authorized_supplier',
            'ppb_license_expiry_date', 'is_ppb_registered', 'pil_source_url', 'pil_version', 'contraindications',
            'side_effects', 'warnings', 'directions', 'pil_reviewed_by', 'pil_reviewed_at', 'is_temperature_sensitive',
            'storage_temperature_min_c', 'storage_temperature_max_c', 'storage_instructions']
        read_only_fields = ['id', 'name', 'sku', 'pil_reviewed_by', 'pil_reviewed_at']

    @transaction.atomic
    def update(self, instance, validated_data):
        for key, value in validated_data.items():
            setattr(instance, key, value)
        instance.pil_reviewed_by = self.context['request'].user
        instance.pil_reviewed_at = timezone.now()
        instance.save()
        record_change(instance, self.context['request'].user, 'curate')
        return instance


class CurationListView(generics.ListAPIView):
    permission_classes = [ReviewerAccess]
    serializer_class = CurationSerializer
    search_fields = ['name', 'sku', 'product__name']
    def get_queryset(self):
        from apps.products.models import Variant
        return Variant.objects.filter(is_active=True).order_by('name')


class CurationDetailView(LockedUpdateMixin, generics.RetrieveUpdateAPIView):
    permission_classes = [ReviewerAccess]
    serializer_class = CurationSerializer
    def get_queryset(self):
        from apps.products.models import Variant
        return Variant.objects.all()
