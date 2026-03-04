import base64
import json
import logging
from datetime import datetime
from urllib import error, parse, request

from django.conf import settings


logger = logging.getLogger(__name__)


class MpesaConfigurationError(Exception):
    pass


class MpesaAPIError(Exception):
    pass


class MpesaClient:
    def __init__(self):
        environment = getattr(settings, 'MPESA_ENVIRONMENT', 'sandbox').lower()
        if environment == 'production':
            self.base_url = 'https://api.safaricom.co.ke'
        else:
            self.base_url = 'https://sandbox.safaricom.co.ke'

        self.consumer_key = settings.MPESA_CONSUMER_KEY
        self.consumer_secret = settings.MPESA_CONSUMER_SECRET
        self.shortcode = settings.MPESA_SHORTCODE
        self.passkey = settings.MPESA_PASSKEY
        self.callback_url = settings.MPESA_CALLBACK_URL
        self.transaction_type = settings.MPESA_TRANSACTION_TYPE
        self.timeout = settings.MPESA_TIMEOUT_SECONDS

    def is_configured(self):
        return all([
            self.consumer_key,
            self.consumer_secret,
            self.shortcode,
            self.passkey,
            self.callback_url,
        ])

    def _require_configuration(self):
        if not self.is_configured():
            raise MpesaConfigurationError('M-Pesa credentials are not fully configured.')

    def _access_token(self):
        self._require_configuration()
        credentials = f'{self.consumer_key}:{self.consumer_secret}'.encode('utf-8')
        encoded_credentials = base64.b64encode(credentials).decode('utf-8')
        req = request.Request(
            f'{self.base_url}/oauth/v1/generate?grant_type=client_credentials',
            headers={'Authorization': f'Basic {encoded_credentials}'},
        )
        try:
            with request.urlopen(req, timeout=self.timeout) as response:
                payload = json.loads(response.read().decode('utf-8'))
            return payload['access_token']
        except (error.URLError, KeyError, json.JSONDecodeError) as exc:
            raise MpesaAPIError(f'Failed to acquire M-Pesa access token: {exc}') from exc

    def _timestamp(self):
        return datetime.utcnow().strftime('%Y%m%d%H%M%S')

    def _password(self, timestamp):
        raw_password = f'{self.shortcode}{self.passkey}{timestamp}'.encode('utf-8')
        return base64.b64encode(raw_password).decode('utf-8')

    def _post(self, path, payload):
        token = self._access_token()
        req = request.Request(
            f'{self.base_url}{path}',
            data=json.dumps(payload).encode('utf-8'),
            headers={
                'Authorization': f'Bearer {token}',
                'Content-Type': 'application/json',
            },
            method='POST',
        )
        try:
            with request.urlopen(req, timeout=self.timeout) as response:
                body = response.read().decode('utf-8') or '{}'
                return json.loads(body)
        except error.HTTPError as exc:
            body = exc.read().decode('utf-8')
            raise MpesaAPIError(f'M-Pesa HTTP error {exc.code}: {body}') from exc
        except (error.URLError, json.JSONDecodeError) as exc:
            raise MpesaAPIError(f'M-Pesa request failed: {exc}') from exc

    def normalize_phone(self, phone):
        digits = ''.join(char for char in str(phone or '') if char.isdigit())
        if digits.startswith('0') and len(digits) == 10:
            return f'254{digits[1:]}'
        if digits.startswith('254') and len(digits) == 12:
            return digits
        if digits.startswith('7') and len(digits) == 9:
            return f'254{digits}'
        raise MpesaAPIError('Phone number must be a valid Kenyan mobile number.')

    def initiate_stk_push(self, payment_intent, phone, account_reference, description):
        normalized_phone = self.normalize_phone(phone)
        timestamp = self._timestamp()
        payload = {
            'BusinessShortCode': self.shortcode,
            'Password': self._password(timestamp),
            'Timestamp': timestamp,
            'TransactionType': self.transaction_type,
            'Amount': int(payment_intent.amount),
            'PartyA': normalized_phone,
            'PartyB': self.shortcode,
            'PhoneNumber': normalized_phone,
            'CallBackURL': self.callback_url,
            'AccountReference': account_reference[:12],
            'TransactionDesc': description[:13],
        }
        response = self._post('/mpesa/stkpush/v1/processrequest', payload)
        response_code = str(response.get('ResponseCode', ''))
        if response_code and response_code != '0':
            raise MpesaAPIError(response.get('ResponseDescription') or 'M-Pesa STK push rejected.')
        return normalized_phone, response

    def query_stk_status(self, payment_intent):
        if not payment_intent.checkout_request_id:
            raise MpesaAPIError('Checkout request id is missing for this payment intent.')
        timestamp = self._timestamp()
        payload = {
            'BusinessShortCode': self.shortcode,
            'Password': self._password(timestamp),
            'Timestamp': timestamp,
            'CheckoutRequestID': payment_intent.checkout_request_id,
        }
        return self._post('/mpesa/stkpushquery/v1/query', payload)


def parse_mpesa_callback(payload):
    callback = (
        payload.get('Body', {})
        .get('stkCallback', {})
    )
    metadata_items = callback.get('CallbackMetadata', {}).get('Item', []) or []
    metadata = {}
    for item in metadata_items:
        name = item.get('Name')
        if name:
            metadata[name] = item.get('Value')

    result_code = callback.get('ResultCode')
    result_desc = callback.get('ResultDesc', '')
    return {
        'merchant_request_id': callback.get('MerchantRequestID', ''),
        'checkout_request_id': callback.get('CheckoutRequestID', ''),
        'result_code': str(result_code) if result_code is not None else '',
        'result_desc': result_desc,
        'metadata': metadata,
    }
