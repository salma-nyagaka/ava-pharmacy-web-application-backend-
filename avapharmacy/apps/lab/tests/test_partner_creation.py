"""Partner-to-laboratory creation journey using only synthetic test records."""
import re
import tempfile
from datetime import timedelta

from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.lab.models import LabPartner, LaboratoryFacility


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class PartnerLaboratoryCreationTests(APITestCase):
    def setUp(self):
        media = tempfile.TemporaryDirectory(prefix='ava-lab-creation-')
        self.addCleanup(media.cleanup)
        settings_override = override_settings(MEDIA_ROOT=media.name)
        settings_override.enable()
        self.addCleanup(settings_override.disable)
        self.admin = User.objects.create_user(email='creation-admin@example.test', role='admin', status='active')
        self.patient = User.objects.create_user(email='creation-patient@example.test', role='customer', status='active')
        self.expiry = str(timezone.localdate() + timedelta(days=365))

    def partner_payload(self):
        return {'name': 'SYNTHETIC Creation Diagnostics', 'email': 'creation-partner@example.test', 'phone': '0700000901', 'license_number': 'SYNTHETIC-PARTNER-001', 'license_expiry': self.expiry, 'documents': [SimpleUploadedFile('synthetic-licence.pdf', b'%PDF-1.4\nSynthetic test fixture', content_type='application/pdf')]}

    def facility_payload(self):
        return {'name': 'SYNTHETIC Creation Laboratory', 'email': 'creation-lab@example.test', 'phone': '0700000902', 'county': 'Nairobi', 'address': 'Synthetic QA Address', 'license_number': 'SYNTHETIC-FACILITY-001', 'license_expiry': self.expiry, 'supported_counties': '["Nairobi"]', 'accreditation': 'QA Accreditation', 'operating_hours': '{"monday_friday":"08:00-17:00","saturday":"Closed"}', 'home_collection_enabled': False, 'physical_result_pickup_enabled': False, 'registration_document': SimpleUploadedFile('lab-licence.pdf', b'%PDF-1.4 QA', content_type='application/pdf')}

    def test_admin_creates_partner_then_activated_partner_creates_lab(self):
        self.client.force_authenticate(self.admin)
        response = self.client.post(reverse('admin-lab-partners'), self.partner_payload(), format='multipart')
        self.assertEqual(response.status_code, 201, response.content)
        partner = LabPartner.objects.get(pk=response.data['id'])
        self.assertEqual(partner.status, 'pending')
        self.assertIsNone(partner.user_id)
        self.assertEqual(partner.created_by_id, self.admin.pk)
        self.assertEqual(partner.documents.count(), 1)
        response = self.client.post(reverse('admin-lab-partner-action', args=[partner.pk]), {'action': 'verify'}, format='json')
        self.assertEqual(response.status_code, 200, response.content)
        response = self.client.post(reverse('admin-lab-partner-provision-account', args=[partner.pk]), {}, format='json')
        self.assertEqual(response.status_code, 201, response.content)
        message = next(item for item in reversed(mail.outbox) if partner.email in item.to and '/activate/' in item.body)
        token = re.search(r'/activate/([^/\s]+)/', message.body).group(1)
        self.client.force_authenticate(None)
        response = self.client.post(reverse('professional-activate'), {'token': token, 'new_password': 'SyntheticLabPass123!', 'new_password_confirm': 'SyntheticLabPass123!', 'accepted_terms': True}, format='json')
        self.assertEqual(response.status_code, 200, response.content)
        partner.refresh_from_db()
        self.client.force_authenticate(partner.user)
        response = self.client.post(reverse('lab-partner-facilities'), self.facility_payload(), format='multipart')
        self.assertEqual(response.status_code, 201, response.content)
        facility = LaboratoryFacility.objects.get(pk=response.data['id'])
        self.assertEqual(facility.partner_id, partner.pk)
        self.assertEqual(facility.status, 'pending')
        response = self.client.post(reverse('lab-partner-facility-documents', args=[facility.pk]), {'name': 'Synthetic facility licence', 'file': SimpleUploadedFile('facility.pdf', b'%PDF-1.4\nSynthetic test fixture', content_type='application/pdf')}, format='multipart')
        self.assertEqual(response.status_code, 201, response.content)
        self.client.force_authenticate(self.admin)
        response = self.client.post(reverse('admin-lab-facility-action', args=[facility.pk]), {'action': 'verify'}, format='json')
        self.assertEqual(response.status_code, 200, response.content)
        facility.refresh_from_db(); self.assertEqual(facility.status, 'verified')

    def test_partner_creation_requires_documents_and_admin(self):
        self.client.force_authenticate(self.patient)
        self.assertEqual(self.client.post(reverse('admin-lab-partners'), self.partner_payload(), format='multipart').status_code, 403)
        self.client.force_authenticate(self.admin)
        payload = self.partner_payload(); del payload['documents']
        self.assertEqual(self.client.post(reverse('admin-lab-partners'), payload, format='multipart').status_code, 400)
        self.assertEqual(LabPartner.objects.count(), 0)

    def test_unverified_partner_cannot_register_laboratory(self):
        user = User.objects.create_user(email='pending-partner@example.test', role='lab_partner', status='active')
        LabPartner.objects.create(user=user, name='SYNTHETIC Pending Partner', email=user.email, phone='0700000903')
        self.client.force_authenticate(user)
        response = self.client.post(reverse('lab-partner-facilities'), self.facility_payload(), format='multipart')
        self.assertIn(response.status_code, (400, 403), response.content)
        self.assertEqual(LaboratoryFacility.objects.count(), 0)

    def test_ui_approval_provisions_login_and_all_labs_are_visible_to_admin(self):
        self.client.force_authenticate(self.admin)
        created = self.client.post(reverse('admin-lab-partners'), self.partner_payload(), format='multipart')
        self.assertEqual(created.status_code, 201, created.content)
        partner = LabPartner.objects.get(pk=created.data['id'])
        approved = self.client.post(reverse('admin-lab-partner-action', args=[partner.pk]), {'action': 'verify', 'provision_account': True}, format='json')
        self.assertEqual(approved.status_code, 200, approved.content)
        partner.refresh_from_db()
        self.assertIsNotNone(partner.user_id)
        self.assertFalse(partner.user.is_active)
        self.assertEqual(partner.user.role, 'lab_partner')
        self.assertTrue(any(partner.email in item.to and '/activate/' in item.body for item in mail.outbox))
        email_count = len(mail.outbox)
        repeated = self.client.post(reverse('admin-lab-partner-action', args=[partner.pk]), {'action': 'verify', 'provision_account': True}, format='json')
        self.assertEqual(repeated.status_code, 200)
        self.assertEqual(len(mail.outbox), email_count)
        facility = LaboratoryFacility.objects.create(partner=partner, name='SYNTHETIC Pending Lab', phone='0700000902', county='Nairobi', address='QA')
        response = self.client.get(reverse('admin-lab-facilities'))
        self.assertEqual(response.status_code, 200)
        rows = response.data.get('results', []) if isinstance(response.data, dict) else response.data
        self.assertTrue(any(row['id'] == facility.pk and row['partner'] == partner.pk and row['status'] == 'pending' for row in rows))

    def test_account_conflict_keeps_application_pending(self):
        self.client.force_authenticate(self.admin)
        created = self.client.post(reverse('admin-lab-partners'), self.partner_payload(), format='multipart')
        partner = LabPartner.objects.get(pk=created.data['id'])
        User.objects.create_user(email=partner.email, role='customer')
        response = self.client.post(reverse('admin-lab-partner-action', args=[partner.pk]), {'action': 'verify', 'provision_account': True}, format='json')
        self.assertEqual(response.status_code, 400, response.content)
        partner.refresh_from_db()
        self.assertEqual(partner.status, 'pending')
        self.assertIsNone(partner.user_id)

    def test_every_creation_field_is_required_and_invalid_submission_saves_nothing(self):
        from apps.lab.serializers import LaboratoryFacilitySerializer
        required = ('name', 'email', 'phone', 'county', 'address', 'accreditation', 'license_number', 'license_expiry', 'supported_counties', 'operating_hours', 'home_collection_enabled', 'physical_result_pickup_enabled', 'registration_document')
        for field in required:
            with self.subTest(field=field):
                payload = self.facility_payload()
                payload['supported_counties'] = ['Nairobi']
                payload['operating_hours'] = {'monday_friday': '08:00-17:00', 'saturday': 'Closed'}
                del payload[field]
                serializer = LaboratoryFacilitySerializer(data=payload)
                self.assertFalse(serializer.is_valid(), field)
                self.assertIn(field, serializer.errors)
        self.assertEqual(LaboratoryFacility.objects.count(), 0)

    def test_pickup_instructions_required_only_if_physical_pickup_enabled(self):
        from apps.lab.serializers import LaboratoryFacilitySerializer
        payload = self.facility_payload()
        payload['supported_counties'] = ['Nairobi']
        payload['operating_hours'] = {'monday_friday': '08:00-17:00', 'saturday': 'Closed'}
        serializer = LaboratoryFacilitySerializer(data=payload)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        payload['physical_result_pickup_enabled'] = True
        serializer = LaboratoryFacilitySerializer(data=payload)
        self.assertFalse(serializer.is_valid())
        self.assertIn('pickup_instructions', serializer.errors)
