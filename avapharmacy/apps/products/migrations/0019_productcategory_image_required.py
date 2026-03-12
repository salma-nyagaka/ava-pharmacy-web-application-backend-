from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0018_sync_product_category_from_subcategory'),
    ]

    operations = [
        migrations.AddField(
            model_name='productcategory',
            name='image',
            field=models.ImageField(default='categories/default-category-image.svg', upload_to='categories/'),
            preserve_default=False,
        ),
    ]
