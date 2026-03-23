from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0003_shippingmethod_alter_cartitem_unique_together_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='OutboundOrderPush',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('action', models.CharField(max_length=20)),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('retrying', 'Retrying'), ('succeeded', 'Succeeded'), ('exhausted', 'Exhausted')], default='pending', max_length=20)),
                ('payload', models.JSONField(blank=True, default=dict)),
                ('attempt_count', models.PositiveIntegerField(default=0)),
                ('max_attempts', models.PositiveIntegerField(default=0)),
                ('next_attempt_at', models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ('last_attempt_at', models.DateTimeField(blank=True, null=True)),
                ('processed_at', models.DateTimeField(blank=True, null=True)),
                ('response_status_code', models.IntegerField(blank=True, null=True)),
                ('response_body', models.TextField(blank=True)),
                ('last_error', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('order', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='outbound_pushes', to='orders.order')),
            ],
            options={
                'ordering': ['next_attempt_at', 'created_at'],
                'indexes': [
                    models.Index(fields=['status', 'next_attempt_at'], name='orders_outb_status_8350b9_idx'),
                    models.Index(fields=['order', 'action', 'status'], name='orders_outb_order_i_44b93f_idx'),
                ],
            },
        ),
    ]
