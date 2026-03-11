"""
Custom DRF exception handler for the AvaPharma project.

Normalises all API error responses into a consistent JSON envelope::

    {"error": {"code": "<code>", "message": "<msg>", "details": ...}}

Handles DRF exceptions, Django built-in exceptions (Http404, PermissionDenied,
ValidationError, ObjectDoesNotExist), and falls back to HTTP 500 for any
unhandled exception while logging it via the ``avapharmacy`` logger.
"""
import logging
from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status
from django.core.exceptions import ValidationError, PermissionDenied, ObjectDoesNotExist
from django.http import Http404

logger = logging.getLogger('avapharmacy')


def _build_error(code, message, details=None):
    """Build the standard error response payload.

    Args:
        code: A short machine-readable error code string.
        message: A human-readable error description.
        details: Optional extra detail (list or dict); omitted when empty.

    Returns:
        dict: Error envelope payload.
    """
    error_obj = {'code': code, 'message': message}
    if details not in (None, {}, []):
        error_obj['details'] = details
    return {'error': error_obj}


def _first_error_message(details, default_message):
    """Return the first human-readable message from nested error details."""
    if isinstance(details, dict):
        for key, value in details.items():
            if key in {'detail', 'message'} and value not in (None, '', [], {}):
                return _first_error_message(value, default_message)
            message = _first_error_message(value, None)
            if message:
                return message
    elif isinstance(details, list):
        for value in details:
            message = _first_error_message(value, None)
            if message:
                return message
    elif details not in (None, '', [], {}):
        return str(details)
    return default_message


def custom_exception_handler(exc, context):
    """DRF exception handler that wraps all errors in the standard envelope.

    First delegates to DRF's default handler so authentication / permission
    exceptions are handled normally, then patches the response data into the
    ``_build_error`` format. Unhandled Django exceptions are caught and mapped
    to appropriate HTTP status codes.  Any remaining exception is logged and
    returned as HTTP 500.

    Args:
        exc: The exception instance raised by the view.
        context: A dict containing ``request`` and ``view``.

    Returns:
        Response: A DRF Response with the normalised error payload.
    """
    response = exception_handler(exc, context)

    if response is not None:
        if isinstance(response.data, list):
            response.data = _build_error(
                'validation_error',
                _first_error_message(response.data, 'Request validation failed.'),
                response.data,
            )
        elif isinstance(response.data, dict):
            if 'error' in response.data and isinstance(response.data['error'], dict):
                return response
            if {'detail', 'data', 'errors'}.issubset(response.data.keys()):
                details = response.data.get('errors', {}).get('details')
                response.data = _build_error(
                    response.data.get('errors', {}).get('code', 'request_error'),
                    response.data.get('detail') or _first_error_message(details, 'Request failed.'),
                    details,
                )
            elif 'detail' in response.data and len(response.data) == 1:
                response.data = _build_error('request_error', str(response.data['detail']))
            else:
                response.data = _build_error(
                    'validation_error',
                    _first_error_message(response.data, 'Request validation failed.'),
                    response.data,
                )
        else:
            response.data = _build_error('request_error', 'Request failed.')
        return response

    if isinstance(exc, Http404):
        return Response(_build_error('not_found', 'Not found.'), status=status.HTTP_404_NOT_FOUND)

    if isinstance(exc, PermissionDenied):
        return Response(_build_error('permission_denied', 'Permission denied.'), status=status.HTTP_403_FORBIDDEN)

    if isinstance(exc, ValidationError):
        details = getattr(exc, 'message_dict', None) or exc.messages
        return Response(
            _build_error(
                'validation_error',
                _first_error_message(details, 'Request validation failed.'),
                details,
            ),
            status=status.HTTP_400_BAD_REQUEST,
        )

    if isinstance(exc, ObjectDoesNotExist):
        return Response(_build_error('not_found', 'Resource not found.'), status=status.HTTP_404_NOT_FOUND)

    # Unhandled exception — log with full traceback and return 500
    request = context.get('request')
    view = context.get('view')
    logger.error(
        'Unhandled exception in %s',
        view.__class__.__name__ if view else 'unknown view',
        exc_info=exc,
        extra={
            'request': request,
            'path': getattr(request, 'path', ''),
            'method': getattr(request, 'method', ''),
            'user': getattr(request, 'user', None),
        },
    )
    return Response(_build_error('server_error', 'An unexpected error occurred. Our team has been notified.'), status=status.HTTP_500_INTERNAL_SERVER_ERROR)
