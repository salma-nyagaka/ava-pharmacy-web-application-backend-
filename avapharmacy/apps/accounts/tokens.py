"""Helpers for invalidating JWT sessions for account lifecycle changes."""

from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken


def blacklist_user_refresh_tokens(user):
    """Blacklist all outstanding refresh tokens for a user.

    Access tokens are stateless and expire naturally, but authenticated API
    requests reject inactive or deleted users on every request. Blacklisting
    refresh tokens prevents a deactivated account from minting new access tokens.
    """
    if not user or not getattr(user, 'pk', None):
        return 0

    count = 0
    for token in OutstandingToken.objects.filter(user_id=user.pk):
        _, created = BlacklistedToken.objects.get_or_create(token=token)
        if created:
            count += 1
    return count
