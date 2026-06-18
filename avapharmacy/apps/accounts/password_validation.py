from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _


class CharacterClassPasswordValidator:
    """Require the same password character mix shown in the auth UI."""

    def validate(self, password, user=None):
        errors = []
        if not any(char.isupper() for char in password):
            errors.append(_('Password must contain at least one uppercase letter.'))
        if not any(char.islower() for char in password):
            errors.append(_('Password must contain at least one lowercase letter.'))
        if not any(char.isdigit() for char in password):
            errors.append(_('Password must contain at least one number.'))
        if not any(not char.isalnum() for char in password):
            errors.append(_('Password must contain at least one special character.'))

        if errors:
            raise ValidationError(errors, code='password_missing_character_class')

    def get_help_text(self):
        return _(
            'Your password must include at least one uppercase letter, '
            'one lowercase letter, one number, and one special character.'
        )
