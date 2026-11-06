from unittest.mock import patch
from types import SimpleNamespace
from datetime import timedelta

from django.test import SimpleTestCase
from django.utils import timezone
from rest_framework.test import APIRequestFactory

from apps.accounts.bot_protection import BotProtectionError, enforce_checkout_risk, score_checkout_risk
from apps.accounts.models import BotRiskEvent, User


class CheckoutRiskRoutingTests(SimpleTestCase):
    def setUp(self):
        self.request = APIRequestFactory().post('/checkout/', {})
        self.request.data = {}

    @patch('apps.accounts.bot_protection._payment_failure_count', return_value=0)
    @patch('apps.accounts.bot_protection._recent_events')
    def test_denied_retries_do_not_escalate_shared_ip_checkout(self, events, failures):
        self.request.user = SimpleNamespace(
            date_joined=timezone.now() - timedelta(days=30),
            status=User.STATUS_ACTIVE, is_active=True, phone='0712345678',
            email='customer@example.com',
        )
        item = SimpleNamespace(variant=None, quantity=1, prescription_reference='RX-test')
        # Three denied checkouts exist, but no allowed checkout exists.
        events.side_effect = lambda **filters: (
            0 if filters.get('decision') == BotRiskEvent.DECISION_ALLOW else 3
        )
        score, reasons = score_checkout_risk(self.request, [item])
        self.assertEqual(score, 60)
        self.assertNotIn('rapid_checkout_attempts', reasons)
        self.assertIn('many_registrations_from_ip', reasons)

    @patch('apps.accounts.bot_protection._payment_failure_count', return_value=0)
    @patch('apps.accounts.bot_protection._recent_events', return_value=3)
    def test_repeated_allowed_checkouts_still_increase_risk(self, events, failures):
        self.request.user = SimpleNamespace(
            date_joined=timezone.now() - timedelta(days=30),
            status=User.STATUS_ACTIVE, is_active=True, phone='0712345678',
            email='customer@example.com',
        )
        score, reasons = score_checkout_risk(self.request, [])
        self.assertIn('rapid_checkout_attempts', reasons)
        self.assertEqual(score, 50)

    @patch('apps.accounts.bot_protection.log_bot_event')
    @patch('apps.accounts.bot_protection.verify_turnstile_token', return_value=(True, ''))
    @patch('apps.accounts.bot_protection.score_checkout_risk', return_value=(60, ['prescription_cart', 'many_registrations_from_ip']))
    def test_shared_ip_prescription_checkout_can_pass_challenge(self, score, challenge, log):
        enforce_checkout_risk(self.request, [])
        challenge.assert_called_once()
        self.assertEqual(log.call_args.kwargs['decision'], 'allow')

    @patch('apps.accounts.bot_protection.log_bot_event')
    @patch('apps.accounts.bot_protection.verify_turnstile_token', return_value=(False, 'missing_challenge_token'))
    @patch('apps.accounts.bot_protection.score_checkout_risk', return_value=(60, ['prescription_cart', 'many_registrations_from_ip']))
    def test_shared_ip_still_requires_successful_challenge(self, score, challenge, log):
        with self.assertRaises(BotProtectionError) as caught:
            enforce_checkout_risk(self.request, [])
        self.assertEqual(caught.exception.detail['code'], 'BOT_CHALLENGE_REQUIRED')

    @patch('apps.accounts.bot_protection.log_bot_event')
    @patch('apps.accounts.bot_protection.verify_turnstile_token')
    @patch('apps.accounts.bot_protection.score_checkout_risk', return_value=(60, ['prescription_cart', 'account_not_active']))
    def test_account_restriction_still_requires_verification(self, score, challenge, log):
        with self.assertRaises(BotProtectionError) as caught:
            enforce_checkout_risk(self.request, [])
        self.assertEqual(caught.exception.detail['code'], 'ACCOUNT_VERIFICATION_REQUIRED')
        challenge.assert_not_called()
