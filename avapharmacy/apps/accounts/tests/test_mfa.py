"""Staff MFA integration and bypass regression tests."""
import hashlib
from concurrent.futures import ThreadPoolExecutor
from unittest import skipUnless
from datetime import timedelta
from unittest.mock import patch

import pyotp
from django.contrib import admin
from django.core import management
from django.core.cache import cache
from django.db import connection, connections, transaction
from django.test import TestCase, RequestFactory, TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts import mfa
from apps.accounts.admin_site import MFAAdminAuthenticationForm
from apps.accounts.models import AdminAuditLog, MFAChallenge, MFACredential, User


class MFATests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.user = User.objects.create_user(email='staff@example.com', password='StrongPass123!', role=User.ADMIN)
        self.bot = patch('apps.accounts.views.enforce_public_bot_controls')
        self.bot.start()
        self.addCleanup(self.bot.stop)
        self.now = timezone.now().replace(microsecond=0)
        clock = patch('apps.accounts.mfa.timezone.now', return_value=self.now)
        self.clock = clock.start()
        self.addCleanup(clock.stop)

    def post(self, name, **data):
        return self.client.post(reverse(name), data, format='json')

    def login(self):
        return self.post('login', email=self.user.email, password='StrongPass123!')

    def enroll(self):
        login = self.login()
        self.assertEqual(login.status_code, 200)
        self.assertNotIn('tokens', login.data)
        challenge = login.data['challenge_token']
        setup = self.post('mfa-setup', challenge_token=challenge)
        self.assertEqual(setup.status_code, 200)
        secret = setup.data['secret']
        result = self.post('mfa-confirm', challenge_token=challenge, code=pyotp.TOTP(secret).at(self.now))
        self.assertEqual(result.status_code, 200, result.data)
        return result.data, secret, challenge

    def test_all_requested_roles_require_mfa_and_other_roles_keep_login(self):
        for role in [User.ADMIN, User.PHARMACIST, User.DOCTOR, User.PEDIATRICIAN]:
            with self.subTest(role=role):
                cache.clear()
                self.user.role = role
                self.user.save(update_fields=['role'])
                response = self.login()
                self.assertTrue(response.data['mfa_required'])
                self.assertTrue(response.data['mfa_setup_required'])
                self.assertNotIn('tokens', response.data)
        for role in [User.CUSTOMER, User.LAB_PARTNER, User.LAB_TECHNICIAN, User.INVENTORY_STAFF]:
            cache.clear()
            self.user.role = role
            self.user.is_staff = False
            self.user.save(update_fields=['role', 'is_staff'])
            self.assertIn('tokens', self.login().data)

    def test_staff_flag_cannot_bypass_mfa_with_customer_role(self):
        self.user.role = User.CUSTOMER
        self.user.is_staff = True
        self.user.save()
        self.assertTrue(self.login().data['mfa_required'])

    def test_enrollment_encryption_single_use_and_verified_tokens(self):
        payload, secret, challenge = self.enroll()
        credential = MFACredential.objects.get(user=self.user)
        self.assertNotIn(secret, credential.secret)
        self.assertEqual(mfa.cipher().decrypt(credential.secret.encode()).decode(), secret)
        self.assertEqual(len(payload['recovery_codes']), 10)
        self.assertNotIn(payload['recovery_codes'][0], credential.recovery_hashes)
        row = MFAChallenge.objects.get(user=self.user)
        self.assertNotEqual(row.token_hash, challenge)
        self.assertEqual(row.token_hash, hashlib.sha256(challenge.encode()).hexdigest())
        self.assertEqual(row.pending_secret, '')
        self.assertEqual(self.post('mfa-confirm', challenge_token=challenge, code=pyotp.TOTP(secret).at(self.now)).status_code, 400)
        self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + payload['tokens']['access'])
        self.assertEqual(self.client.get(reverse('me')).status_code, 200)
        self.client.credentials()
        refreshed = self.post('token-refresh', refresh=payload['tokens']['refresh'])
        self.assertEqual(refreshed.status_code, 200, refreshed.data)
        self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + refreshed.data['access'])
        self.assertEqual(self.client.get(reverse('me')).status_code, 200)

    def test_existing_access_and_refresh_tokens_are_rejected(self):
        old = RefreshToken.for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + str(old.access_token))
        self.assertEqual(self.client.get(reverse('me')).status_code, 401)
        self.client.credentials()
        self.assertIn(self.post('token-refresh', refresh=str(old)).status_code, [401, 403])

    def test_totp_replay_rejected_and_later_code_accepted(self):
        _, secret, _ = self.enroll()
        challenge = self.login().data['challenge_token']
        self.assertEqual(self.post('mfa-verify', challenge_token=challenge, code=pyotp.TOTP(secret).at(self.now)).status_code, 400)
        self.clock.return_value = self.now + timedelta(seconds=30)
        result = self.post('mfa-verify', challenge_token=challenge, code=pyotp.TOTP(secret).at(self.clock.return_value))
        self.assertEqual(result.status_code, 200)
        self.assertNotIn('recovery_codes', result.data)
        self.assertEqual(self.post('mfa-verify', challenge_token=challenge, code=pyotp.TOTP(secret).at(self.clock.return_value)).status_code, 400)

    def test_recovery_code_is_single_use(self):
        payload, _, _ = self.enroll()
        challenge = self.login().data['challenge_token']
        self.assertEqual(self.post('mfa-verify', challenge_token=challenge, code=payload['recovery_codes'][0]).status_code, 200)
        challenge = self.login().data['challenge_token']
        self.assertEqual(self.post('mfa-verify', challenge_token=challenge, code=payload['recovery_codes'][0]).status_code, 400)
        self.assertEqual(len(MFACredential.objects.get(user=self.user).recovery_hashes), 9)

    def test_lockout_persists_across_new_challenges(self):
        payload, _, _ = self.enroll()
        challenge = self.login().data['challenge_token']
        for _ in range(5):
            self.assertEqual(self.post('mfa-verify', challenge_token=challenge, code='invalid').status_code, 400)
        challenge = self.login().data['challenge_token']
        self.assertEqual(self.post('mfa-verify', challenge_token=challenge, code=payload['recovery_codes'][0]).status_code, 429)
        self.clock.return_value = self.now + timedelta(minutes=16)
        cache.clear()
        challenge = self.login().data['challenge_token']
        self.assertEqual(self.post('mfa-verify', challenge_token=challenge, code=payload['recovery_codes'][0]).status_code, 200)

    def test_enrollment_cannot_be_replaced_or_bypassed(self):
        response = self.login()
        challenge = response.data['challenge_token']
        self.assertEqual(self.post('mfa-verify', challenge_token=challenge, code='123456').status_code, 400)
        first = self.post('mfa-setup', challenge_token=challenge)
        second = self.post('mfa-setup', challenge_token=challenge)
        self.assertEqual(first.data['secret'], second.data['secret'])
        code = pyotp.TOTP(first.data['secret']).at(self.now)
        self.assertEqual(self.post('mfa-confirm', challenge_token=challenge, code=code).status_code, 200)
        challenge = self.login().data['challenge_token']
        self.assertEqual(self.post('mfa-setup', challenge_token=challenge).status_code, 400)
        self.assertEqual(self.post('mfa-confirm', challenge_token=challenge, code=code).status_code, 400)

    def test_expired_superseded_tampered_and_password_changed_challenges(self):
        old = self.login().data['challenge_token']
        current = self.login().data['challenge_token']
        self.assertEqual(self.post('mfa-setup', challenge_token=old).status_code, 400)
        self.assertEqual(self.post('mfa-setup', challenge_token=current + 'x').status_code, 400)
        self.clock.return_value = self.now + timedelta(minutes=6)
        self.assertEqual(self.post('mfa-setup', challenge_token=current).status_code, 400)
        cache.clear()
        current = self.login().data['challenge_token']
        self.user.set_password('Changed123!')
        self.user.save(update_fields=['password'])
        self.assertEqual(self.post('mfa-setup', challenge_token=current).status_code, 400)

    def test_suspended_user_cannot_finish_mfa(self):
        challenge = self.login().data['challenge_token']
        User.objects.filter(pk=self.user.pk).update(status=User.STATUS_SUSPENDED)
        self.assertEqual(self.post('mfa-setup', challenge_token=challenge).status_code, 400)

    def test_reset_revokes_verified_tokens_and_requires_enrollment(self):
        from io import StringIO
        payload, _, _ = self.enroll()
        management.call_command('reset_mfa', email=self.user.email, reason='Verified support case 123', stdout=StringIO())
        self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + payload['tokens']['access'])
        self.assertEqual(self.client.get(reverse('me')).status_code, 401)
        self.client.credentials()
        self.assertEqual(self.post('token-refresh', refresh=payload['tokens']['refresh']).status_code, 401)
        self.assertTrue(self.login().data['mfa_setup_required'])
        self.assertTrue(AdminAuditLog.objects.filter(action='mfa_reset').exists())

    def admin_form(self, code):
        request = RequestFactory().post('/admin/login/')
        request.session = {}
        form = MFAAdminAuthenticationForm(request, data={'username': self.user.email, 'password': 'StrongPass123!', 'mfa_code': code})
        return form, request

    def test_admin_requires_enrollment_and_mfa_session(self):
        form, _ = self.admin_form('123456')
        self.assertFalse(form.is_valid())
        payload, _, _ = self.enroll()
        form, request = self.admin_form(payload['recovery_codes'][0])
        self.assertTrue(form.is_valid(), form.errors)
        request.user = self.user
        self.assertTrue(admin.site.has_permission(request))
        request.session = {}
        self.assertFalse(admin.site.has_permission(request))

    def test_admin_invalid_attempts_commit(self):
        self.enroll()
        for _ in range(5):
            form, _ = self.admin_form('wrong')
            self.assertFalse(form.is_valid())
        credential = MFACredential.objects.get(user=self.user)
        self.assertEqual(credential.failed_attempts, 5)
        self.assertTrue(mfa.locked(credential))

    def test_mfa_input_validation_and_no_store(self):
        self.assertEqual(self.post('mfa-setup').status_code, 400)
        self.assertEqual(self.post('mfa-setup', challenge_token='unknown')['Cache-Control'], 'no-store')
        challenge = self.login().data['challenge_token']
        self.post('mfa-setup', challenge_token=challenge)
        self.assertEqual(self.post('mfa-confirm', challenge_token=challenge).status_code, 400)

    def test_websocket_authenticator_uses_mfa(self):
        from apps.consultations.consumers import JWTAuthentication
        from apps.accounts.authentication import MFAJWTAuthentication
        self.assertIs(JWTAuthentication, MFAJWTAuthentication)

    @override_settings(STATICFILES_STORAGE='django.contrib.staticfiles.storage.StaticFilesStorage')
    def test_admin_login_page_and_session_require_code(self):
        payload, _, _ = self.enroll()
        page = self.client.get(reverse('admin:login'))
        self.assertContains(page, 'name="mfa_code"')
        data = {'username': self.user.email, 'password': 'StrongPass123!', 'next': reverse('admin:index')}
        self.assertEqual(self.client.post(reverse('admin:login'), data).status_code, 200)
        data['mfa_code'] = payload['recovery_codes'][0]
        self.assertEqual(self.client.post(reverse('admin:login'), data).status_code, 302)
        self.assertEqual(self.client.get(reverse('admin:index')).status_code, 200)
        MFACredential.objects.filter(user=self.user).delete()
        self.assertEqual(self.client.get(reverse('admin:index')).status_code, 302)

    def test_public_staff_registration_defers_mfa_until_login(self):
        response = self.post('register', email='doctor.register@example.test', first_name='Test', last_name='Doctor',
                             password='StrongPass123!', password_confirm='StrongPass123!', role=User.DOCTOR,
                             date_of_birth='1990-01-01')
        self.assertEqual(response.status_code, 201, response.data)
        self.assertNotIn('mfa_setup_required', response.data)
        self.assertNotIn('challenge_token', response.data)
        self.assertNotIn('tokens', response.data)
        self.assertFalse(MFAChallenge.objects.filter(user__email='doctor.register@example.test').exists())
        login = self.post('login', email='doctor.register@example.test', password='StrongPass123!')
        self.assertTrue(login.data['mfa_setup_required'])


