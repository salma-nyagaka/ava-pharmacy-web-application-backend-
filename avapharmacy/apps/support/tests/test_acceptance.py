from unittest.mock import patch
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APIClient
from apps.accounts.models import User
from apps.support.models import SupportTicket, SupportNote, SiteSettings, NewsletterSubscriber
from apps.notifications.models import Notification


class SupportAcceptanceTests(TestCase):
    def setUp(self):
        self.client=APIClient()
        self.customer=User.objects.create_user(email='support-qa@example.test',password='SyntheticQA123!',role='customer')
        self.other=User.objects.create_user(email='support-other@example.test',password='SyntheticQA123!',role='customer')
        self.admin=User.objects.create_user(email='support-admin@example.test',password='SyntheticQA123!',role='admin')
        self.inspector=User.objects.create_user(email='support-inspector@example.test',password='SyntheticQA123!',role='ppb_inspector')
        self.ticket=SupportTicket.objects.create(customer=self.customer,customer_name='SYNTHETIC QA',customer_email=self.customer.email,subject='SYNTHETIC QA ticket')
        self.client.force_authenticate(self.customer)

    def test_public_reply_private_internal_note_and_history(self):
        path=reverse('support-ticket-notes',args=[self.ticket.pk])
        self.assertEqual(self.client.post(path,{'message':'SYNTHETIC customer reply'},format='json').status_code,200)
        self.assertEqual(self.client.post(path,{'message':'forbidden','is_internal':True},format='json').status_code,403)
        self.client.force_authenticate(self.admin)
        self.client.post(path,{'message':'PRIVATE INTERNAL QA','is_internal':True},format='json')
        self.assertEqual(Notification.objects.filter(recipient=self.customer).count(),0)
        self.client.post(path,{'message':'PUBLIC QA reply','is_internal':False},format='json')
        r=self.client.patch(reverse('support-ticket-detail',args=[self.ticket.pk]),{'status':'resolved','assigned_to':self.admin.pk},format='json')
        self.assertEqual(r.status_code,200,r.content)
        self.assertIn('PRIVATE INTERNAL QA',str(r.data))
        self.client.force_authenticate(self.customer)
        r=self.client.get(reverse('support-ticket-detail',args=[self.ticket.pk]));self.assertNotIn('PRIVATE INTERNAL QA',str(r.data));self.assertIn('PUBLIC QA reply',str(r.data));self.assertIn('resolved',str(r.data))
        self.assertEqual(self.client.patch(reverse('support-ticket-detail',args=[self.ticket.pk]),{'status':'open'},format='json').status_code,403)

    def test_other_customer_cannot_read_reply_or_update(self):
        self.client.force_authenticate(self.other)
        self.assertEqual(self.client.get(reverse('support-ticket-detail',args=[self.ticket.pk])).status_code,404)
        self.assertEqual(self.client.post(reverse('support-ticket-notes',args=[self.ticket.pk]),{'message':'not allowed'},format='json').status_code,403)
        self.assertEqual(self.client.patch(reverse('support-ticket-detail',args=[self.ticket.pk]),{'status':'resolved'},format='json').status_code,403)

    def test_ticket_create_validation_assignment_and_not_found(self):
        r=self.client.post(reverse('support-tickets'),{'subject':'SYNTHETIC new ticket','channel':'other'},format='json');self.assertEqual(r.status_code,201,r.content)
        self.assertEqual(r.data['customer'],self.customer.pk)
        self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.patch(reverse('support-ticket-detail',args=[self.ticket.pk]),{'assigned_to':self.other.pk},format='json').status_code,400)
        self.assertEqual(self.client.patch(reverse('support-ticket-detail',args=[999999]),{'status':'resolved'},format='json').status_code,404)

    def test_site_settings_validation_and_public_allowlist(self):
        self.client.force_authenticate(self.admin)
        for changes in [{'base_delivery_fee':'-1'},{'free_delivery_threshold':'-1'},{'privacy_policy_url':'javascript:alert(1)'},{'returns_policy_url':'//untrusted.example/path'}]:
            self.assertEqual(self.client.patch(reverse('site-settings'),changes,format='json').status_code,400)
        r=self.client.patch(reverse('site-settings'),{'support_hours':'SYNTHETIC QA hours'},format='json');self.assertEqual(r.status_code,200)
        self.client.force_authenticate(None);r=self.client.get(reverse('site-settings'));self.assertEqual(r.data['support_hours'],'SYNTHETIC QA hours');self.assertNotIn('smtp_password',r.data)
        self.admin.status='suspended';self.admin.save();self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.patch(reverse('site-settings'),{'support_hours':'bad'},format='json').status_code,403)

    def test_compliance_private_download_and_read_only_inspector(self):
        self.client.force_authenticate(self.admin)
        r=self.client.post(reverse('compliance-evidence'),{'evidence_type':'qa_audit_report','title':'SYNTHETIC QA evidence','file':SimpleUploadedFile('qa.pdf',b'%PDF-1.4 QA',content_type='application/pdf')},format='multipart')
        self.assertEqual(r.status_code,201,r.content);pk=r.data['id'];self.assertIn('/download/',r.data['file']);self.assertNotIn('/media/',r.data['file'])
        self.assertEqual(self.client.get('/media/compliance/evidence/qa.pdf').status_code,404)
        self.client.force_authenticate(self.inspector)
        self.assertEqual(self.client.get(reverse('compliance-evidence-detail',args=[pk])).status_code,200)
        self.assertEqual(self.client.get(reverse('compliance-evidence-download',args=[pk])).status_code,200)
        self.assertEqual(self.client.patch(reverse('compliance-evidence-detail',args=[pk]),{'title':'not allowed'},format='json').status_code,403)
        self.client.force_authenticate(self.customer)
        self.assertEqual(self.client.get(reverse('compliance-evidence')).status_code,403)
        self.assertEqual(self.client.get(reverse('compliance-evidence-download',args=[pk])).status_code,403)

    def test_invalid_compliance_file_and_dates(self):
        self.client.force_authenticate(self.admin)
        r=self.client.post(reverse('compliance-evidence'),{'evidence_type':'qa_audit_report','title':'QA','file':SimpleUploadedFile('qa.pdf',b'<html>QA</html>',content_type='application/pdf')},format='multipart');self.assertEqual(r.status_code,400)
        r=self.client.post(reverse('compliance-evidence'),{'evidence_type':'qa_audit_report','title':'QA','issued_at':'2026-10-30','expires_at':'2026-01-01'},format='json');self.assertEqual(r.status_code,400)

    def test_notification_failure_does_not_undo_status_change(self):
        self.client.force_authenticate(self.admin)
        with patch('apps.notifications.utils.notify_support_update',side_effect=RuntimeError('SYNTHETIC failure')):
            with self.captureOnCommitCallbacks(execute=True):
                r=self.client.patch(reverse('support-ticket-detail',args=[self.ticket.pk]),{'status':'resolved'},format='json')
        self.assertEqual(r.status_code,200);self.ticket.refresh_from_db();self.assertEqual(self.ticket.status,'resolved')

    def test_newsletter_duplicate_invalid_and_delivery_failure_preserves_subscription(self):
        # Avoid global request throttles obscuring the functional scenarios.
        from django.core.cache import cache
        cache.clear();self.client.force_authenticate(None)
        with patch('apps.support.views.send_newsletter_subscription_email',side_effect=RuntimeError('SYNTHETIC SMTP failure')):
            r=self.client.post(reverse('newsletter-subscribe'),{'email':'SYNTHETIC-QA@Example.test'},format='json')
        self.assertEqual(r.status_code,201,r.content);self.assertTrue(NewsletterSubscriber.objects.filter(email='synthetic-qa@example.test').exists());self.assertIsNone(NewsletterSubscriber.objects.get(email='synthetic-qa@example.test').last_confirmation_sent_at)
        with patch('apps.support.views.send_newsletter_subscription_email') as send:
            self.assertEqual(self.client.post(reverse('newsletter-subscribe'),{'email':'synthetic-qa@example.test'},format='json').status_code,200)
            self.assertEqual(self.client.post(reverse('newsletter-subscribe'),{'email':'synthetic-qa@example.test'},format='json').status_code,200)
            self.assertEqual(send.call_count,1)
        self.assertEqual(self.client.post(reverse('newsletter-subscribe'),{'email':'not-an-email'},format='json').status_code,400)

    def test_newsletter_throttles_repeated_public_requests(self):
        from django.core.cache import cache
        cache.clear();self.client.force_authenticate(None)
        with patch('apps.support.views.send_newsletter_subscription_email'):
            statuses=[self.client.post(reverse('newsletter-subscribe'),{'email':'throttle-qa@example.test'},format='json').status_code for _ in range(6)]
        self.assertEqual(statuses,[201,200,200,200,200,429]);cache.clear()

    def test_customer_reply_reopens_a_resolved_ticket(self):
        self.ticket.status='resolved';self.ticket.save()
        r=self.client.post(reverse('support-ticket-notes',args=[self.ticket.pk]),{'message':'SYNTHETIC QA follow-up'},format='json')
        self.assertEqual(r.status_code,200,r.content);self.assertEqual(r.data['status'],'open')

    def test_failed_reactivation_confirmation_can_be_retried(self):
        from django.core.cache import cache
        from django.utils import timezone
        cache.clear();self.client.force_authenticate(None)
        subscriber=NewsletterSubscriber.objects.create(email='reactivation-qa@example.test',is_active=False,last_confirmation_sent_at=timezone.now())
        with patch('apps.support.views.send_newsletter_subscription_email',side_effect=RuntimeError('SYNTHETIC reactivation failure')):
            self.assertEqual(self.client.post(reverse('newsletter-subscribe'),{'email':subscriber.email},format='json').status_code,200)
        subscriber.refresh_from_db();self.assertTrue(subscriber.is_active);self.assertIsNone(subscriber.last_confirmation_sent_at)
        with patch('apps.support.views.send_newsletter_subscription_email',return_value=1) as send:
            self.assertEqual(self.client.post(reverse('newsletter-subscribe'),{'email':subscriber.email},format='json').status_code,200)
        self.assertEqual(send.call_count,1);subscriber.refresh_from_db();self.assertIsNotNone(subscriber.last_confirmation_sent_at);cache.clear()
