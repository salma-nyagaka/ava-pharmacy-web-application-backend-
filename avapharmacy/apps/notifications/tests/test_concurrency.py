from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch
from django.db import connections
from django.test import TransactionTestCase
from django.urls import reverse
from rest_framework.test import APIClient
from apps.accounts.models import User
from apps.notifications.models import Notification,NotificationDelivery


class DeliveryConcurrencyTests(TransactionTestCase):
    def test_two_retries_send_once_without_recreating_business_notification(self):
        user=User.objects.create_user(email='retry-concurrency@example.test',password='SyntheticQA123!',role='customer')
        n=Notification.objects.create(recipient=user,type='system',title='SYNTHETIC QA',message='QA only')
        d=NotificationDelivery.objects.create(notification=n,recipient=user,channel='email',destination=user.email,subject='SYNTHETIC QA',message='QA only',status='failed',metadata={'attempts':[{'number':1,'status':'failed'}]})
        barrier=Barrier(2)
        def run(_):
            connections.close_all();client=APIClient();client.force_authenticate(user);barrier.wait(timeout=10)
            try:return client.post(reverse('notification-delivery-retry',args=[d.pk])).status_code
            finally:connections.close_all()
        with patch('apps.notifications.utils.send_rendered_email',return_value=1) as send:
            with ThreadPoolExecutor(max_workers=2) as pool:results=sorted(pool.map(run,range(2)))
        self.assertEqual(results,[200,409]);self.assertEqual(send.call_count,1)
        self.assertEqual(Notification.objects.count(),1);self.assertEqual(NotificationDelivery.objects.count(),1)
