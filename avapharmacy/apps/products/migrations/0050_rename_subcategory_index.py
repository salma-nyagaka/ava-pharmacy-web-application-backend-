from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0049_rename_catalogsubcategory_table'),
    ]

    operations = [
        migrations.RenameIndex(
            model_name='catalogsubcategory',
            old_name='products_ca_categor_cdd20d_idx',
            new_name='products_su_categor_86a9be_idx',
        ),
    ]
