"""Credential capture is separate from independent professional verification."""
from django.db import transaction
from django.utils import timezone
from rest_framework import serializers, generics
from rest_framework.response import Response
from apps.support.views import ActiveEvidenceAccess, ActiveAccount
from apps.support.compliance_audit import AuditedSerializerMixin, LockedUpdateMixin, record_change
from .models import Pharmacist, User


class PharmacistCredentialSerializer(AuditedSerializerMixin, serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.full_name', read_only=True)
    credential_is_current = serializers.BooleanField(read_only=True)

    class Meta:
        model = Pharmacist
        fields = ['id', 'user', 'user_name', 'license_number', 'license_country', 'license_board',
            'license_expiry', 'credential_evidence', 'credential_status', 'credential_verified_at',
            'credential_verified_by', 'credential_verification_reference', 'credential_is_current', 'permissions']
        read_only_fields = ['id', 'credential_status', 'credential_verified_at', 'credential_verified_by', 'credential_verification_reference']

    def to_internal_value(self, data):
        if {'credential_status', 'credential_verified_at', 'credential_verified_by', 'credential_verification_reference'}.intersection(data):
            raise serializers.ValidationError({'verification': 'Use the independent verification or suspension action; verification stamps cannot be submitted.'})
        return super().to_internal_value(data)

    def validate_user(self, user):
        if self.instance and user.pk != self.instance.user_id:
            raise serializers.ValidationError('The credential subject cannot be changed.')
        if user.role not in [User.PHARMACIST, User.ADMIN]:
            raise serializers.ValidationError('Select a pharmacy professional or licensed administrator.')
        return user

    def validate_permissions(self, permissions):
        if set(permissions)-Pharmacist.VALID_PERMISSIONS:
            raise serializers.ValidationError('Unknown clinical permission.')
        return list(dict.fromkeys(permissions))


class PharmacistCredentialListView(generics.ListCreateAPIView):
    permission_classes = [ActiveEvidenceAccess]
    serializer_class = PharmacistCredentialSerializer
    queryset = Pharmacist.objects.select_related('user', 'credential_evidence').order_by('id')
    search_fields = ['user__first_name', 'user__last_name', 'license_number']
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user, updated_by=self.request.user)


class PharmacistCredentialDetailView(LockedUpdateMixin, generics.RetrieveUpdateAPIView):
    permission_classes = [ActiveEvidenceAccess]
    serializer_class = PharmacistCredentialSerializer
    queryset = Pharmacist.objects.select_related('user', 'credential_evidence')
    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)


class CredentialVerificationSerializer(serializers.Serializer):
    verification_reference = serializers.CharField(max_length=2000)


class PharmacistCredentialVerifyView(generics.GenericAPIView):
    permission_classes = [ActiveEvidenceAccess]
    serializer_class = CredentialVerificationSerializer

    @transaction.atomic
    def post(self, request, pk):
        serializer = self.get_serializer(data=request.data); serializer.is_valid(raise_exception=True)
        profile = generics.get_object_or_404(Pharmacist.objects.select_for_update(of=('self',)).select_related('user', 'credential_evidence'), pk=pk)
        if request.user.pk == profile.user_id:
            raise serializers.ValidationError('A pharmacist cannot approve their own credentials.')
        profile.credential_status = 'verified'
        profile.credential_verified_at = timezone.now()
        profile.credential_verified_by = request.user
        profile.credential_verification_reference = serializer.validated_data['verification_reference']
        if not profile.credential_is_current:
            raise serializers.ValidationError('Current Kenyan registration, board, licence expiry and independently verified matching professional-credential evidence are required.')
        profile.save(update_fields=['credential_status', 'credential_verified_at', 'credential_verified_by', 'credential_verification_reference'])
        record_change(profile, request.user, 'credential_verified')
        return Response(PharmacistCredentialSerializer(profile).data)


class PharmacistCredentialSuspendView(generics.GenericAPIView):
    permission_classes = [ActiveEvidenceAccess]
    serializer_class = CredentialVerificationSerializer
    @transaction.atomic
    def post(self, request, pk):
        serializer = self.get_serializer(data=request.data); serializer.is_valid(raise_exception=True)
        profile = generics.get_object_or_404(Pharmacist.objects.select_for_update(), pk=pk)
        profile.credential_status = 'suspended'
        profile.credential_verification_reference = serializer.validated_data['verification_reference']
        profile.save(update_fields=['credential_status', 'credential_verification_reference'])
        record_change(profile, request.user, 'credential_suspended')
        return Response(PharmacistCredentialSerializer(profile).data)


class MyPharmacistCredentialView(generics.RetrieveAPIView):
    permission_classes = [ActiveAccount]
    serializer_class = PharmacistCredentialSerializer
    def get_object(self):
        return generics.get_object_or_404(Pharmacist, user=self.request.user)


class CredentialSubjectSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source='full_name', read_only=True)
    class Meta:
        model=User
        fields=['id','name','role']


class CredentialSubjectListView(generics.ListAPIView):
    permission_classes=[ActiveEvidenceAccess]
    serializer_class=CredentialSubjectSerializer
    queryset=User.objects.filter(role__in=['pharmacist','admin'],is_active=True,status='active').order_by('first_name','id')
    search_fields=['first_name','last_name','email']


