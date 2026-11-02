from django.test import TestCase

from apps.accounts.models import Address, User
from apps.orders.views import persist_checkout_address


class CheckoutAddressConsentTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email='address-consent@example.test', password='test-only')
        self.data = {'street': 'Synthetic QA Street', 'city': 'Nairobi', 'county': 'Nairobi'}

    def test_first_address_is_not_saved_without_consent(self):
        for flags in ({}, {'save_address': False}, {'save_address': False, 'set_default_address': True}):
            self.assertIsNone(persist_checkout_address(self.user, {**self.data, **flags}))
            self.assertFalse(Address.objects.filter(user=self.user).exists())

    def test_first_explicitly_saved_address_becomes_default(self):
        address = persist_checkout_address(self.user, {**self.data, 'save_address': True})
        self.assertTrue(address.is_default)

    def test_selecting_existing_address_does_not_change_default_without_consent(self):
        address = Address.objects.create(user=self.user, **self.data, is_default=False)
        self.assertEqual(persist_checkout_address(self.user, {'saved_address': address}), address)
        address.refresh_from_db()
        self.assertFalse(address.is_default)
