import hashlib
import hmac
import json
from urllib import error, request

from django.conf import settings


class FlutterwaveConfigurationError(Exception):
    pass


class FlutterwaveAPIError(Exception):
    pass


class FlutterwaveClient:
    def __init__(self):
        self.secret_key = settings.FLUTTERWAVE_SECRET_KEY
        self.secret_hash = settings.FLUTTERWAVE_SECRET_HASH
        self.base_url = settings.FLUTTERWAVE_BASE_URL.rstrip('/')
        self.timeout = settings.FLUTTERWAVE_TIMEOUT_SECONDS

    def is_configured(self):
        return bool(self.secret_key)

    def _require_configuration(self):
        if not self.is_configured():
            raise FlutterwaveConfigurationError('Flutterwave credentials are not fully configured.')

    def _request(self, method, path, payload=None):
        self._require_configuration()
        req = request.Request(
            f'{self.base_url}{path}',
            data=json.dumps(payload).encode('utf-8') if payload is not None else None,
            headers={
                'Authorization': f'Bearer {self.secret_key}',
                'Content-Type': 'application/json',
            },
            method=method,
        )
        try:
            with request.urlopen(req, timeout=self.timeout) as response:
                body = response.read().decode('utf-8') or '{}'
                return json.loads(body)
        except error.HTTPError as exc:
            body = exc.read().decode('utf-8')
            raise FlutterwaveAPIError(f'Flutterwave HTTP error {exc.code}: {body}') from exc
        except (error.URLError, json.JSONDecodeError) as exc:
            raise FlutterwaveAPIError(f'Flutterwave request failed: {exc}') from exc

    def create_card_checkout(self, payment_intent, order, customer, redirect_url):
        payload = {
            'tx_ref': payment_intent.reference,
            'amount': str(order.total),
            'currency': payment_intent.currency,
            'redirect_url': redirect_url,
            'payment_options': 'card',
            'customer': {
                'email': order.shipping_email,
                'phonenumber': order.shipping_phone,
                'name': customer.full_name if customer else f'{order.shipping_first_name} {order.shipping_last_name}'.strip(),
            },
            'customizations': {
                'title': 'AvaPharma Checkout',
                'description': f'Payment for order {order.order_number}',
            },
            'meta': {
                'order_id': order.id,
                'order_number': order.order_number,
                'payment_intent_id': payment_intent.id,
            },
        }
        response = self._request('POST', '/v3/payments', payload)
        status = str(response.get('status', '')).lower()
        data = response.get('data') or {}
        if status != 'success' or not data.get('link'):
            raise FlutterwaveAPIError(response.get('message') or 'Flutterwave checkout link creation failed.')
        return response

    def verify_transaction(self, transaction_id):
        return self._request('GET', f'/v3/transactions/{transaction_id}/verify')

    def verify_signature(self, raw_body, headers):
        signature = (
            headers.get('flutterwave-signature')
            or headers.get('verif-hash')
            or headers.get('Verif-Hash')
            or ''
        ).strip()
        if not signature:
            return False
        if self.secret_hash and hmac.compare_digest(signature, self.secret_hash):
            return True
        if self.secret_hash:
            computed = hmac.new(
                self.secret_hash.encode('utf-8'),
                raw_body,
                hashlib.sha256,
            ).hexdigest()
            return hmac.compare_digest(signature, computed)
        return False
