from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('prescriptions', '0005_prescriptionclarificationmessage'),
    ]

    operations = [
        migrations.CreateModel(
            name='PrescriptionReviewDecision',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('action', models.CharField(choices=[('approve', 'Approve'), ('reject', 'Reject'), ('request_clarification', 'Request Clarification')], max_length=30)),
                ('from_status', models.CharField(choices=[('pending', 'Pending'), ('approved', 'Approved'), ('clarification', 'Clarification Required'), ('rejected', 'Rejected')], max_length=20)),
                ('to_status', models.CharField(choices=[('pending', 'Pending'), ('approved', 'Approved'), ('clarification', 'Clarification Required'), ('rejected', 'Rejected')], max_length=20)),
                ('notes', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('pharmacist', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='prescription_review_decisions', to=settings.AUTH_USER_MODEL)),
                ('prescription', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='review_decisions', to='prescriptions.prescription')),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='prescriptionreviewdecision',
            index=models.Index(fields=['prescription', '-created_at'], name='rxrev_rx_created_idx'),
        ),
        migrations.AddIndex(
            model_name='prescriptionreviewdecision',
            index=models.Index(fields=['pharmacist', '-created_at'], name='rxrev_pharm_created_idx'),
        ),
        migrations.AddIndex(
            model_name='prescriptionreviewdecision',
            index=models.Index(fields=['action', '-created_at'], name='rxrev_action_created_idx'),
        ),
    ]
