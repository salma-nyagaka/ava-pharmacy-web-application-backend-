from decimal import Decimal

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('support', '0003_newslettersubscriber'),
    ]

    operations = [
        migrations.CreateModel(
            name='SiteSettings',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('support_email', models.EmailField(default='support@avapharmacy.co.ke', max_length=254)),
                ('support_phone', models.CharField(default='+254 700 000 000', max_length=50)),
                ('whatsapp_phone', models.CharField(default='+254 700 000 000', max_length=50)),
                ('support_address', models.CharField(default='Karen / The Hub, Karen, Nairobi, Kenya', max_length=255)),
                ('support_hours', models.CharField(default='Mon - Sun: 09am - 5pm', max_length=120)),
                ('base_delivery_fee', models.DecimalField(decimal_places=2, default=Decimal('300'), max_digits=10)),
                ('free_delivery_threshold', models.DecimalField(decimal_places=2, default=Decimal('3000'), max_digits=10)),
                ('active_delivery_zones', models.TextField(default='Nairobi, Kiambu, Mombasa')),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'site settings',
                'verbose_name_plural': 'site settings',
            },
        ),
    ]
