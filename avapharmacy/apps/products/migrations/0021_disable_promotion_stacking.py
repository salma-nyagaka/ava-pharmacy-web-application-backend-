from django.db import migrations


def disable_promotion_stacking(apps, schema_editor):
    Promotion = apps.get_model('products', 'Promotion')
    Promotion.objects.exclude(is_stackable=False).update(is_stackable=False)


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0020_sync_promotion_badges'),
    ]

    operations = [
        migrations.RunPython(disable_promotion_stacking, migrations.RunPython.noop),
    ]
