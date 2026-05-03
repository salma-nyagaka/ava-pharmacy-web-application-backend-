from django.db import migrations, models
import django.db.models.deletion


def copy_variant_brand_and_subcategory_to_new_fields(apps, schema_editor):
    Product = apps.get_model('products', 'Product')
    Variant = apps.get_model('products', 'Variant')
    db_alias = schema_editor.connection.alias

    Variant.objects.using(db_alias).filter(
        subcategory_id__isnull=True,
        catalog_subcategory_id__isnull=False,
    ).update(subcategory_id=models.F('catalog_subcategory_id'))

    seen_product_ids = set()
    variants = Variant.objects.using(db_alias).exclude(
        brand_id__isnull=True,
    ).order_by('product_id', 'sort_order', 'name', 'pk')

    for variant in variants.iterator():
        if variant.product_id in seen_product_ids:
            continue
        Product.objects.using(db_alias).filter(
            pk=variant.product_id,
            brand_id__isnull=True,
        ).update(brand_id=variant.brand_id)
        seen_product_ids.add(variant.product_id)


def restore_variant_brand_and_catalog_subcategory(apps, schema_editor):
    Product = apps.get_model('products', 'Product')
    Variant = apps.get_model('products', 'Variant')
    db_alias = schema_editor.connection.alias

    Variant.objects.using(db_alias).filter(
        catalog_subcategory_id__isnull=True,
        subcategory_id__isnull=False,
    ).update(catalog_subcategory_id=models.F('subcategory_id'))

    product_brand_map = dict(
        Product.objects.using(db_alias).exclude(brand_id__isnull=True).values_list('id', 'brand_id')
    )
    variants = Variant.objects.using(db_alias).filter(
        brand_id__isnull=True,
        product_id__in=product_brand_map.keys(),
    )
    for variant in variants.iterator():
        variant.brand_id = product_brand_map.get(variant.product_id)
        variant.save(update_fields=['brand'])


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0050_rename_subcategory_index'),
    ]

    operations = [
        migrations.AddField(
            model_name='product',
            name='brand',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='products',
                to='products.brand',
            ),
        ),
        migrations.AddField(
            model_name='variant',
            name='subcategory',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='variants_as_subcategory',
                to='products.catalogsubcategory',
            ),
        ),
        migrations.RunPython(
            copy_variant_brand_and_subcategory_to_new_fields,
            restore_variant_brand_and_catalog_subcategory,
        ),
        migrations.RemoveIndex(
            model_name='variant',
            name='products_va_brand_i_04a1b4_idx',
        ),
        migrations.RemoveIndex(
            model_name='variant',
            name='products_va_catalog_af619c_idx',
        ),
        migrations.RemoveField(
            model_name='variant',
            name='brand',
        ),
        migrations.RemoveField(
            model_name='variant',
            name='catalog_subcategory',
        ),
        migrations.AddIndex(
            model_name='product',
            index=models.Index(fields=['brand', 'is_active'], name='products_pr_brand_i_8f789e_idx'),
        ),
        migrations.AddIndex(
            model_name='variant',
            index=models.Index(fields=['subcategory', 'is_active'], name='products_va_subcate_436923_idx'),
        ),
    ]
