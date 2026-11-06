from rest_framework_simplejwt.authentication import JWTAuthentication
from .mfa import require_verified_token


class MFAJWTAuthentication(JWTAuthentication):
    def get_user(self, validated_token):
        user = super().get_user(validated_token)
        require_verified_token(user, validated_token)
        return user
