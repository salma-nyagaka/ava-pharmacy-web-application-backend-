from django.db import migrations


def align_item_status(apps, schema_editor):
    Product = apps.get_model('products', 'Product')
    # Splitting an active family must never reactivate an inactive exact SKU.
    Product.objects.using(schema_editor.connection.alias).filter(is_active=True, variants__is_active=False).update(is_active=False)


class Migration(migrations.Migration):
    dependencies = [('products', '0071_flat_sellable_items')]
    operations = [migrations.RunPython(align_item_status, migrations.RunPython.noop)]
