from datetime import timedelta
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from apps.accounts.models import User, Pharmacist
from apps.support.models import ComplianceEvidence, ComplianceEvent
from apps.prescriptions.access import can_review
from avapharmacy.test_compliance_fixtures import credential_fixture


class PharmacistCredentialValidityTests(TestCase):
    def setUp(self):
        self.client=APIClient()
        self.maker=User.objects.create_user(email='credential-maker@example.invalid',role='admin')
        self.verifier=User.objects.create_user(email='credential-verifier@example.invalid',role='admin')
        self.pharmacist=User.objects.create_user(email='credential-subject@example.invalid',role='pharmacist')
        self.profile=Pharmacist.objects.create(user=self.pharmacist, permissions=['prescription_review'], **credential_fixture())

    def test_admin_role_alone_cannot_review(self):
        self.assertFalse(can_review(self.maker))
        self.client.force_authenticate(self.maker)
        self.assertEqual(self.client.post('/api/compliance/medicine-assessments/',{},format='json').status_code,403)

    def test_current_matching_verified_credentials_allow_review(self):
        self.assertTrue(can_review(self.pharmacist))

    def test_expiry_and_identity_change_invalidate_verification(self):
        self.profile.license_expiry=timezone.localdate()-timedelta(days=1)
        self.profile.save(update_fields=['license_expiry'])
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.credential_status,'pending');self.assertIsNone(self.profile.credential_verified_at)
        self.assertFalse(can_review(self.pharmacist))

    def test_revoked_evidence_and_mismatched_reference_block_review(self):
        evidence=self.profile.credential_evidence
        evidence.reference_number='OTHER-LICENCE';evidence.save()
        self.assertFalse(can_review(self.pharmacist))
        evidence.reference_number=self.profile.license_number;evidence.status='expired';evidence.save()
        self.assertFalse(can_review(self.pharmacist))

    def test_subject_or_maker_cannot_self_verify(self):
        self.profile.created_by=self.maker;self.profile.updated_by=self.maker;self.profile.save()
        self.client.force_authenticate(self.maker)
        self.assertEqual(self.client.post(f'/api/compliance/pharmacist-credentials/{self.profile.pk}/verify/',{'verification_reference':'Synthetic'},format='json').status_code,400)
        self.client.force_authenticate(self.pharmacist)
        self.assertEqual(self.client.post(f'/api/compliance/pharmacist-credentials/{self.profile.pk}/verify/',{'verification_reference':'Synthetic'},format='json').status_code,403)

    def test_independent_verification_and_suspend_are_audited(self):
        self.profile.credential_status='pending';self.profile.created_by=self.maker;self.profile.updated_by=self.maker;self.profile.save()
        self.client.force_authenticate(self.verifier)
        url=f'/api/compliance/pharmacist-credentials/{self.profile.pk}/'
        response=self.client.post(url+'verify/',{'verification_reference':'Synthetic independently checked'},format='json')
        self.assertEqual(response.status_code,200,response.data);self.assertTrue(can_review(self.pharmacist))
        self.assertEqual(self.client.post(url+'suspend/',{'verification_reference':'Synthetic suspension'},format='json').status_code,200)
        self.assertFalse(can_review(self.pharmacist))
        self.assertEqual(ComplianceEvent.objects.filter(record_id=self.profile.pk,model_label='accounts.pharmacist').count(),2)

    def test_forged_verification_stamps_rejected(self):
        self.client.force_authenticate(self.maker)
        r=self.client.patch(f'/api/compliance/pharmacist-credentials/{self.profile.pk}/',{'credential_status':'verified'},format='json')
        self.assertEqual(r.status_code,400)

    def test_inspector_read_only_and_subject_scoping(self):
        inspector=User.objects.create_user(email='credential-inspector@example.invalid',role='ppb_inspector')
        self.client.force_authenticate(inspector)
        self.assertEqual(self.client.get('/api/compliance/pharmacist-credentials/').status_code,200)
        self.assertEqual(self.client.patch(f'/api/compliance/pharmacist-credentials/{self.profile.pk}/',{'license_country':'Kenya'},format='json').status_code,403)
        self.client.force_authenticate(self.pharmacist)
        r=self.client.get('/api/compliance/pharmacist-credentials/me/');self.assertEqual(r.status_code,200);self.assertEqual(r.data['user'],self.pharmacist.pk)
        self.assertEqual(self.client.get('/api/compliance/pharmacist-credentials/').status_code,403)

    def test_real_profiles_default_to_pending_without_evidence(self):
        other=User.objects.create_user(email='credential-pending@example.invalid',role='pharmacist')
        p=Pharmacist.objects.create(user=other,license_number='SYNTHETIC-NOT-VERIFIED',permissions=['prescription_review'])
        self.assertEqual(p.credential_status,'pending');self.assertFalse(p.credential_is_current)

    def test_edit_via_admin_user_api_clears_prior_verification(self):
        self.client.force_authenticate(self.maker)
        r=self.client.patch(f'/api/admin/users/{self.pharmacist.pk}/',{'pharmacist_license_number':'SYNTHETIC-CHANGED'},format='json')
        self.assertEqual(r.status_code,200,r.data)
        self.assertFalse(can_review(self.pharmacist))
