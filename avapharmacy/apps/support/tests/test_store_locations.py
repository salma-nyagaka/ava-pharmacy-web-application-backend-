from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.support.models import SiteSettings


class StoreLocationsTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.url = reverse('site-settings')
        self.admin = User.objects.create_user(
            email='locations-admin@example.com', password='password',
            first_name='Admin', last_name='User', role=User.ADMIN,
        )

    def test_admin_locations_are_persisted_and_publicly_visible_in_order(self):
        self.client.force_authenticate(self.admin)
        locations = ['Karen / The Hub, Nairobi', 'Westlands, Nairobi']
        response = self.client.patch(self.url, {'store_locations': locations}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(SiteSettings.get_solo().store_locations, locations)
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get(self.url).data['store_locations'], locations)

    def test_old_settings_updates_preserve_locations_and_list_can_be_cleared(self):
        settings = SiteSettings.get_solo()
        settings.store_locations = ['Karen', 'Westlands']
        settings.save()
        self.client.force_authenticate(self.admin)
        response = self.client.patch(self.url, {'support_address': 'Nairobi'}, format='json')
        self.assertEqual(response.data['store_locations'], ['Karen', 'Westlands'])
        response = self.client.patch(self.url, {'store_locations': []}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['store_locations'], [])

    def test_invalid_location_lists_are_rejected(self):
        self.client.force_authenticate(self.admin)
        for value in ['Karen', [''], [' '], ['a' * 256], [None], [{}]]:
            with self.subTest(value=value):
                response = self.client.patch(self.url, {'store_locations': value}, format='json')
                self.assertEqual(response.status_code, 400)

    def test_non_admin_cannot_change_locations(self):
        response = self.client.patch(self.url, {'store_locations': ['Karen']}, format='json')
        self.assertEqual(response.status_code, 403)
        self.admin.role = User.CUSTOMER
        self.admin.save()
        self.client.force_authenticate(self.admin)
        response = self.client.patch(self.url, {'store_locations': ['Karen']}, format='json')
        self.assertEqual(response.status_code, 403)
