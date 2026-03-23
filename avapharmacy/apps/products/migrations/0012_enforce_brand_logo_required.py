from django.db import migrations, models


DEFAULT_BRAND_LOGO = 'brands/default-brand-logo.svg'


def backfill_brand_logos(apps, schema_editor):
    Brand = apps.get_model('products', 'Brand')
    Brand.objects.filter(logo__isnull=True).update(logo=DEFAULT_BRAND_LOGO)
    Brand.objects.filter(logo='').update(logo=DEFAULT_BRAND_LOGO)


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0011_add_stock_movement'),
    ]

    operations = [
        migrations.RunPython(backfill_brand_logos, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='brand',
            name='logo',
            field=models.ImageField(upload_to='brands/'),
        ),
    ]
