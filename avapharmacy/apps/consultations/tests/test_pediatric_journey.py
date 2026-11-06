from avapharmacy.test_compliance_fixtures import inventory_fixture
from avapharmacy.test_compliance_fixtures import catalogue_fixture
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.urls import reverse
from apps.consultations.models import ConsultationPaymentIntent, Consultation, ClinicianEarning
from apps.notifications.models import Notification
from apps.prescriptions.models import Prescription
from apps.products.models import Product, Variant, VariantInventory
from . import test_payment_acceptance as fixtures


@override_settings(MPESA_CALLBACK_SECRET='pediatric-qa-callback')
class PediatricJourneyTests(TestCase):
    setUp = fixtures.ConsultationPaymentAcceptanceTests.setUp

    @patch('apps.consultations.views.MpesaClient')
    def test_guardian_consent_paid_child_chat_prescription_completion_and_earning(self, mpesa):
        self.provider.consult_fee = Decimal('1.00')
        self.provider.commission = Decimal('10.00')
        self.provider.save()
        mpesa.return_value.initiate_stk_push.return_value = ('254708374149', {'ResponseCode': '0', 'CheckoutRequestID': 'ped-journey-stk', 'MerchantRequestID': 'ped-journey-merchant'})
        response = self.client.post(reverse('consultation-payment-intents'), {'provider': 'mpesa', 'phone': '0708374149', 'consultation': {'pediatrician': self.provider.pk, 'child_patient_id': self.child.pk, 'patient_name': 'Synthetic Guardian', 'guardian_consent': True, 'issue': 'SYNTHETIC pediatric journey QA'}}, format='json')
        self.assertEqual(response.status_code, 201, response.content)
        intent_id = response.data['id']
        self.assertEqual(self.client.post(reverse('consultation-payment-finalize'), {'payment_intent_id': intent_id}, format='json').status_code, 402)
        payload = {'Body': {'stkCallback': {'CheckoutRequestID': 'ped-journey-stk', 'MerchantRequestID': 'ped-journey-merchant', 'ResultCode': 0, 'CallbackMetadata': {'Item': [{'Name': 'Amount', 'Value': 1}, {'Name': 'MpesaReceiptNumber', 'Value': 'SIMULATED-PEDIATRIC-JOURNEY'}]}}}}
        self.client.force_authenticate(None)
        for _ in range(2):
            self.assertEqual(self.client.post(reverse('consultation-payment-mpesa-callback'), payload, format='json', HTTP_X_AVA_MPESA_SECRET='pediatric-qa-callback').status_code, 200)
        intent = ConsultationPaymentIntent.objects.get(pk=intent_id)
        consultation = Consultation.objects.get(pk=intent.consultation_id)
        self.assertEqual(Consultation.objects.filter(child_patient=self.child).count(), 1)
        self.assertEqual(consultation.consent_status, 'granted')
        self.assertEqual(consultation.patient_id, self.guardian.pk)
        self.assertEqual(consultation.child_snapshot['id'], self.child.pk)
        for user in [self.guardian, self.user]:
            self.client.force_authenticate(user)
            self.assertEqual(self.client.get(reverse('consultation-detail', args=[consultation.pk])).status_code, 200)
            self.assertEqual(self.client.post(reverse('consultation-messages', args=[consultation.pk]), {'message': 'SYNTHETIC QA chat'}, format='json').status_code, 201)
        product = Product.objects.create(name='SYNTHETIC pediatric training item', sku='PED-JOURNEY-QA', slug='ped-journey-qa', is_active=True)
        variant = Variant.objects.create(product=product, name='QA exact pack', sku='PED-JOURNEY-QA-EXACT', price=1, requires_prescription=True, is_active=True,**catalogue_fixture(medicine=True, exclude=('product', 'name', 'sku', 'price', 'requires_prescription', 'is_active')))
        VariantInventory.objects.create(variant=variant, location=Product.STOCK_BRANCH, stock_quantity=4,**inventory_fixture(exclude=('variant', 'location', 'stock_quantity')))
        prescription = self.client.post(reverse('pediatrician-prescriptions'), {'consultation': consultation.pk, 'patient_name': self.child.full_name, 'items': [{'variant_id': variant.pk, 'dose': 'SYNTHETIC QA only', 'quantity': 1}], 'notes': 'No real clinical instructions.'}, format='json')
        self.assertEqual(prescription.status_code, 201, prescription.content)
        prescription_id = prescription.data['id']
        self.assertEqual(self.client.post(reverse('pediatrician-prescription-send', args=[prescription_id]), {}, format='json').status_code, 200)
        rx = Prescription.objects.get(clinician_prescription_id=prescription_id)
        self.assertEqual(rx.patient_id, self.guardian.pk)
        self.assertEqual(rx.patient_name, self.child.full_name)
        self.assertEqual(rx.items.get().variant_id, variant.pk)
        self.assertTrue(Notification.objects.filter(recipient=self.guardian, data__prescription_id=rx.pk).exists())
        for _ in range(2):
            self.assertEqual(self.client.post(reverse('consultation-end', args=[consultation.pk]), {}, format='json').status_code, 200)
        self.assertEqual(ClinicianEarning.objects.filter(consultation=consultation).count(), 1)
        self.assertEqual(ClinicianEarning.objects.get(consultation=consultation).amount, Decimal('0.90'))
        self.client.force_authenticate(self.guardian)
        completed = self.client.get(reverse('consultation-detail', args=[consultation.pk]))
        self.assertEqual(completed.data['status'], 'completed')
        self.assertEqual(completed.data['child_patient'], self.child.pk)
