from django.db import migrations, models
from django.db.models.functions import Lower


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0052_rename_catalogsubcategory_to_subcategory'),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name='subcategory',
            name='unique_catalog_subcategory_name_per_category_ci',
        ),
        migrations.AddConstraint(
            model_name='subcategory',
            constraint=models.UniqueConstraint(Lower('name'), models.F('category'), name='unique_subcategory_name_per_category_ci'),
        ),
    ]
