from unittest.mock import AsyncMock

from asgiref.sync import async_to_sync
from django.test import TestCase, SimpleTestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.consultations.access import can_access_chat
from apps.consultations.consumers import ConsultationConsumer
from apps.consultations.models import ClinicianProfile, Consultation, ConsultationMessage
from apps.consultations.serializers import ConsultationMessageSerializer


class ConsultationPrivacyTests(TestCase):
    def setUp(self):
        self.patient = User.objects.create_user(email='privacy-patient@example.test', role='customer')
        self.other = User.objects.create_user(email='privacy-other@example.test', role='customer')
        self.clinician_user = User.objects.create_user(email='privacy-doctor@example.test', role='doctor')
        self.clinician = ClinicianProfile.objects.create(
            user=self.clinician_user, provider_type='doctor', name='QA Doctor',
            status='active', id_number='PRIVATE-ID', payout_account='PRIVATE-PAYOUT',
        )
        self.consultation = Consultation.objects.create(patient=self.patient, clinician=self.clinician, patient_name='QA Patient', issue='QA')
        self.client = APIClient()

    def test_public_profiles_exclude_private_fields_and_ineligible_accounts(self):
        for provider_type, endpoint, listing in [('doctor', 'doctor-detail', 'doctors'), ('pediatrician', 'pediatrician-detail', 'pediatricians')]:
            with self.subTest(provider_type=provider_type):
                self.clinician.provider_type = provider_type
                self.clinician.status = 'active'
                self.clinician.save()
                self.clinician_user.is_active = True
                self.clinician_user.save()
                response = self.client.get(reverse(endpoint, args=[self.clinician.pk]))
                self.assertEqual(response.status_code, 200)
                for field in ['payout_account', 'id_number', 'documents', 'date_of_birth', 'background_consent']:
                    self.assertNotIn(field, response.data)
                self.clinician_user.is_active = False
                self.clinician_user.save()
                self.assertEqual(self.client.get(reverse(endpoint, args=[self.clinician.pk])).status_code, 404)
                self.assertNotIn('QA Doctor', str(self.client.get(reverse(listing)).data))
                self.clinician_user.is_active = True
                self.clinician_user.save()
                self.clinician.status = 'pending'
                self.clinician.save()
                self.assertEqual(self.client.get(reverse(endpoint, args=[self.clinician.pk])).status_code, 404)

    def test_attachment_uses_protected_url_and_raw_media_is_denied(self):
        message = ConsultationMessage.objects.create(consultation=self.consultation, sender=self.patient, attachment='consultations/messages/private.txt', message_type='file')
        data = ConsultationMessageSerializer(message).data
        self.assertEqual(data['attachment'], reverse('consultation-message-attachment', args=[message.pk]))
        self.assertEqual(self.client.get('/media/consultations/messages/private.txt').status_code, 404)
        self.client.force_authenticate(self.other)
        self.assertEqual(self.client.get(reverse('consultation-message-attachment', args=[message.pk])).status_code, 404)
        self.clinician.status = 'suspended'
        self.clinician.save()
        self.client.force_authenticate(self.clinician_user)
        self.assertEqual(self.client.get(reverse('consultation-message-attachment', args=[message.pk])).status_code, 404)

    def test_open_queue_does_not_expose_contacts_or_snapshots(self):
        from types import SimpleNamespace
        from apps.consultations.serializers import ConsultationListSerializer
        self.consultation.clinician = None
        self.consultation.patient_email = 'private@example.test'
        self.consultation.patient_phone = '0700000000'
        self.consultation.guardian_snapshot = {'email': 'private@example.test'}
        self.consultation.child_snapshot = {'notes': 'private'}
        self.consultation.save()
        data = ConsultationListSerializer(self.consultation, context={'request': SimpleNamespace(user=self.clinician_user)}).data
        self.assertEqual(data['patient_email'], '')
        self.assertEqual(data['patient_phone'], '')
        self.assertEqual(data['child_snapshot'], {})
        self.assertEqual(data['guardian_snapshot'], {})

    def test_chat_membership_and_revocation(self):
        self.assertTrue(can_access_chat(self.patient, self.consultation))
        self.assertTrue(can_access_chat(self.clinician_user, self.consultation))
        self.assertFalse(can_access_chat(self.other, self.consultation))
        self.clinician.status = 'suspended'
        self.assertFalse(can_access_chat(self.clinician_user, self.consultation))
        self.patient.is_active = False
        self.assertFalse(can_access_chat(self.patient, self.consultation))


