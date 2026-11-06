"""Read-only audit of CURRENT behavior, using a disposable test database.
A passing probe confirms its observation; AUDIT_GAP is NOT a compliance pass.
No live payments, provider callbacks, emails or clinical care are executed.
"""
import json
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch
from django.contrib import admin
from django.test import TestCase,override_settings
from django.utils import timezone
from rest_framework.test import APIClient,APIRequestFactory
from apps.accounts.models import User,Pharmacist
from apps.orders.models import Order,OrderItem,Cart,DeliveryAudit
from apps.products.models import Promotion,VariantInventory
from apps.prescriptions.models import Prescription,PrescriptionItem
from apps.consultations.models import ClinicianProfile
from apps.consultations.serializers import ConsultationCreateSerializer
from apps.orders.tests import test_order_creation as fixtures
OBS=[]

def observed(id,kind,details):
 row={'finding':id,'result':kind,'observed':details};OBS.append(row);print('AUDIT_OBSERVATION '+json.dumps(row))

@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class GuidelineAuditProbes(TestCase):
 setUp=fixtures.OrderCreationFlowTests.setUp
 _direct_order=fixtures.OrderCreationFlowTests._direct_order
 @classmethod
 def tearDownClass(cls):
  Path('docs/compliance-audit/2026-11-04/probe-results.json').write_text(json.dumps(OBS,indent=2));super().tearDownClass()
 def cart(self,screening=None):
  self.client.force_authenticate(self.customer);payload={'product_id':self.product.pk,'variant_id':self.variant.pk,'quantity':1}
  if screening is not None:payload['otc_screening']=screening
  return self.client.post('/api/cart/items/',payload,format='json')
 def draft(self):
  return self.client.post('/api/checkout/draft/',{'first_name':'Synthetic','last_name':'Audit','email':self.customer.email,'phone':'0700000010','street':'Synthetic','city':'Nairobi','county':'Nairobi','payment_method':'mpesa_stk','delivery_method':'store_pickup'},format='json')
 def test_01_regulatory_registration_and_licensing_not_a_checkout_gate(self):
  self.assertEqual(self.variant.ppb_registration_number,'');self.assertNotEqual(self.variant.regulatory_status,'approved')
  r=self.cart();self.assertEqual(r.status_code,201,r.data);d=self.draft();self.assertEqual(d.status_code,201,d.data)
  observed('PPB-01','AUDIT_GAP',{'cart':201,'draft':201,'ppb_registration_blank':True,'regulatory_not_approved':True,'business_authorization_gate':False})
 def test_02_controlled_classification_not_enforced_when_rx_flag_false(self):
  self.variant.prescription_classification='controlled';self.variant.requires_prescription=False;self.variant.save()
  r=self.cart();self.assertEqual(r.status_code,201,r.data)
  observed('PPB-02','AUDIT_GAP',{'controlled_classification':True,'requires_prescription':False,'cart':201})
 def test_03_suspended_regulatory_status_does_not_block_cart(self):
  self.variant.regulatory_status='suspended';self.variant.save();r=self.cart();self.assertEqual(r.status_code,201,r.data)
  observed('PPB-01','AUDIT_GAP',{'regulatory_status':'suspended','cart':201})
 def test_04_public_rx_promotional_discount(self):
  self.variant.requires_prescription=True;self.variant.save();today=timezone.now().date()
  promo=Promotion.objects.create(title='SYNTHETIC RX SALE',value=10,scope='all',status='active',start_date=today,end_date=today)
  r=APIClient().get('/api/products/'+self.product.slug+'/');self.assertEqual(r.status_code,200,r.data)
  self.assertTrue(r.data.get('active_promotions'),r.data);self.assertGreater(Decimal(str(r.data['discount_total'])),0)
  observed('PPB-03','AUDIT_GAP',{'anonymous_detail':200,'requires_prescription':True,'discount_total':str(r.data['discount_total']),'promotion_id':promo.pk})
 def test_05_otc_screening_is_keyword_based_not_classification_based(self):
  self.variant.prescription_classification='otc';self.variant.save();r=self.cart();self.assertEqual(r.status_code,201,r.data)
  observed('PPB-04','AUDIT_GAP',{'classified_otc':True,'neutral_catalog_name':True,'screening_absent':True,'cart':201})
 def test_06_patient_acknowledgement_can_reach_draft_without_pharmacist(self):
  self.product.name='SYNTHETIC pain medicine';self.product.save(update_fields=['name'])
  r=self.cart({'intended_user':'self','age_group':'adult','symptoms_or_reason':'QA only','allergies':'none','current_medicines':'none','pregnant_or_breastfeeding':'no','counseling_acknowledged':True});self.assertEqual(r.status_code,201,r.data)
  d=self.draft();self.assertEqual(d.status_code,201,d.data)
  observed('PPB-04','AUDIT_GAP',{'patient_supplied_screening':True,'pharmacist_decision':False,'draft':201})
 def test_07_delivery_completion_ignores_recipient_and_cold_chain(self):
  self.variant.is_temperature_sensitive=True;self.variant.save()
  o=self._direct_order(status='shipped',payment_status='paid',inventory_committed=True);OrderItem.objects.create(order=o,variant=self.variant,quantity=1,unit_price=700)
  self.client.force_authenticate(self.admin)
  audit=self.client.post(f'/api/admin/orders/{o.pk}/delivery-audits/',{'event_type':'delivered','recipient_verified':False,'temperature_sensitive':True,'cold_chain_intact':False},format='json');self.assertEqual(audit.status_code,201,audit.data)
  with patch('apps.orders.views.notify_order_update'),patch('apps.orders.views._save_order_push_result'):
   r=self.client.patch(f'/api/admin/orders/{o.pk}/',{'status':'delivered'},format='json')
  self.assertEqual(r.status_code,200,r.data)
  observed('PPB-05','AUDIT_GAP',{'delivery_audit':201,'recipient_verified':False,'cold_chain_intact':False,'delivered_transition':200})
 def test_08_recent_prescription_deletable_in_django_admin(self):
  rx=Prescription.objects.create(patient=self.customer,patient_name='SYNTHETIC',doctor_name='SYNTHETIC');pk=rx.pk
  self.admin.is_superuser=True;self.admin.is_staff=True;self.admin.save();request=APIRequestFactory().post('/admin/');request.user=self.admin
  modeladmin=admin.site._registry[Prescription];self.assertTrue(modeladmin.has_delete_permission(request,rx));modeladmin.delete_model(request,rx)
  self.assertFalse(Prescription.objects.filter(pk=pk).exists())
  observed('PPB-06','AUDIT_GAP',{'age_of_record':'created during test','django_admin_delete_permitted':True,'prescription_retained':False})
 def test_09_expired_unverified_clinician_still_bookable_by_serializer(self):
  u=User.objects.create_user(email='audit-doctor@example.test',password='Synthetic123!',role='doctor',status='active')
  c=ClinicianProfile.objects.create(user=u,provider_type='doctor',name='SYNTHETIC',email=u.email,phone='0700000012',specialty='QA',license_number='SYNTHETIC',license_expiry=timezone.now().date()-timedelta(days=1),is_verified=False,status='active',consult_fee=1)
  request=APIRequestFactory().post('/');request.user=self.customer
  s=ConsultationCreateSerializer(data={'doctor':c.pk,'patient_name':'SYNTHETIC','issue':'SYNTHETIC QA'},context={'request':request});self.assertTrue(s.is_valid(),s.errors)
  observed('PPB-07','AUDIT_GAP',{'expired_license':True,'is_verified':False,'booking_payload_accepted':True})
 def test_10_rx_approval_has_no_authenticity_or_original_receipt_gate(self):
  u=User.objects.create_user(email='audit-pharmacist@example.test',password='Synthetic123!',role='pharmacist');Pharmacist.objects.create(user=u,permissions=[Pharmacist.PERMISSION_PRESCRIPTION_REVIEW])
  rx=Prescription.objects.create(patient=self.customer,patient_name='SYNTHETIC',doctor_name='');PrescriptionItem.objects.create(prescription=rx,product=self.product,variant=self.variant,name='SYNTHETIC',quantity=1)
  self.client.force_authenticate(u);r=self.client.post(f'/api/pharmacist/prescriptions/{rx.pk}/review/',{'action':'approve'},format='json');self.assertEqual(r.status_code,200,r.data)
  observed('PPB-08','AUDIT_GAP',{'approval':200,'prescriber_identity_blank':True,'authenticity_evidence_required':False,'original_due_date_required':False})
 def test_11_inspector_can_read_but_not_write_prescription_register(self):
  u=User.objects.create_user(email='audit-inspector@example.test',password='Synthetic123!',role='ppb_inspector');self.client.force_authenticate(u)
  r=self.client.get('/api/admin/prescriptions/');self.assertEqual(r.status_code,200,r.data)
  write=self.client.post('/api/admin/prescriptions/',{},format='json');self.assertIn(write.status_code,[403,405])
  observed('CONTROL-04','CONTROL_PASS',{'inspector_prescription_read':200,'inspector_write':write.status_code})
 def test_12_protected_customer_prescription_access(self):
  rx=Prescription.objects.create(patient=self.customer,patient_name='SYNTHETIC');other=User.objects.create_user(email='audit-other@example.test',password='Synthetic123!');self.client.force_authenticate(other)
  r=self.client.get(f'/api/prescriptions/{rx.pk}/');self.assertIn(r.status_code,[403,404]);observed('CONTROL-01','CONTROL_PASS',{'unrelated_prescription_read':r.status_code})
 def test_13_unsigned_payment_callback_denied(self):
  r=APIClient().post('/api/payments/mpesa/callback/',{},format='json');self.assertEqual(r.status_code,403);observed('CONTROL-02','CONTROL_PASS',{'unsigned_callback':403})
 def test_14_unpaid_order_finalization_denied(self):
  o=self._direct_order();self.client.force_authenticate(self.customer);r=self.client.post(f'/api/checkout/{o.pk}/finalize/',{},format='json');self.assertEqual(r.status_code,400);observed('CONTROL-03','CONTROL_PASS',{'unpaid_finalization':400})
