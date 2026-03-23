from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0012_enforce_brand_logo_required'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='brand',
            name='health_concerns',
        ),
    ]
