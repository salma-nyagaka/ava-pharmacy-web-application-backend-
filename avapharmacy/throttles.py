from rest_framework.throttling import AnonRateThrottle


SAFE_METHODS = frozenset({'GET', 'HEAD', 'OPTIONS'})


class PublicReadRateThrottle(AnonRateThrottle):
    """A separate anonymous bucket for cacheable storefront reads.

    Public catalogue pages fan out across products, navigation, banners, FAQs,
    and site settings. Sharing their allowance with anonymous write endpoints
    makes a normal browsing session exhaust the API before checkout.
    """

    scope = 'public_read'

    def allow_request(self, request, view):
        if request.method not in SAFE_METHODS:
            return True
        return super().allow_request(request, view)


class AnonWriteRateThrottle(AnonRateThrottle):
    """Retain the stricter anonymous bucket for unsafe HTTP methods."""

    scope = 'anon'

    def allow_request(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        return super().allow_request(request, view)
