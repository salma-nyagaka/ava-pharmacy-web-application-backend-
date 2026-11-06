from datetime import timedelta
from decimal import Decimal
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase
from apps.lab.models import LabRequest, LabResult, LabTechnicianProfile, FacilityLabTest, LabTest
from . import test_workflow_security as fixtures


class LabModuleAcceptanceTests(APITestCase):
    setUp = fixtures.LabWorkflowSecurityTests.setUp
    make_user = staticmethod(fixtures.LabWorkflowSecurityTests.make_user)
    authenticate = fixtures.LabWorkflowSecurityTests.authenticate
    list_items = staticmethod(fixtures.LabWorkflowSecurityTests.list_items)

    def collection(self):
        return LabRequest.objects.create(test=self.test, patient=self.patient, patient_name='Synthetic QA patient', patient_phone='0700000000', channel='collection', collection_address='Synthetic QA address', assigned_partner=self.partner, laboratory=self.facility, assigned_technician=self.technician)

    def test_price_snapshot_and_hidden_test_booking(self):
        self.authenticate(self.patient)
        payload={'test':self.test.pk,'patient_name':'Synthetic QA','patient_phone':'0700000000','channel':'walk_in'}
        r=self.client.post(reverse('lab-requests'),payload,format='json')
        self.assertEqual(r.status_code,201,r.content)
        self.test.price=2500;self.test.save()
        detail=self.client.get(reverse('lab-request-detail',args=[r.data['id']]))
        self.assertEqual(Decimal(str(detail.data['test_price'])),Decimal('1500'))
        FacilityLabTest.objects.filter(test=self.test).update(is_active=False)
        rows=self.list_items(self.client.get(reverse('lab-tests')))
        self.assertNotIn(self.test.pk,[x['id'] for x in rows])
        self.assertEqual(self.client.post(reverse('lab-requests'),payload,format='json').status_code,400)

    def test_same_facility_technician_cannot_read_assigned_patient_or_nested_result(self):
        other=self.make_user('same-facility-qa@example.test','lab_technician')
        profile=LabTechnicianProfile.objects.create(user=other,partner=self.partner,name='Other QA',email=other.email,status='active')
        self.facility.technicians.add(profile)
        LabResult.objects.create(request=self.request,summary='PRIVATE SYNTHETIC RESULT')
        self.authenticate(other)
        self.assertEqual(self.client.get(reverse('lab-request-detail',args=[self.request.pk])).status_code,404)
        self.assertNotIn('PRIVATE SYNTHETIC RESULT',str(self.client.get(reverse('lab-dashboard')).data))
        self.request.assigned_technician=None;self.request.save()
        response=self.client.get(reverse('lab-request-detail',args=[self.request.pk]))
        self.assertEqual(response.status_code,200)
        self.assertIsNone(response.data['result'])
        self.assertEqual(response.data['patient_phone'],'')
        self.assertEqual(response.data['collection_address'],'')
        self.assertIsNone(response.data['patient'])

    def test_revoked_technician_cannot_read_result(self):
        result=LabResult.objects.create(request=self.request,summary='PRIVATE QA')
        self.technician_profile.status='suspended';self.technician_profile.save()
        self.authenticate(self.technician)
        self.assertEqual(self.client.get(reverse('lab-result-detail',args=[result.pk])).status_code,404)
        self.assertEqual(self.client.get(reverse('lab-request-detail',args=[self.request.pk])).status_code,404)

    def test_patient_cancellation_preserves_unpaid_state_and_invalidates_code(self):
        req=self.collection();self.authenticate(self.patient)
        code=self.client.post(reverse('lab-collection-code',args=[req.pk]),{},format='json').data['code']
        r=self.client.patch(reverse('lab-request-update',args=[req.pk]),{'status':'cancelled'},format='json')
        self.assertEqual(r.status_code,200,r.content)
        req.refresh_from_db();self.assertEqual(req.payment_status,'pending');self.assertEqual(req.collection_verification_code_hash,'')
        self.authenticate(self.technician)
        self.assertEqual(self.client.post(reverse('lab-verify-collection',args=[req.pk]),{'code':code},format='json').status_code,400)
        self.authenticate(self.patient)
        self.assertEqual(self.client.patch(reverse('lab-request-update',args=[self.request.pk]),{'status':'cancelled'},format='json').status_code,400)

    def test_wrong_expired_other_request_and_replayed_codes(self):
        req=self.collection();other=self.collection();self.authenticate(self.patient)
        issued=self.client.post(reverse('lab-collection-code',args=[req.pk]),{},format='json')
        self.assertEqual(issued.status_code,200)
        code=issued.data['code'];self.authenticate(self.technician)
        self.assertEqual(self.client.post(reverse('lab-verify-collection',args=[other.pk]),{'code':code},format='json').status_code,400)
        req.collection_code_expires_at=timezone.now()-timedelta(seconds=1);req.save()
        self.assertEqual(self.client.post(reverse('lab-verify-collection',args=[req.pk]),{'code':code},format='json').status_code,400)
        self.authenticate(self.patient)
        code=self.client.post(reverse('lab-collection-code',args=[req.pk]),{},format='json').data['code']
        self.authenticate(self.technician)
        wrong='999999' if code!='999999' else '888888'
        for _ in range(5):
            self.assertEqual(self.client.post(reverse('lab-verify-collection',args=[req.pk]),{'code':wrong},format='json').status_code,400)
        self.assertEqual(self.client.post(reverse('lab-verify-collection',args=[req.pk]),{'code':code},format='json').status_code,429)
        req.refresh_from_db();self.assertEqual(req.collection_verification_attempts,5)
        self.authenticate(self.patient)
        code=self.client.post(reverse('lab-collection-code',args=[req.pk]),{},format='json').data['code']
        self.authenticate(self.technician)
        self.assertEqual(self.client.post(reverse('lab-verify-collection',args=[req.pk]),{'code':code},format='json').status_code,200)
        self.assertEqual(self.client.post(reverse('lab-verify-collection',args=[req.pk]),{'code':code},format='json').status_code,400)

    def test_private_raw_media_and_invalid_result_content(self):
        for path in ['lab/results/result.pdf','lab_partners/documents/licence.pdf','lab_tech/documents/licence.pdf','laboratory_facilities/documents/licence.pdf']:
            self.assertEqual(self.client.get('/media/'+path).status_code,404)
        self.authenticate(self.technician)
        bad=self.client.post(reverse('lab-result-create',args=[self.request.pk]),{'summary':'QA','file':SimpleUploadedFile('fake.pdf',b'<html>not a PDF</html>',content_type='application/pdf')},format='multipart')
        self.assertEqual(bad.status_code,400)
        valid=self.client.post(reverse('lab-result-create',args=[self.request.pk]),{'summary':'SYNTHETIC QA result','file':SimpleUploadedFile('qa.pdf',b'%PDF-1.4\nSYNTHETIC QA',content_type='application/pdf')},format='multipart')
        self.assertEqual(valid.status_code,201,valid.content)
        self.assertNotIn('/media/',str(valid.data))
        self.assertEqual(self.client.post(reverse('lab-result-create',args=[self.request.pk]),{'summary':'Duplicate'},format='multipart').status_code,400)
        self.authenticate(self.patient)
        self.assertEqual(self.client.get(reverse('lab-result-download',args=[valid.data['id']])).status_code,200)

    def test_suspension_preserves_staff_and_offering_history(self):
        self.authenticate(self.admin)
        r=self.client.post(reverse('admin-lab-partner-action',args=[self.partner.pk]),{'action':'suspend'},format='json')
        self.assertEqual(r.status_code,200)
        self.assertTrue(LabTechnicianProfile.objects.filter(pk=self.technician_profile.pk).exists())
        self.assertTrue(FacilityLabTest.objects.filter(facility=self.facility).exists())
        self.assertFalse(FacilityLabTest.objects.get(facility=self.facility,test=self.test).is_active)

    def test_partner_application_verification_provision_and_activation(self):
        import re
        from django.core import mail
        self.client.force_authenticate(None)
        r=self.client.post(reverse('lab-partner-register'),{'name':'SYNTHETIC QA Application','email':'lab-application-qa@example.test','phone':'0700000901','license_number':'SYNTHETIC-LAB-QA','license_expiry':'2030-12-31','background_consent':True,'compliance_declaration':True,'agreed_to_terms':True,'documents':[SimpleUploadedFile('qa.pdf',b'%PDF-1.4\nQA',content_type='application/pdf')]},format='multipart')
        self.assertEqual(r.status_code,201,r.content)
        from apps.lab.models import LabPartner
        partner=LabPartner.objects.get(email='lab-application-qa@example.test')
        self.authenticate(self.admin)
        self.assertEqual(self.client.post(reverse('admin-lab-partner-action',args=[partner.pk]),{'action':'verify'},format='json').status_code,200)
        r=self.client.post(reverse('admin-lab-partner-provision-account',args=[partner.pk]),{},format='json')
        self.assertEqual(r.status_code,201,r.content)
        message=next(x for x in reversed(mail.outbox) if partner.email in x.to and '/activate/' in x.body)
        token=re.search(r'/activate/([^/\s]+)/',message.body).group(1)
        self.client.force_authenticate(None)
        r=self.client.post(reverse('professional-activate'),{'token':token,'new_password':'SyntheticLabPass123!','new_password_confirm':'SyntheticLabPass123!','accepted_terms':True},format='json')
        self.assertEqual(r.status_code,200,r.content)

    def test_inactive_facility_cannot_collect_or_publish(self):
        req=self.collection();self.authenticate(self.patient)
        code=self.client.post(reverse('lab-collection-code',args=[req.pk]),{},format='json').data['code']
        self.facility.is_active=False;self.facility.save()
        self.authenticate(self.technician)
        self.assertEqual(self.client.post(reverse('lab-verify-collection',args=[req.pk]),{'code':code},format='json').status_code,403)
        self.assertEqual(self.client.post(reverse('lab-result-create',args=[self.request.pk]),{'summary':'QA'},format='multipart').status_code,403)

    def test_status_response_includes_latest_audit_and_result_notification_opens_account(self):
        self.authenticate(self.technician)
        r=self.client.post(reverse('lab-result-create',args=[self.request.pk]),{'summary':'SYNTHETIC QA'},format='multipart')
        self.assertEqual(r.status_code,201,r.content)
        from apps.notifications.models import Notification
        notification=Notification.objects.get(recipient=self.patient,type='lab_result')
        self.assertEqual(notification.data['url'],f'/account/lab-tests?request={self.request.pk}')
        r=self.client.patch(reverse('lab-request-update',args=[self.request.pk]),{'status':'completed'},format='json')
        self.assertEqual(r.status_code,200,r.content)
        self.assertTrue(any('Completed' in row['action'] for row in r.data['audit_logs']))

    def test_patient_cancellation_after_facility_suspension_and_paid_restriction(self):
        req=self.collection();self.facility.is_active=False;self.facility.save()
        self.authenticate(self.patient)
        r=self.client.patch(reverse('lab-request-update',args=[req.pk]),{'status':'cancelled'},format='json')
        self.assertEqual(r.status_code,200,r.content)
        paid=self.collection();paid.payment_status='paid';paid.save()
        self.assertEqual(self.client.patch(reverse('lab-request-update',args=[paid.pk]),{'status':'cancelled'},format='json').status_code,400)

    def test_administrative_payment_change_is_audited(self):
        self.authenticate(self.admin)
        r=self.client.patch(reverse('lab-request-update',args=[self.request.pk]),{'payment_status':'paid'},format='json')
        self.assertEqual(r.status_code,200,r.content)
        self.assertTrue(any('administrative record' in row['action'] for row in r.data['audit_logs']))

    def test_oversized_and_unsupported_result_uploads_and_other_partner_access(self):
        self.authenticate(self.technician)
        for file in [SimpleUploadedFile('qa.txt',b'QA',content_type='text/plain'), SimpleUploadedFile('large.pdf',b'%PDF-'+b'x'*(10*1024*1024),content_type='application/pdf')]:
            self.assertEqual(self.client.post(reverse('lab-result-create',args=[self.request.pk]),{'summary':'QA','file':file},format='multipart').status_code,400)
        result=LabResult.objects.create(request=self.request,summary='PRIVATE QA')
        self.authenticate(self.other_partner_user)
        self.assertEqual(self.client.get(reverse('lab-result-detail',args=[result.pk])).status_code,404)
        self.assertEqual(self.client.patch(reverse('lab-request-update',args=[self.request.pk]),{'notes':'Not allowed'},format='json').status_code,404)

    def test_technician_document_download_is_private(self):
        from apps.lab.models import LabTechDocument
        doc=LabTechDocument.objects.create(tech=self.technician_profile,name='SYNTHETIC QA licence',file=SimpleUploadedFile('qa.pdf',b'%PDF-1.4 QA',content_type='application/pdf'))
        self.authenticate(self.technician)
        self.assertEqual(self.client.get(reverse('lab-tech-document-download',args=[doc.pk])).status_code,200)
        self.authenticate(self.other_partner_user)
        self.assertEqual(self.client.get(reverse('lab-tech-document-download',args=[doc.pk])).status_code,404)
