from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0047_split_catalog_subcategories'),
    ]

    operations = [
        migrations.RenameIndex(
            model_name='catalogsubcategory',
            old_name='products_ca_categor_6a9cdd_idx',
            new_name='products_ca_categor_cdd20d_idx',
        ),
    ]
