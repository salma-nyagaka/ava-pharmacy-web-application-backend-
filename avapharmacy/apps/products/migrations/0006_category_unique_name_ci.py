from django.db import migrations, models
from django.db.models.functions.text import Lower


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0005_product_strength'),
    ]

    operations = [
        migrations.AddConstraint(
            model_name='category',
            constraint=models.UniqueConstraint(Lower('name'), name='unique_category_name_ci'),
        ),
    ]
