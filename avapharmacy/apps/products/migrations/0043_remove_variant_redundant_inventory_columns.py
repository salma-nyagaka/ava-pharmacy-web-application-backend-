from django.db import migrations


def ensure_variant_inventory_rows(apps, schema_editor):
    Variant = apps.get_model('products', 'Variant')
    VariantInventory = apps.get_model('products', 'VariantInventory')

    branch_location = 'branch'
    warehouse_location = 'warehouse'
    valid_locations = {branch_location, warehouse_location}

    for variant in Variant.objects.all().iterator():
        inventories = {
            inventory.location: inventory
            for inventory in VariantInventory.objects.filter(variant_id=variant.id)
        }
        if inventories:
            for location in valid_locations - set(inventories):
                VariantInventory.objects.create(
                    variant_id=variant.id,
                    location=location,
                    stock_quantity=0,
                    low_stock_threshold=5 if location == branch_location else 0,
                    allow_backorder=False,
                    max_backorder_quantity=0,
                )
            continue

        source_location = variant.stock_source if variant.stock_source in valid_locations else branch_location
        for location in (branch_location, warehouse_location):
            is_source = location == source_location
            VariantInventory.objects.create(
                variant_id=variant.id,
                location=location,
                stock_quantity=variant.stock_quantity if is_source else 0,
                low_stock_threshold=variant.low_stock_threshold if is_source else (5 if location == branch_location else 0),
                allow_backorder=variant.allow_backorder if is_source else False,
                max_backorder_quantity=variant.max_backorder_quantity if is_source else 0,
            )


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0042_move_product_fields_to_variant'),
    ]

    operations = [
        migrations.RunPython(ensure_variant_inventory_rows, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name='variant',
            name='allow_backorder',
        ),
        migrations.RemoveField(
            model_name='variant',
            name='low_stock_threshold',
        ),
        migrations.RemoveField(
            model_name='variant',
            name='max_backorder_quantity',
        ),
        migrations.RemoveField(
            model_name='variant',
            name='stock_quantity',
        ),
        migrations.RemoveField(
            model_name='variant',
            name='stock_source',
        ),
    ]
