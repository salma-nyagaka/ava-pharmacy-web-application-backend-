from django.db import migrations, models


def backfill_variant_inventory(apps, schema_editor):
    Product = apps.get_model('products', 'Product')
    ProductVariant = apps.get_model('products', 'ProductVariant')
    VariantInventory = apps.get_model('products', 'VariantInventory')

    for variant in ProductVariant.objects.all().iterator():
        VariantInventory.objects.get_or_create(
            variant=variant,
            location=Product.STOCK_BRANCH,
            defaults={
                'stock_quantity': variant.stock_quantity,
                'low_stock_threshold': variant.low_stock_threshold,
                'allow_backorder': variant.allow_backorder,
                'max_backorder_quantity': variant.max_backorder_quantity,
            },
        )
        VariantInventory.objects.get_or_create(
            variant=variant,
            location=Product.STOCK_WAREHOUSE,
            defaults={
                'stock_quantity': 0,
                'low_stock_threshold': 0,
                'allow_backorder': False,
                'max_backorder_quantity': 0,
                'source_name': 'POS Store',
            },
        )


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0033_productvariant_warnings'),
    ]

    operations = [
        migrations.CreateModel(
            name='VariantInventory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('location', models.CharField(choices=[('branch', 'Main Shop'), ('warehouse', 'POS Store')], default='branch', max_length=20)),
                ('source_name', models.CharField(blank=True, max_length=120)),
                ('stock_quantity', models.PositiveIntegerField(default=0)),
                ('low_stock_threshold', models.PositiveIntegerField(default=0)),
                ('allow_backorder', models.BooleanField(default=False)),
                ('max_backorder_quantity', models.PositiveIntegerField(default=0)),
                ('next_restock_date', models.DateField(blank=True, null=True)),
                ('is_pos_synced', models.BooleanField(default=False)),
                ('last_synced_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('variant', models.ForeignKey(on_delete=models.deletion.CASCADE, related_name='inventories', to='products.productvariant')),
            ],
            options={
                'ordering': ['variant_id', 'location'],
            },
        ),
        migrations.AddIndex(
            model_name='variantinventory',
            index=models.Index(fields=['location'], name='products_va_locatio_b95cce_idx'),
        ),
        migrations.AddConstraint(
            model_name='variantinventory',
            constraint=models.UniqueConstraint(fields=('variant', 'location'), name='unique_variant_inventory_location'),
        ),
        migrations.RunPython(backfill_variant_inventory, migrations.RunPython.noop),
    ]
