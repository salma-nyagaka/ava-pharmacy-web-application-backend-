import re
from urllib.parse import parse_qs, urlparse

from django.core import mail
from django.test import override_settings
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import Address, CustomerEmailVerificationToken, PaymentMethod, Pharmacist, PharmacistActivationToken, User
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


class AccountSessionInvalidationTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_user(
            email='admin@example.com',
            password='AdminPass123!',
            first_name='Admin',
            last_name='User',
            role=User.ADMIN,
            is_staff=True,
            is_superuser=True,
        )
        self.user = User.objects.create_user(
            email='customer.session@example.com',
            password='CustomerPass123!',
            first_name='Customer',
            last_name='Session',
            role=User.CUSTOMER,
        )

    def _tokens_for_user(self, user):
        refresh = RefreshToken.for_user(user)
        return str(refresh.access_token), str(refresh)

    def test_suspended_user_access_and_refresh_tokens_are_invalidated(self):
        access, refresh = self._tokens_for_user(self.user)
        self.client.force_authenticate(self.admin)
        response = self.client.post(reverse('admin-user-suspend', args=[self.user.id]), {}, format='json')
        self.assertEqual(response.status_code, 200)

        self.user.refresh_from_db()
        self.assertFalse(self.user.is_active)
        self.assertEqual(self.user.status, User.STATUS_SUSPENDED)
        self.assertEqual(
            BlacklistedToken.objects.filter(token__user=self.user).count(),
            OutstandingToken.objects.filter(user=self.user).count(),
        )

        api_client = APIClient()
        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {access}')
        me_response = api_client.get(reverse('me'))
        self.assertEqual(me_response.status_code, 401)

        refresh_response = APIClient().post(reverse('token-refresh'), {'refresh': refresh}, format='json')
        self.assertEqual(refresh_response.status_code, 401)

    def test_soft_deleted_account_cannot_refresh_or_continue_with_access_token(self):
        access, refresh = self._tokens_for_user(self.user)
        api_client = APIClient()
        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {access}')

        delete_response = api_client.delete(reverse('account-delete'))
        self.assertEqual(delete_response.status_code, 200)

        self.user.refresh_from_db()
        self.assertFalse(self.user.is_active)
        self.assertTrue(self.user.email.startswith(f'deleted_{self.user.pk}_'))
        self.assertEqual(
            BlacklistedToken.objects.filter(token__user=self.user).count(),
            OutstandingToken.objects.filter(user=self.user).count(),
        )

        me_response = api_client.get(reverse('me'))
        self.assertEqual(me_response.status_code, 401)

        refresh_response = APIClient().post(reverse('token-refresh'), {'refresh': refresh}, format='json')
        self.assertEqual(refresh_response.status_code, 401)


@override_settings(
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    FRONTEND_BASE_URL='http://localhost:3000',
)
class CustomerRegistrationVerificationTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_customer_registers_pending_and_verifies_email(self):
        response = self.client.post(
            reverse('register'),
            {
                'email': 'new.customer@example.com',
                'first_name': 'New',
                'last_name': 'Customer',
                'phone': '+254700000101',
                'password': 'StrongCustomer123!',
                'password_confirm': 'StrongCustomer123!',
                'role': User.CUSTOMER,
                'delivery_address': 'Ava Towers, Westlands',
                'city': 'Nairobi',
                'county': 'Nairobi',
                'date_of_birth': '1990-01-01',
                'gender': 'female',
            },
            format='json',
        )

        self.assertEqual(response.status_code, 201)
        user = User.objects.get(email='new.customer@example.com')
        self.assertFalse(user.is_active)
        self.assertEqual(user.status, User.STATUS_PENDING_VERIFICATION)
        self.assertEqual(user.gender, 'female')
        self.assertTrue(Address.objects.filter(user=user, street='Ava Towers, Westlands', city='Nairobi', is_default=True).exists())
        self.assertEqual(CustomerEmailVerificationToken.objects.filter(user=user, used_at__isnull=True).count(), 1)
        self.assertEqual(len(mail.outbox), 1)

        login_response = self.client.post(
            reverse('login'),
            {'email': user.email, 'password': 'StrongCustomer123!'},
            format='json',
        )
        self.assertEqual(login_response.status_code, 403)

        match = re.search(r'(http://localhost:3000/verify-email\?token=[^\s]+)', mail.outbox[0].body)
        self.assertIsNotNone(match)
        raw_token = parse_qs(urlparse(match.group(1)).query)['token'][0]
        verify_response = self.client.post(reverse('verify-email'), {'token': raw_token}, format='json')

        self.assertEqual(verify_response.status_code, 200)
        user.refresh_from_db()
        self.assertTrue(user.is_active)
        self.assertEqual(user.status, User.STATUS_ACTIVE)
        self.assertFalse(CustomerEmailVerificationToken.objects.filter(user=user, used_at__isnull=True).exists())

    def test_customer_registration_requires_delivery_address(self):
        response = self.client.post(
            reverse('register'),
            {
                'email': 'no.address@example.com',
                'first_name': 'No',
                'last_name': 'Address',
                'phone': '+254700000102',
                'password': 'StrongCustomer123!',
                'password_confirm': 'StrongCustomer123!',
                'role': User.CUSTOMER,
            },
            format='json',
        )

        self.assertEqual(response.status_code, 400)


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
                'pharmacist_license_number': 'PPB-PHARM-001',
                'pharmacist_branch_location': 'Main Branch, Nairobi',
                'pharmacist_position': 'Senior Pharmacist',
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
        self.assertEqual(pharmacist_user.pharmacist.license_number, 'PPB-PHARM-001')
        self.assertEqual(pharmacist_user.pharmacist.branch_location, 'Main Branch, Nairobi')
        self.assertEqual(pharmacist_user.pharmacist.position, 'Senior Pharmacist')
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
                'accepted_terms': True,
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
                'pharmacist_license_number': 'PPB-PHARM-002',
                'pharmacist_branch_location': 'Main Branch, Nairobi',
                'pharmacist_position': 'Pharmacist',
                'pharmacist_permissions': ['approve_everything'],
            },
            format='json',
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn('pharmacist_permissions', response.data['error']['details'])
        self.assertFalse(User.objects.filter(email='bad-permission@example.com').exists())

    def test_admin_cannot_create_duplicate_pharmacist_license(self):
        Pharmacist.objects.create(
            user=User.objects.create_user(
                email='existing-pharmacist@example.com',
                password='ExistingPass123!',
                first_name='Existing',
                last_name='Pharmacist',
                phone='+254700001010',
                role=User.PHARMACIST,
            ),
            license_number='PPB-DUP-001',
        )
        response = self.client.post(
            reverse('admin-users'),
            {
                'email': 'duplicate-pharmacist@example.com',
                'first_name': 'Duplicate',
                'last_name': 'Pharmacist',
                'phone': '+254700001011',
                'role': User.PHARMACIST,
                'pharmacist_license_number': 'PPB-DUP-001',
                'pharmacist_branch_location': 'Westlands',
                'pharmacist_position': 'Pharmacist',
                'pharmacist_permissions': [Pharmacist.PERMISSION_PRESCRIPTION_REVIEW],
            },
            format='json',
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn('pharmacist_license_number', response.data['error']['details'])
