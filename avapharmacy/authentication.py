from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.settings import api_settings
from rest_framework_simplejwt.exceptions import AuthenticationFailed

from apps.accounts.models import User


class ActiveUserJWTAuthentication(JWTAuthentication):
    """Reject JWTs for users that have been deactivated or suspended."""

    def get_user(self, validated_token):
        try:
            user_id = validated_token[api_settings.USER_ID_CLAIM]
        except KeyError:
            raise AuthenticationFailed('Token contained no recognizable user identification')

        try:
            user = self.user_model.objects.get(**{api_settings.USER_ID_FIELD: user_id})
        except self.user_model.DoesNotExist:
            raise AuthenticationFailed('User not found', code='user_not_found')

        if not user.is_active or user.status != User.STATUS_ACTIVE:
            raise AuthenticationFailed(
                'Account suspended. Contact support.',
                code='account_suspended',
            )
        return user
