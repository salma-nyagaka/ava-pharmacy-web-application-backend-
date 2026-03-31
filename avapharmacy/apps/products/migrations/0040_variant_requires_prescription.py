from django.db import migrations, models


def forwards(apps, schema_editor):
    Product = apps.get_model('products', 'Product')
    Variant = apps.get_model('products', 'Variant')

    for variant in Variant.objects.select_related('product').all().iterator():
        variant.requires_prescription = bool(getattr(variant.product, 'requires_prescription', False))
        variant.save(update_fields=['requires_prescription'])

    product_ids_with_variants = set(Variant.objects.values_list('product_id', flat=True))
    for product in Product.objects.exclude(id__in=product_ids_with_variants).iterator():
        Variant.objects.create(
            product=product,
            sku=f'{product.sku}-STD',
            name='Standard',
            price=getattr(product, 'price', 0) or 0,
            requires_prescription=bool(product.requires_prescription),
            is_active=product.is_active,
        )


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0039_reapply_generic_product_name_normalization'),
    ]

    operations = [
        migrations.AddField(
            model_name='variant',
            name='requires_prescription',
            field=models.BooleanField(default=False),
        ),
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
