import json
from unittest.mock import patch
from django.test import RequestFactory, SimpleTestCase, override_settings
from apps.accounts.bot_protection import verify_turnstile_token


@override_settings(BOT_CHALLENGE_PROVIDER='hcaptcha', HCAPTCHA_SECRET_KEY='test-secret', BOT_CHALLENGE_REQUIRED=True)
class ImageCaptchaVerificationTests(SimpleTestCase):
    def setUp(self):
        self.request = RequestFactory().post('/auth/login/')

    @patch('apps.accounts.bot_protection.urllib.request.urlopen')
    def test_success_requires_provider_verification(self, urlopen):
        urlopen.return_value.__enter__.return_value.read.return_value = json.dumps({'success': True}).encode()
        self.assertTrue(verify_turnstile_token(self.request, 'user-token')[0])
        request = urlopen.call_args.args[0]
        self.assertEqual(request.full_url, 'https://api.hcaptcha.com/siteverify')
        self.assertIn(b'response=user-token', request.data)

    @patch('apps.accounts.bot_protection.urllib.request.urlopen')
    def test_missing_token_never_calls_provider(self, urlopen):
        self.assertFalse(verify_turnstile_token(self.request, '')[0])
        urlopen.assert_not_called()

    @patch('apps.accounts.bot_protection.urllib.request.urlopen')
    def test_rejected_token_and_network_failure_fail_closed(self, urlopen):
        urlopen.return_value.__enter__.return_value.read.return_value = b'{"success":false}'
        self.assertFalse(verify_turnstile_token(self.request, 'invalid')[0])
        urlopen.side_effect = OSError('unavailable')
        self.assertFalse(verify_turnstile_token(self.request, 'token')[0])

    @override_settings(HCAPTCHA_SECRET_KEY='')
    def test_missing_required_secret_fails_closed(self):
        self.assertFalse(verify_turnstile_token(self.request, 'token')[0])
