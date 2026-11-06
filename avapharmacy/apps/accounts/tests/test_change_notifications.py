from django.core import mail
from django.db import transaction
from django.test import TestCase, override_settings
from apps.accounts.models import User


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class AccountChangeNotificationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email='old@example.test', password='OriginalSecret123!', first_name='Test')

    def test_email_change_notifies_old_address_after_commit(self):
        with self.captureOnCommitCallbacks(execute=True):
            self.user.email = 'NEW@EXAMPLE.TEST'
            self.user.save()
            self.assertEqual(len(mail.outbox), 0)
        self.assertEqual({m.to[0] for m in mail.outbox}, {'old@example.test'})
        self.assertTrue(all('new@example.test' in m.body for m in mail.outbox))
        self.assertIn('Your account details have changed', mail.outbox[0].alternatives[0][0])

    def test_password_confirmation_never_contains_password(self):
        with self.captureOnCommitCallbacks(execute=True):
            self.user.set_password('ChangedSecret456!')
            self.user.save()
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('password was changed', mail.outbox[0].body)
        self.assertNotIn('ChangedSecret456!', mail.outbox[0].body)
        self.assertNotIn(self.user.password, mail.outbox[0].body)

    def test_creation_and_unchanged_credentials_do_not_notify(self):
        with self.captureOnCommitCallbacks(execute=True):
            User.objects.create_user(email='fresh@example.test', password='InitialSecret123!')
            self.user.first_name = 'Updated'
            self.user.save()
        self.assertEqual(len(mail.outbox), 0)

    def test_rollback_and_unsaved_email_do_not_notify(self):
        with self.captureOnCommitCallbacks(execute=True):
            try:
                with transaction.atomic():
                    self.user.email = 'rollback@example.test'
                    self.user.save()
                    raise ValueError('rollback')
            except ValueError:
                pass
        self.assertEqual(len(mail.outbox), 0)
        self.user.refresh_from_db()
        with self.captureOnCommitCallbacks(execute=True):
            self.user.email = 'not-saved@example.test'
            self.user.save(update_fields=['first_name'])
        self.assertEqual(len(mail.outbox), 0)
