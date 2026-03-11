"""
Custom DRF renderer enforcing a consistent API response envelope.

Success format:
  { "success": true, "data": ..., "meta": {...}, "message": "..." }

Error format:
  { "success": false, "error": { "code": "...", "message": "...", "details": {...} } }
"""
import math
from rest_framework.renderers import JSONRenderer


class StandardizedJSONRenderer(JSONRenderer):

    SUCCESS_MESSAGES = {
        200: 'Request successful.',
        201: 'Created successfully.',
        202: 'Request accepted.',
        204: 'Deleted successfully.',
    }

    @staticmethod
    def _is_already_enveloped(data):
        return isinstance(data, dict) and 'success' in data

    @staticmethod
    def _is_paginated(data):
        return isinstance(data, dict) and {'count', 'next', 'previous', 'results'}.issubset(data.keys())

    @staticmethod
    def _should_bypass(renderer_context, data):
        request = renderer_context.get('request')
        response = renderer_context.get('response')
        path = request.path if request else ''

        if path.endswith('/api/schema/') or '/payments/mpesa/callback' in path:
            return True
        if getattr(response, 'skip_envelope', False):
            return True
        if isinstance(data, dict) and {'ResultCode', 'ResultDesc'}.issubset(data.keys()):
            return True
        return False

    @staticmethod
    def _first_error_message(details, default_message):
        """Return the first human-readable message from nested error details."""
        if isinstance(details, dict):
            for key, value in details.items():
                if key in {'detail', 'message'} and value not in (None, '', [], {}):
                    return StandardizedJSONRenderer._first_error_message(value, default_message)
                message = StandardizedJSONRenderer._first_error_message(value, None)
                if message:
                    return message
        elif isinstance(details, list):
            for value in details:
                message = StandardizedJSONRenderer._first_error_message(value, None)
                if message:
                    return message
        elif details not in (None, '', [], {}):
            return str(details)
        return default_message

    @staticmethod
    def _extract_error_info(data):
        """Return (code, message, details) from a DRF error response."""
        if isinstance(data, dict):
            # Already structured error
            if 'error' in data and isinstance(data['error'], dict):
                err = data['error']
                details = err.get('details') or (err.get('field') and {'field': err['field']})
                return (
                    err.get('code', 'error'),
                    str(err.get('message') or StandardizedJSONRenderer._first_error_message(details, 'An error occurred.')),
                    details,
                )
            if {'detail', 'data', 'errors'}.issubset(data.keys()):
                err = data.get('errors') or {}
                details = err.get('details')
                return (
                    err.get('code', 'error'),
                    str(data.get('detail') or err.get('message') or StandardizedJSONRenderer._first_error_message(details, 'An error occurred.')),
                    details,
                )
            # DRF single-key detail
            if list(data.keys()) == ['detail']:
                return 'error', str(data['detail']), None
            # Validation errors (field: [errors])
            if 'non_field_errors' in data:
                msgs = data.get('non_field_errors') or []
                details = {key: value for key, value in data.items() if key != 'non_field_errors'}
                return (
                    'validation_error',
                    str(StandardizedJSONRenderer._first_error_message(msgs, 'Validation error.')),
                    details or None,
                )
            # Field-level validation errors dict
            return (
                'validation_error',
                str(StandardizedJSONRenderer._first_error_message(data, 'Request validation failed.')),
                data,
            )

        if isinstance(data, list):
            return (
                'validation_error',
                str(StandardizedJSONRenderer._first_error_message(data, 'An error occurred.')),
                data or None,
            )

        if isinstance(data, str):
            return 'error', data, None

        return 'error', 'An error occurred.', None

    def render(self, data, accepted_media_type=None, renderer_context=None):
        if renderer_context is None:
            return super().render(data, accepted_media_type, renderer_context)

        if self._should_bypass(renderer_context, data):
            return super().render(data, accepted_media_type, renderer_context)

        if self._is_already_enveloped(data):
            return super().render(data, accepted_media_type, renderer_context)

        response = renderer_context.get('response')
        status_code = getattr(response, 'status_code', 200) or 200

        # ── Error response ────────────────────────────────────────────────────
        if status_code >= 400:
            code, message, details = self._extract_error_info(data)
            error_obj = {'code': code, 'message': message}
            if details:
                error_obj['details'] = details
            payload = {'success': False, 'error': error_obj}
            return super().render(payload, accepted_media_type, renderer_context)

        # ── Paginated response ────────────────────────────────────────────────
        if self._is_paginated(data):
            count = data.get('count', 0)
            # Try to figure out per_page from request
            request = renderer_context.get('request')
            per_page = 20
            if request:
                try:
                    per_page = int(request.query_params.get('page_size') or request.query_params.get('per_page', 20))
                except (TypeError, ValueError):
                    per_page = 20
            total_pages = math.ceil(count / per_page) if per_page > 0 else 1
            try:
                page = int(request.query_params.get('page', 1)) if request else 1
            except (TypeError, ValueError):
                page = 1
            payload = {
                'success': True,
                'data': data.get('results', []),
                'meta': {
                    'page': page,
                    'per_page': per_page,
                    'total': count,
                    'total_pages': total_pages,
                    'next': data.get('next'),
                    'previous': data.get('previous'),
                },
                'message': self.SUCCESS_MESSAGES.get(status_code, 'Request successful.'),
            }
            return super().render(payload, accepted_media_type, renderer_context)

        # ── Standard success response ─────────────────────────────────────────
        message = self.SUCCESS_MESSAGES.get(status_code, 'Request successful.')

        # Views can pass 'message' inside their response dict; extract it
        if isinstance(data, dict) and 'message' in data and len(data) > 1:
            message = data.pop('message', message)

        # Views can pass a bare 'detail' string
        if isinstance(data, dict) and list(data.keys()) == ['detail']:
            message = str(data['detail'])
            data = None

        payload = {
            'success': True,
            'data': data if data is not None else None,
            'message': message,
        }
        return super().render(payload, accepted_media_type, renderer_context)
