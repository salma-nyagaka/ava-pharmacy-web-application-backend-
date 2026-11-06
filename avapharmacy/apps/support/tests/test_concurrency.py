from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch
from django.core.cache import cache
from django.db import connections
from django.test import TransactionTestCase
from django.urls import reverse
from rest_framework.test import APIClient
from apps.support.models import NewsletterSubscriber


class NewsletterConcurrencyTests(TransactionTestCase):
    def test_simultaneous_duplicate_signup_has_one_subscription_and_confirmation(self):
        cache.clear();barrier=Barrier(2)
        def submit(_):
            connections.close_all();client=APIClient();barrier.wait(timeout=10)
            try:return client.post(reverse('newsletter-subscribe'),{'email':'concurrent-qa@example.test'},format='json').status_code
            finally:connections.close_all()
        with patch('apps.support.views.send_newsletter_subscription_email',return_value=1) as send:
            with ThreadPoolExecutor(max_workers=2) as pool:statuses=sorted(pool.map(submit,range(2)))
        self.assertEqual(statuses,[200,201]);self.assertEqual(NewsletterSubscriber.objects.count(),1);self.assertEqual(send.call_count,1);cache.clear()
