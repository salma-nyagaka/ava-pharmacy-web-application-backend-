import re
from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import LoginOTP, User


@override_settings(LOGIN_OTP_DELIVERY='email', LOGIN_OTP_REQUIRED=True, BOT_CHALLENGE_REQUIRED=False, TURNSTILE_SECRET_KEY='', HCAPTCHA_SECRET_KEY='', EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class LoginOTPTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            email='otp@example.com', password='LoginSecret123!', phone='0712345678',
        )
        from django.core.cache import cache
        cache.clear()

    def login(self):
        return self.client.post(reverse('login'), {
            'email': self.user.email, 'password': 'LoginSecret123!',
        }, format='json')

    def verify(self, challenge, code):
        return self.client.post(reverse('login-verify-otp'), {
            'challenge_id': challenge, 'code': code,
        }, format='json')

    @patch('apps.accounts.login_otp.send_mail', return_value=1)
    def test_login_requires_sms_and_code_is_single_use(self, sms):
        response = self.login()
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('tokens', response.data)
        code = re.search(r'\b[0-9]{6}\b', sms.call_args.args[1]).group()
        self.assertEqual(sms.call_args.args[3], [self.user.email])
        challenge = response.data['challenge_id']
        self.assertNotIn(code, str(response.data))
        self.assertNotEqual(LoginOTP.objects.get().code_hash, code)
        verified = self.verify(challenge, code)
        self.assertEqual(verified.status_code, 200)
        self.assertIn('access', verified.data['tokens'])
        self.assertEqual(self.verify(challenge, code).status_code, 400)

    @patch('apps.accounts.login_otp.send_mail', return_value=1)
    def test_expiry_attempt_limit_and_account_changes(self, sms):
        from apps.accounts.login_otp import OTPError, verify_login_otp
        self.login()
        challenge = LoginOTP.objects.get()
        code = re.search(r'\b[0-9]{6}\b', sms.call_args.args[1]).group()
        wrong = '000000' if code != '000000' else '111111'
        for _ in range(5):
            with self.assertRaises(OTPError):
                verify_login_otp(challenge.pk, wrong)
        with self.assertRaises(OTPError):
            verify_login_otp(challenge.pk, code)
        challenge.refresh_from_db()
        self.assertEqual(challenge.attempts, 5)
        challenge.attempts = 0
        challenge.expires_at = timezone.now() - timedelta(seconds=1)
        challenge.save()
        with self.assertRaises(OTPError):
            verify_login_otp(challenge.pk, code)
        challenge.expires_at = timezone.now() + timedelta(minutes=5)
        challenge.save()
        for changes in ({'status': 'suspended'}, {'email': 'changed@example.com'}, {'password': 'changed'}):
            with self.subTest(changes=changes):
                original = {key: getattr(self.user, key) for key in changes}
                User.objects.filter(pk=self.user.pk).update(**changes)
                with self.assertRaises(OTPError):
                    verify_login_otp(challenge.pk, code)
                User.objects.filter(pk=self.user.pk).update(**original)

    @patch('apps.accounts.login_otp.send_mail', return_value=1)
    def test_resend_cooldown(self, sms):
        self.login()
        response = self.login()
        self.assertEqual(response.status_code, 429)
        self.assertGreater(int(response['Retry-After']), 0)
        self.assertEqual(sms.call_count, 1)

    @patch('apps.accounts.login_otp.send_mail', side_effect=RuntimeError('provider down'))
    def test_delivery_failure_issues_no_challenge(self, sms):
        self.assertEqual(self.login().status_code, 503)
        self.assertFalse(LoginOTP.objects.exists())

    @patch('apps.accounts.login_otp.send_mail', return_value=1)
    def test_missing_phone_is_allowed_and_invalid_password_sends_nothing(self, sms):
        self.user.phone = ''
        self.user.save()
        self.assertEqual(self.login().status_code, 200)
        sms.assert_called_once()
        sms.reset_mock()
        self.user.set_password('DifferentPassword123!')
        self.user.save()
        self.assertEqual(self.login().status_code, 401)
        sms.assert_not_called()

    @patch('apps.accounts.login_otp.send_mail', return_value=1)
    def test_resend_replaces_code_and_invalidates_old_code(self, sms):
        from apps.accounts.login_otp import OTPError, issue_login_otp, verify_login_otp
        with patch('apps.accounts.login_otp.secrets.randbelow', return_value=123456):
            self.login()
        challenge = LoginOTP.objects.get()
        LoginOTP.objects.filter(pk=challenge.pk).update(sent_at=timezone.now() - timedelta(seconds=61))
        with patch('apps.accounts.login_otp.secrets.randbelow', return_value=654321):
            replacement = issue_login_otp(self.user)
        with self.assertRaises(OTPError):
            verify_login_otp(replacement['challenge_id'], '123456')
        self.assertEqual(verify_login_otp(replacement['challenge_id'], '654321'), self.user)


