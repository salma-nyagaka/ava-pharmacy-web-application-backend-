from django.db import migrations, models


def copy_product_health_concerns_to_variants(apps, schema_editor):
    Product = apps.get_model('products', 'Product')

    for product in Product.objects.prefetch_related('health_concerns', 'variants').iterator():
        concern_ids = list(product.health_concerns.values_list('id', flat=True))
        if not concern_ids:
            continue
        for variant in product.variants.all():
            variant.health_concerns.add(*concern_ids)


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0040_variant_requires_prescription'),
    ]

    operations = [
        migrations.AddField(
            model_name='variant',
            name='health_concerns',
            field=models.ManyToManyField(blank=True, related_name='variants', to='products.healthconcern'),
        ),
        migrations.RunPython(copy_product_health_concerns_to_variants, migrations.RunPython.noop),
    ]
