from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0045_remove_variant_legacy_subcategory'),
    ]

    operations = [
        migrations.DeleteModel(
            name='ProductSubcategory',
        ),
        migrations.DeleteModel(
            name='ProductCategory',
        ),
    ]
