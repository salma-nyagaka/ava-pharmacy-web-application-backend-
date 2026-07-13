from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APIClient

from apps.support.checks import (
    check_bot_challenge_settings,
    check_frontend_origin_settings,
    check_payment_settings,
    check_site_compliance_settings,
)
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


class DeploymentReadinessCheckTests(TestCase):
    def test_site_compliance_check_flags_missing_pharmacy_display_fields(self):
        SiteSettings.objects.create(
            support_email='care@example.com',
            health_safety_code='Pending update',
        )

        messages = check_site_compliance_settings(None)

        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0].id, 'ava.E001')
        self.assertIn('Health safety code', messages[0].hint)
        self.assertIn('Online pharmacy license number', messages[0].hint)

    def test_site_compliance_check_passes_when_required_fields_are_present(self):
        SiteSettings.objects.create(
            support_email='care@example.com',
            support_phone='+254 711 111 111',
            whatsapp_phone='+254 722 222 222',
            support_address='Nairobi, Kenya',
            support_hours='Mon - Sun: 09am - 5pm',
            postal_address='P.O. Box 12345-00100 Nairobi',
            health_safety_code='HS-12345',
            premises_registration_number='PPB-PREM-12345',
            online_pharmacy_license_number='PPB-ONLINE-12345',
            superintendent_name='Jane Pharmacist',
            superintendent_registration_number='PPB-SUP-12345',
            pharmacist_consultation_hours='Mon - Sun: 09am - 5pm',
            ppb_contact_name='The Pharmacy and Poisons Board',
            ppb_contact_address='Lenana Road, Nairobi',
            ppb_contact_phone='+254 709 770 100',
            ppb_contact_email='info@pharmacyboardkenya.org.ke',
            ppb_website='https://www.pharmacyboardkenya.org.ke',
            complaint_policy_url='/help',
            privacy_policy_url='/privacy',
            returns_policy_url='/returns',
        )

        self.assertEqual(check_site_compliance_settings(None), [])

    @override_settings(
        BOT_CHALLENGE_PROVIDER='turnstile',
        TURNSTILE_SECRET_KEY='turnstile-secret',
        BOT_CHALLENGE_REQUIRED=True,
    )
    def test_bot_challenge_check_passes_when_turnstile_is_configured(self):
        self.assertEqual(check_bot_challenge_settings(None), [])

    @override_settings(BOT_CHALLENGE_PROVIDER='turnstile', TURNSTILE_SECRET_KEY='', BOT_CHALLENGE_REQUIRED=False)
    def test_bot_challenge_check_flags_missing_turnstile_configuration(self):
        messages = check_bot_challenge_settings(None)
        self.assertEqual({message.id for message in messages}, {'ava.E011', 'ava.E012'})

    @override_settings(
        MPESA_CONSUMER_KEY='key',
        MPESA_CONSUMER_SECRET='secret',
        MPESA_SHORTCODE='123456',
        MPESA_PASSKEY='passkey',
        MPESA_CALLBACK_URL='https://api.example.com/api/payments/mpesa/callback/',
        MPESA_PAYBILL_NUMBER='123456',
        MPESA_C2B_SHORTCODE='123456',
        MPESA_C2B_VALIDATION_URL='https://api.example.com/api/payments/mpesa/paybill/validation/',
        MPESA_C2B_CONFIRMATION_URL='https://api.example.com/api/payments/mpesa/paybill/confirmation/',
        MPESA_C2B_URLS_REGISTERED=True,
        MPESA_STK_PUSH_AMOUNT_OVERRIDE='',
    )
    def test_payment_check_passes_for_public_mpesa_configuration(self):
        self.assertEqual(check_payment_settings(None), [])

    @override_settings(
        MPESA_CONSUMER_KEY='',
        MPESA_CONSUMER_SECRET='',
        MPESA_SHORTCODE='',
        MPESA_PASSKEY='',
        MPESA_CALLBACK_URL='http://localhost:8000/api/payments/mpesa/callback/',
        MPESA_PAYBILL_NUMBER='',
        MPESA_C2B_SHORTCODE='',
        MPESA_C2B_VALIDATION_URL='http://localhost:8000/api/payments/mpesa/paybill/validation/',
        MPESA_C2B_CONFIRMATION_URL='http://localhost:8000/api/payments/mpesa/paybill/confirmation/',
        MPESA_C2B_URLS_REGISTERED=False,
        MPESA_STK_PUSH_AMOUNT_OVERRIDE='1',
    )
    def test_payment_check_flags_incomplete_mpesa_configuration(self):
        messages = check_payment_settings(None)
        ids = {message.id for message in messages}
        self.assertIn('ava.E020', ids)
        self.assertIn('ava.E021', ids)
        self.assertIn('ava.E022', ids)
        self.assertIn('ava.E023', ids)

    @override_settings(
        CORS_ALLOWED_ORIGINS=['https://shop.example.com'],
        FRONTEND_BASE_URL='https://shop.example.com',
    )
    def test_frontend_origin_check_passes_for_public_https_origin(self):
        self.assertEqual(check_frontend_origin_settings(None), [])

    @override_settings(
        CORS_ALLOWED_ORIGINS=['http://localhost:5173', 'https://shop.example.com'],
        FRONTEND_BASE_URL='http://localhost:5173',
    )
    def test_frontend_origin_check_flags_local_origins(self):
        messages = check_frontend_origin_settings(None)
        self.assertEqual({message.id for message in messages}, {'ava.E030', 'ava.E031'})
