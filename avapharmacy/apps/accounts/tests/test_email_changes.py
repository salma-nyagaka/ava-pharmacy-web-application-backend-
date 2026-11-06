from datetime import timedelta
from urllib.parse import urlparse, parse_qs
import re
from unittest.mock import patch
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient
from apps.accounts.models import User, EmailChangeRequest


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class EmailChangeSecurityTests(TestCase):
    def setUp(self):
        from django.core.cache import cache
        cache.clear()
        self.user = User.objects.create_user(email='old@example.test', password='OriginalSecret123!', first_name='Test')
        self.client = APIClient(); self.client.force_authenticate(self.user)

    def request_change(self, target='new@example.test', **extra):
        return self.client.patch(reverse('me'), {'email':target,'current_password':'OriginalSecret123!', **extra}, format='json')

    def tokens(self):
        return [parse_qs(urlparse(re.search(r'https?://\S+confirm-email-change\?token=\S+', message.body).group()).query)['token'][0] for message in mail.outbox[:2]]

    def confirm(self, token):
        return APIClient().post(reverse('confirm-email-change'), {'token':token}, format='json')

    def test_password_required_and_old_email_stays_active(self):
        for password in ('', 'wrong'):
            response = self.client.patch(reverse('me'), {'email':'new@example.test','current_password':password}, format='json')
            self.assertEqual(response.status_code,400,response.data)
            self.assertIn('current_password', str(response.data))
        response = self.request_change()
        self.assertEqual(response.status_code,200,response.data)
        self.user.refresh_from_db();self.assertEqual(self.user.email,'old@example.test')
        self.assertEqual(response.data['email_change']['sent_to'], ['old@example.test'])
        self.assertNotIn('current_password',response.data)

    def test_old_link_completes_change_single_use_and_hashed_at_rest(self):
        self.request_change()
        old = self.tokens()[0]
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['old@example.test'])
        pending = EmailChangeRequest.objects.get()
        self.assertNotEqual(old, pending.old_token_hash)
        with self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(self.confirm(old).status_code,200)
        self.user.refresh_from_db(); self.assertEqual(self.user.email,'new@example.test')
        self.assertEqual(self.confirm(old).status_code,400)
        self.assertTrue(all(message.to == ['old@example.test'] for message in mail.outbox))

    def test_expired_superseded_and_tampered_tokens(self):
        self.request_change(); old=self.tokens()[0]
        EmailChangeRequest.objects.update(expires_at=timezone.now()-timedelta(seconds=1))
        self.assertEqual(self.confirm(old).status_code,400)
        self.assertEqual(self.confirm('x'*43).status_code,400)
        self.request_change('other@example.test')
        self.assertEqual(self.confirm(old).status_code,400)

    def test_password_change_invalidates_pending_request(self):
        self.request_change();old=self.tokens()[0]
        self.user.set_password('ChangedSecret456!');self.user.save()
        self.assertEqual(self.confirm(old).status_code,400)

    def test_email_taken_after_request_is_not_overwritten(self):
        self.request_change();old=self.tokens()[0]
        User.objects.create_user(email='new@example.test')
        self.assertEqual(self.confirm(old).status_code,400)
        self.user.refresh_from_db();self.assertEqual(self.user.email,'old@example.test')

    def test_failed_smtp_never_claims_sent_or_changes_email(self):
        with patch('apps.accounts.email_changes.send_rendered_email', side_effect=RuntimeError('SMTP failed')):
            response=self.request_change()
        self.assertEqual(response.status_code,200,response.data)
        self.assertEqual(response.data['email_change']['sent_to'],[])
        self.assertEqual(len(response.data['email_change']['failed_to']),1)
        self.user.refresh_from_db();self.assertEqual(self.user.email,'old@example.test')

    def test_password_change_delivery_result_and_wrong_password(self):
        with self.captureOnCommitCallbacks(execute=True):
            response=self.client.post(reverse('password-change'),{'old_password':'OriginalSecret123!','new_password':'ChangedSecret456!','new_password_confirm':'ChangedSecret456!'},format='json')
        self.assertEqual(response.status_code,200,response.data)
        self.assertEqual(response.data['confirmation_email']['sent_to'],['old@example.test'])
        self.assertNotIn('ChangedSecret456!',str(response.data))

    def test_profile_updates_without_email_change_do_not_require_password(self):
        response=self.client.patch(reverse('me'),{'first_name':'Updated','email':'OLD@EXAMPLE.TEST'},format='json')
        self.assertEqual(response.status_code,200,response.data)
        self.assertFalse(EmailChangeRequest.objects.exists())

    def test_email_change_requests_are_rate_limited(self):
        for attempt in range(5):
            self.assertEqual(self.request_change().status_code, 200)
        self.assertEqual(self.request_change().status_code, 429)

    def test_failed_password_notification_reports_failure(self):
        with patch('apps.accounts.change_notifications.send_rendered_email', side_effect=RuntimeError('SMTP failed')):
            with self.captureOnCommitCallbacks(execute=True):
                response=self.client.post(reverse('password-change'), {'old_password':'OriginalSecret123!','new_password':'ChangedSecret456!','new_password_confirm':'ChangedSecret456!'},format='json')
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.data['confirmation_email']['sent_to'],[])
        self.assertEqual(response.data['confirmation_email']['failed_to'],['old@example.test'])

    def test_admin_edit_uses_admin_password_and_preserves_target_email(self):
        admin=User.objects.create_user(email='admin-change@example.test',password='AdminSecret456!',role='admin')
        self.client.force_authenticate(admin)
        response=self.client.patch(reverse('admin-user-detail',args=[self.user.pk]),{'email':'new@example.test'},format='json')
        self.assertEqual(response.status_code,400,response.data)
        response=self.client.patch(reverse('admin-user-detail',args=[self.user.pk]),{'email':'new@example.test','current_password':'AdminSecret456!'},format='json')
        self.assertEqual(response.status_code,200,response.data)
        self.assertIn('email_change',response.data)
        self.user.refresh_from_db();self.assertEqual(self.user.email,'old@example.test')
        self.assertEqual(EmailChangeRequest.objects.get().user_id,self.user.pk)

    def test_wrong_password_error_is_distinct_from_missing_password(self):
        response=self.client.patch(reverse('me'), {'email':'new@example.test','current_password':'incorrect'},format='json')
        self.assertEqual(response.status_code,400)
        self.assertIn('Incorrect current password', str(response.data))
        self.assertFalse(EmailChangeRequest.objects.exists())
        self.assertEqual(self.request_change().status_code,200)

    def test_password_with_spaces_is_not_trimmed(self):
        self.user.set_password(' OriginalSecret123! ');self.user.save()
        response=self.client.patch(reverse('account-profile'), {'email':'new@example.test','current_password':' OriginalSecret123! '}, format='json')
        self.assertEqual(response.status_code,200,response.data)
