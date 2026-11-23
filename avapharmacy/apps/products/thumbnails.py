"""Generate public catalog thumbnails without changing original media storage."""
from functools import partial
from hashlib import sha256
from io import BytesIO
import logging

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.db import transaction
from django.db.models.signals import post_save, pre_save
from PIL import Image, ImageOps

from .models import Product, Variant

logger = logging.getLogger(__name__)
THUMBNAIL_SIZE = (480, 480)


def thumbnail_storage():
    bucket = settings.CATALOG_THUMBNAIL_SPACES_BUCKET
    if not bucket:
        return default_storage

    region = settings.CATALOG_THUMBNAIL_SPACES_REGION
    key = settings.CATALOG_THUMBNAIL_SPACES_KEY
    secret = settings.CATALOG_THUMBNAIL_SPACES_SECRET
    if not all((region, key, secret)):
        raise ValueError('Configure region, key and secret for catalog thumbnail storage.')

    from storages.backends.s3 import S3Storage

    return S3Storage(
        bucket_name=bucket,
        region_name=region,
        endpoint_url=f'https://{region}.digitaloceanspaces.com',
        custom_domain=f'{bucket}.{region}.cdn.digitaloceanspaces.com',
        access_key=key,
        secret_key=secret,
        default_acl='public-read',
        querystring_auth=False,
        object_parameters={'CacheControl': 'public, max-age=31536000, immutable'},
    )


def generate_thumbnail(model, pk, source_name, using):
    queryset = model.objects.using(using).filter(pk=pk, image=source_name)
    instance = queryset.only('image').first()
    if instance is None or not instance.image:
        return False

    try:
        with instance.image.storage.open(source_name, 'rb') as source, Image.open(source) as original:
            photo = ImageOps.exif_transpose(original)
            photo.thumbnail(THUMBNAIL_SIZE, Image.Resampling.LANCZOS)
            mode = 'RGBA' if 'A' in photo.getbands() or 'transparency' in photo.info else 'RGB'
            with BytesIO() as output:
                photo.convert(mode).save(output, format='WEBP', quality=82)
                content = output.getvalue()

        storage = thumbnail_storage()
        digest = sha256(content).hexdigest()
        name = f'products/thumbnails/{digest}.webp'
        if not storage.exists(name):
            name = storage.save(name, ContentFile(content))
        return bool(queryset.update(catalog_thumbnail_url=storage.url(name)))
    except Exception as exc:
        logger.warning('Catalog thumbnail failed for %s %s (%s)', model.__name__, pk, type(exc).__name__)
        return False


def track_image_change(sender, instance, using, update_fields=None, raw=False, **kwargs):
    instance._catalog_image_changed = False
    if raw or (update_fields is not None and 'image' not in update_fields):
        return

    previous = None
    if instance.pk is not None:
        previous = sender.objects.using(using).filter(pk=instance.pk).values('image', 'catalog_thumbnail_url').first()
    image = instance.image
    instance._catalog_image_changed = (
        (image.name or '') != ((previous or {}).get('image') or '')
        or bool(image and not image._committed)
    )
    instance.catalog_thumbnail_url = (
        '' if instance._catalog_image_changed else (previous or {}).get('catalog_thumbnail_url', '')
    )


def queue_thumbnail(sender, instance, using, update_fields=None, raw=False, **kwargs):
    if raw or not instance._catalog_image_changed:
        return

    if update_fields is not None:
        sender.objects.using(using).filter(pk=instance.pk).update(catalog_thumbnail_url='')
    if instance.image:
        transaction.on_commit(
            partial(generate_thumbnail, sender, instance.pk, instance.image.name, using),
            using=using,
        )


def connect_thumbnail_signals():
    for model in (Product, Variant):
        pre_save.connect(track_image_change, sender=model, dispatch_uid=f'thumbnail-track-{model.__name__}')
        post_save.connect(queue_thumbnail, sender=model, dispatch_uid=f'thumbnail-generate-{model.__name__}')
