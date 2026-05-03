from django.db import migrations, models
import django.db.models.deletion


def backfill_variant_references(apps, schema_editor):
    Variant = apps.get_model('products', 'Variant')
    CartItem = apps.get_model('orders', 'CartItem')
    OrderItem = apps.get_model('orders', 'OrderItem')

    representative_variants = {}
    for variant in Variant.objects.filter(is_active=True).order_by('product_id', 'sort_order', 'name', 'pk'):
        representative_variants.setdefault(variant.product_id, variant.id)

    for item in CartItem.objects.filter(variant__isnull=True).iterator():
        variant_id = representative_variants.get(item.product_id)
        if variant_id:
            item.variant_id = variant_id
            item.save(update_fields=['variant'])

    for item in OrderItem.objects.filter(variant__isnull=True).iterator():
        variant_id = representative_variants.get(item.product_id)
        if variant_id:
            item.variant_id = variant_id
            item.save(update_fields=['variant'])


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ('products', '0037_variant_first_commerce_models'),
        ('orders', '0008_remove_cartitem_unique_cart_item_product_variant_prescription_and_more'),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name='cartitem',
            name='unique_cart_item_variant_prescription',
        ),
        migrations.RunPython(backfill_variant_references, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name='cartitem',
            name='product',
        ),
        migrations.RemoveField(
            model_name='orderitem',
            name='product',
        ),
        migrations.AlterField(
            model_name='cartitem',
            name='variant',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='cart_items', to='products.variant'),
        ),
        migrations.AlterField(
            model_name='orderitem',
            name='variant',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='order_items', to='products.variant'),
        ),
        migrations.AddConstraint(
            model_name='cartitem',
            constraint=models.UniqueConstraint(fields=('cart', 'variant', 'prescription', 'prescription_item'), name='unique_cart_item_variant_prescription'),
        ),
    ]
