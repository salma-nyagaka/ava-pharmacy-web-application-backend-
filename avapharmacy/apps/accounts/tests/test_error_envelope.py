from django.test import SimpleTestCase
from rest_framework.exceptions import ValidationError

from apps.accounts.bot_protection import BotProtectionError
from avapharmacy.exception_handler import custom_exception_handler


class ErrorEnvelopeTests(SimpleTestCase):
    def test_checkout_verification_preserves_code_message_and_reasons(self):
        response = custom_exception_handler(BotProtectionError({
            'code': 'ACCOUNT_VERIFICATION_REQUIRED',
            'message': 'Please verify your account details before checking out.',
            'reasons': ['account_not_active'],
        }), {})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data['error'], {
            'code': 'ACCOUNT_VERIFICATION_REQUIRED',
            'message': 'Please verify your account details before checking out.',
            'details': {'reasons': ['account_not_active']},
        })

    def test_nested_message_takes_priority_over_machine_code(self):
        response = custom_exception_handler(ValidationError({
            'payment': {'code': 'INVALID_PHONE', 'message': 'Enter a valid phone number.'},
        }), {})
        self.assertEqual(response.data['error']['message'], 'Enter a valid phone number.')

    def test_field_validation_still_uses_field_message(self):
        response = custom_exception_handler(ValidationError({'phone': ['This field is required.']}), {})
        self.assertEqual(response.data['error']['message'], 'This field is required.')
