from datetime import timedelta
from decimal import Decimal
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient
from apps.accounts.models import User
from apps.payouts.models import Payout, PayoutAuditLog, PayoutRule
from apps.consultations.models import ClinicianProfile, Consultation, ConsultationPaymentIntent, ClinicianEarning
from apps.consultations.serializers import DoctorEarningSerializer


class PayoutAcceptanceTests(TestCase):
    def setUp(self):
        self.client=APIClient()
        self.maker=User.objects.create_user(email='maker-qa@example.test',password='SyntheticQA123!',role='admin')
        self.checker=User.objects.create_user(email='checker-qa@example.test',password='SyntheticQA123!',role='admin')
        self.doctor=User.objects.create_user(email='doctor-qa@example.test',password='SyntheticQA123!',role='doctor',first_name='SYNTHETIC Doctor')
        self.other=User.objects.create_user(email='other-qa@example.test',password='SyntheticQA123!',role='doctor')
        self.patient=User.objects.create_user(email='patient-qa@example.test',password='SyntheticQA123!',role='customer')
        self.client.force_authenticate(self.maker)

    def payload(self,source='SYNTHETIC-QA-001'):
        return {'recipient':self.doctor.pk,'recipient_name':'Spoofed name','role':'doctor','period':'SYNTHETIC QA October 2026','source_type':'manual_adjustment','source_reference':source,'gross_amount':'500.00','commission_amount':'50.00','withholding_amount':'20.00','deduction_amount':'10.00','method':'mpesa','currency':'KES'}

    def create(self,source='SYNTHETIC-QA-001'):
        r=self.client.post(reverse('admin-payouts'),self.payload(source),format='json')
        self.assertEqual(r.status_code,201,r.content)
        return r.data['id']

    def action(self,pk,action,**extra):
        return self.client.post(reverse('admin-payout-action',args=[pk]),{'action':action,**extra},format='json')

    def approve(self,pk):
        self.assertEqual(self.action(pk,'submit').status_code,200)
        self.client.force_authenticate(self.checker)
        self.assertEqual(self.action(pk,'approve').status_code,200)

    def test_calculation_recipient_and_manual_execution(self):
        rule=self.client.post(reverse('admin-payout-rules'),{'role':'doctor','amount':'500.00','currency':'KES','is_active':True},format='json')
        self.assertEqual(rule.status_code,201,rule.content)
        pk=self.create();p=Payout.objects.get(pk=pk)
        self.assertEqual(p.amount,Decimal('420.00'))
        self.assertEqual(p.recipient_name,self.doctor.full_name)
        self.assertEqual(self.client.get(reverse('admin-payout-detail',args=[pk])).data['execution_mode'],'administrative_record')
        self.assertEqual(Payout.objects.count(),1)

    def test_negative_deductions_bad_currency_and_invalid_recipient(self):
        for changes in [{'commission_amount':'-1'},{'withholding_amount':'-1'},{'deduction_amount':'-1'},{'currency':'USD'},{'recipient':None},{'recipient':self.patient.pk},{'source_reference':''},{'source_type':'made_up'},{'source_reference':'CONS-NOT-A-MANUAL-ADJUSTMENT'},{'deduction_amount':'1000'}]:
            payload=self.payload();payload.update(changes)
            self.assertEqual(self.client.post(reverse('admin-payouts'),payload,format='json').status_code,400,changes)
        self.assertEqual(self.client.post(reverse('admin-payout-rules'),{'role':'doctor','amount':'-1'},format='json').status_code,400)

    def test_maker_checker_audit_and_reconciliation_idempotency(self):
        pk=self.create();self.assertEqual(self.action(pk,'submit').status_code,200)
        self.assertEqual(self.action(pk,'approve').status_code,403)
        self.client.force_authenticate(self.checker)
        self.assertEqual(self.action(pk,'approve').status_code,200)
        self.assertEqual(self.action(pk,'process',batch_reference='SYNTHETIC-QA-BATCH').status_code,200)
        r=self.action(pk,'mark_paid',payment_reference='synthetic-qa-ref')
        self.assertEqual(r.status_code,200,r.content);self.assertEqual(r.data['payment_reference'],'SYNTHETIC-QA-REF')
        self.assertEqual(self.action(pk,'mark_paid',payment_reference='synthetic-qa-ref').status_code,409)
        self.assertEqual(self.action(pk,'reconcile').status_code,200)
        self.assertEqual(self.action(pk,'reconcile').status_code,409)
        self.assertEqual(PayoutAuditLog.objects.filter(payout_id=pk).count(),6)
        p=Payout.objects.get(pk=pk)
        self.assertTrue(all([p.created_by_id,p.reviewed_at,p.approved_at,p.submitted_at,p.paid_at]))
        self.assertEqual(p.reconciliation_status,'matched')

    def test_hold_release_requires_reapproval_and_failed_retry(self):
        pk=self.create();self.approve(pk)
        self.assertEqual(self.action(pk,'hold').status_code,400)
        self.assertEqual(self.action(pk,'hold',reason='SYNTHETIC review').status_code,200)
        r=self.action(pk,'release');self.assertEqual(r.status_code,200);self.assertIsNone(r.data['approved_by'])
        self.assertEqual(self.action(pk,'mark_paid',payment_reference='QA').status_code,409)
        self.assertEqual(self.action(pk,'approve').status_code,200)
        self.assertEqual(self.action(pk,'mark_failed',reason='SYNTHETIC failure').status_code,200)
        self.assertEqual(self.action(pk,'submit').status_code,409)
        r=self.action(pk,'retry');self.assertEqual(r.status_code,200);self.assertEqual(r.data['retry_count'],1)
        self.assertEqual(self.action(pk,'retry').status_code,409)
        self.assertEqual(self.action(pk,'mark_paid',payment_reference='SYNTHETIC-QA-RETRY').status_code,200)
        r=self.action(pk,'reverse',reason='SYNTHETIC administrative reversal');self.assertEqual(r.status_code,200);self.assertEqual(r.data['reconciliation_status'],'exception')
        self.assertEqual(self.action(pk,'reverse',reason='Again').status_code,409)
        self.assertEqual(self.action(pk,'mark_paid',payment_reference='OTHER').status_code,409)
        self.assertEqual(Payout.objects.get(pk=pk).amount,Decimal('420'))

    def test_cancelled_source_stays_reserved(self):
        pk=self.create();self.assertEqual(self.action(pk,'cancel',reason='SYNTHETIC cancel').status_code,200)
        self.assertEqual(self.action(pk,'submit').status_code,409)
        self.assertEqual(self.client.post(reverse('admin-payouts'),self.payload(),format='json').status_code,409)

    def test_future_or_pre_request_payment_date_is_rejected(self):
        pk=self.create();self.approve(pk)
        for value in [timezone.now()+timedelta(days=1),timezone.now()-timedelta(days=1)]:
            self.assertEqual(self.action(pk,'mark_paid',payment_reference='SYNTHETIC-QA-DATE',paid_at=value.isoformat()).status_code,400)
        self.assertEqual(Payout.objects.get(pk=pk).status,'approved')

    def test_cross_field_payment_reference_reuse_is_blocked(self):
        one=self.create();two=self.create('SYNTHETIC-QA-002');self.approve(one)
        self.assertEqual(self.action(one,'mark_paid',payment_reference='SYNTHETIC-A',provider_transaction_id='SYNTHETIC-B').status_code,200)
        self.client.force_authenticate(self.maker);self.approve(two)
        self.assertEqual(self.action(two,'mark_paid',payment_reference='synthetic-b',provider_transaction_id='SYNTHETIC-C').status_code,409)

    def test_professional_and_customer_permissions_and_own_ledger(self):
        pk=self.create()
        for user in [self.patient,self.doctor,self.other]:
            self.client.force_authenticate(user)
            for path in [reverse('admin-payouts'),reverse('admin-payout-detail',args=[pk]),reverse('admin-payout-summary'),reverse('admin-payout-rules'),reverse('admin-payout-recipients')]:
                self.assertEqual(self.client.get(path).status_code,403,path)
            self.assertEqual(self.action(pk,'approve').status_code,403)
            r=self.client.get(reverse('my-payouts'));rows=r.data.get('results',[]) if isinstance(r.data,dict) else r.data
            self.assertEqual(len(rows),1 if user==self.doctor else 0)
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get(reverse('my-payouts')).status_code,401)

    def test_inactive_admin_and_recipient_are_rejected(self):
        self.maker.status='suspended';self.maker.save()
        self.assertEqual(self.client.get(reverse('admin-payouts')).status_code,403)
        self.client.force_authenticate(self.checker);self.doctor.status='suspended';self.doctor.save()
        self.assertEqual(self.client.post(reverse('admin-payouts'),self.payload(),format='json').status_code,400)

    def test_consultation_source_matches_recorded_payment_and_earning(self):
        profile=ClinicianProfile.objects.create(user=self.doctor,provider_type='doctor',name='SYNTHETIC QA',status='verified')
        consultation=Consultation.objects.create(clinician=profile,patient=self.patient,patient_name='SYNTHETIC',issue='QA only',status='completed')
        earning=ClinicianEarning.objects.create(clinician=profile,consultation=consultation,amount='450.00')
        payment=ConsultationPaymentIntent.objects.create(clinician=profile,consultation=consultation,provider='mpesa',amount='500.00',status='succeeded')
        payload=self.payload(consultation.reference);payload['source_type']='consultation';payload['withholding_amount']='0';payload['deduction_amount']='0'
        payload['gross_amount']='600';self.assertEqual(self.client.post(reverse('admin-payouts'),payload,format='json').status_code,400)
        payload['gross_amount']='500';r=self.client.post(reverse('admin-payouts'),payload,format='json');self.assertEqual(r.status_code,201,r.content)
        self.assertEqual(DoctorEarningSerializer(earning).data['payout']['reference'],r.data['reference'])
        self.assertEqual(DoctorEarningSerializer(earning).data['payout']['amount'],'450.00')
        payload['recipient']=self.other.pk;self.assertEqual(self.client.post(reverse('admin-payouts'),payload,format='json').status_code,400)

    def test_legacy_lowercase_reference_cannot_be_reused(self):
        one=self.create();two=self.create('SYNTHETIC-QA-LEGACY')
        Payout.objects.filter(pk=one).update(status='paid',payment_reference='synthetic-legacy-ref')
        self.approve(two)
        self.assertEqual(self.action(two,'mark_paid',payment_reference='SYNTHETIC-LEGACY-REF').status_code,409)

    def test_notification_identifies_recorded_status_without_transfer_claim(self):
        from unittest.mock import patch
        from apps.notifications.utils import notify_payout_status
        pk=self.create()
        with patch('apps.notifications.utils.create_notification') as create:
            notify_payout_status(Payout.objects.get(pk=pk))
        self.assertIn('recorded as',create.call_args.kwargs['message'])
        self.assertEqual(create.call_args.kwargs['data']['execution_mode'],'administrative_record')
