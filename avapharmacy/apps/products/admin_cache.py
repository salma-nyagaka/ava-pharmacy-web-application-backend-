"""Shared admin read cache. Mutations change the generation after commit."""
import hashlib
import uuid
from django.conf import settings
from django.core.cache import cache
from django.db import connection, transaction
from django.db.models.signals import post_save, post_delete, m2m_changed
from rest_framework.response import Response

VERSION_KEY = 'admin-catalog-generation-v1'

def version_key():
    database = str(connection.settings_dict['NAME'])
    return VERSION_KEY + ':' + hashlib.sha256(database.encode()).hexdigest()[:16]

def invalidate_admin_catalog():
    key = version_key()
    transaction.on_commit(lambda: cache.set(key, uuid.uuid4().hex, timeout=None))

def generation():
    key = version_key()
    value = cache.get(key)
    if value is None:
        cache.add(key, uuid.uuid4().hex, timeout=None)
        value = cache.get(key)
    return value

class CachedAdminListMixin:
    def list(self, request, *args, **kwargs):
        # Absolute pagination/media URLs must be scoped to the request origin.
        fingerprint = request.build_absolute_uri() + ':' + str(request.user.pk)
        key = 'admin-list:' + str(generation()) + ':' + hashlib.sha256(fingerprint.encode()).hexdigest()
        payload = cache.get(key)
        if payload is not None:
            return Response(payload)
        response = super().list(request, *args, **kwargs)
        if response.status_code == 200:
            cache.set(key, response.data, getattr(settings, 'ADMIN_CATALOG_CACHE_TTL', 60))
        return response


def connect_catalog_signals():
    from django.apps import apps
    def changed(sender, **kwargs):
        if not kwargs.get('raw', False):
            invalidate_admin_catalog()
    # Includes stock saves from checkout, POS sync and inventory edits.
    for model in apps.get_app_config('products').get_models():
        post_save.connect(changed, sender=model, weak=False, dispatch_uid='admin-read-save:'+model._meta.label)
        post_delete.connect(changed, sender=model, weak=False, dispatch_uid='admin-read-delete:'+model._meta.label)
    m2m_changed.connect(changed, sender=apps.get_model('products.Variant').health_concerns.through, weak=False, dispatch_uid='admin-read-concerns')
