from decimal import Decimal
from datetime import timedelta
from django.test import TestCase, override_settings
from django.urls import reverse
from django.core import mail
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from rest_framework.test import APIClient
from apps.accounts.models import User, Pharmacist
from apps.accounts.serializers import ProfessionalRegistrationSerializer, PasswordChangeSerializer
from apps.products.models import Product, VariantInventory
from apps.products.compliance import supply_error
from apps.consultations.models import ClinicianProfile
from apps.consultations.views import _professional_resubmission_token
from apps.prescriptions.models import Prescription


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend', BOT_CHALLENGE_REQUIRED=False)
class ReportedFlowTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user=User.objects.create_user(email='reported@example.test',password='AccountSecret123!',first_name='Test')
        self.client=APIClient();self.client.force_authenticate(self.user)

    def test_suspended_login_explained_only_for_correct_password(self):
        self.user.status='suspended';self.user.is_active=False;self.user.save()
        client=APIClient()
        result=client.post(reverse('login'),{'email':self.user.email,'password':'AccountSecret123!'},format='json')
        self.assertEqual(result.status_code,403,result.data)
        self.assertIn('suspended',str(result.data).lower())
        result=client.post(reverse('login'),{'email':self.user.email,'password':'wrong'},format='json')
        self.assertEqual(result.status_code,401,result.data)
        self.assertNotIn('suspended',str(result.data).lower())

    def test_unreviewed_nonprescription_stock_can_be_added(self):
        product=Product.objects.create(name='Unreviewed ordinary item',price=100)
        variant=product.variants.get()
        VariantInventory.objects.create(variant=variant,stock_quantity=10)
        self.assertIsNone(supply_error(variant))
        result=self.client.post(reverse('cart-items'),{'product_id':product.pk,'variant_id':variant.pk,'quantity':1},format='json')
        self.assertIn(result.status_code,(200,201),result.data)
        variant.is_active=False;variant.save()
        self.assertIn('inactive',supply_error(variant))

    def test_pharmacist_with_queue_permission_sees_new_unassigned_prescription(self):
        rx=Prescription.objects.create(patient=self.user,patient_name='Test patient')
        pharmacist=User.objects.create_user(email='pharmacy@example.test',role='pharmacist')
        Pharmacist.objects.create(user=pharmacist,permissions=['prescription_review'])
        self.client.force_authenticate(pharmacist)
        result=self.client.get(reverse('pharmacist-prescriptions'))
        self.assertEqual(result.status_code,200,result.data)
        self.assertIn(str(rx.pk),str(result.data))
        result=self.client.post(reverse('pharmacist-prescription-review',args=[rx.pk]),{'status':'approved'},format='json')
        self.assertEqual(result.status_code,403)
        outsider=User.objects.create_user(email='outsider@example.test')
        self.client.force_authenticate(outsider)
        self.assertEqual(self.client.get(reverse('pharmacist-prescriptions')).status_code,403)

    def test_prescription_upload_limits_have_messages(self):
        result=self.client.post(reverse('prescription-upload'),{'patient_name':'Test','files':[SimpleUploadedFile(f'{i}.pdf',b'%PDF-1.4 test',content_type='application/pdf') for i in range(6)]},format='multipart')
        self.assertEqual(result.status_code,400,result.data)
        self.assertIn('5',str(result.data))
        result=self.client.post(reverse('prescription-upload'),{'patient_name':'Test','files':[SimpleUploadedFile('large.pdf',b'x'*(5*1024*1024+1),content_type='application/pdf')]},format='multipart')
        self.assertEqual(result.status_code,400,result.data)
        self.assertIn('5 MB',str(result.data))
        self.assertFalse(Prescription.objects.exists())

    def test_optional_empty_lab_expiry_is_not_a_date_error(self):
        data={'type':'lab_partner','name':'Lab QA','email':'labqa@example.test','phone':'0722000011','license_expiry':'','lab_name':'Lab QA','lab_location':'Nairobi','lab_accreditation':'TEST','license_number':'TEST','payout_method':'mpesa','payout_account':'0722000011','backgroundConsent':True,'complianceDeclaration':True,'agreedToTerms':True}
        serializer=ProfessionalRegistrationSerializer(data=data)
        self.assertTrue(serializer.is_valid(),serializer.errors)
        self.assertIsNone(serializer.validated_data['licenseExpiry'])

    def test_resubmission_available_only_for_pending_application(self):
        profile=ClinicianProfile.objects.create(name='Doctor QA',email='docqa@example.test',provider_type='doctor',status='pending')
        token=_professional_resubmission_token(profile)
        client=APIClient()
        result=client.get(reverse('professional-document-resubmission',args=[token]))
        self.assertEqual(result.status_code,200,result.data)
        self.assertEqual(result.data['application']['id'],profile.pk)
        profile.status='active';profile.save()
        result=client.get(reverse('professional-document-resubmission',args=[token]))
        self.assertEqual(result.status_code,404)

    def test_fee_fixed_split_shown_in_email(self):
        from apps.accounts.utils import send_pharmacist_activation_email
        doctor=User.objects.create_user(email='feeqa@example.test',role='doctor')
        profile=ClinicianProfile.objects.create(user=doctor,name='Fee QA',provider_type='doctor',consult_fee=2200,commission=15)
        profile.refresh_from_db();self.assertEqual(profile.consult_fee,1500)
        self.assertEqual(profile.commission,15)
        profile.consult_fee=9999;profile.save();profile.refresh_from_db()
        self.assertEqual(profile.consult_fee,1500)
        send_pharmacist_activation_email(user=doctor,raw_token='synthetic-test-token')
        self.assertIn('1000',mail.outbox[-1].body)
        self.assertIn('1500',mail.outbox[-1].body)
        self.assertIn('500',mail.outbox[-1].body)

    def test_password_change_uses_registration_strength_rules(self):
        for password in ('short','alllowercase123!','ALLUPPERCASE123!','NoDigitsHere!','NoSymbols123'):
            serializer=PasswordChangeSerializer(data={'old_password':'AccountSecret123!','new_password':password,'new_password_confirm':password})
            self.assertFalse(serializer.is_valid(),password)

    def test_pending_professional_can_resubmit_a_document(self):
        from tempfile import TemporaryDirectory
        profile=ClinicianProfile.objects.create(name='Upload QA',email='uploadqa@example.test',provider_type='doctor',status='pending',status_note='Please attach licence')
        token=_professional_resubmission_token(profile)
        with TemporaryDirectory() as media:
            with override_settings(MEDIA_ROOT=media):
                result=APIClient().post(reverse('professional-document-resubmission',args=[token]),{'documents':[SimpleUploadedFile('licence.pdf',b'%PDF-1.4 synthetic',content_type='application/pdf')],'document_names':['Licence']},format='multipart')
                self.assertEqual(result.status_code,201,result.data)
                self.assertEqual(result.data['uploaded_count'],1)
                self.assertEqual(profile.documents.count(),1)
