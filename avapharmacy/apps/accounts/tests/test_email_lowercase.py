from django.test import TestCase
from apps.accounts.models import User
from apps.accounts.serializers import AdminUserCreateSerializer, RegisterSerializer


class LowercaseEmailTests(TestCase):
    def test_manager_and_direct_creation_lowercase_entire_email(self):
        user = User.objects.create_user(email='  Mixed.Case@Example.TEST  ')
        user.refresh_from_db()
        self.assertEqual(user.email, 'mixed.case@example.test')
        direct = User.objects.create(email='DIRECT@Example.TEST')
        direct.refresh_from_db()
        self.assertEqual(direct.email, 'direct@example.test')

    def test_creation_serializers_normalize_and_reject_case_duplicate(self):
        for cls in (AdminUserCreateSerializer, RegisterSerializer):
            serializer = cls()
            self.assertEqual(serializer.validate_email('  New.User@Example.TEST  '), 'new.user@example.test')
        User.objects.create_user(email='Existing@Example.TEST')
        from rest_framework.exceptions import ValidationError
        for cls in (AdminUserCreateSerializer, RegisterSerializer):
            with self.assertRaises(ValidationError):
                cls().validate_email('EXISTING@example.test')