@override_settings(
    LOGIN_SMS_PROVIDER='bongasms',
    BONGASMS_SEND_URL='https://sms.example.test/v1/send-sms',
    BONGASMS_CLIENT_ID='123', BONGASMS_API_KEY='synthetic-key',
    BONGASMS_API_SECRET='synthetic-secret', BONGASMS_SERVICE_ID='1',
)
class BongaSMSDeliveryTests(TestCase):
    @patch('requests.post')
    def test_documented_request_and_success(self, post):
        from apps.accounts.login_otp import send_login_sms
        post.return_value.status_code = 200
        post.return_value.json.return_value = {'status': 222, 'error': None}
        send_login_sms('+254712345678', '012345')
        params = post.call_args.kwargs['data']
        self.assertEqual(params['MSISDN'], '254712345678')
        self.assertEqual(params['apiClientID'], '123')
        self.assertIn('012345', params['txtMessage'])
        self.assertFalse(post.call_args.kwargs['allow_redirects'])
        post.return_value.close.assert_called_once()

    @patch('requests.post')
    def test_provider_error_is_rejected(self, post):
        from apps.accounts.login_otp import send_login_sms
        post.return_value.status_code = 200
        post.return_value.json.return_value = {'status': 666}
        with self.assertRaises(RuntimeError):
            send_login_sms('+254712345678', '123456')

    @override_settings(BONGASMS_SEND_URL='http://sms.example.test/v1/send-sms')
    @patch('requests.post')
    def test_insecure_endpoint_sends_nothing(self, post):
        from apps.accounts.login_otp import send_login_sms
        with self.assertRaises(RuntimeError):
            send_login_sms('+254712345678', '123456')
        post.assert_not_called()


