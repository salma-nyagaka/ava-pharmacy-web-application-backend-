from types import SimpleNamespace
from unittest.mock import patch
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APIClient
from apps.accounts.models import User
from apps.notifications.models import Notification, NotificationDelivery, NotificationPreference
from apps.notifications.utils import create_notification, notify_order_status, notify_prescription_status, notify_consultation_message, notify_lab_result_ready


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class NotificationWorkflowTests(TestCase):
    def setUp(self):
        self.client=APIClient()
        self.user=User.objects.create_user(email='notify-qa@example.test',password='SyntheticQA123!',role='customer',phone='0700000902')
        self.other=User.objects.create_user(email='other-notify-qa@example.test',password='SyntheticQA123!',role='customer')
        self.client.force_authenticate(self.user)

    def rows(self,r):
        return r.data.get('results',[]) if isinstance(r.data,dict) else r.data

    def test_unread_mark_one_all_refresh_and_object_access(self):
        a=create_notification(self.user,'system','QA one','Synthetic only');b=create_notification(self.user,'system','QA two','Synthetic only');other=create_notification(self.other,'system','OTHER PRIVATE','QA')
        self.assertEqual(self.client.get(reverse('notifications-unread')).data['unread_count'],2)
        self.assertEqual(len(self.rows(self.client.get(reverse('notifications')))),2)
        self.assertEqual(self.client.post(reverse('notification-read',args=[other.pk])).status_code,404)
        self.assertEqual(self.client.get(reverse('notification-detail',args=[other.pk])).status_code,404)
        self.assertEqual(self.client.delete(reverse('notification-detail',args=[other.pk])).status_code,404)
        self.assertEqual(self.client.post(reverse('notification-read',args=[a.pk])).status_code,200)
        self.assertEqual(self.client.get(reverse('notifications-unread')).data['unread_count'],1)
        self.assertEqual(self.client.post(reverse('notifications-mark-all-read')).status_code,200)
        self.assertEqual(self.client.get(reverse('notifications-unread')).data['unread_count'],0)
        other.refresh_from_db();self.assertFalse(other.is_read)

    def test_optional_channels_follow_preferences_but_inbox_is_retained(self):
        self.client.patch(reverse('notification-preferences'),{'email_enabled':False,'sms_enabled':False,'push_enabled':False},format='json')
        with patch('apps.notifications.utils._push_to_websocket') as push:
            n=create_notification(self.user,'system','QA','Synthetic only',send_email=True,send_sms=True)
        self.assertIsNotNone(n);self.assertEqual(NotificationDelivery.objects.count(),0);push.assert_not_called()
        self.assertFalse(self.client.get(reverse('notification-preferences')).data['email_enabled'])

    def test_marketing_requires_opt_in(self):
        create_notification(self.user,'marketing','SYNTHETIC QA','Optional marketing test',send_email=True)
        self.assertEqual(NotificationDelivery.objects.count(),0)
        self.client.patch(reverse('notification-preferences'),{'marketing_enabled':True},format='json')
        create_notification(self.user,'marketing','SYNTHETIC QA','Optional marketing test',send_email=True)
        self.assertEqual(NotificationDelivery.objects.count(),1)

    def test_order_processing_email_honors_master_and_order_preferences(self):
        NotificationPreference.objects.create(user=self.user,email_enabled=False)
        order=SimpleNamespace(customer=self.user,status='processing',shipping_email=self.user.email,id=999,order_number='SYNTHETIC-ORDER',get_status_display=lambda:'Processing')
        with patch('apps.notifications.utils.queue_order_status_email') as queue:
            notify_order_status(order)
        queue.assert_not_called();self.assertEqual(Notification.objects.filter(type='order_status').count(),1)

    def test_trigger_recipient_links_and_sensitive_email_redaction(self):
        prescription=SimpleNamespace(patient=self.user,id=41,reference='SYNTHETIC-RX',get_status_display=lambda:'Approved')
        consultation=SimpleNamespace(id=42,reference='SYNTHETIC-CONS')
        lab=SimpleNamespace(patient=self.user,id=43,reference='SYNTHETIC-LAB')
        notify_prescription_status(prescription);notify_consultation_message(self.user,consultation,'SYNTHETIC Doctor');notify_lab_result_ready(lab)
        self.assertEqual(Notification.objects.filter(recipient=self.other).count(),0)
        links={n.type:n.data['url'] for n in Notification.objects.all()}
        self.assertEqual(links['prescription_status'],'/account/prescriptions?prescription=41')
        self.assertEqual(links['consultation_message'],'/account/consultations?consultation=42')
        self.assertEqual(links['lab_result'],'/account/lab-tests?request=43')
        delivery=NotificationDelivery.objects.get(notification__type='prescription_status')
        self.assertNotIn('SYNTHETIC-RX',delivery.message);self.assertEqual(delivery.subject,'Secure account update')

    def test_failure_retry_preserves_one_notification_and_delivery_history(self):
        with patch('apps.notifications.utils.send_rendered_email',side_effect=RuntimeError('SYNTHETIC delivery failure')):
            n=create_notification(self.user,'system','SYNTHETIC QA','QA only',send_email=True)
        d=NotificationDelivery.objects.get(notification=n);self.assertEqual(d.status,'failed');self.assertEqual(len(d.metadata['attempts']),1)
        self.client.force_authenticate(self.other)
        self.assertEqual(self.client.post(reverse('notification-delivery-retry',args=[d.pk])).status_code,404)
        self.client.force_authenticate(self.user)
        r=self.client.post(reverse('notification-delivery-retry',args=[d.pk]));self.assertEqual(r.status_code,200,r.content);self.assertEqual(r.data['status'],'sent')
        self.assertEqual(self.client.post(reverse('notification-delivery-retry',args=[d.pk])).status_code,409)
        d.refresh_from_db();self.assertEqual(len(d.metadata['attempts']),2);self.assertEqual(Notification.objects.count(),1);self.assertEqual(NotificationDelivery.objects.count(),1)

    def test_failed_retry_cap_and_disabled_preferences(self):
        with patch('apps.notifications.utils.send_rendered_email',side_effect=RuntimeError('SYNTHETIC failure')):
            n=create_notification(self.user,'system','QA','QA only',send_email=True);d=NotificationDelivery.objects.get(notification=n)
            for _ in range(2):
                self.assertEqual(self.client.post(reverse('notification-delivery-retry',args=[d.pk])).status_code,200)
            self.assertEqual(self.client.post(reverse('notification-delivery-retry',args=[d.pk])).status_code,429)
        self.assertEqual(Notification.objects.count(),1)

    def test_delivery_scope_and_inactive_user(self):
        n=create_notification(self.user,'system','QA','QA only',send_email=True)
        self.client.force_authenticate(self.other);self.assertEqual(len(self.rows(self.client.get(reverse('notification-deliveries')))),0)
        self.user.status='suspended';self.user.save();self.client.force_authenticate(self.user)
        self.assertEqual(self.client.get(reverse('notifications')).status_code,403)

    def test_search_pagination_and_zero_accepted_email_are_safe(self):
        Notification.objects.bulk_create([Notification(recipient=self.user,type='system',title=f'SYNTHETIC page {i}',message='QA only') for i in range(22)])
        self.assertEqual(len(self.rows(self.client.get(reverse('notifications')))),20)
        self.assertEqual(len(self.rows(self.client.get(reverse('notifications'),{'page':2}))),2)
        self.assertEqual(len(self.rows(self.client.get(reverse('notifications'),{'search':'page 21'}))),1)
        with patch('apps.notifications.utils.send_rendered_email',return_value=0):
            n=create_notification(self.user,'system','SYNTHETIC ZERO','QA only',send_email=True)
        self.assertEqual(NotificationDelivery.objects.get(notification=n).status,'failed')

    def test_retry_respects_disabled_channel_and_changed_destination(self):
        with patch('apps.notifications.utils.send_rendered_email',side_effect=RuntimeError('SYNTHETIC failure')):
            n=create_notification(self.user,'system','SYNTHETIC QA','QA only',send_email=True)
        d=NotificationDelivery.objects.get(notification=n)
        self.client.patch(reverse('notification-preferences'),{'email_enabled':False},format='json')
        self.assertEqual(self.client.post(reverse('notification-delivery-retry',args=[d.pk])).status_code,400)
        self.client.patch(reverse('notification-preferences'),{'email_enabled':True},format='json')
        self.user.email='changed-qa@example.test';self.user.save()
        self.assertEqual(self.client.post(reverse('notification-delivery-retry',args=[d.pk])).status_code,400)
        d.refresh_from_db();self.assertEqual(len(d.metadata['attempts']),1)

    def test_transactional_receipt_policy_is_separate_from_optional_updates(self):
        from decimal import Decimal
        from django.utils import timezone
        from apps.orders.utils import send_mpesa_receipt_email
        NotificationPreference.objects.create(user=self.user,email_enabled=False)
        order=SimpleNamespace(customer=self.user,shipping_email=self.user.email,shipping_first_name='SYNTHETIC QA',placed_at=timezone.now(),updated_at=timezone.now(),order_number='SYNTHETIC-RECEIPT',id=1000,total=Decimal('500'),payment_reference='SYNTHETIC-NO-PROVIDER-TRANSFER',items=SimpleNamespace(all=lambda:[]))
        with patch('apps.orders.utils.send_rendered_email',return_value=1) as send:
            send_mpesa_receipt_email(order=order)
        self.assertEqual(send.call_count,1)
