import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0023_add_image_to_health_concern'),
    ]

    operations = [
        migrations.CreateModel(
            name='ProductBadge',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(help_text="Unique identifier, e.g. 'new', 'hot-deal'", max_length=50, unique=True)),
                ('label', models.CharField(help_text="Display text shown on product, e.g. 'New', '20% Off'", max_length=50)),
                ('badge_type', models.CharField(choices=[('custom', 'Custom'), ('percentage', 'Percentage Off'), ('amount', 'Amount Off')], default='custom', max_length=20)),
                ('value', models.DecimalField(blank=True, decimal_places=2, help_text='Numeric value for percentage/amount types', max_digits=10, null=True)),
                ('color', models.CharField(choices=[('green', 'Green'), ('red', 'Red'), ('orange', 'Orange'), ('blue', 'Blue'), ('purple', 'Purple'), ('teal', 'Teal')], default='green', max_length=20)),
                ('expires_at', models.DateField(blank=True, null=True)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'ordering': ['name'],
            },
        ),
        migrations.RemoveField(
            model_name='product',
            name='badge',
        ),
        migrations.AddField(
            model_name='product',
            name='badge',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='products', to='products.productbadge'),
        ),
    ]
