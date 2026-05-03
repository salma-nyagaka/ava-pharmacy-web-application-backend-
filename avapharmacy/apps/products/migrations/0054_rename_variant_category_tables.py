from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0053_rename_subcategory_constraint'),
    ]

    operations = [
        migrations.AlterModelTable(
            name='category',
            table='prodcut_variants_categories',
        ),
        migrations.AlterModelTable(
            name='subcategory',
            table='product_variants_subcategories',
        ),
    ]
