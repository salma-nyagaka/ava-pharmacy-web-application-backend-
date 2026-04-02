from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0043_remove_variant_redundant_inventory_columns'),
    ]

    operations = [
        migrations.RemoveIndex(
            model_name='variant',
            name='products_va_stock_s_3439d4_idx',
        ),
        migrations.RenameIndex(
            model_name='variant',
            old_name='products_va_brand_i_544baa_idx',
            new_name='products_va_brand_i_04a1b4_idx',
        ),
        migrations.RenameIndex(
            model_name='variant',
            old_name='products_va_categor_8d84ea_idx',
            new_name='products_va_categor_91350d_idx',
        ),
        migrations.RenameIndex(
            model_name='variant',
            old_name='products_va_catalog_14231d_idx',
            new_name='products_va_catalog_af619c_idx',
        ),
    ]
