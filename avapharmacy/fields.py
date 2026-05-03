from django.core.exceptions import ImproperlyConfigured
from django.db import models

try:
    from encrypted_model_fields.fields import EncryptedCharField as _BaseEncryptedCharField
except (ImportError, ImproperlyConfigured):  # pragma: no cover - optional dependency/config in local dev
    _BaseEncryptedCharField = models.CharField


class OptionalEncryptedCharField(_BaseEncryptedCharField):
    """Use encrypted storage when available, otherwise fall back to CharField."""
