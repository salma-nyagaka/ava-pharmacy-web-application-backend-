from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0027_remove_product_products_pr_is_feat_a1ecf6_idx_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='product',
            name='barcode',
            field=models.CharField(blank=True, max_length=64),
        ),
        migrations.AddField(
            model_name='product',
            name='pos_product_id',
            field=models.CharField(blank=True, max_length=80),
        ),
        migrations.AddField(
            model_name='productvariant',
            name='barcode',
            field=models.CharField(blank=True, max_length=64),
        ),
        migrations.AddField(
            model_name='productvariant',
            name='pos_product_id',
            field=models.CharField(blank=True, max_length=80),
        ),
    ]
