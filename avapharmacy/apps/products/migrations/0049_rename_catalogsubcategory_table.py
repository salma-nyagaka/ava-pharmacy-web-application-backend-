from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0048_rename_catalogsubcategory_index'),
    ]

    operations = [
        migrations.AlterModelTable(
            name='catalogsubcategory',
            table='products_subcategory',
        ),
    ]