class PharmacistDocumentsView(generics.GenericAPIView):
    from .permissions import IsAdminUser
    permission_classes = [ActiveAccount, IsAdminUser]

    def profile(self, pk):
        return generics.get_object_or_404(Pharmacist, user_id=pk, user__role=User.PHARMACIST)

    def get(self, request, pk):
        from django.db.models import Q
        from apps.support.models import ComplianceEvidence
        from apps.support.serializers import ComplianceEvidenceSerializer
        profile = self.profile(pk)
        documents = ComplianceEvidence.objects.filter(Q(pharmacist_document_subjects=profile) | Q(pk=profile.credential_evidence_id)).distinct().order_by('-created_at')
        return Response(ComplianceEvidenceSerializer(documents, many=True, context={'request': request}).data)

    @transaction.atomic
    def post(self, request, pk):
        from apps.support.serializers import ComplianceEvidenceSerializer
        profile = self.profile(pk)
        profile = Pharmacist.objects.select_for_update().get(pk=profile.pk)
        data = request.data.copy()
        data['evidence_type'] = 'professional_credential'
        data['reference_number'] = profile.license_number or ''
        data['issuing_authority'] = profile.license_board
        data['status'] = 'active'
        data.pop('verified_at', None)
        data.pop('verified_by', None)
        data.pop('verification_reference', None)
        if not data.get('title'):
            data['title'] = 'Pharmacist document'
        if 'upload' not in request.FILES:
            raise serializers.ValidationError({'upload': 'Select a document to upload.'})
        serializer = ComplianceEvidenceSerializer(data=data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        renewal = request.data.get('renewal') == 'true'
        if renewal:
            issued = serializer.validated_data.get('issued_at')
            expires = serializer.validated_data.get('expires_at')
            if not issued or issued > timezone.localdate() or not expires or expires < timezone.localdate():
                raise serializers.ValidationError('Provide a valid issue date and an unexpired licence expiry date.')
        document = serializer.save(created_by=request.user, updated_by=request.user)
        profile.documents.add(document)
        if renewal:
            profile.license_expiry = expires
            profile.credential_evidence = document
            profile.updated_by = request.user
            profile.save()
        record_change(profile, request.user, 'document_added')
        return Response(ComplianceEvidenceSerializer(document, context={'request': request}).data, status=201)


class PharmacistDocumentDeleteView(PharmacistDocumentsView):
    http_method_names = ['delete', 'options']
    @transaction.atomic
    def delete(self, request, pk, document_pk):
        profile = self.profile(pk)
        if not profile.documents.filter(pk=document_pk).exists() and profile.credential_evidence_id != document_pk:
            from rest_framework.exceptions import NotFound
            raise NotFound('Document not found for this pharmacist.')
        if profile.credential_evidence_id == document_pk:
            profile.credential_evidence = None
            profile.updated_by = request.user
            profile.save()
        profile.documents.remove(document_pk)
        # Historical evidence can be referenced by clinical audits; remove the
        # association without erasing evidence underlying past decisions.
        record_change(profile, request.user, 'document_removed')
        return Response(status=204)


class MyPharmacistDocumentsView(PharmacistDocumentsView):
    permission_classes = [ActiveAccount]

    def profile(self, pk=None):
        if self.request.user.role != User.PHARMACIST:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('Pharmacist access required.')
        return generics.get_object_or_404(Pharmacist, user=self.request.user)

    def get(self, request):
        return super().get(request, request.user.pk)

    def post(self, request):
        return super().post(request, request.user.pk)


class MyPharmacistDocumentDownloadView(MyPharmacistDocumentsView):
    def get(self, request, document_pk):
        from django.http import FileResponse
        from apps.support.models import ComplianceEvidence
        from django.db.models import Q
        profile = self.profile()
        document = generics.get_object_or_404(ComplianceEvidence.objects.filter(
            Q(pharmacist_document_subjects=profile) | Q(pk=profile.credential_evidence_id)
        ).distinct(), pk=document_pk)
        if not document.file:
            from rest_framework.exceptions import NotFound
            raise NotFound('Document file unavailable.')
        return FileResponse(document.file.open('rb'), as_attachment=True)

    http_method_names = ['get', 'head', 'options']


class PharmacistLicenceApproveView(generics.GenericAPIView):
    """Approve matching evidence and credentials together, or change neither."""
    from .permissions import IsAdminUser
    permission_classes = [ActiveAccount, IsAdminUser]
    serializer_class = CredentialVerificationSerializer

    @transaction.atomic
    def post(self, request, pk):
        from apps.support.models import ComplianceEvidence
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        profile = generics.get_object_or_404(Pharmacist.objects.select_for_update(), pk=pk)
        if not profile.credential_evidence_id:
            raise serializers.ValidationError('Upload a current licence before approving this pharmacist.')
        if str(request.data.get('evidence_id', '')) != str(profile.credential_evidence_id):
            raise serializers.ValidationError('The primary licence changed. Refresh and review the latest document.')
        evidence = ComplianceEvidence.objects.select_for_update().get(pk=profile.credential_evidence_id)
        if request.user.pk == profile.user_id:
            raise serializers.ValidationError('A pharmacist cannot approve their own credentials.')
        reference = serializer.validated_data['verification_reference']
        if not (evidence.file or evidence.external_url):
            raise serializers.ValidationError('A licence document is required.')
        evidence.verified_by = request.user
        evidence.verified_at = timezone.now()
        evidence.verification_reference = reference
        profile.credential_evidence = evidence
        profile.credential_status = 'verified'
        profile.credential_verified_by = request.user
        profile.credential_verified_at = timezone.now()
        profile.credential_verification_reference = reference
        if not profile.credential_is_current:
            raise serializers.ValidationError('Check the licence number, country, registration board, issue date and expiry. The uploaded licence must match the pharmacist and be current; the account must be active.')
        evidence.save(update_fields=['verified_by', 'verified_at', 'verification_reference'])
        profile.save(update_fields=['credential_status', 'credential_verified_by', 'credential_verified_at', 'credential_verification_reference'])
        record_change(evidence, request.user, 'evidence_verified')
        record_change(profile, request.user, 'credential_verified')
        return Response(PharmacistCredentialSerializer(profile).data)
