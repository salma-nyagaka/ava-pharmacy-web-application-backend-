from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0029_productinventory_next_restock_date_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='promotion',
            name='image',
            field=models.ImageField(blank=True, null=True, upload_to='promotions/'),
        ),
    ]
