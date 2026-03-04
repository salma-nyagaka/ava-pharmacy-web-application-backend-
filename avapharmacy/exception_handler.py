import logging
from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status
from django.core.exceptions import ValidationError, PermissionDenied, ObjectDoesNotExist
from django.http import Http404

logger = logging.getLogger('avapharmacy')


def custom_exception_handler(exc, context):
    response = exception_handler(exc, context)

    if response is not None:
        # Normalise all DRF error responses to {"detail": "..."} or {"field": [...]}
        if isinstance(response.data, list):
            response.data = {'detail': response.data}
        elif isinstance(response.data, dict) and 'detail' not in response.data:
            response.data = {'errors': response.data}
        return response

    # Handle Django exceptions not caught by DRF
    if isinstance(exc, Http404):
        return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

    if isinstance(exc, PermissionDenied):
        return Response({'detail': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)

    if isinstance(exc, ValidationError):
        return Response({'detail': exc.messages}, status=status.HTTP_400_BAD_REQUEST)

    if isinstance(exc, ObjectDoesNotExist):
        return Response({'detail': 'Resource not found.'}, status=status.HTTP_404_NOT_FOUND)

    # Unhandled exception — log it fully and return 500
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
    return Response(
        {'detail': 'An unexpected error occurred. Our team has been notified.'},
        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )
