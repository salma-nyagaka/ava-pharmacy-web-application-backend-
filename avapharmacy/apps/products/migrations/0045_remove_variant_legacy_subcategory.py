from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0044_align_variant_indexes_after_inventory_cleanup'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='variant',
            name='subcategory',
        ),
    ]
