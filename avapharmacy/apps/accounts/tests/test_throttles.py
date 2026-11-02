from django.contrib.auth.models import AnonymousUser
from django.core.cache import cache
from django.test import SimpleTestCase
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory

from avapharmacy.throttles import AnonWriteRateThrottle, PublicReadRateThrottle


class MethodAwareThrottleTests(SimpleTestCase):
    class TestPublicReadRateThrottle(PublicReadRateThrottle):
        rate = '2/min'

    class TestAnonWriteRateThrottle(AnonWriteRateThrottle):
        rate = '1/min'

    def setUp(self):
        cache.clear()
        self.factory = APIRequestFactory()

    def request(self, method):
        request = Request(getattr(self.factory, method.lower())('/api/example/'))
        request.user = AnonymousUser()
        return request

    def test_public_reads_have_their_own_larger_bucket(self):
        throttle = self.TestPublicReadRateThrottle()
        self.assertTrue(throttle.allow_request(self.request('GET'), object()))
        self.assertTrue(throttle.allow_request(self.request('GET'), object()))
        self.assertFalse(throttle.allow_request(self.request('GET'), object()))

    def test_anonymous_writes_keep_the_strict_bucket(self):
        throttle = self.TestAnonWriteRateThrottle()
        self.assertTrue(throttle.allow_request(self.request('POST'), object()))
        self.assertFalse(throttle.allow_request(self.request('POST'), object()))

    def test_each_throttle_ignores_the_other_method_group(self):
        self.assertTrue(PublicReadRateThrottle().allow_request(self.request('POST'), object()))
        self.assertTrue(AnonWriteRateThrottle().allow_request(self.request('GET'), object()))
