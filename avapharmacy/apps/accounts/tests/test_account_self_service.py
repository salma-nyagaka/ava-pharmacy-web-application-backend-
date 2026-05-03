import re

from django.core import mail
from django.test import override_settings
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.models import Address, PaymentMethod, Pharmacist, PharmacistActivationToken, User
from apps.notifications.models import NotificationPreference


class AccountSelfServiceTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            email='customer@example.com',
            password='testpass123',
            first_name='Customer',
            last_name='User',
            role=User.CUSTOMER,
            phone='+254700000001',
        )
        self.client.force_authenticate(self.user)

    def test_customer_can_update_profile_password_and_notification_preferences(self):
        profile_response = self.client.patch(
            reverse('me'),
            {
                'email': 'updated.customer@example.com',
                'first_name': 'Updated',
                'last_name': 'Customer',
                'phone': '+254700000009',
                'date_of_birth': '1994-06-12',
            },
            format='json',
        )
        self.assertEqual(profile_response.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, 'updated.customer@example.com')
        self.assertEqual(self.user.first_name, 'Updated')
        self.assertEqual(str(self.user.date_of_birth), '1994-06-12')

        password_response = self.client.post(
            reverse('password-change'),
            {
                'old_password': 'testpass123',
                'new_password': 'StrongerPass123!',
                'new_password_confirm': 'StrongerPass123!',
            },
            format='json',
        )
        self.assertEqual(password_response.status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('StrongerPass123!'))

        preferences_response = self.client.patch(
            reverse('notification-preferences'),
            {
                'sms_enabled': False,
                'marketing_enabled': True,
                'order_updates_email': True,
                'order_updates_sms': False,
            },
            format='json',
        )
        self.assertEqual(preferences_response.status_code, 200)
        preferences = NotificationPreference.objects.get(user=self.user)
        self.assertFalse(preferences.sms_enabled)
        self.assertTrue(preferences.marketing_enabled)
        self.assertFalse(preferences.order_updates_sms)

    def test_customer_can_manage_saved_payment_methods(self):
        create_response = self.client.post(
            reverse('payment-methods'),
            {
                'brand': 'visa',
                'last4': '4242',
                'expiry_month': 8,
                'expiry_year': 2030,
                'cardholder_name': 'Customer User',
                'is_default': True,
            },
            format='json',
        )
        self.assertEqual(create_response.status_code, 201)
        payment_method = PaymentMethod.objects.get(user=self.user, last4='4242')
        self.assertTrue(payment_method.is_default)

        second_response = self.client.post(
            reverse('payment-methods'),
            {
                'brand': 'mastercard',
                'last4': '5454',
                'expiry_month': 11,
                'expiry_year': 2031,
                'cardholder_name': 'Customer User',
                'is_default': True,
            },
            format='json',
        )
        self.assertEqual(second_response.status_code, 201)
        payment_method.refresh_from_db()
        self.assertFalse(payment_method.is_default)
        second_method = PaymentMethod.objects.get(user=self.user, last4='5454')
        self.assertTrue(second_method.is_default)

        update_response = self.client.patch(
            reverse('payment-method-detail', args=[payment_method.id]),
            {'is_default': True},
            format='json',
        )
        self.assertEqual(update_response.status_code, 200)
        payment_method.refresh_from_db()
        second_method.refresh_from_db()
        self.assertTrue(payment_method.is_default)
        self.assertFalse(second_method.is_default)

        delete_response = self.client.delete(reverse('payment-method-detail', args=[payment_method.id]))
        self.assertEqual(delete_response.status_code, 204)
        second_method.refresh_from_db()
        self.assertTrue(second_method.is_default)

    def test_customer_can_manage_saved_addresses_with_phone(self):
        create_response = self.client.post(
            reverse('addresses'),
            {
                'label': 'Home',
                'phone': '+254700000111',
                'street': '123 Moi Avenue',
                'city': 'Nairobi',
                'county': 'Nairobi',
                'is_default': True,
            },
            format='json',
        )
        self.assertEqual(create_response.status_code, 201)
        address = Address.objects.get(user=self.user, street='123 Moi Avenue')
        self.assertEqual(address.phone, '+254700000111')
        self.assertTrue(address.is_default)

        second_response = self.client.post(
            reverse('addresses'),
            {
                'label': 'Office',
                'phone': '+254700000222',
                'street': '456 Kenyatta Avenue',
                'city': 'Nairobi',
                'county': 'Nairobi',
                'is_default': True,
            },
            format='json',
        )
        self.assertEqual(second_response.status_code, 201)
        address.refresh_from_db()
        self.assertFalse(address.is_default)
        second_address = Address.objects.get(user=self.user, street='456 Kenyatta Avenue')
        self.assertEqual(second_address.phone, '+254700000222')
        self.assertTrue(second_address.is_default)

        update_response = self.client.patch(
            reverse('address-detail', args=[address.id]),
            {'phone': '+254700000333', 'is_default': True},
            format='json',
        )
        self.assertEqual(update_response.status_code, 200)
        address.refresh_from_db()
        second_address.refresh_from_db()
        self.assertEqual(address.phone, '+254700000333')
        self.assertTrue(address.is_default)
        self.assertFalse(second_address.is_default)


