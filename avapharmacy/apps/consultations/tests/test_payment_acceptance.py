from avapharmacy.test_compliance_fixtures import clinician_fixture
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.consultations.models import ChildPatient, ClinicianProfile, Consultation, ConsultationPaymentIntent
from apps.orders.mpesa import MpesaClient, MpesaConfigurationError


class ConsultationPaymentAcceptanceTests(TestCase):
    def setUp(self):
        self.guardian = User.objects.create_user(email='measure-guardian@example.test', role='customer')
        self.other = User.objects.create_user(email='measure-other@example.test', role='customer')
        self.user = User.objects.create_user(email='measure-ped@example.test', role='pediatrician')
        self.provider = ClinicianProfile.objects.create(user=self.user, provider_type='pediatrician', status='active', name='QA Pediatrician', consult_fee=500,**clinician_fixture(exclude=('user', 'provider_type', 'status', 'name', 'consult_fee')))
        self.child = ChildPatient.objects.create(guardian=self.guardian, first_name='QA Alpha', age_years=6, weight_kg=Decimal('21.5'), height_cm=Decimal('110.5'), bmi=Decimal('17.61'), muac_cm=Decimal('15.5'), blood_glucose_mmol_l=Decimal('4.8'))
        self.client = APIClient()
        self.client.force_authenticate(self.guardian)

    @patch('apps.consultations.views.MpesaClient')
    def test_all_measurements_survive_payment_intent_and_finalize(self, mpesa):
        mpesa.return_value.initiate_stk_push.return_value = ('254708374149', {'ResponseCode': '0', 'CheckoutRequestID': 'qa-stk', 'MerchantRequestID': 'qa-merchant'})
        response = self.client.post(reverse('consultation-payment-intents'), {'provider': 'mpesa', 'phone': '0708374149', 'consultation': {'pediatrician': self.provider.pk, 'child_patient_id': self.child.pk, 'patient_name': 'QA Guardian', 'issue': 'Synthetic QA'}}, format='json')
        self.assertEqual(response.status_code, 201, response.content)
        intent = ConsultationPaymentIntent.objects.get(pk=response.data['id'])
        self.assertEqual(intent.amount, Decimal('500'))
        self.assertEqual(intent.consultation_payload['height_cm'], '110.50')
        self.assertEqual(intent.consultation_payload['blood_glucose_mmol_l'], '4.80')
        self.assertEqual(self.client.post(reverse('consultation-payment-finalize'), {'payment_intent_id': intent.pk}, format='json').status_code, 402)
        intent.status = 'succeeded'
        intent.save()
        for _ in range(2):
            result = self.client.post(reverse('consultation-payment-finalize'), {'payment_intent_id': intent.pk}, format='json')
            self.assertEqual(result.status_code, 201, result.content)
        self.assertEqual(Consultation.objects.filter(child_patient=self.child).count(), 1)
        consultation = Consultation.objects.get(child_patient=self.child)
        self.assertEqual(consultation.height_cm, self.child.height_cm)
        self.assertEqual(result.data['child_snapshot']['height_cm'], '110.50')
        self.assertEqual(result.data['guardian_snapshot']['id'], self.guardian.pk)
        self.assertEqual(consultation.patient_id, self.guardian.pk)
        self.client.force_authenticate(self.other)
        self.assertEqual(self.client.post(reverse('consultation-payment-finalize'), {'payment_intent_id': intent.pk}, format='json').status_code, 404)

    @override_settings(MPESA_CALLBACK_SECRET='qa-callback-token')
    def test_callback_authentication_amount_and_replays(self):
        intent = ConsultationPaymentIntent.objects.create(initiated_by=self.guardian, clinician=self.provider, provider='mpesa', amount=500, checkout_request_id='qa-callback', merchant_request_id='qa-merchant', consultation_payload={'pediatrician': self.provider.pk, 'child_patient_id': self.child.pk, 'patient_name': 'QA Guardian', 'issue': 'Synthetic QA'})
        payload = {'Body': {'stkCallback': {'CheckoutRequestID': 'qa-callback', 'MerchantRequestID': 'qa-merchant', 'ResultCode': 0, 'CallbackMetadata': {'Item': [{'Name': 'Amount', 'Value': 1}, {'Name': 'MpesaReceiptNumber', 'Value': 'SIMULATED-QA'}]}}}}
        url = reverse('consultation-payment-mpesa-callback')
        self.client.force_authenticate(None)
        self.assertEqual(self.client.post(url, payload, format='json').status_code, 403)
        headers = {'HTTP_X_AVA_MPESA_SECRET': 'qa-callback-token'}
        self.assertEqual(self.client.post(url, payload, format='json', **headers).status_code, 400)
        intent.refresh_from_db()
        self.assertNotEqual(intent.status, 'succeeded')
        payload['Body']['stkCallback']['CallbackMetadata']['Item'][0]['Value'] = 500
        self.assertEqual(self.client.post(url, payload, format='json', **headers).status_code, 200)
        self.assertEqual(self.client.post(url, payload, format='json', **headers).status_code, 200)
        payload['Body']['stkCallback']['ResultCode'] = 1032
        self.assertEqual(self.client.post(url, payload, format='json', **headers).status_code, 200)
        intent.refresh_from_db()
        self.assertEqual(intent.status, 'succeeded')
        self.assertEqual(Consultation.objects.filter(child_patient=self.child).count(), 1)

    def test_child_age_and_measurement_validation(self):
        from datetime import timedelta
        from django.utils import timezone
        url = reverse('guardian-children')
        for extra in [{'age_years': 19}, {'age_years': 6, 'weight_kg': '-1'}, {'date_of_birth': (timezone.localdate() + timedelta(days=1)).isoformat()}]:
            with self.subTest(extra=extra):
                response = self.client.post(url, {'first_name': 'Invalid QA', **extra}, format='json')
                self.assertEqual(response.status_code, 400)
        birth = timezone.localdate().replace(year=timezone.localdate().year - 6)
        response = self.client.post(url, {'first_name': 'DOB QA', 'date_of_birth': birth.isoformat()}, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['age_years'], 6)

    @patch('apps.consultations.views.MpesaClient')
    def test_booking_consent_is_preserved_through_payment_and_finalization(self, mpesa):
        mpesa.return_value.initiate_stk_push.return_value = ('254708374149', {'ResponseCode': '0', 'CheckoutRequestID': 'qa-consent', 'MerchantRequestID': 'qa-consent-merchant'})
        response = self.client.post(reverse('consultation-payment-intents'), {'provider': 'mpesa', 'phone': '0708374149', 'consultation': {'pediatrician': self.provider.pk, 'child_patient_id': self.child.pk, 'patient_name': 'QA Guardian', 'guardian_consent': True, 'issue': 'Synthetic consent QA'}}, format='json')
        self.assertEqual(response.status_code, 201, response.content)
        intent = ConsultationPaymentIntent.objects.get(pk=response.data['id'])
        self.assertIs(intent.consultation_payload['guardian_consent'], True)
        intent.status = 'succeeded'
        intent.save()
        for _ in range(2):
            finalized = self.client.post(reverse('consultation-payment-finalize'), {'payment_intent_id': intent.pk}, format='json')
            self.assertEqual(finalized.status_code, 201, finalized.content)
            self.assertEqual(finalized.data['consent_status'], 'granted')
        self.assertEqual(Consultation.objects.filter(child_patient=self.child).count(), 1)
        self.client.force_authenticate(self.user)
        rows = self.client.get(reverse('doctor-consultations')).data
        if isinstance(rows, dict):
            rows = rows['results']
        self.assertEqual(rows[0]['patient'], self.guardian.pk)

    def test_booking_does_not_invent_guardian_consent(self):
        intent = ConsultationPaymentIntent.objects.create(initiated_by=self.guardian, clinician=self.provider, provider='mpesa', status='succeeded', amount=500, consultation_payload={'pediatrician': self.provider.pk, 'child_patient_id': self.child.pk, 'patient_name': 'QA Guardian', 'issue': 'Synthetic pending consent QA'})
        response = self.client.post(reverse('consultation-payment-finalize'), {'payment_intent_id': intent.pk}, format='json')
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(response.data['consent_status'], 'pending')

    @patch('apps.consultations.views.MpesaClient')
    def test_provider_connection_error_keeps_payment_pending(self, mpesa):
        from apps.orders.mpesa import MpesaAPIError
        intent = ConsultationPaymentIntent.objects.create(initiated_by=self.guardian, clinician=self.provider, provider='mpesa', status='requires_action', amount=500, checkout_request_id='ped-network-drop')
        mpesa.return_value.query_stk_status.side_effect = MpesaAPIError('Provider disconnected')
        response = self.client.post(reverse('consultation-payment-intent-sync', args=[intent.pk]), {}, format='json')
        self.assertEqual(response.status_code, 202, response.content)
        intent.refresh_from_db()
        self.assertEqual(intent.status, 'requires_action')
        self.assertIsNone(intent.consultation_id)

    def test_other_guardian_cannot_read_or_book_child(self):
        self.client.force_authenticate(self.other)
        self.assertEqual(self.client.get(reverse('guardian-child-detail', args=[self.child.pk])).status_code, 404)
        response = self.client.post(reverse('consultation-payment-intents'), {'provider': 'mpesa', 'phone': '0708374149', 'consultation': {'pediatrician': self.provider.pk, 'child_patient_id': self.child.pk, 'patient_name': 'QA Other', 'issue': 'Synthetic QA'}}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertFalse(ConsultationPaymentIntent.objects.exists())

    def test_history_groups_same_child_and_separates_sibling(self):
        sibling = ChildPatient.objects.create(guardian=self.guardian, first_name='QA Alpha', age_years=3)
        for child in [self.child, self.child, sibling]:
            Consultation.objects.create(patient=self.guardian, clinician=self.provider, child_patient=child, patient_name='QA Guardian', child_name=child.full_name, issue='Synthetic QA')
        self.client.force_authenticate(self.user)
        response = self.client.get(reverse('pediatrician-patients'))
        self.assertEqual(response.status_code, 200)
        rows = response.data['results']
        counts = {row['child']['id']: row['consultations_count'] for row in rows}
        self.assertEqual(counts, {self.child.pk: 2, sibling.pk: 1})
        unrelated = User.objects.create_user(email='unrelated-ped@example.test', role='pediatrician')
        ClinicianProfile.objects.create(user=unrelated, provider_type='pediatrician', status='active', name='Other',**clinician_fixture(exclude=('user', 'provider_type', 'status', 'name')))
        self.client.force_authenticate(unrelated)
        self.assertEqual(self.client.get(reverse('pediatrician-patient-detail', args=[self.child.pk])).status_code, 404)


@override_settings(MPESA_CONSUMER_KEY='qa-key', MPESA_CONSUMER_SECRET='qa-secret', MPESA_SHORTCODE='174379', MPESA_PASSKEY='qa-pass', MPESA_CALLBACK_SECRET='qa-callback-token', MPESA_CALLBACK_URL='https://example.test/callback/', MPESA_REQUIRE_PUBLIC_CALLBACK_URLS=True)
class ConsultationCallbackConfigurationTests(TestCase):
    def test_callback_override_retains_authentication(self):
        client = MpesaClient()
        with patch.object(client, '_post', return_value={'ResponseCode': '0'}) as post:
            client.initiate_stk_push(SimpleNamespace(amount=500), '0708374149', 'QA', 'QA', callback_url='https://example.test/consultation/')
        url = post.call_args.args[1]['CallBackURL']
        self.assertEqual(urlsplit(url).path, '/consultation/')
        self.assertEqual(parse_qs(urlsplit(url).query)['token'], ['qa-callback-token'])

    def test_localhost_override_is_rejected_before_provider_request(self):
        client = MpesaClient()
        with patch.object(client, '_post') as post, self.assertRaises(MpesaConfigurationError):
            client.initiate_stk_push(SimpleNamespace(amount=500), '0708374149', 'QA', 'QA', callback_url='http://127.0.0.1:8000/callback/')
        post.assert_not_called()
