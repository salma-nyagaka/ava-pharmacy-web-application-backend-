"""
Custom DRF renderer enforcing a consistent API response envelope.
"""
from rest_framework.renderers import JSONRenderer


class StandardizedJSONRenderer(JSONRenderer):
    """
    Wrap JSON responses in a consistent envelope:

    {
      "detail": "...",
      "data": ...,
      "errors": null
    }
    """

    SUCCESS_MESSAGES = {
        200: 'Request successful.',
        201: 'Created successfully.',
        202: 'Request accepted.',
        204: 'Request successful.',
    }

    @staticmethod
    def _is_standard_payload(data):
        return isinstance(data, dict) and {'detail', 'data', 'errors'}.issubset(data.keys())

    @staticmethod
    def _is_paginated_payload(data):
        return isinstance(data, dict) and {'count', 'next', 'previous', 'results'}.issubset(data.keys())

    @staticmethod
    def _extract_error(data):
        if isinstance(data, dict) and isinstance(data.get('error'), dict):
            error = data['error']
            detail = str(error.get('message') or 'Request failed.')
            errors = {'code': error.get('code', 'request_error')}
            if error.get('details') not in (None, {}, []):
                errors['details'] = error.get('details')
            return detail, errors

        if isinstance(data, dict) and 'detail' in data and len(data) == 1:
            return str(data['detail']), {'code': 'request_error'}

        if isinstance(data, dict):
            return 'Request validation failed.', {'code': 'validation_error', 'details': data}

        if isinstance(data, list):
            return 'Request validation failed.', {'code': 'validation_error', 'details': data}

        if isinstance(data, str):
            return data, {'code': 'request_error'}

        return 'Request failed.', {'code': 'request_error'}

    @staticmethod
    def _should_bypass(renderer_context, data):
        request = renderer_context.get('request')
        response = renderer_context.get('response')
        path = request.path if request else ''

        if path.endswith('/api/schema/') or path.endswith('/payments/mpesa/callback/'):
            return True

        if getattr(response, 'skip_envelope', False):
            return True

        if isinstance(data, dict) and {'ResultCode', 'ResultDesc'}.issubset(data.keys()):
            return True

        return False

    def render(self, data, accepted_media_type=None, renderer_context=None):
        if renderer_context is None:
            return super().render(data, accepted_media_type, renderer_context)

        if self._should_bypass(renderer_context, data):
            return super().render(data, accepted_media_type, renderer_context)

        response = renderer_context.get('response')
        status_code = getattr(response, 'status_code', 200) or 200

        if self._is_standard_payload(data):
            return super().render(data, accepted_media_type, renderer_context)

        if status_code >= 400:
            detail, errors = self._extract_error(data)
            payload = {
                'detail': detail,
                'data': None,
                'errors': errors,
            }
            return super().render(payload, accepted_media_type, renderer_context)

        detail = self.SUCCESS_MESSAGES.get(status_code, 'Request successful.')
        payload_data = data
        payload = {
            'detail': detail,
            'data': None,
            'errors': None,
        }

        if self._is_paginated_payload(data):
            payload['data'] = data.get('results', [])
            payload['meta'] = {
                'count': data.get('count', 0),
                'next': data.get('next'),
                'previous': data.get('previous'),
            }
            return super().render(payload, accepted_media_type, renderer_context)

        if isinstance(data, dict) and 'detail' in data:
            detail_value = data.get('detail')
            if isinstance(detail_value, (str, int, float)):
                payload['detail'] = str(detail_value)
            remaining = {k: v for k, v in data.items() if k != 'detail'}
            payload['data'] = remaining or None
            return super().render(payload, accepted_media_type, renderer_context)

        payload['data'] = payload_data
        return super().render(payload, accepted_media_type, renderer_context)
