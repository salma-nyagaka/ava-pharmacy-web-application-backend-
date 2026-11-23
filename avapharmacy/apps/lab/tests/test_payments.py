from unittest.mock import patch
from django.test import override_settings
from django.urls import reverse
from rest_framework.test import APITestCase
from apps.lab.tests import test_workflow_security as fixtures
from apps.lab.models import LabPayment, LabRequest


@override_settings(LAB_MPESA_CALLBACK_URL='https://api.example.test/lab/payments/mpesa/callback/')
class LabPaymentTests(APITestCase):
    setUp = fixtures.LabWorkflowSecurityTests.setUp
    make_user = staticmethod(fixtures.LabWorkflowSecurityTests.make_user)
    authenticate = fixtures.LabWorkflowSecurityTests.authenticate

    def booking(self):
        return LabRequest.objects.create(test=self.test, patient=self.patient, patient_name='QA', patient_phone='0700000000', channel='collection', collection_fee_amount=200, quoted_test_price=1500)

    @patch('apps.lab.payments.MpesaClient')
    def test_collection_then_selected_lab_test_fee_and_duplicate_protection(self, client):
        booking = self.booking(); self.authenticate(self.patient)
        client.return_value.initiate_stk_push.return_value = ('254700000000', {'CheckoutRequestID':'qa-checkout', 'MerchantRequestID':'qa-merchant'})
        client.return_value.query_stk_status.return_value = {'ResultCode':0}
        url = reverse('lab-payment-create', args=[booking.pk])
        self.assertEqual(self.client.post(url, {'stage':'test'}, format='json').status_code, 400)
        result = self.client.post(url, {'stage':'collection'}, format='json')
        self.assertEqual(result.status_code, 201, result.content)
        self.assertEqual(result.data['amount'], '200.00')
        repeated = self.client.post(url, {'stage':'collection'}, format='json')
        self.assertEqual(repeated.data['id'], result.data['id'])
        self.assertEqual(client.return_value.initiate_stk_push.call_count, 1)
        sync = self.client.post(reverse('lab-payment-sync', args=[result.data['id']]))
        self.assertEqual(sync.data['status'], 'succeeded')
        booking.refresh_from_db(); self.assertEqual(booking.payment_status, 'pending')
        booking.laboratory = self.facility; booking.assigned_partner = self.partner; booking.save()
        result = self.client.post(url, {'stage':'test'}, format='json')
        self.assertEqual(result.data['amount'], '1500.00')
        self.client.post(reverse('lab-payment-sync', args=[result.data['id']]))
        booking.refresh_from_db(); self.assertEqual(booking.payment_status, 'paid')

    def test_unpaid_collection_cannot_be_assigned_and_other_user_cannot_pay(self):
        booking = self.booking(); self.authenticate(self.admin)
        result = self.client.patch(reverse('lab-request-update', args=[booking.pk]), {'assigned_partner':self.partner.pk}, format='json')
        self.assertEqual(result.status_code, 400)
        self.authenticate(self.other_patient)
        self.assertEqual(self.client.post(reverse('lab-payment-create', args=[booking.pk]), {'stage':'collection'}, format='json').status_code, 404)

    @patch('apps.orders.views._trusted_mpesa_callback', return_value=True)
    def test_callback_checks_amount_and_is_idempotent(self, trusted):
        booking = self.booking()
        payment = LabPayment.objects.create(request=booking, stage='collection', amount=200, checkout_request_id='qa', merchant_request_id='merchant')
        payload = {'Body':{'stkCallback':{'CheckoutRequestID':'qa','MerchantRequestID':'merchant','ResultCode':0,'ResultDesc':'Success','CallbackMetadata':{'Item':[{'Name':'Amount','Value':1},{'Name':'MpesaReceiptNumber','Value':'QA-RECEIPT'}]}}}}
        url = reverse('lab-payment-callback')
        self.assertEqual(self.client.post(url, payload, format='json').status_code, 400)
        payload['Body']['stkCallback']['CallbackMetadata']['Item'][0]['Value'] = 200
        self.assertEqual(self.client.post(url, payload, format='json').status_code, 200)
        self.assertEqual(self.client.post(url, payload, format='json').status_code, 200)
        payment.refresh_from_db(); self.assertEqual(payment.status, 'succeeded')

    @override_settings(LAB_COLLECTION_FEE='1.00')
    def test_new_booking_uses_temporary_backend_collection_fee(self):
        doctor, consultation = fixtures.ordering_consultation(self)
        self.authenticate(doctor)
        response = self.client.post(reverse('lab-requests'), {'test':self.test.pk, 'consultation':consultation.pk, 'assigned_partner':self.partner.pk, 'patient_name':'QA', 'patient_phone':'0700000000', 'channel':'collection', 'collection_address':'Synthetic QA address'}, format='json')
        self.assertEqual(response.status_code, 201, response.content)
        booking = LabRequest.objects.get(pk=response.data['id'])
        self.assertEqual(str(booking.collection_fee_amount), '1.00')
        self.assertEqual(response.data['collection_fee'], '1.00')
