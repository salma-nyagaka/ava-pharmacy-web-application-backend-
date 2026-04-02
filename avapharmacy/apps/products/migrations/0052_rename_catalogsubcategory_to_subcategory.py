from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0051_move_brand_to_product_and_rename_variant_subcategory'),
    ]

    operations = [
        migrations.RenameModel(
            old_name='CatalogSubcategory',
            new_name='Subcategory',
        ),
        migrations.AlterModelOptions(
            name='subcategory',
            options={'ordering': ['category__name', 'name'], 'verbose_name_plural': 'subcategories'},
        ),
        migrations.AlterField(
            model_name='category',
            name='parent',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='child_categories', to='products.category'),
        ),
        migrations.AlterField(
            model_name='subcategory',
            name='category',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='subcategories', to='products.category'),
        ),
        migrations.AlterField(
            model_name='subcategory',
            name='created_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='created_subcategories', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AlterField(
            model_name='subcategory',
            name='updated_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='updated_subcategories', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AlterField(
            model_name='variant',
            name='subcategory',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='variants_as_subcategory', to='products.subcategory'),
        ),
    ]