class ConsultationSocketGateTests(SimpleTestCase):
    def test_unrelated_socket_cannot_join_group(self):
        consumer = ConsultationConsumer()
        consumer.scope = {'url_route': {'kwargs': {'pk': 1}}}
        consumer._authenticate = AsyncMock(return_value=type('UserStub', (), {'pk': 1})())
        consumer._has_access = AsyncMock(return_value=False)
        consumer.close = AsyncMock()
        consumer.channel_layer = AsyncMock()
        consumer.accept = AsyncMock()
        async_to_sync(consumer.connect)()
        consumer.close.assert_awaited_once_with(code=4403)
        consumer.channel_layer.group_add.assert_not_awaited()
        consumer.accept.assert_not_awaited()

    def test_revoked_socket_does_not_receive_or_send_events(self):
        consumer = ConsultationConsumer()
        consumer._has_access = AsyncMock(return_value=False)
        consumer.close = AsyncMock()
        consumer.send_json = AsyncMock()
        consumer.channel_layer = AsyncMock()
        async_to_sync(consumer.consultation_event)({'event_type': 'message', 'payload': {'message': 'private'}})
        async_to_sync(consumer.receive_json)({'type': 'typing.indicator'})
        self.assertEqual(consumer.close.await_count, 2)
        consumer.send_json.assert_not_awaited()
        consumer.channel_layer.group_send.assert_not_awaited()

class ConsultationClinicalRulesTests(TestCase):
    setUp = ConsultationPrivacyTests.setUp

    def test_patient_cannot_set_clinical_status_or_consent(self):
        self.client.force_authenticate(self.patient)
        response = self.client.patch(reverse('consultation-detail', args=[self.consultation.pk]), {'status': 'completed', 'consent_status': 'granted'}, format='json')
        self.assertEqual(response.status_code, 403)
        self.consultation.refresh_from_db()
        self.assertNotEqual(self.consultation.status, 'completed')

    def test_completion_uses_paid_amount_after_fee_changes(self):
        from decimal import Decimal
        from apps.consultations.models import ClinicianEarning, ConsultationPaymentIntent
        ConsultationPaymentIntent.objects.create(initiated_by=self.patient, clinician=self.clinician, consultation=self.consultation, provider='mpesa', status='succeeded', amount=500)
        self.clinician.consult_fee = 1000
        self.clinician.save()
        self.client.force_authenticate(self.clinician_user)
        self.assertEqual(self.client.post(reverse('consultation-end', args=[self.consultation.pk])).status_code, 200)
        self.assertEqual(ClinicianEarning.objects.get(consultation=self.consultation).amount, Decimal('450'))

    def test_fractional_earning_preserves_cents(self):
        from decimal import Decimal
        from apps.consultations.models import ClinicianEarning, ConsultationPaymentIntent
        ConsultationPaymentIntent.objects.create(initiated_by=self.patient, clinician=self.clinician, consultation=self.consultation, provider='mpesa', status='succeeded', amount='1.00')
        self.client.force_authenticate(self.clinician_user)
        self.assertEqual(self.client.post(reverse('consultation-end', args=[self.consultation.pk])).status_code, 200)
        self.assertEqual(ClinicianEarning.objects.get(consultation=self.consultation).amount, Decimal('0.90'))

    def test_patch_completion_records_one_earning(self):
        from apps.consultations.models import ClinicianEarning
        self.client.force_authenticate(self.clinician_user)
        url = reverse('consultation-detail', args=[self.consultation.pk])
        self.assertEqual(self.client.patch(url, {'status': 'completed'}, format='json').status_code, 200)
        self.assertEqual(self.client.patch(url, {'status': 'completed'}, format='json').status_code, 200)
        self.assertEqual(ClinicianEarning.objects.filter(consultation=self.consultation).count(), 1)

    def test_pediatric_prescription_requires_guardian_consent(self):
        from apps.consultations.models import ClinicianPrescription
        self.clinician_user.role = 'pediatrician'
        self.clinician_user.save()
        self.clinician.provider_type = 'pediatrician'
        self.clinician.save()
        self.consultation.is_pediatric = True
        self.consultation.save()
        prescription = ClinicianPrescription.objects.create(clinician=self.clinician, consultation=self.consultation, items=[{'name': 'QA'}])
        self.client.force_authenticate(self.clinician_user)
        response = self.client.post(reverse('doctor-prescription-send', args=[prescription.pk]))
        self.assertEqual(response.status_code, 400)
        self.assertIn('Guardian consent', str(response.data))

    def test_suspended_clinician_cannot_read_private_detail_or_messages(self):
        self.clinician.status = 'suspended'
        self.clinician.save()
        self.client.force_authenticate(self.clinician_user)
        self.assertEqual(self.client.get(reverse('consultation-detail', args=[self.consultation.pk])).status_code, 404)
        self.assertNotIn('QA Patient', str(self.client.get(reverse('consultation-messages', args=[self.consultation.pk])).data))