@override_settings(LOGIN_OTP_DELIVERY='email', EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class EmailOTPDeliveryTests(TestCase):
    def test_email_contains_code_and_verifies_without_phone(self):
        from django.core import mail
        from apps.accounts.login_otp import issue_login_otp, verify_login_otp
        user = User.objects.create_user(email='emailotp@example.com', password='Secret123!')
        challenge = issue_login_otp(user)
        self.assertEqual(challenge['delivery_channel'], 'email')
        self.assertEqual(challenge['email_hint'], 'e***@example.com')
        self.assertNotIn('phone_hint', challenge)
        self.assertEqual(mail.outbox[0].to, [user.email])
        code = re.search(r'\b[0-9]{6}\b', mail.outbox[0].body).group()
        self.assertEqual(verify_login_otp(challenge['challenge_id'], code), user)


@override_settings(
    LOGIN_OTP_DELIVERY='sms', LOGIN_OTP_REQUIRED=True, LOGIN_SMS_PROVIDER='bongasms',
    BOT_CHALLENGE_REQUIRED=False, TURNSTILE_SECRET_KEY='', HCAPTCHA_SECRET_KEY='',
    BONGASMS_SEND_URL='https://app.bongasms.co.ke/api/send-bulk-sms',
    BONGASMS_CLIENT_ID='123', BONGASMS_API_KEY='test-key', BONGASMS_API_SECRET='test-secret',
)
@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class BongaSMSLoginFlowTests(TestCase):
    @patch('requests.post')
    def test_login_issues_tokens_only_after_sms_code_verification(self, post):
        from django.core.cache import cache

        cache.clear()
        post.return_value.status_code = 200
        post.return_value.json.return_value = {'status': 222, 'batch_code': None}
        user = User.objects.create_user(
            email='bonga-login@example.com', password='LoginSecret123!', phone='0712 345 678',
        )
        client = APIClient()
        response = client.post(reverse('login'), {
            'email': user.email, 'password': 'LoginSecret123!',
        }, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['delivery_channel'], 'both')
        self.assertEqual(response.data['phone_hint'], '••••5678')
        self.assertNotIn('tokens', response.data)
        post.assert_called_once()
        data = post.call_args.kwargs['data']
        self.assertEqual(data['MSISDN'], '254712345678')
        code = re.search(r'\b[0-9]{6}\b', data['txtMessage']).group()
        verified = client.post(reverse('login-verify-otp'), {
            'challenge_id': response.data['challenge_id'], 'code': code,
        }, format='json')
        self.assertEqual(verified.status_code, 200)
        self.assertIn('access', verified.data['tokens'])


    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    @patch('requests.post')
    def test_email_fallback_shares_sms_cooldown_and_replaces_code(self, post):
        from django.core import mail
        from django.core.cache import cache

        cache.clear()
        post.return_value.status_code = 200
        post.return_value.json.return_value = {'status': 222}
        user = User.objects.create_user(
            email='otp-fallback@example.com', password='LoginSecret123!', phone='0712345678',
        )
        client = APIClient()
        credentials = {'email': user.email, 'password': 'LoginSecret123!'}
        with patch('apps.accounts.login_otp.secrets.randbelow', return_value=123456):
            first = client.post(reverse('login'), credentials, format='json')
        fallback = {**credentials, 'email_fallback_challenge_id': first.data['challenge_id']}
        early = client.post(reverse('login'), fallback, format='json')
        self.assertEqual(early.status_code, 429)
        self.assertGreater(int(early['Retry-After']), 0)
        self.assertEqual(len(mail.outbox), 1)
        LoginOTP.objects.filter(user=user).update(sent_at=timezone.now() - timedelta(seconds=61))
        with patch('apps.accounts.login_otp.secrets.randbelow', return_value=654321):
            replacement = client.post(reverse('login'), fallback, format='json')
        self.assertEqual(replacement.status_code, 200)
        self.assertEqual(replacement.data['delivery_channel'], 'email')
        self.assertEqual(mail.outbox[0].to, [user.email])
        self.assertEqual(len(mail.outbox), 2)
        post.assert_called_once()
        challenge = {'challenge_id': replacement.data['challenge_id']}
        old = client.post(reverse('login-verify-otp'), {**challenge, 'code': '123456'}, format='json')
        self.assertEqual(old.status_code, 400)
        new = client.post(reverse('login-verify-otp'), {**challenge, 'code': '654321'}, format='json')
        self.assertIn('access', new.data['tokens'])


@override_settings(LOGIN_OTP_DELIVERY='sms', EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class SMSLoginOTPTests(TestCase):
    @patch('apps.accounts.login_otp.send_login_sms')
    def test_sms_challenge_uses_account_phone_and_rejects_a_changed_number(self, send_sms):
        from apps.accounts.login_otp import OTPError, issue_login_otp, verify_login_otp

        user = User.objects.create_user(
            email='smsotp@example.com', password='Secret123!', phone='0712 345 678',
        )
        challenge = issue_login_otp(user)
        phone, code = send_sms.call_args.args
        from django.core import mail
        self.assertEqual(mail.outbox[-1].to, [user.email])
        self.assertIn(code, mail.outbox[-1].body)
        self.assertEqual(phone, '+254712345678')
        self.assertEqual(challenge['delivery_channel'], 'both')
        self.assertEqual(challenge['phone_hint'], '••••5678')
        User.objects.filter(pk=user.pk).update(phone='0712345679')
        with self.assertRaises(OTPError):
            verify_login_otp(challenge['challenge_id'], code)


@override_settings(
    LOGIN_SMS_PROVIDER='twilio',
    TWILIO_ACCOUNT_SID='AC' + '1' * 32,
    TWILIO_AUTH_TOKEN='synthetic-token',
    TWILIO_FROM_NUMBER='+15005550006',
    TWILIO_MESSAGING_SERVICE_SID='',
)
class TwilioLoginSMSDeliveryTests(TestCase):
    @patch('requests.post')
    def test_login_code_uses_twilio_sender_and_form_data(self, post):
        from apps.accounts.login_otp import send_login_sms

        response = post.return_value.__enter__.return_value
        response.status_code = 201
        response.json.return_value = {'sid': 'SMsynthetic', 'status': 'queued'}
        send_login_sms('+254727808457', '012345')
        self.assertEqual(post.call_args.kwargs['data']['From'], '+15005550006')
        self.assertEqual(post.call_args.kwargs['data']['To'], '+254727808457')
        self.assertIn('012345', post.call_args.kwargs['data']['Body'])
        self.assertFalse(post.call_args.kwargs['allow_redirects'])