@skipUnless(connection.vendor == 'postgresql', 'Requires PostgreSQL row locks')
class MFAConcurrencyTests(TransactionTestCase):
    def test_parallel_verification_issues_only_one_session(self):
        cache.clear()
        user = User.objects.create_user(email='race@example.test', password='StrongPass123!', role=User.DOCTOR)
        secret = pyotp.random_base32()
        recovery_code = '0123456789abcdef'
        credential = MFACredential.objects.create(user=user, enabled=True, version='race-version',
                                                secret=mfa.cipher().encrypt(secret.encode()).decode(),
                                                recovery_hashes=[mfa.recovery_hash(recovery_code)])
        for code in (pyotp.TOTP(secret).now(), recovery_code):
            with self.subTest(code_type='totp' if len(code) == 6 else 'recovery'):
                with transaction.atomic():
                    User.objects.select_for_update().get(pk=user.pk)
                    challenge = mfa.issue_challenge(user)['challenge_token']

                def verify():
                    try:
                        return APIClient().post(reverse('mfa-verify'), {'challenge_token': challenge, 'code': code}, format='json').status_code
                    finally:
                        connections.close_all()

                with ThreadPoolExecutor(max_workers=2) as executor:
                    statuses = list(executor.map(lambda _: verify(), range(2)))
                self.assertEqual(sorted(statuses), [200, 400])
        credential.refresh_from_db()
        self.assertEqual(credential.recovery_hashes, [])