@override_settings(
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    FRONTEND_BASE_URL='http://localhost:3000',
)
class AdminPharmacistAccountTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_user(
            email='admin@example.com',
            password='AdminPass123!',
            first_name='Admin',
            last_name='User',
            role=User.ADMIN,
            phone='+254700001000',
        )
        self.client.force_authenticate(self.admin)

    def test_admin_creates_inactive_pharmacist_with_activation_flow(self):
        response = self.client.post(
            reverse('admin-users'),
            {
                'email': 'pharmacist@example.com',
                'first_name': 'Pat',
                'last_name': 'Pharmacist',
                'phone': '+254700001001',
                'role': User.PHARMACIST,
                'pharmacist_permissions': [Pharmacist.PERMISSION_PRESCRIPTION_REVIEW],
            },
            format='json',
        )

        self.assertEqual(response.status_code, 201)
        pharmacist_user = User.objects.get(email='pharmacist@example.com')
        self.assertFalse(pharmacist_user.is_active)
        self.assertEqual(pharmacist_user.role, User.PHARMACIST)
        self.assertEqual(
            pharmacist_user.pharmacist.permissions,
            [Pharmacist.PERMISSION_PRESCRIPTION_REVIEW],
        )
        self.assertEqual(PharmacistActivationToken.objects.filter(user=pharmacist_user, used_at__isnull=True).count(), 1)
        self.assertEqual(response.data['activation_email']['sent_to'], pharmacist_user.email)
        self.assertEqual(len(mail.outbox), 1)

        match = re.search(r'/activate/([^/\s]+)/', mail.outbox[0].body)
        self.assertIsNotNone(match)
        raw_token = match.group(1)

        activate_response = self.client.post(
            reverse('professional-activate'),
            {
                'token': raw_token,
                'new_password': 'NewPharmacistPass123!',
                'new_password_confirm': 'NewPharmacistPass123!',
            },
            format='json',
        )

        self.assertEqual(activate_response.status_code, 200)
        pharmacist_user.refresh_from_db()
        self.assertTrue(pharmacist_user.is_active)
        self.assertTrue(pharmacist_user.check_password('NewPharmacistPass123!'))
        self.assertFalse(PharmacistActivationToken.objects.filter(user=pharmacist_user, used_at__isnull=True).exists())

    def test_admin_cannot_assign_unknown_pharmacist_permission(self):
        response = self.client.post(
            reverse('admin-users'),
            {
                'email': 'bad-permission@example.com',
                'first_name': 'Bad',
                'last_name': 'Permission',
                'phone': '+254700001002',
                'role': User.PHARMACIST,
                'pharmacist_permissions': ['approve_everything'],
            },
            format='json',
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn('pharmacist_permissions', response.data['error']['details'])
        self.assertFalse(User.objects.filter(email='bad-permission@example.com').exists())
