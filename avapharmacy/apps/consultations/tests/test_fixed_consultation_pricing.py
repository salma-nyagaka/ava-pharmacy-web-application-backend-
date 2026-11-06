from decimal import Decimal
from django.test import TestCase
from apps.accounts.models import User
from apps.consultations.models import ClinicianProfile, Consultation
from apps.consultations.views import _clinician_net_earning_amount


class FixedConsultationPricingTests(TestCase):
    def setUp(self):
        self.patient=User.objects.create_user(email='fixed-patient@example.test')
        self.profile=ClinicianProfile.objects.create(name='Fixed doctor',provider_type='doctor',consult_fee=900,commission=15)

    def test_new_consultation_snapshots_fixed_split_and_ignores_percentage(self):
        self.assertEqual(self.profile.consult_fee,1500)
        consultation=Consultation.objects.create(patient=self.patient,clinician=self.profile)
        self.assertEqual((consultation.agreed_total,consultation.agreed_clinician_share),(1500,1000))
        self.assertEqual(_clinician_net_earning_amount(self.profile,Decimal('1500'),consultation),1000)
        self.assertEqual(consultation.agreed_total-consultation.agreed_clinician_share,500)
        self.profile.commission=99;self.profile.save()
        self.assertEqual(_clinician_net_earning_amount(self.profile,Decimal('1500'),consultation),1000)

    def test_underpayment_does_not_create_clinician_earning(self):
        consultation=Consultation.objects.create(patient=self.patient,clinician=self.profile)
        self.assertEqual(_clinician_net_earning_amount(self.profile,Decimal('1499'),consultation),0)

    def test_legacy_agreements_are_not_repriced(self):
        consultation=Consultation.objects.create(patient=self.patient,clinician=self.profile)
        Consultation.objects.filter(pk=consultation.pk).update(agreed_total=None,agreed_clinician_share=None)
        consultation.refresh_from_db()
        self.assertEqual(_clinician_net_earning_amount(self.profile,Decimal('1000'),consultation),Decimal('850'))

    def test_pediatrician_uses_same_patient_fee(self):
        profile=ClinicianProfile.objects.create(name='Fixed pediatrician',provider_type='pediatrician',consult_fee=700)
        self.assertEqual(profile.consult_fee,1500)
        self.assertEqual(_clinician_net_earning_amount(profile),1000)

    def test_payment_started_before_pricing_change_keeps_legacy_agreement(self):
        from unittest.mock import MagicMock, patch
        from apps.consultations.models import ConsultationPaymentIntent
        from apps.consultations.views import _create_paid_consultation_from_intent
        consultation=Consultation.objects.create(patient=self.patient,clinician=self.profile)
        intent=MagicMock(consultation_id=None,status=ConsultationPaymentIntent.STATUS_SUCCEEDED,consultation_payload={},initiated_by=self.patient)
        with patch('apps.consultations.views.ConsultationCreateSerializer') as serializer:
            serializer.return_value.save.return_value=consultation
            result=_create_paid_consultation_from_intent(intent)
        result.refresh_from_db()
        self.assertIsNone(result.agreed_total)
        self.assertEqual(_clinician_net_earning_amount(self.profile,Decimal('1000'),result),Decimal('850'))
