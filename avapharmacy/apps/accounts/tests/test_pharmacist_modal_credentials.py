from unittest.mock import patch
from datetime import date
from django.test import TestCase
from apps.accounts.serializers import AdminUserCreateSerializer


class PharmacistModalCredentialTests(TestCase):
    @patch('apps.accounts.serializers.send_pharmacist_activation_email')
    def test_creation_saves_credential_fields_without_verifying(self, email):
        serializer = AdminUserCreateSerializer(data={
            'email': 'modal-credential@example.com', 'first_name': 'Test', 'last_name': 'Pharmacist',
            'phone': '+254711234567', 'role': 'pharmacist', 'pharmacist_license_number': 'MODAL-123',
            'pharmacist_license_country': 'Kenya', 'pharmacist_license_board': 'Pharmacy and Poisons Board',
            'pharmacist_license_expiry': '2027-12-31', 'pharmacist_credential_evidence': None,
            'pharmacist_permissions': ['prescription_review'],
        })
        self.assertTrue(serializer.is_valid(), serializer.errors)
        user = serializer.save()
        from apps.accounts.models import Pharmacist
        profile = Pharmacist.objects.get(user=user)
        self.assertEqual(profile.license_country, 'Kenya')
        self.assertEqual(profile.license_expiry, date(2027, 12, 31))
        self.assertEqual(profile.license_board, 'Pharmacy and Poisons Board')
        self.assertEqual(profile.credential_status, 'pending')
        self.assertFalse(profile.credential_is_current)
        self.assertFalse(user.is_active)
        email.assert_called_once()

    def test_invalid_evidence_rejected_before_creation(self):
        serializer = AdminUserCreateSerializer(data={
            'email': 'invalid-evidence@example.com', 'role': 'pharmacist', 'first_name': 'Test', 'last_name': 'Invalid',
            'pharmacist_license_number': 'BAD-EVIDENCE', 'pharmacist_credential_evidence': 999999,
        })
        self.assertFalse(serializer.is_valid())
        self.assertIn('pharmacist_credential_evidence', serializer.errors)

    @patch('apps.accounts.serializers.send_pharmacist_activation_email')
    def test_multipart_creation_links_uploaded_document(self, email):
        from tempfile import TemporaryDirectory
        from django.core.files.uploadedfile import SimpleUploadedFile
        from django.test import override_settings
        from rest_framework.test import APIClient
        from apps.accounts.models import User, Pharmacist
        admin = User.objects.create_user(email='upload-admin@example.com', password='test-secret', role='admin')
        client = APIClient(); client.force_authenticate(admin)
        with TemporaryDirectory() as media, override_settings(MEDIA_ROOT=media):
            response = client.post('/api/admin/users/', {
                'first_name': 'Upload', 'last_name': 'Pharmacist', 'email': 'upload-pharm@example.com',
                'phone': '+254722234567', 'role': 'pharmacist', 'pharmacist_license_number': 'UPLOAD-123',
                'pharmacist_license_country': 'Kenya', 'pharmacist_license_board': 'Pharmacy and Poisons Board',
                'pharmacist_license_expiry': '2027-12-31', 'pharmacist_permissions': ['prescription_review', 'inventory_add'],
                'pharmacist_license_document': SimpleUploadedFile('licence.pdf', b'%PDF-1.4\nlicence evidence', content_type='application/pdf'),
            }, format='multipart')
            self.assertEqual(response.status_code, 201, response.data)
            profile = Pharmacist.objects.get(user__email='upload-pharm@example.com')
            self.assertEqual(profile.credential_evidence.reference_number, 'UPLOAD-123')
            self.assertEqual(profile.credential_evidence.created_by_id, admin.pk)
            self.assertIsNone(profile.credential_evidence.verified_at)
            self.assertEqual(set(profile.permissions), {'prescription_review', 'inventory_add'})
            with profile.credential_evidence.file.open('rb') as saved:
                self.assertTrue(saved.read().startswith(b'%PDF-'))

    def test_non_document_upload_rejected(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        serializer = AdminUserCreateSerializer(data={
            'first_name': 'Invalid', 'last_name': 'Document', 'email': 'bad-doc@example.com',
            'role': 'pharmacist', 'pharmacist_license_number': 'BAD-FILE',
            'pharmacist_license_document': SimpleUploadedFile('fake.pdf', b'not a PDF'),
        })
        self.assertFalse(serializer.is_valid())
        self.assertIn('pharmacist_license_document', serializer.errors)

    def test_document_management_is_scoped_and_admin_only(self):
        from tempfile import TemporaryDirectory
        from django.test import override_settings
        from django.core.files.uploadedfile import SimpleUploadedFile
        from rest_framework.test import APIClient
        from apps.accounts.models import User, Pharmacist
        from apps.support.models import ComplianceEvidence
        admin = User.objects.create_user(email='docs-admin@example.com', password='test-secret', role='admin')
        subject = User.objects.create_user(email='docs-pharm@example.com', role='pharmacist')
        other = User.objects.create_user(email='other-pharm@example.com', role='pharmacist')
        profile = Pharmacist.objects.create(user=subject, license_number='DOC-TEST')
        Pharmacist.objects.create(user=other, license_number='OTHER-DOC')
        client = APIClient(); client.force_authenticate(admin)
        base = f'/api/admin/users/{subject.pk}/documents/'
        with TemporaryDirectory() as media, override_settings(MEDIA_ROOT=media):
            for name in ['first.pdf', 'second.pdf']:
                response = client.post(base, {'title': name, 'upload': SimpleUploadedFile(name,b'%PDF-1.4\ncontent',content_type='application/pdf')}, format='multipart')
                self.assertEqual(response.status_code, 201, response.data)
            self.assertEqual(profile.documents.count(), 2)
            doc = profile.documents.first()
            response = client.delete(f'/api/admin/users/{other.pk}/documents/{doc.pk}/')
            self.assertEqual(response.status_code, 404)
            profile.credential_evidence = doc; profile.save()
            response = client.delete(base + str(doc.pk) + '/')
            self.assertEqual(response.status_code, 204)
            profile.refresh_from_db()
            self.assertIsNone(profile.credential_evidence_id)
            self.assertEqual(profile.documents.count(), 1)
            self.assertTrue(ComplianceEvidence.objects.filter(pk=doc.pk).exists())
            client.force_authenticate(subject)
            self.assertEqual(client.get(base).status_code, 403)

    def test_account_suspension_records_reason(self):
        from rest_framework.test import APIClient
        from apps.accounts.models import User, AdminAuditLog
        admin = User.objects.create_user(email='suspend-admin@example.com', role='admin')
        subject = User.objects.create_user(email='suspend-pharm@example.com', role='pharmacist')
        client = APIClient(); client.force_authenticate(admin)
        response = client.post(f'/api/admin/users/{subject.pk}/suspend/', {'reason': 'Licence requires correction'}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        subject.refresh_from_db()
        self.assertEqual(subject.status, 'suspended')
        self.assertFalse(subject.is_active)
        self.assertEqual(AdminAuditLog.objects.get(action='user_suspended', entity_id=str(subject.pk)).metadata['reason'], 'Licence requires correction')
