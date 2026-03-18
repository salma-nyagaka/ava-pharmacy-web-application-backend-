import base64
import json
import logging
from datetime import datetime
from urllib import error, parse, request
from urllib.parse import urlparse

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
        self.paybill_number = str(getattr(settings, 'MPESA_PAYBILL_NUMBER', '') or '').strip()
        self.c2b_shortcode = str(getattr(settings, 'MPESA_C2B_SHORTCODE', '') or '').strip() or self.paybill_number
        self.c2b_validation_url = str(getattr(settings, 'MPESA_C2B_VALIDATION_URL', '') or '').strip()
        self.c2b_confirmation_url = str(getattr(settings, 'MPESA_C2B_CONFIRMATION_URL', '') or '').strip()
        self.c2b_response_type = str(getattr(settings, 'MPESA_C2B_RESPONSE_TYPE', 'Completed') or 'Completed').strip() or 'Completed'
        self.require_public_callback_urls = bool(getattr(settings, 'MPESA_REQUIRE_PUBLIC_CALLBACK_URLS', True))

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

    def is_c2b_configured(self):
        return all([
            self.consumer_key,
            self.consumer_secret,
            self.c2b_shortcode,
            self.c2b_validation_url,
            self.c2b_confirmation_url,
        ])

    def _require_c2b_configuration(self):
        if not self.is_c2b_configured():
            raise MpesaConfigurationError('M-Pesa C2B/paybill callback credentials are not fully configured.')

    def _validate_callback_url(self, url, setting_name):
        parsed = urlparse(str(url or '').strip())
        if parsed.scheme != 'https':
            raise MpesaConfigurationError(f'{setting_name} must be a public HTTPS URL in .env.')
        if not parsed.netloc:
            raise MpesaConfigurationError(f'{setting_name} is invalid. Set it to a public HTTPS URL in .env.')
        hostname = (parsed.hostname or '').strip().lower()
        if hostname in {'localhost', '127.0.0.1', '0.0.0.0'}:
            raise MpesaConfigurationError(f'{setting_name} cannot point to localhost. Use a public HTTPS URL in .env.')

    def validate_stk_configuration(self):
        self._require_configuration()
        if self.require_public_callback_urls:
            self._validate_callback_url(self.callback_url, 'MPESA_CALLBACK_URL')

    def validate_c2b_configuration(self):
        self._require_c2b_configuration()
        if self.require_public_callback_urls:
            self._validate_callback_url(self.c2b_validation_url, 'MPESA_C2B_VALIDATION_URL')
            self._validate_callback_url(self.c2b_confirmation_url, 'MPESA_C2B_CONFIRMATION_URL')

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
        except error.HTTPError as exc:
            body = exc.read().decode('utf-8', errors='replace')
            lowered = body.lower()
            if exc.code == 403 and 'incapsula' in lowered:
                raise MpesaAPIError(
                    'M-Pesa access token request was blocked by Safaricom edge protection. '
                    'Retry later or change network/public IP, then retry.'
                ) from exc
            if exc.code == 403:
                raise MpesaAPIError(
                    'M-Pesa access token request was rejected. '
                    'Check MPESA_CONSUMER_KEY and MPESA_CONSUMER_SECRET in .env.'
                ) from exc
            raise MpesaAPIError(f'Failed to acquire M-Pesa access token: HTTP {exc.code}: {body}') from exc
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
            body = exc.read().decode('utf-8', errors='replace')
            lowered = body.lower()
            if exc.code == 429 or 'spikearrestviolation' in lowered:
                raise MpesaAPIError('M-Pesa rate limit reached. Waiting before the next status check.') from exc
            if exc.code == 403 and 'incapsula' in lowered:
                raise MpesaAPIError(
                    'M-Pesa request was blocked by Safaricom edge protection. '
                    'The system will wait before retrying status sync.'
                ) from exc
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
        self.validate_stk_configuration()
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

    def register_c2b_urls(self):
        self.validate_c2b_configuration()
        payload = {
            'ShortCode': self.c2b_shortcode,
            'ResponseType': self.c2b_response_type,
            'ConfirmationURL': self.c2b_confirmation_url,
            'ValidationURL': self.c2b_validation_url,
        }
        response = self._post('/mpesa/c2b/v1/registerurl', payload)
        response_code = str(response.get('ResponseCode', ''))
        if response_code and response_code != '0':
            raise MpesaAPIError(response.get('ResponseDescription') or 'M-Pesa C2B URL registration failed.')
        return response


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
