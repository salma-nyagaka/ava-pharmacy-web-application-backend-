"""Apply pharmacist credential restrictions to every JWT-authenticated API."""
from rest_framework.exceptions import PermissionDenied
from rest_framework_simplejwt.authentication import JWTAuthentication


class CredentialJWTAuthentication(JWTAuthentication):
    def authenticate(self, request):
        result = super().authenticate(request)
        if result is None:
            return None
        user, token = result
        if user.role == 'pharmacist':
            from .models import Pharmacist
            profile = Pharmacist.objects.select_related('user', 'credential_evidence').filter(user=user).first()
            allowed = request.resolver_match and request.resolver_match.url_name in {
                'me', 'logout', 'token-refresh', 'token-refresh-alias',
                'my-pharmacist-credential', 'my-pharmacist-documents', 'my-pharmacist-document-download',
            }
            # Profile access is read-only while restricted; renewal has its own endpoint.
            if allowed and request.resolver_match.url_name == 'me' and request.method not in {'GET', 'HEAD', 'OPTIONS'}:
                allowed = False
            if not allowed and (not profile or not profile.credential_is_current):
                raise PermissionDenied(detail={
                    'code': 'pharmacist_licence_required',
                    'message': 'Your pharmacist licence is expired or awaiting verification. Upload a renewed licence to restore access after independent verification.',
                })
        return user, token
