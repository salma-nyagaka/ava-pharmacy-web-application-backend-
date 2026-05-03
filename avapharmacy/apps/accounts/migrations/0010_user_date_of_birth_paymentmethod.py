from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0009_address_accounts_ad_user_id_c8244c_idx_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='date_of_birth',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.CreateModel(
            name='PaymentMethod',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('brand', models.CharField(blank=True, default='unknown', max_length=30)),
                ('last4', models.CharField(max_length=4)),
                ('expiry_month', models.PositiveSmallIntegerField()),
                ('expiry_year', models.PositiveSmallIntegerField()),
                ('cardholder_name', models.CharField(max_length=120)),
                ('is_default', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='payment_methods', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-is_default', '-updated_at'],
                'indexes': [
                    models.Index(fields=['user', 'is_default'], name='accounts_pa_user_id_738eaa_idx'),
                    models.Index(fields=['user', '-updated_at'], name='accounts_pa_user_id_0e7c79_idx'),
                ],
            },
        ),
        migrations.AddConstraint(
            model_name='paymentmethod',
            constraint=models.UniqueConstraint(
                condition=models.Q(('is_default', True)),
                fields=('user',),
                name='unique_default_payment_method_per_user',
            ),
        ),
    ]
