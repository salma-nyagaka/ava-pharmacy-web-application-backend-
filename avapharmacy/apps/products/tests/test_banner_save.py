from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.products.models import Banner
from apps.products.serializers import BannerSerializer


class BannerSaveTests(TestCase):
    def test_edit_image_banner_without_message_and_keep_image(self):
        admin = User.objects.create_user(email='banner-save@example.test', role=User.ADMIN)
        banner = Banner.objects.create(title='Family care', message='', image='banners/existing.png')
        client = APIClient()
        client.force_authenticate(admin)
        response = client.patch(reverse('admin-banner-detail', args=[banner.pk]), {
            'title': 'Updated family care', 'message': '', 'status': 'inactive',
            'link': '/products?category=baby-care', 'category': '',
        }, format='multipart')
        self.assertEqual(response.status_code, 200, response.data)
        banner.refresh_from_db()
        self.assertEqual(banner.title, 'Updated family care')
        self.assertEqual(banner.message, '')
        self.assertEqual(banner.status, 'inactive')
        self.assertEqual(banner.link, '/products?category=baby-care')
        self.assertEqual(banner.image.name, 'banners/existing.png')

    def test_custom_link_can_be_cleared(self):
        banner = Banner(title='Family', message='', link='https://example.com')
        serializer = BannerSerializer(banner, data={'link': ''}, partial=True)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data['link'], '')

    def test_invalid_links_are_rejected(self):
        for link in ('javascript:alert(1)', '//example.com', '/\\example.com', 'invalid'):
            with self.subTest(link=link):
                serializer = BannerSerializer(data={'title': 'Family', 'link': link})
                self.assertFalse(serializer.is_valid())
                self.assertIn('link', serializer.errors)
