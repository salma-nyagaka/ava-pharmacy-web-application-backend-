from datetime import timedelta
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken
from unittest.mock import patch, PropertyMock, PropertyMock
from apps.accounts.models import Pharmacist, User
from apps.support.models import ComplianceEvidence


class PharmacistRenewalAccessTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email='renewal@example.test', password='TestPassword123!', role='pharmacist')
        self.profile = Pharmacist.objects.create(user=self.user, license_number='RENEW-123', license_country='Kenya', license_board='PPB', license_expiry=timezone.localdate() - timedelta(days=1))
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {RefreshToken.for_user(self.user).access_token}')

    def test_expired_user_can_read_credentials_but_cannot_use_other_apis(self):
        self.assertEqual(self.client.get(reverse('my-pharmacist-credential')).status_code, 200)
        # Both read and write requests are blocked before business logic executes.
        for method in ('get', 'post', 'patch'):
            with self.subTest(method=method):
                response = getattr(self.client, method)(reverse('addresses'), {}, format='json')
                self.assertEqual(response.status_code, 403)
        self.assertEqual(self.client.patch(reverse('me'), {'first_name': 'Changed'}, format='json').status_code, 403)

    def upload(self, **changes):
        data = {'upload': SimpleUploadedFile('renewed.pdf', b'%PDF-1.4\nrenewal', content_type='application/pdf'),
            'renewal': 'true', 'issued_at': str(timezone.localdate()),
            'expires_at': str(timezone.localdate() + timedelta(days=365))}
        data.update(changes)
        return self.client.post(reverse('my-pharmacist-documents'), data, format='multipart')

    def test_renewal_upload_is_owned_pending_and_does_not_unlock_work(self):
        response = self.upload()
        self.assertEqual(response.status_code, 201, response.data)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.credential_status, 'pending')
        self.assertGreater(self.profile.license_expiry, timezone.localdate())
        self.assertIsNotNone(self.profile.credential_evidence_id)
        evidence = self.profile.credential_evidence
        self.assertEqual(evidence.reference_number, 'RENEW-123')
        self.assertIsNone(evidence.verified_at)
        self.assertEqual(evidence.created_by_id, self.user.pk)
        self.assertFalse(self.profile.credential_is_current)
        self.assertEqual(self.client.get(reverse('addresses')).status_code, 403)
        self.assertEqual(self.client.get(reverse('my-pharmacist-documents')).status_code, 200)

    def test_invalid_renewal_cannot_update_expiry(self):
        original = self.profile.license_expiry
        self.assertEqual(self.upload(expires_at=str(original)).status_code, 400)
        self.assertEqual(self.upload(upload=SimpleUploadedFile('fake.pdf', b'fake')).status_code, 400)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.license_expiry, original)
        self.assertFalse(self.profile.documents.exists())

    def test_current_credential_passes_global_gate(self):
        with patch.object(Pharmacist, 'credential_is_current', new_callable=PropertyMock, return_value=True):
            self.assertEqual(self.client.get(reverse('addresses')).status_code, 200)

    def test_document_download_cannot_access_another_subject(self):
        other = ComplianceEvidence.objects.create(evidence_type='professional_credential', title='Other licence')
        response = self.client.get(reverse('my-pharmacist-document-download', args=[other.pk]))
        self.assertEqual(response.status_code, 404)

    def test_multiple_licences_remain_associated_with_the_same_pharmacist(self):
        self.assertEqual(self.upload().status_code, 201)
        primary = Pharmacist.objects.get(pk=self.profile.pk).credential_evidence_id
        self.assertEqual(self.upload(renewal='false').status_code, 201)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.documents.count(), 2)
        self.assertEqual(self.profile.credential_evidence_id, primary)
        self.assertFalse(self.profile.credential_is_current)

    def test_admin_can_upload_renewal_for_pharmacist(self):
        admin = User.objects.create_user(email='renewal-admin@example.test', role='admin')
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {RefreshToken.for_user(admin).access_token}')
        response = self.client.post(reverse('pharmacist-documents', args=[self.user.pk]), {
            'upload': SimpleUploadedFile('admin-renewed.pdf', b'%PDF-1.4\nrenewal'),
            'renewal': 'true', 'issued_at': str(timezone.localdate()),
            'expires_at': str(timezone.localdate() + timedelta(days=365)),
        }, format='multipart')
        self.assertEqual(response.status_code, 201, response.data)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.credential_evidence.created_by_id, admin.pk)
        self.assertEqual(self.profile.credential_status, 'pending')
