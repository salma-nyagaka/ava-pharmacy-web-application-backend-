from django.core import mail
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.support.models import NewsletterSubscriber, SiteSettings


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


class SiteSettingsTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_public_user_can_fetch_site_settings(self):
        response = self.client.get(reverse('site-settings'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['support_email'], 'support@avapharmacy.co.ke')
        self.assertEqual(response.data['active_delivery_zones_list'], ['Nairobi', 'Kiambu', 'Mombasa'])

    def test_anonymous_user_cannot_update_site_settings(self):
        response = self.client.put(
            reverse('site-settings'),
            {'support_email': 'care@example.com'},
            format='json',
        )

        self.assertEqual(response.status_code, 403)

    def test_admin_can_update_site_settings(self):
        admin = User.objects.create_user(
            email='admin@example.com',
            password='password',
            first_name='Admin',
            last_name='User',
            role=User.ADMIN,
        )
        self.client.force_authenticate(admin)

        response = self.client.put(
            reverse('site-settings'),
            {
                'support_email': 'care@example.com',
                'support_phone': '+254 711 111 111',
                'whatsapp_phone': '+254 722 222 222',
                'support_address': 'Nairobi, Kenya',
                'support_hours': 'Mon - Fri: 08am - 06pm',
                'base_delivery_fee': '250.00',
                'free_delivery_threshold': '2500.00',
                'active_delivery_zones': 'Nairobi, Nakuru',
            },
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        settings = SiteSettings.get_solo()
        self.assertEqual(settings.support_email, 'care@example.com')
        self.assertEqual(response.data['active_delivery_zones_list'], ['Nairobi', 'Nakuru'])
