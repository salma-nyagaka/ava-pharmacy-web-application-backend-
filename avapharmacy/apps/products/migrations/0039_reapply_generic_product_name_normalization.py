import re

from django.db import migrations
from django.utils.text import slugify


GENERIC_PRODUCT_SUFFIX_WORDS = {
    'tablet', 'tablets', 'capsule', 'capsules', 'caplet', 'caplets', 'syrup', 'syrups',
    'cream', 'creams', 'ointment', 'gel', 'gels', 'lotion', 'lotions', 'solution',
    'solutions', 'liquid', 'liquids', 'drop', 'drops', 'spray', 'sprays', 'powder',
    'powders', 'softgel', 'softgels', 'lozenge', 'lozenges', 'effervescent',
    'inhaler', 'inhalers', 'mask', 'masks', 'bundle', 'bundles', 'pack', 'packs',
    'sheet', 'sheets', 'starter', 'kit', 'kits', 'monitor', 'monitors',
}

GENERIC_PRODUCT_MODIFIERS = {
    'extra', 'normal', 'original', 'advance', 'advanced', 'plus', 'max', 'flu', 'gone',
    'cough', 'cold', 'day', 'night', 'honey', 'lemon', 'repair', 'protect',
}

DOSAGE_TOKEN_RE = re.compile(
    r'^(?:(?:\d+(?:[./+]\d+)*(?:mg|mcg|g|kg|ml|l|%|iu|spf))(?:/\d+(?:[./+]\d+)*(?:mg|mcg|g|kg|ml|l|%|iu|spf))*|\d+(?:s|pcs|pc))$',
    re.IGNORECASE,
)


def normalize_generic_product_name(name):
    text = re.sub(r'\s+', ' ', str(name or '')).strip()
    if not text:
        return ''

    text = re.sub(r'\([^)]*\)$', '', text).strip()
    tokens = text.split()
    while tokens:
        token = tokens[-1].strip(",").lower()
        if DOSAGE_TOKEN_RE.match(token):
            tokens.pop()
            continue
        if token in GENERIC_PRODUCT_SUFFIX_WORDS:
            tokens.pop()
            continue
        break

    while len(tokens) > 1 and tokens[-1].lower() in GENERIC_PRODUCT_MODIFIERS:
        tokens.pop()

    normalized = ' '.join(tokens).strip()
    return normalized or text


def generate_unique_slug(Product, instance, base_name):
    base_slug = slugify(base_name) or 'product'
    slug = base_slug
    counter = 2
    while Product.objects.exclude(pk=instance.pk).filter(slug=slug).exists():
        slug = f'{base_slug}-{counter}'
        counter += 1
    return slug


def forwards(apps, schema_editor):
    Product = apps.get_model('products', 'Product')
    for product in Product.objects.all().iterator():
        normalized_name = normalize_generic_product_name(product.name)
        if not normalized_name:
            continue
        if normalized_name != product.name:
            product.name = normalized_name
            product.slug = generate_unique_slug(Product, product, normalized_name)
            product.save(update_fields=['name', 'slug', 'updated_at'])


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0038_normalize_product_generic_names'),
    ]

    operations = [
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
