from datetime import timedelta
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient
from apps.accounts.models import User, Pharmacist
from avapharmacy.test_compliance_fixtures import credential_fixture


class LicenceApprovalTests(TestCase):
    def setUp(self):
        self.subject = User.objects.create_user(email='approval-subject@example.test', role='pharmacist')
        self.admin = User.objects.create_user(email='approval-admin@example.test', role='admin')
        self.profile = Pharmacist.objects.create(user=self.subject, **credential_fixture())
        self.profile.credential_status = 'pending'
        self.profile.credential_verified_at = None
        self.profile.credential_verified_by = None
        self.profile.save()
        self.evidence = self.profile.credential_evidence
        self.evidence.verified_at = None
        self.evidence.verified_by = None
        self.evidence.save()
        self.client = APIClient()
        self.client.force_authenticate(self.admin)

    def approve(self, **changes):
        data = {'verification_reference': 'Independently checked register REF123', 'evidence_id': self.evidence.pk}
        data.update(changes)
        return self.client.post(reverse('pharmacist-licence-approve', args=[self.profile.pk]), data, format='json')

    def test_single_approval_verifies_evidence_and_restores_access(self):
        response = self.approve()
        self.assertEqual(response.status_code, 200, response.data)
        self.profile.refresh_from_db(); self.evidence.refresh_from_db()
        self.assertTrue(self.profile.credential_is_current)
        self.assertEqual(self.evidence.verified_by_id, self.admin.pk)
        self.assertEqual(self.profile.credential_verified_by_id, self.admin.pk)

    def test_expired_evidence_rolls_back_both_approvals(self):
        self.evidence.expires_at = timezone.localdate() - timedelta(days=1)
        self.evidence.save()
        self.assertEqual(self.approve().status_code, 400)
        self.evidence.refresh_from_db(); self.profile.refresh_from_db()
        self.assertIsNone(self.evidence.verified_at)
        self.assertEqual(self.profile.credential_status, 'pending')

    def test_same_admin_can_create_edit_upload_and_approve(self):
        self.evidence.created_by = self.admin; self.evidence.updated_by = self.admin; self.evidence.save()
        self.profile.created_by = self.admin; self.profile.updated_by = self.admin; self.profile.save()
        response = self.approve()
        self.assertEqual(response.status_code, 200, response.data)
        self.profile.refresh_from_db()
        self.assertTrue(self.profile.credential_is_current)

    def test_stale_document_and_missing_reference_cannot_approve(self):
        self.assertEqual(self.approve(evidence_id=0).status_code, 400)
        self.assertEqual(self.approve(verification_reference='').status_code, 400)

    def test_pharmacist_cannot_self_approve(self):
        self.client.force_authenticate(self.subject)
        self.assertEqual(self.approve().status_code, 403)
