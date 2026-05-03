from django.core import mail
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.support.models import NewsletterSubscriber


class NewsletterSubscriptionTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_public_user_can_subscribe_and_receive_confirmation_email(self):
        response = self.client.post(
            reverse('newsletter-subscribe'),
            {'email': 'Customer@Example.com', 'source': 'homepage-footer'},
            format='json',
        )

        self.assertEqual(response.status_code, 201)
        subscriber = NewsletterSubscriber.objects.get(email='customer@example.com')
        self.assertEqual(subscriber.source, 'homepage-footer')
        self.assertTrue(subscriber.is_active)
        self.assertIsNotNone(subscriber.last_confirmation_sent_at)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['customer@example.com'])
        self.assertIn('newsletter', mail.outbox[0].subject.lower())
        self.assertTrue(mail.outbox[0].alternatives)
        self.assertIn('You are subscribed', mail.outbox[0].alternatives[0][0])

    def test_existing_subscriber_is_reactivated_and_receives_new_confirmation_email(self):
        subscriber = NewsletterSubscriber.objects.create(
            email='customer@example.com',
            source='website',
            is_active=False,
        )

        response = self.client.post(
            reverse('newsletter-subscribe'),
            {'email': 'customer@example.com', 'source': 'footer'},
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        subscriber.refresh_from_db()
        self.assertTrue(subscriber.is_active)
        self.assertEqual(subscriber.source, 'footer')
        self.assertIsNotNone(subscriber.last_confirmation_sent_at)
        self.assertEqual(len(mail.outbox), 1)
        self.assertTrue(mail.outbox[0].alternatives)
