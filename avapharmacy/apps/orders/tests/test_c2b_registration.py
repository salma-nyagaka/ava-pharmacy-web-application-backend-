from unittest.mock import patch
from django.test import SimpleTestCase, override_settings
from apps.orders.mpesa import MpesaClient, MpesaAPIError, MpesaConfigurationError


@override_settings(MPESA_ENVIRONMENT='sandbox', MPESA_CALLBACK_SECRET='qa-only',
    MPESA_CONSUMER_KEY='qa-key', MPESA_CONSUMER_SECRET='qa-secret',
    MPESA_SHORTCODE='174379', MPESA_PASSKEY='qa-passkey',
    MPESA_CALLBACK_URL='https://example.test/callback', MPESA_C2B_SHORTCODE='600984',
    MPESA_C2B_VALIDATION_URL='https://example.test/validate',
    MPESA_C2B_CONFIRMATION_URL='https://example.test/confirm', MPESA_C2B_API_VERSION='v2')
class C2BRegistrationTests(SimpleTestCase):
    def test_v2_registers_c2b_shortcode_and_authenticated_urls(self):
        with patch.object(MpesaClient, '_post', return_value={'ResponseCode': '0'}) as send:
            self.assertEqual(MpesaClient().register_c2b_urls()['ResponseCode'], '0')
        endpoint, payload = send.call_args.args
        self.assertEqual(endpoint, '/mpesa/c2b/v2/registerurl')
        self.assertEqual(payload['ShortCode'], '600984')
        self.assertIn('token=qa-only', payload['ConfirmationURL'])
        self.assertIn('token=qa-only', payload['ValidationURL'])

    @override_settings(MPESA_C2B_API_VERSION='v1')
    def test_legacy_zero_success_code_is_accepted(self):
        with patch.object(MpesaClient, '_post', return_value={'ResponseCode': '00000000', 'ResponseDescription': 'Success'}):
            self.assertEqual(MpesaClient().register_c2b_urls()['ResponseCode'], '00000000')

    def test_missing_success_code_is_not_registration_evidence(self):
        with patch.object(MpesaClient, '_post', return_value={'requestId': 'qa-request'}):
            with self.assertRaises(MpesaAPIError):
                MpesaClient().register_c2b_urls()

    @override_settings(MPESA_C2B_API_VERSION='v1')
    def test_explicit_v1_compatibility(self):
        with patch.object(MpesaClient, '_post', return_value={'ResponseCode': '0'}) as send:
            MpesaClient().register_c2b_urls()
        self.assertEqual(send.call_args.args[0], '/mpesa/c2b/v1/registerurl')

    @override_settings(MPESA_C2B_API_VERSION='invalid')
    def test_invalid_version_rejected_without_provider_call(self):
        with patch.object(MpesaClient, '_post') as send:
            with self.assertRaises(MpesaConfigurationError):
                MpesaClient().register_c2b_urls()
        send.assert_not_called()

