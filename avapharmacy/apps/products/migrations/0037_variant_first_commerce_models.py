from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def backfill_variant_first_product_data(apps, schema_editor):
    Variant = apps.get_model('products', 'Variant')
    VariantInventory = apps.get_model('products', 'VariantInventory')
    ProductReview = apps.get_model('products', 'ProductReview')
    VariantReview = apps.get_model('products', 'VariantReview')
    Wishlist = apps.get_model('products', 'Wishlist')
    StockMovement = apps.get_model('products', 'StockMovement')
    Product = apps.get_model('products', 'Product')

    representative_variants = {}
    for variant in Variant.objects.filter(is_active=True).order_by('product_id', 'sort_order', 'name', 'pk'):
        representative_variants.setdefault(variant.product_id, variant)

    for product in Product.objects.all().iterator():
        variant = representative_variants.get(product.id)
        if variant is None:
            continue
        if variant.price is None:
            variant.price = product.price or 0
            variant.save(update_fields=['price'])

    for review in ProductReview.objects.all().iterator():
        variant = representative_variants.get(review.product_id)
        if variant is None:
            continue
        VariantReview.objects.update_or_create(
            variant_id=variant.id,
            user_id=review.user_id,
            defaults={
                'rating': review.rating,
                'comment': review.comment,
                'is_approved': review.is_approved,
                'created_at': review.created_at,
            },
        )

    for wishlist in Wishlist.objects.all().iterator():
        variant = representative_variants.get(wishlist.product_id)
        if variant is None:
            continue
        wishlist.variant_id = variant.id
        wishlist.save(update_fields=['variant'])

    for movement in StockMovement.objects.all().iterator():
        variant = representative_variants.get(movement.product_id)
        if variant is None:
            continue
        inventory = VariantInventory.objects.filter(variant_id=variant.id).order_by('location', 'pk').first()
        if inventory is None:
            inventory = VariantInventory.objects.create(
                variant_id=variant.id,
                location='branch',
                stock_quantity=0,
                low_stock_threshold=0,
            )
        movement.variant_inventory_id = inventory.id
        movement.save(update_fields=['variant_inventory'])


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('products', '0036_rename_productvariant_variant_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='VariantReview',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('rating', models.PositiveSmallIntegerField()),
                ('comment', models.TextField(blank=True)),
                ('is_approved', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='reviews', to=settings.AUTH_USER_MODEL)),
                ('variant', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='reviews', to='products.variant')),
            ],
            options={
                'ordering': ['-created_at'],
                'unique_together': {('variant', 'user')},
            },
        ),
        migrations.AddField(
            model_name='stockmovement',
            name='variant_inventory',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='stock_movements', to='products.variantinventory'),
        ),
        migrations.AddField(
            model_name='wishlist',
            name='variant',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='wishlisted_by', to='products.variant'),
        ),
        migrations.AlterField(
            model_name='product',
            name='price',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=10),
        ),
        migrations.RunPython(backfill_variant_first_product_data, migrations.RunPython.noop),
        migrations.RemoveIndex(
            model_name='stockmovement',
            name='products_st_product_3ae061_idx',
        ),
        migrations.RemoveField(
            model_name='stockmovement',
            name='product',
        ),
        migrations.AddIndex(
            model_name='stockmovement',
            index=models.Index(fields=['variant_inventory', '-created_at'], name='products_st_variant_4efc87_idx'),
        ),
        migrations.AlterUniqueTogether(
            name='wishlist',
            unique_together=set(),
        ),
        migrations.RemoveField(
            model_name='wishlist',
            name='product',
        ),
        migrations.AlterUniqueTogether(
            name='wishlist',
            unique_together={('user', 'variant')},
        ),
        migrations.DeleteModel(
            name='ProductReview',
        ),
        migrations.AlterField(
            model_name='variant',
            name='price',
            field=models.DecimalField(decimal_places=2, max_digits=10),
        ),
    ]
