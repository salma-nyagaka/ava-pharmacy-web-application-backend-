from http.client import RemoteDisconnected
from unittest.mock import patch
from django.test import SimpleTestCase, override_settings
from apps.orders.mpesa import MpesaClient, MpesaAPIError


@override_settings(MPESA_CONSUMER_KEY='qa-key', MPESA_CONSUMER_SECRET='qa-secret', MPESA_SHORTCODE='174379', MPESA_PASSKEY='qa-pass', MPESA_CALLBACK_SECRET='qa-callback', MPESA_CALLBACK_URL='https://example.test/callback/')
class MpesaTransportTests(SimpleTestCase):
    @patch('apps.orders.mpesa.request.urlopen', side_effect=RemoteDisconnected('Provider connection closed'))
    def test_token_connection_drop_becomes_recoverable_provider_error(self, urlopen):
        with self.assertRaises(MpesaAPIError):
            MpesaClient()._access_token()

    @patch('apps.orders.mpesa.request.urlopen', side_effect=RemoteDisconnected('Provider connection closed'))
    def test_payment_connection_drop_becomes_recoverable_provider_error(self, urlopen):
        client = MpesaClient()
        with patch.object(client, '_access_token', return_value='qa-only-token'), self.assertRaises(MpesaAPIError):
            client._post('/qa-only/', {})
