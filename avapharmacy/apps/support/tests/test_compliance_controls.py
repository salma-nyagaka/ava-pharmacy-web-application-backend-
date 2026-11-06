from avapharmacy.test_compliance_fixtures import grant_clinical_credentials
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch
from django.db import connection, transaction, DatabaseError
from django.db.models.deletion import ProtectedError
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient
from apps.accounts.models import User
from apps.products.models import Product, Variant, VariantInventory, Promotion
from apps.products.compliance import supply_error, prescription_required
from apps.products.services import calculate_variant_pricing, get_product_promotions
from apps.orders.models import Cart, CartItem, Order, OrderItem, DeliveryAudit
from apps.orders.stock import commit_order_inventory
from apps.orders.serializers import AdminOrderUpdateSerializer, DeliveryAuditSerializer
from apps.prescriptions.models import Prescription
from apps.prescriptions.compliance import approval_error, working_day_due
from apps.consultations.models import ClinicianProfile
from apps.support.models import MedicineAssessment, PrivacyRequest, ComplianceEvidence
from apps.support.compliance import assessment_error, screening_digest, delivery_error
from avapharmacy.test_compliance_fixtures import catalogue_fixture, clinician_fixture, prescription_fixture


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class ComplianceControlTests(TestCase):
    def setUp(self):
        self.customer = User.objects.create_user(email='compliance-customer@example.invalid', password='test', role='customer')
        self.other = User.objects.create_user(email='compliance-other@example.invalid', password='test', role='customer')
        self.admin = User.objects.create_user(email='compliance-admin@example.invalid', password='test', role='admin')
        grant_clinical_credentials(self.admin)
        self.inspector = User.objects.create_user(email='compliance-inspector@example.invalid', password='test', role='ppb_inspector')
        self.product = Product.objects.create(sku='COMPLIANCE-TEST', name='Synthetic test item', price=10)
        self.variant = Variant.objects.create(product=self.product, sku='COMPLIANCE-SKU', name='Synthetic variant', price=10)
        VariantInventory.objects.create(variant=self.variant, stock_quantity=20, batch_number='TEST-BATCH', supplier='Synthetic supplier')
        self.cart = Cart.objects.create(user=self.customer)
        self.item = CartItem.objects.create(cart=self.cart, product=self.product, variant=self.variant, quantity=1)
        self.client = APIClient()

    def medicine(self, classification='otc'):
        for k,v in catalogue_fixture(medicine=True).items(): setattr(self.variant,k,v)
        self.variant.prescription_classification=classification
        self.variant.requires_prescription=classification=='prescription'
        self.variant.save()
        self.item.variant = self.variant
        self.variant.inventories.update(expiry_date=timezone.localdate()+timedelta(days=365))

    def order(self):
        o=Order.objects.create(customer=self.customer, subtotal=10, total=10, status='shipped', payment_status='paid', inventory_committed=True)
        OrderItem.objects.create(order=o, product=self.product, variant=self.variant, product_name='Synthetic', product_sku=self.product.sku, quantity=1, unit_price=10)
        return o

    def test_unreviewed_catalog_is_blocked(self):
        self.assertIn('classification',supply_error(self.variant))

    def test_verified_non_medicine_can_be_supplied(self):
        self.variant.regulatory_scope='non_medicine';self.variant.save()
        self.assertIsNone(supply_error(self.variant))

    def test_inconsistent_rx_non_medicine_is_blocked(self):
        self.variant.regulatory_scope='non_medicine';self.variant.requires_prescription=True
        self.assertIn('inconsistent',supply_error(self.variant))

    def test_controlled_classification_blocks_with_false_boolean(self):
        self.variant.regulatory_scope='medicine';self.variant.prescription_classification='controlled'
        self.assertTrue(prescription_required(self.variant));self.assertIn('Controlled',supply_error(self.variant))

    def test_medicine_registration_safety_and_supplier_are_required(self):
        self.medicine();self.assertIsNone(supply_error(self.variant))
        for name, value in [('ppb_registration_number',''),('authorized_supplier',''),('regulatory_status','suspended'),('regulatory_status','withdrawn'),('ppb_license_expiry_date',timezone.localdate()-timedelta(days=1)),('pil_source_url',''),('contraindications',''),('side_effects',''),('pil_reviewed_at',None)]:
            with self.subTest(name=name,value=value):
                old=getattr(self.variant,name);setattr(self.variant,name,value);self.assertIsNotNone(supply_error(self.variant));setattr(self.variant,name,old)


    def test_rx_promotions_and_mixed_product_promotions_are_excluded(self):
        self.medicine('prescription');today=timezone.localdate()
        promo=Promotion.objects.create(title='Synthetic',value=10,scope='all',status='active',start_date=today,end_date=today)
        self.assertEqual(calculate_variant_pricing(self.variant)['discount_total'],Decimal('0'))
        self.assertEqual(get_product_promotions(self.product),[])

    def test_otc_requires_professional_decision_not_customer_checkbox(self):
        self.medicine();self.item.otc_screening={'counseling_acknowledged':True};self.item.save()
        self.assertIsNotNone(assessment_error(self.item))
        MedicineAssessment.objects.create(customer=self.customer,variant=self.variant,cart_item=self.item,quantity=1,
            screening_digest=screening_digest(self.item.otc_screening),decision='approved',suitability='Synthetic assessment',counselling='Synthetic counselling',reviewed_by=self.admin,expires_at=timezone.now()+timedelta(hours=1))
        self.assertIsNone(assessment_error(self.item))
        self.item.quantity=2;self.assertIsNotNone(assessment_error(self.item))
        self.item.quantity=1;self.item.otc_screening={'symptoms':'changed'};self.assertIsNotNone(assessment_error(self.item))

    def test_patient_cannot_forge_assessment(self):
        self.client.force_authenticate(self.customer)
        response=self.client.post('/api/compliance/medicine-assessments/',{'cart_item':self.item.pk,'decision':'approved','suitability':'x','counselling':'y'},format='json')
        self.assertEqual(response.status_code,403)

    def test_inspector_can_read_but_not_write_assessments(self):
        self.client.force_authenticate(self.inspector)
        self.assertEqual(self.client.get('/api/compliance/medicine-assessments/').status_code,200)
        self.assertEqual(self.client.post('/api/compliance/medicine-assessments/',{},format='json').status_code,403)

    def test_refusal_supersedes_approval(self):
        self.medicine()
        for decision in ['approved','refused']:
            MedicineAssessment.objects.create(customer=self.customer,variant=self.variant,cart_item=self.item,quantity=1,screening_digest=screening_digest({}),decision=decision,suitability='Synthetic',counselling='Synthetic',reviewed_by=self.admin,expires_at=timezone.now()+timedelta(hours=1))
        self.assertIsNotNone(assessment_error(self.item))

    def test_expired_assessment_is_rejected(self):
        self.medicine();MedicineAssessment.objects.create(customer=self.customer,variant=self.variant,cart_item=self.item,quantity=1,screening_digest=screening_digest({}),decision='approved',suitability='Synthetic',counselling='Synthetic',reviewed_by=self.admin,expires_at=timezone.now()-timedelta(seconds=1))
        self.assertIsNotNone(assessment_error(self.item))

    def test_delivery_requires_verified_recipient(self):
        serializer=DeliveryAuditSerializer(data={'event_type':'delivered','recipient_verified':False,'recipient_name':'Synthetic','package_condition':'intact'})
        self.assertFalse(serializer.is_valid())

    def test_temperature_failure_cannot_be_recorded_as_success(self):
        serializer=DeliveryAuditSerializer(data={'event_type':'delivered','recipient_verified':True,'recipient_name':'Synthetic','package_condition':'intact','temperature_sensitive':True,'cold_chain_intact':False,'temperature_reading_c':'6'})
        self.assertFalse(serializer.is_valid())

    def test_missing_or_failed_delivery_audit_blocks_completion(self):
        self.variant.regulatory_scope='non_medicine';self.variant.save();o=self.order()
        self.assertIsNotNone(delivery_error(o))
        self.assertFalse(AdminOrderUpdateSerializer(o,data={'status':'delivered'},partial=True).is_valid())
        DeliveryAudit.objects.create(order=o,event_type='failed',failure_reason='Synthetic',recorded_by=self.admin)
        self.assertIsNotNone(delivery_error(o))

    def test_valid_delivery_audit_allows_completion(self):
        self.variant.regulatory_scope='non_medicine';self.variant.save();o=self.order()
        DeliveryAudit.objects.create(order=o,event_type='delivered',recipient_verified=True,recipient_name='Synthetic',package_condition='intact',recorded_by=self.admin)
        self.assertIsNone(delivery_error(o));self.assertTrue(AdminOrderUpdateSerializer(o,data={'status':'delivered'},partial=True).is_valid())

    def test_cold_chain_temperature_must_be_within_medicine_limits(self):
        self.medicine();self.variant.is_temperature_sensitive=True;self.variant.storage_temperature_min_c=2;self.variant.storage_temperature_max_c=8;self.variant.save();o=self.order()
        DeliveryAudit.objects.create(order=o,event_type='delivered',recipient_verified=True,recipient_name='Synthetic',package_condition='intact',temperature_sensitive=True,cold_chain_intact=True,temperature_reading_c=12,recorded_by=self.admin)
        self.assertIn('excursion',delivery_error(o))

    def test_prescription_authenticity_and_original_overdue(self):
        rx=Prescription(patient=self.customer,patient_name='Synthetic');self.assertIsNotNone(approval_error(rx))
        for k,v in prescription_fixture().items():setattr(rx,k,v)
        self.assertIsNone(approval_error(rx));rx.original_due_on=timezone.localdate()-timedelta(days=1)
        self.assertIn('overdue',approval_error(rx))

    @override_settings(KENYA_PUBLIC_HOLIDAYS=['2026-11-09'])
    def test_original_deadline_excludes_weekends_and_configured_holidays(self):
        from datetime import date
        self.assertEqual(working_day_due(date(2026,11,6),1),date(2026,11,10))

    def test_clinician_expiry_verification_and_jurisdiction(self):
        clinician=ClinicianProfile(user=self.admin,name='Synthetic',provider_type='doctor',status='active',**clinician_fixture())
        self.assertTrue(clinician.eligible_to_practice)
        clinician.is_verified=False;self.assertFalse(clinician.eligible_to_practice)
        clinician.is_verified=True;clinician.license_expiry=timezone.localdate()-timedelta(days=1);self.assertFalse(clinician.eligible_to_practice)
        clinician.license_expiry=timezone.localdate()+timedelta(days=1);clinician.license_country='Other';self.assertFalse(clinician.eligible_to_practice)

    def test_prescription_and_cascade_deletion_are_protected(self):
        rx=Prescription.objects.create(patient=self.customer,patient_name='Synthetic')
        with self.assertRaises(ProtectedError), transaction.atomic():rx.delete()
        self.assertTrue(Prescription.objects.filter(pk=rx.pk).exists())

    def test_bulk_sql_cannot_delete_prescription_on_postgresql(self):
        if connection.vendor!='postgresql':self.skipTest('PostgreSQL trigger')
        rx=Prescription.objects.create(patient=self.customer,patient_name='Synthetic')
        with self.assertRaises(DatabaseError),transaction.atomic():
            with connection.cursor() as cursor:cursor.execute('DELETE FROM prescriptions_prescription WHERE id=%s',[rx.pk])

    def test_privacy_requests_are_owner_scoped_and_no_auto_erasure(self):
        self.client.force_authenticate(self.customer)
        r=self.client.post('/api/privacy/requests/',{'request_type':'erasure','details':'Synthetic request'},format='json');self.assertEqual(r.status_code,201,r.data)
        request=PrivacyRequest.objects.get(customer=self.customer)
        self.assertTrue(User.objects.filter(pk=self.customer.pk).exists())
        self.client.force_authenticate(self.other);self.assertEqual(self.client.get(f'/api/privacy/requests/{request.pk}/').status_code,404)

    def test_patient_cannot_set_privacy_resolution_or_verify_identity(self):
        self.client.force_authenticate(self.customer)
        r=self.client.post('/api/privacy/requests/',{'request_type':'access','details':'Synthetic','status':'resolved'},format='json');self.assertEqual(r.status_code,400)

    def test_evidence_requires_independent_current_verification(self):
        evidence=ComplianceEvidence.objects.create(evidence_type='ppb_authorization',title='Synthetic',external_url='https://example.invalid/test',expires_at=timezone.localdate()+timedelta(days=1),created_by=self.admin,updated_by=self.admin)
        self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.post(f'/api/compliance/evidence/{evidence.pk}/verify/',{'verification_reference':'Synthetic'},format='json').status_code,400)
        second=User.objects.create_user(email='second@example.invalid',role='admin')
        self.client.force_authenticate(second)
        self.assertEqual(self.client.post(f'/api/compliance/evidence/{evidence.pk}/verify/',{'verification_reference':'Synthetic'},format='json').status_code,200)
        self.client.patch(f'/api/compliance/evidence/{evidence.pk}/',{'notes':'Changed'},format='json')
        evidence.refresh_from_db();self.assertIsNone(evidence.verified_at)


    def test_all_route_aliases_enforce_owner_and_staff_access(self):
        self.client.force_authenticate(self.customer)
        for prefix in ['/api/','/api/v1/','/avapharmacy/api/','/avapharmacy/api/v1/']:
            self.assertEqual(self.client.get(prefix+'compliance/readiness/').status_code,403)
            self.assertEqual(self.client.get(prefix+'privacy/requests/').status_code,200)

    def test_otc_assessment_is_single_order_and_survives_cart_cleanup(self):
        from apps.support.models import MedicineAssessment
        self.medicine();self.item.otc_screening={'intended_user':'self','age_group':'adult','symptoms_or_reason':'Synthetic','allergies':'none','current_medicines':'none','pregnant_or_breastfeeding':'no','counseling_acknowledged':True};self.item.save()
        self.client.force_authenticate(self.admin)
        r=self.client.post('/api/compliance/medicine-assessments/',{'cart_item':self.item.pk,'decision':'approved','suitability':'Synthetic suitable','counselling':'Synthetic safe use/storage/disposal'},format='json')
        self.assertEqual(r.status_code,201,r.data)
        self.client.force_authenticate(self.customer)
        payload={'first_name':'Synthetic','last_name':'Test','email':self.customer.email,'phone':'0700000010','street':'Synthetic','city':'Nairobi','county':'Nairobi','payment_method':'mpesa_stk','delivery_method':'store_pickup'}
        r=self.client.post('/api/checkout/draft/',payload,format='json');self.assertEqual(r.status_code,201,r.data)
        order=Order.objects.get(customer=self.customer);self.assertIsNotNone(order.items.get().medicine_assessment_id)
        commit_order_inventory(order)
        cart_id=self.item.pk;self.item.delete()
        assessment=MedicineAssessment.objects.get(customer=self.customer);self.assertEqual(assessment.cart_item_id,cart_id)
        new=CartItem.objects.create(cart=self.cart,product=self.product,variant=self.variant,quantity=1,otc_screening=assessment.order_item.otc_screening)
        self.assertIsNotNone(assessment_error(new))

    def test_allocation_batch_evidence_survives_stock_release(self):
        from apps.support.models import SupplyAllocation
        from apps.orders.stock import release_order_inventory
        self.variant.regulatory_scope='non_medicine';self.variant.save();order=self.order();order.inventory_committed=False;order.save(update_fields=['inventory_committed'])
        commit_order_inventory(order);release_order_inventory(order)
        records=list(SupplyAllocation.objects.filter(order_item__order=order).order_by('created_at'))
        self.assertEqual([r.event for r in records],['commit','release'])
        self.assertEqual(records[0].allocation_snapshot[0]['batch_number'],'TEST-BATCH')
        self.assertEqual(records[1].allocation_snapshot,records[0].allocation_snapshot)

    def test_approval_keeps_an_immutable_prescription_version(self):
        from apps.prescriptions.models import PrescriptionVersion
        rx=Prescription.objects.create(patient=self.customer,patient_name='Synthetic',status='approved',**prescription_fixture())
        self.assertEqual(rx.preserved_versions.count(),1)
        if connection.vendor=='postgresql':
            with self.assertRaises(DatabaseError),transaction.atomic():
                PrescriptionVersion.objects.filter(prescription=rx).update(snapshot={})

    def test_production_supply_requires_verified_business_evidence(self):
        self.medicine()
        with override_settings(REQUIRE_VERIFIED_OPERATIONAL_EVIDENCE=True):
            self.assertIn('disclosures',supply_error(self.variant))

    def test_curation_cannot_be_written_by_customer_or_inspector(self):
        for user in [self.customer,self.inspector]:
            self.client.force_authenticate(user)
            self.assertEqual(self.client.patch(f'/api/compliance/catalogue/{self.variant.pk}/',{'regulatory_scope':'non_medicine'},format='json').status_code,403)
        self.client.force_authenticate(self.admin)
        r=self.client.patch(f'/api/compliance/catalogue/{self.variant.pk}/',{'regulatory_scope':'non_medicine'},format='json')
        self.assertEqual(r.status_code,200,r.data)
        self.variant.refresh_from_db();self.assertEqual(self.variant.pil_reviewed_by_id,self.admin.pk)

    def test_patient_cannot_modify_retained_clinical_records_by_privacy_request(self):
        request=PrivacyRequest.objects.create(customer=self.customer,request_type='erasure',details='Synthetic')
        self.client.force_authenticate(self.customer)
        self.assertEqual(self.client.patch(f'/api/privacy/requests/{request.pk}/',{'status':'resolved','response':'done','lawful_basis':'self'},format='json').status_code,403)

    def test_operational_review_cannot_complete_without_verified_evidence(self):
        self.client.force_authenticate(self.admin)
        r=self.client.post('/api/compliance/reviews/',{'area':'backup_restore','owner':self.admin.pk,'procedure_reference':'Synthetic SOP','due_on':timezone.localdate().isoformat(),'completed_at':timezone.now().isoformat(),'findings':'Synthetic'},format='json')
        self.assertEqual(r.status_code,400)

    def test_edited_evidence_has_an_attributed_immutable_change_log(self):
        from apps.support.models import ComplianceEvent
        self.client.force_authenticate(self.admin)
        r=self.client.post('/api/compliance/evidence/',{'evidence_type':'ppb_authorization','title':'Synthetic pending evidence'},format='json')
        self.assertEqual(r.status_code,201,r.data)
        event=ComplianceEvent.objects.get(model_label='support.complianceevidence')
        self.assertEqual(event.actor_id,self.admin.pk)
        if connection.vendor=='postgresql':
            with self.assertRaises(DatabaseError),transaction.atomic():ComplianceEvent.objects.filter(pk=event.pk).delete()

    def test_public_advertisements_cannot_target_rx_products(self):
        from apps.products.compliance import public_advertisement_allowed
        self.medicine('prescription')
        self.assertFalse(public_advertisement_allowed('/product/'+self.product.slug))
        today=timezone.localdate()
        promo=Promotion.objects.create(title='Synthetic Rx promo',value=10,scope='product',targets=[str(self.product.pk)],status='active',start_date=today,end_date=today)
        response=self.client.get('/api/promotions/')
        self.assertEqual(response.status_code,200,response.data)
        rows=response.data.get('results',response.data) if isinstance(response.data,dict) else response.data
        self.assertNotIn(promo.pk,[row['id'] for row in rows])


    def test_release_readiness_fails_with_missing_evidence(self):
        from django.core.management import call_command, CommandError
        with self.assertRaises(CommandError):call_command('check_pharmacy_readiness')

    def test_patient_email_contains_actual_superintendent_identifiers(self):
        from django.core import mail
        from apps.notifications.emailing import send_rendered_email
        from apps.support.models import SiteSettings
        site=SiteSettings.get_solo();site.superintendent_name='Synthetic superintendent';site.superintendent_registration_number='TEST-STAFF';site.health_safety_code='TEST-CODE';site.save()
        send_rendered_email(subject='Synthetic',recipient_list=[self.customer.email],text_template='emails/notification.txt',html_template='emails/notification.html',context={'heading':'Synthetic','intro':'Synthetic','detail_rows':[]})
        self.assertIn('TEST-STAFF',mail.outbox[-1].body)
        self.assertIn('TEST-CODE',mail.outbox[-1].alternatives[0][0])

    def test_medicine_stock_requires_traceable_unexpired_batches(self):
        from apps.orders.views import _product_availability_error
        self.medicine()
        self.assertIsNone(_product_availability_error(self.variant,1))
        for field,value in [('batch_number',''),('supplier',''),('expiry_date',None),('expiry_date',timezone.localdate()-timedelta(days=1))]:
            row=self.variant.inventories.get();old=getattr(row,field);setattr(row,field,value);row.save()
            self.assertIn('batches',_product_availability_error(self.variant,1))
            setattr(row,field,old);row.save()

    @override_settings(TIME_ZONE='Africa/Nairobi', KENYA_PUBLIC_HOLIDAYS=[])
    def test_original_deadline_uses_kenyan_date_at_utc_day_boundary(self):
        from datetime import datetime, date, timezone as dt_timezone
        with patch('django.utils.timezone.now',return_value=datetime(2026,11,4,22,30,tzinfo=dt_timezone.utc)):
            rx=Prescription.objects.create(patient=self.customer,patient_name='Synthetic')
        self.assertEqual(rx.original_due_on,date(2026,11,16))

    def test_public_detail_does_not_leak_raw_rx_price_comparisons(self):
        self.medicine('prescription');self.variant.original_price=20;self.variant.save()
        response=self.client.get('/api/products/'+self.product.slug+'/')
        self.assertEqual(response.status_code,200,response.data)
        self.assertIsNone(response.data['original_price'])
        self.assertIsNone(response.data['variants'][0]['original_price'])

    def test_otc_screening_rejects_boolean_or_object_patient_details(self):
        from apps.orders.views import _otc_screening_error
        self.medicine()
        screening={'intended_user':'self','age_group':'adult','symptoms_or_reason':'Synthetic','allergies':'none','current_medicines':'none','pregnant_or_breastfeeding':'no','counseling_acknowledged':True}
        self.assertIsNone(_otc_screening_error(self.variant,screening))
        for value in [True,{},[], '   ', 'x'*3001]:
            self.assertIsNotNone(_otc_screening_error(self.variant,{**screening,'age_group':value}))
