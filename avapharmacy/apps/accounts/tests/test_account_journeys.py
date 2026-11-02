"""Account acceptance journeys using real JWT login and an isolated test database."""
import re
from datetime import timedelta
from urllib.parse import parse_qs, urlparse
from unittest.mock import patch

from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import Address, PaymentMethod, Pharmacist, User
from apps.accounts.utils import issue_customer_verification_token, issue_pharmacist_activation_token
from apps.consultations.models import ClinicianProfile


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend', BOT_CHALLENGE_REQUIRED=False)
class AccountJourneyTests(TestCase):
    password = 'JourneyCustomer123!'

    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.user = User.objects.create_user(
            email='journey.customer@example.test', password=self.password,
            first_name='Journey', last_name='Customer', role=User.CUSTOMER,
        )
        self.other = User.objects.create_user(
            email='other.customer@example.test', password=self.password, role=User.CUSTOMER,
        )

    def login(self, password=None):
        response = APIClient().post(reverse('login'), {
            'email': self.user.email, 'password': password or self.password,
        }, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['tokens']['access']}")
        return response.data['tokens']

    def test_registration_verification_login_and_duplicate_rejection(self):
        payload = {
            'email': 'register.journey@example.test', 'password': self.password,
            'password_confirm': self.password, 'first_name': 'Register', 'last_name': 'Journey', 'gender': 'prefer_not_to_say',
            'phone': '+254700009901', 'role': User.CUSTOMER, 'date_of_birth': '1990-01-01',
            'delivery_address': 'Synthetic QA address', 'city': 'Nairobi', 'county': 'Nairobi',
        }
        response = self.client.post(reverse('register'), payload, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(self.client.post(reverse('register'), payload, format='json').status_code, 400)
        credentials = {'email': payload['email'], 'password': self.password}
        self.assertEqual(self.client.post(reverse('login'), credentials, format='json').status_code, 403)
        token = re.search(r'verify-email\?token=([^\s]+)', mail.outbox[0].body).group(1)
        self.assertEqual(self.client.post(reverse('verify-email'), {'token': token}).status_code, 200)
        self.assertEqual(self.client.post(reverse('verify-email'), {'token': token}).status_code, 400)
        self.assertEqual(self.client.post(reverse('login'), credentials, format='json').status_code, 200)

    def test_registration_requires_valid_date_of_birth(self):
        payload = {
            'email': 'dob.required@example.test', 'password': self.password,
            'password_confirm': self.password, 'first_name': 'Date', 'last_name': 'Check',
            'phone': '+254700009902', 'role': User.CUSTOMER,
            'delivery_address': 'Synthetic QA address', 'city': 'Nairobi',
        }
        for value in ('missing', None, '', 'invalid', '2999-01-01'):
            with self.subTest(date_of_birth=value):
                data = dict(payload)
                if value != 'missing':
                    data['date_of_birth'] = value
                response = self.client.post(reverse('register'), data, format='json')
                self.assertEqual(response.status_code, 400, response.data)
                self.assertIn('date_of_birth', str(response.data))
                self.assertFalse(User.objects.filter(email=payload['email']).exists())

    def test_registration_rejects_each_empty_required_field(self):
        payload = {
            'email': 'required.fields@example.test', 'password': self.password,
            'password_confirm': self.password, 'first_name': 'Required', 'last_name': 'Fields',
            'phone': '+254700009903', 'role': User.CUSTOMER, 'gender': 'prefer_not_to_say',
            'delivery_address': 'Synthetic QA address', 'city': 'Nairobi',
            'date_of_birth': '1990-01-01',
        }
        for field in ('email', 'first_name', 'last_name', 'phone', 'gender',
                      'delivery_address', 'city', 'date_of_birth', 'password', 'password_confirm'):
            for empty in ('missing', '', '   '):
                with self.subTest(field=field, empty=empty):
                    cache.clear()
                    data = dict(payload)
                    if empty == 'missing':
                        del data[field]
                    else:
                        data[field] = empty
                    response = self.client.post(reverse('register'), data, format='json')
                    self.assertEqual(response.status_code, 400, response.data)
                    self.assertIn(field, str(response.data))
                    self.assertFalse(User.objects.filter(email=payload['email']).exists())

    def test_profile_persistence_and_no_self_promotion(self):
        self.login()
        response = self.client.patch(reverse('me'), {
            'first_name': 'Updated', 'role': User.ADMIN, 'is_staff': True, 'is_superuser': True,
        }, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, 'Updated')
        self.assertEqual(self.user.role, User.CUSTOMER)
        self.assertFalse(self.user.is_staff)
        self.assertFalse(self.user.is_superuser)
        self.assertEqual(self.client.get(reverse('me')).data['first_name'], 'Updated')
        self.assertEqual(self.client.get(reverse('admin-users')).status_code, 403)
        public = APIClient()
        response = public.post(reverse('register'), {
            'email': 'escalation@example.test', 'password': self.password,
            'password_confirm': self.password, 'role': User.ADMIN,
        }, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertFalse(User.objects.filter(email='escalation@example.test').exists())

    def test_address_and_payment_records_are_private(self):
        address = Address.objects.create(user=self.other, label='Private', street='Synthetic private address', city='Nairobi')
        method = PaymentMethod.objects.create(
            user=self.other, brand='visa', last4='4242', expiry_month=12, expiry_year=2030,
        )
        self.login()
        for name, record in [('address-detail', address), ('payment-method-detail', method)]:
            with self.subTest(resource=name):
                url = reverse(name, args=[record.pk])
                self.assertEqual(self.client.get(url).status_code, 404)
                self.assertEqual(self.client.patch(url, {'is_default': True}, format='json').status_code, 404)
                self.assertEqual(self.client.delete(url).status_code, 404)
        self.assertTrue(Address.objects.filter(pk=address.pk, user=self.other).exists())
        self.assertTrue(PaymentMethod.objects.filter(pk=method.pk, user=self.other).exists())

    def test_profile_save_returns_complete_profile_for_the_website(self):
        self.login()
        for route in ['me', 'account-profile']:
            with self.subTest(route=route):
                response = self.client.patch(reverse(route), {'first_name': 'Saved'}, format='json')
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.data['full_name'], 'Saved Customer')
                self.assertEqual(response.data['id'], self.user.pk)
                self.assertEqual(response.data['role'], User.CUSTOMER)
                self.assertIn('date_joined', response.data)
                self.assertEqual(response.data, self.client.get(reverse(route)).data)

    def test_password_change_rejects_wrong_old_password_and_changes_login(self):
        self.login()
        payload = {'old_password': 'Incorrect123!', 'new_password': 'ChangedJourney123!', 'new_password_confirm': 'ChangedJourney123!'}
        self.assertEqual(self.client.post(reverse('password-change'), payload, format='json').status_code, 400)
        payload['old_password'] = self.password
        self.assertEqual(self.client.post(reverse('password-change'), payload, format='json').status_code, 200)
        self.assertEqual(APIClient().post(reverse('login'), {
            'email': self.user.email, 'password': self.password,
        }, format='json').status_code, 401)
        self.login(password='ChangedJourney123!')

    def test_reset_email_changes_login_and_cannot_be_reused(self):
        response = self.client.post(reverse('forgot-password'), {'email': self.user.email}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(len(mail.outbox), 1)
        match = re.search(r'https?://[^\s]+/reset-password\?[^\s]+', mail.outbox[0].body)
        self.assertIsNotNone(match)
        query = parse_qs(urlparse(match.group(0)).query)
        payload = {'uid': query['uid'][0], 'token': query['token'][0], 'new_password': 'ResetJourney123!'}
        self.assertEqual(self.client.post(reverse('reset-password'), payload, format='json').status_code, 200)
        self.assertEqual(self.client.post(reverse('reset-password'), payload, format='json').status_code, 400)
        self.assertEqual(APIClient().post(reverse('login'), {
            'email': self.user.email, 'password': self.password,
        }, format='json').status_code, 401)
        self.login(password='ResetJourney123!')

    @override_settings(PASSWORD_RESET_TIMEOUT=1)
    def test_expired_reset_link_is_rejected(self):
        from django.contrib.auth.tokens import default_token_generator
        from django.utils.encoding import force_bytes
        from django.utils.http import urlsafe_base64_encode
        from unittest.mock import patch
        token = default_token_generator.make_token(self.user)
        with patch.object(default_token_generator, '_now', return_value=default_token_generator._now() + timedelta(seconds=5)):
            response = self.client.post(reverse('reset-password'), {
                'uid': urlsafe_base64_encode(force_bytes(self.user.pk)), 'token': token,
                'new_password': 'ExpiredJourney123!',
            }, format='json')
        self.assertEqual(response.status_code, 400)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(self.password))

    def test_refresh_then_logout_blocks_refresh_reuse(self):
        tokens = self.login()
        response = APIClient().post(reverse('token-refresh'), {'refresh': tokens['refresh']}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        active_refresh = response.data.get('refresh', tokens['refresh'])
        self.assertEqual(self.client.post(reverse('logout'), {'refresh': active_refresh}, format='json').status_code, 200)
        self.assertEqual(APIClient().post(reverse('token-refresh'), {'refresh': active_refresh}, format='json').status_code, 401)

    def test_expired_verification_and_activation_links_fail(self):
        for issuer, route in [
            (issue_customer_verification_token, 'verify-email'),
            (issue_pharmacist_activation_token, 'professional-activate'),
        ]:
            with self.subTest(route=route):
                if route == 'professional-activate':
                    self.user.role = User.PHARMACIST
                    self.user.save()
                record, raw = issuer(self.user)
                record.expires_at = timezone.now() - timedelta(seconds=1)
                record.save(update_fields=['expires_at'])
                response = self.client.post(reverse(route), {
                    'token': raw, 'new_password': 'ActivationJourney123!',
                    'new_password_confirm': 'ActivationJourney123!', 'accepted_terms': True,
                }, format='json')
                self.assertEqual(response.status_code, 400, response.data)

    def test_staff_activation_login_and_activation_reuse(self):
        admin = User.objects.create_user(email='admin.journey@example.test', password=self.password, role=User.ADMIN)
        admin_tokens = APIClient().post(reverse('login'), {'email': admin.email, 'password': self.password}, format='json')
        self.assertEqual(admin_tokens.status_code, 200)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {admin_tokens.data['tokens']['access']}")
        email = 'pharmacist.journey@example.test'
        response = self.client.post(reverse('admin-users'), {
            'email': email, 'first_name': 'QA', 'last_name': 'Pharmacist', 'role': User.PHARMACIST,
            'pharmacist_license_number': 'E2E-QA-PHARM-001',
            'pharmacist_branch_location': 'Synthetic QA branch',
            'pharmacist_permissions': [Pharmacist.PERMISSION_PRESCRIPTION_REVIEW],
        }, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        raw = re.search(r'/activate/([^/\s]+)/', mail.outbox[0].body).group(1)
        payload = {'token': raw, 'new_password': self.password, 'new_password_confirm': self.password, 'accepted_terms': True}
        public = APIClient()
        self.assertEqual(public.post(reverse('professional-activate'), payload, format='json').status_code, 200)
        self.assertEqual(public.post(reverse('professional-activate'), payload, format='json').status_code, 400)
        response = public.post(reverse('login'), {'email': email, 'password': self.password}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['user']['role'], User.PHARMACIST)

    def test_suspend_and_reactivate_controls_existing_session_and_login(self):
        tokens = self.login()
        admin = User.objects.create_user(email='admin.lifecycle@example.test', password=self.password, role=User.ADMIN)
        admin_client = APIClient()
        admin_tokens = admin_client.post(reverse('login'), {'email': admin.email, 'password': self.password}, format='json')
        self.assertEqual(admin_tokens.status_code, 200)
        admin_client.credentials(HTTP_AUTHORIZATION=f"Bearer {admin_tokens.data['tokens']['access']}")
        self.assertEqual(admin_client.post(reverse('admin-user-suspend', args=[self.user.pk]), {}, format='json').status_code, 200)
        self.assertEqual(self.client.get(reverse('me')).status_code, 401)
        public = APIClient()
        self.assertIn(public.post(reverse('login'), {'email': self.user.email, 'password': self.password}, format='json').status_code, [401, 403])
        self.assertEqual(admin_client.post(reverse('admin-user-activate', args=[self.user.pk]), {}, format='json').status_code, 200)
        self.login()
        self.assertEqual(self.client.get(reverse('me')).status_code, 200)
        self.assertEqual(public.post(reverse('token-refresh'), {'refresh': tokens['refresh']}, format='json').status_code, 401)

    def test_mpesa_save_edit_default_and_delete_without_card_expiry(self):
        self.login()
        response = self.client.post(reverse('payment-methods'), {
            'brand': 'mpesa', 'last4': '1234', 'expiry_month': 0, 'expiry_year': 0,
            'cardholder_name': 'Synthetic QA', 'is_default': True,
        }, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        method = PaymentMethod.objects.get(user=self.user, brand='mpesa')
        url = reverse('payment-method-detail', args=[method.pk])
        response = self.client.patch(url, {'cardholder_name': 'Edited QA', 'is_default': True}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        method.refresh_from_db()
        self.assertEqual(method.cardholder_name, 'Edited QA')
        self.assertEqual((method.expiry_month, method.expiry_year), (0, 0))
        self.assertEqual(self.client.delete(url).status_code, 204)
        self.assertFalse(PaymentMethod.objects.filter(pk=method.pk).exists())

    def test_card_expiry_and_brand_validation_still_apply(self):
        self.login()
        for extra in [
            {'brand': 'visa', 'expiry_month': 0, 'expiry_year': 0},
            {'brand': 'visa', 'expiry_month': 13, 'expiry_year': 2035},
            {'brand': 'unsupported', 'expiry_month': 12, 'expiry_year': 2035},
            {'brand': 'visa', 'expiry_month': 1, 'expiry_year': timezone.now().year - 1},
        ]:
            with self.subTest(extra=extra):
                response = self.client.post(reverse('payment-methods'), {
                    'last4': '4242', 'cardholder_name': 'QA', **extra,
                }, format='json')
                self.assertEqual(response.status_code, 400, response.data)
        self.assertFalse(PaymentMethod.objects.filter(user=self.user).exists())

    def test_switching_mpesa_to_card_requires_valid_card_expiry(self):
        method = PaymentMethod.objects.create(user=self.user, brand='mpesa', last4='1234',
            expiry_month=0, expiry_year=0, cardholder_name='Synthetic QA')
        self.login()
        url = reverse('payment-method-detail', args=[method.pk])
        response = self.client.patch(url, {'brand': 'visa'}, format='json')
        self.assertEqual(response.status_code, 400, response.data)
        method.refresh_from_db()
        self.assertEqual(method.brand, 'mpesa')

    def test_reset_enforces_password_policy_and_revokes_refresh_sessions(self):
        from django.contrib.auth.tokens import default_token_generator
        from django.utils.encoding import force_bytes
        from django.utils.http import urlsafe_base64_encode
        tokens = self.login()
        token = default_token_generator.make_token(self.user)
        payload = {'uid': urlsafe_base64_encode(force_bytes(self.user.pk)), 'token': token}
        for weak in ['abcdefgh', '12345678', 'weakpassword1', 'NoSymbol123']:
            response = APIClient().post(reverse('reset-password'), {**payload, 'new_password': weak}, format='json')
            self.assertEqual(response.status_code, 400, response.data)
            self.user.refresh_from_db()
            self.assertTrue(self.user.check_password(self.password))
        response = APIClient().post(reverse('reset-password'), {**payload, 'new_password': 'SecureResetJourney123!'}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(APIClient().post(reverse('token-refresh'), {'refresh': tokens['refresh']}, format='json').status_code, 401)

    def test_password_change_revokes_previous_refresh_sessions(self):
        tokens = self.login()
        response = self.client.post(reverse('password-change'), {
            'old_password': self.password, 'new_password': 'SecureChangedJourney123!',
            'new_password_confirm': 'SecureChangedJourney123!',
        }, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(APIClient().post(reverse('token-refresh'), {'refresh': tokens['refresh']}, format='json').status_code, 401)

    def test_doctor_and_pediatrician_application_approval_activation_and_dashboard(self):
        admin = User.objects.create_user(email='onboarding.admin@example.test', password=self.password, role=User.ADMIN)
        admin_client = APIClient()
        admin_login = admin_client.post(reverse('login'), {'email': admin.email, 'password': self.password}, format='json')
        self.assertEqual(admin_login.status_code, 200)
        admin_client.credentials(HTTP_AUTHORIZATION=f"Bearer {admin_login.data['tokens']['access']}")
        for number, provider in enumerate(['doctor', 'pediatrician'], 1):
            with self.subTest(provider=provider):
                public = APIClient()
                email = f'{provider}.complete@example.test'
                response = public.post(reverse('professional-register'), {
                    'type': provider, 'name': f'QA {provider}', 'email': email,
                    'phone': f'+25470000880{number}', 'license_number': f'QA-LICENSE-{provider}',
                    'license_board': 'QA licensing board', 'license_expiry': '2030-12-31',
                    'id_number': f'SYNTHETIC-ID-{provider}', 'payout_account': '0700000000',
                    'specialty': 'General Medicine' if provider == 'doctor' else 'Paediatrics',
                    'background_consent': True, 'compliance_declaration': True, 'agreed_to_terms': True,
                    'documents': SimpleUploadedFile('synthetic-license.pdf', b'%PDF-1.4\nSynthetic QA only', content_type='application/pdf'),
                }, format='multipart')
                self.assertEqual(response.status_code, 201, response.data)
                profile_id = response.data['application']['id']
                self.assertFalse(User.objects.filter(email=email, is_active=True).exists())
                response = admin_client.post(reverse(f'admin-{provider}-action', args=[profile_id]), {'action': 'approve'}, format='json')
                self.assertEqual(response.status_code, 200, response.data)
                user = User.objects.get(email=email)
                self.assertFalse(user.is_active)
                self.assertEqual(public.post(reverse('login'), {'email': email, 'password': self.password}, format='json').status_code, 401)
                activation_mail = next(message for message in reversed(mail.outbox) if email in message.to and '/activate/' in message.body)
                raw = re.search(r'/activate/([^/\s]+)/', activation_mail.body).group(1)
                payload = {'token': raw, 'new_password': self.password, 'new_password_confirm': self.password, 'accepted_terms': False}
                self.assertEqual(public.post(reverse('professional-activate'), payload, format='json').status_code, 400)
                payload['accepted_terms'] = True
                self.assertEqual(public.post(reverse('professional-activate'), payload, format='json').status_code, 200)
                self.assertEqual(public.post(reverse('professional-activate'), payload, format='json').status_code, 400)
                response = public.post(reverse('login'), {'email': email, 'password': self.password}, format='json')
                self.assertEqual(response.status_code, 200, response.data)
                self.assertEqual(response.data['user']['role'], provider)
                public.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['tokens']['access']}")
                self.assertEqual(public.get(reverse(f'{provider}-dashboard')).status_code, 200)
                self.assertEqual(public.get(reverse('admin-users')).status_code, 403)

    def test_incomplete_professional_application_returns_validation_not_server_error(self):
        response = APIClient().post(reverse('professional-register'), {
            'type': 'doctor', 'name': 'Incomplete QA', 'email': 'incomplete@example.test',
            'phone': '+254700008899', 'background_consent': True,
            'compliance_declaration': True, 'agreed_to_terms': True,
        }, format='json')
        self.assertEqual(response.status_code, 400, response.data)
        self.assertFalse(User.objects.filter(email='incomplete@example.test').exists())

    def test_failed_activation_delivery_rolls_back_approval_and_allows_retry(self):
        admin = User.objects.create_user(email='retry.admin@example.test', password=self.password, role=User.ADMIN)
        self.client.force_authenticate(admin)
        for provider in ['doctor', 'pediatrician']:
            with self.subTest(provider=provider):
                email = f'retry.{provider}@example.test'
                profile = ClinicianProfile.objects.create(
                    provider_type=provider, name=f'QA Retry {provider}', email=email,
                    status=ClinicianProfile.STATUS_PENDING,
                )
                url = reverse(f'admin-{provider}-action', args=[profile.pk])
                with patch('apps.accounts.serializers.send_pharmacist_activation_email', side_effect=RuntimeError('Synthetic SMTP failure')):
                    response = self.client.post(url, {'action': 'approve'}, format='json')
                self.assertEqual(response.status_code, 500)
                profile.refresh_from_db()
                self.assertEqual(profile.status, ClinicianProfile.STATUS_PENDING)
                self.assertIsNone(profile.user_id)
                self.assertFalse(User.objects.filter(email=email).exists())
                response = self.client.post(url, {'action': 'approve'}, format='json')
                self.assertEqual(response.status_code, 200, response.data)
                profile.refresh_from_db()
                self.assertIsNotNone(profile.user_id)
                self.assertEqual(profile.status, ClinicianProfile.STATUS_APPROVED_PENDING_ACTIVATION)
