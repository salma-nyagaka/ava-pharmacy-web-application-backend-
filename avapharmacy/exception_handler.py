import logging
from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status
from django.core.exceptions import ValidationError, PermissionDenied, ObjectDoesNotExist
from django.http import Http404

logger = logging.getLogger('avapharmacy')


def _build_error(code, message, details=None):
    payload = {
        'error': {
            'code': code,
            'message': message,
        }
    }
    if details not in (None, {}, []):
        payload['error']['details'] = details
    return payload


def custom_exception_handler(exc, context):
    response = exception_handler(exc, context)

    if response is not None:
        if isinstance(response.data, list):
            response.data = _build_error('validation_error', 'Request validation failed.', response.data)
        elif isinstance(response.data, dict):
            if 'detail' in response.data and len(response.data) == 1:
                response.data = _build_error('request_error', str(response.data['detail']))
            else:
                response.data = _build_error('validation_error', 'Request validation failed.', response.data)
        return response

    if isinstance(exc, Http404):
        return Response(_build_error('not_found', 'Not found.'), status=status.HTTP_404_NOT_FOUND)

    if isinstance(exc, PermissionDenied):
        return Response(_build_error('permission_denied', 'Permission denied.'), status=status.HTTP_403_FORBIDDEN)

    if isinstance(exc, ValidationError):
        return Response(
            _build_error('validation_error', 'Request validation failed.', exc.messages),
            status=status.HTTP_400_BAD_REQUEST,
        )

    if isinstance(exc, ObjectDoesNotExist):
        return Response(_build_error('not_found', 'Resource not found.'), status=status.HTTP_404_NOT_FOUND)

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
