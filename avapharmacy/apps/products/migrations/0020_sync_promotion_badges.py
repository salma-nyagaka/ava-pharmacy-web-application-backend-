from decimal import Decimal

from django.db import migrations


def format_badge_value(value):
    normalized = Decimal(value)
    if normalized == normalized.to_integral():
        return str(int(normalized))
    return format(normalized.normalize(), 'f').rstrip('0').rstrip('.')


def sync_promotion_badges(apps, schema_editor):
    Promotion = apps.get_model('products', 'Promotion')
    for promotion in Promotion.objects.all():
        value = format_badge_value(promotion.value)
        if promotion.type == 'percentage':
            promotion.badge = f'{value}% Off'
        else:
            promotion.badge = f'KSh {value} Off'
        promotion.save(update_fields=['badge'])


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0019_productcategory_image_required'),
    ]

    operations = [
        migrations.RunPython(sync_promotion_badges, migrations.RunPython.noop),
    ]
