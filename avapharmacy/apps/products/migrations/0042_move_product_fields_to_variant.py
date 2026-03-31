from django.db import migrations, models
import django.db.models.deletion


def migrate_product_fields_to_variants(apps, schema_editor):
    Product = apps.get_model('products', 'Product')
    Variant = apps.get_model('products', 'Variant')

    for product in Product.objects.prefetch_related('health_concerns', 'variants').iterator():
        variants = list(product.variants.all().order_by('sort_order', 'name', 'pk'))
        if not variants:
            variants = [
                Variant.objects.create(
                    product=product,
                    sku=f'{product.sku}-STD',
                    barcode=product.barcode,
                    pos_product_id=product.pos_product_id,
                    name=(product.strength or '').strip() or 'Standard',
                    price=product.price or 0,
                    cost_price=product.cost_price,
                    requires_prescription=bool(product.requires_prescription),
                    is_active=product.is_active,
                )
            ]

        concern_ids = list(product.health_concerns.values_list('id', flat=True))
        product_features = product.features if isinstance(product.features, list) else []

        for variant in variants:
            update_fields = []

            field_values = {
                'brand_id': product.brand_id,
                'category_id': product.category_id,
                'subcategory_id': product.subcategory_id,
                'catalog_subcategory_id': product.catalog_subcategory_id,
                'short_description': product.short_description or '',
                'description': product.description or '',
                'features': product_features,
                'dosage_quantity': product.dosage_quantity or '',
                'dosage_unit': product.dosage_unit or '',
                'dosage_frequency': product.dosage_frequency or '',
                'dosage_notes': product.dosage_notes or '',
            }

            for field_name, value in field_values.items():
                if getattr(variant, field_name) != value:
                    setattr(variant, field_name, value)
                    update_fields.append(field_name)

            if not variant.strength and product.strength:
                variant.strength = product.strength
                update_fields.append('strength')
            if not variant.directions and product.directions:
                variant.directions = product.directions
                update_fields.append('directions')
            if not variant.warnings and product.warnings:
                variant.warnings = product.warnings
                update_fields.append('warnings')
            if (variant.price is None or variant.price == 0) and product.price:
                variant.price = product.price
                update_fields.append('price')
            if variant.cost_price is None and product.cost_price is not None:
                variant.cost_price = product.cost_price
                update_fields.append('cost_price')
            if product.requires_prescription and not variant.requires_prescription:
                variant.requires_prescription = True
                update_fields.append('requires_prescription')

            if update_fields:
                variant.save(update_fields=sorted(set(update_fields)))

            if concern_ids and not variant.health_concerns.filter(id__in=concern_ids).exists():
                variant.health_concerns.add(*concern_ids)


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0041_variant_health_concerns'),
    ]

    operations = [
        migrations.AddField(
            model_name='variant',
            name='brand',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='variants', to='products.brand'),
        ),
        migrations.AddField(
            model_name='variant',
            name='catalog_subcategory',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='variants_as_subcategory', to='products.category'),
        ),
        migrations.AddField(
            model_name='variant',
            name='category',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='variants', to='products.category'),
        ),
        migrations.AddField(
            model_name='variant',
            name='description',
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name='variant',
            name='dosage_frequency',
            field=models.CharField(blank=True, help_text='e.g. once_daily, twice_daily', max_length=50),
        ),
        migrations.AddField(
            model_name='variant',
            name='dosage_notes',
            field=models.CharField(blank=True, help_text='e.g. with food, before meals', max_length=150),
        ),
        migrations.AddField(
            model_name='variant',
            name='dosage_quantity',
            field=models.CharField(blank=True, help_text='e.g. 1, 2, 1-2', max_length=20),
        ),
        migrations.AddField(
            model_name='variant',
            name='dosage_unit',
            field=models.CharField(blank=True, help_text='e.g. tablet, capsule, ml, drop', max_length=30),
        ),
        migrations.AddField(
            model_name='variant',
            name='features',
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name='variant',
            name='short_description',
            field=models.CharField(blank=True, max_length=500),
        ),
        migrations.AddField(
            model_name='variant',
            name='subcategory',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='variants', to='products.productsubcategory'),
        ),
        migrations.RunPython(migrate_product_fields_to_variants, migrations.RunPython.noop),
        migrations.RemoveIndex(
            model_name='product',
            name='products_pr_categor_50f5f1_idx',
        ),
        migrations.RemoveIndex(
            model_name='product',
            name='products_pr_brand_i_8f789e_idx',
        ),
        migrations.RemoveIndex(
            model_name='product',
            name='products_pr_catalog_439756_idx',
        ),
        migrations.RemoveIndex(
            model_name='product',
            name='products_pr_require_ad0b8d_idx',
        ),
        migrations.RemoveField(
            model_name='product',
            name='brand',
        ),
        migrations.RemoveField(
            model_name='product',
            name='catalog_subcategory',
        ),
        migrations.RemoveField(
            model_name='product',
            name='category',
        ),
        migrations.RemoveField(
            model_name='product',
            name='cost_price',
        ),
        migrations.RemoveField(
            model_name='product',
            name='description',
        ),
        migrations.RemoveField(
            model_name='product',
            name='directions',
        ),
        migrations.RemoveField(
            model_name='product',
            name='dosage_frequency',
        ),
        migrations.RemoveField(
            model_name='product',
            name='dosage_notes',
        ),
        migrations.RemoveField(
            model_name='product',
            name='dosage_quantity',
        ),
        migrations.RemoveField(
            model_name='product',
            name='dosage_unit',
        ),
        migrations.RemoveField(
            model_name='product',
            name='features',
        ),
        migrations.RemoveField(
            model_name='product',
            name='health_concerns',
        ),
        migrations.RemoveField(
            model_name='product',
            name='price',
        ),
        migrations.RemoveField(
            model_name='product',
            name='requires_prescription',
        ),
        migrations.RemoveField(
            model_name='product',
            name='short_description',
        ),
        migrations.RemoveField(
            model_name='product',
            name='strength',
        ),
        migrations.RemoveField(
            model_name='product',
            name='subcategory',
        ),
        migrations.RemoveField(
            model_name='product',
            name='warnings',
        ),
        migrations.AddIndex(
            model_name='variant',
            index=models.Index(fields=['brand', 'is_active'], name='products_va_brand_i_544baa_idx'),
        ),
        migrations.AddIndex(
            model_name='variant',
            index=models.Index(fields=['category', 'is_active'], name='products_va_categor_8d84ea_idx'),
        ),
        migrations.AddIndex(
            model_name='variant',
            index=models.Index(fields=['catalog_subcategory', 'is_active'], name='products_va_catalog_14231d_idx'),
        ),
    ]
