# Generated for consultation privacy audit logging.

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('consultations', '0014_alter_clinicianprofile_status_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='ConsultationAuditLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('action', models.CharField(choices=[('view_detail', 'View Detail'), ('list_messages', 'List Messages'), ('send_message', 'Send Message'), ('update_status', 'Update Status'), ('end_consultation', 'End Consultation'), ('send_prescription', 'Send Prescription'), ('download_attachment', 'Download Attachment')], max_length=40)),
                ('target_type', models.CharField(blank=True, max_length=60)),
                ('target_id', models.CharField(blank=True, max_length=80)),
                ('ip_address', models.GenericIPAddressField(blank=True, null=True)),
                ('user_agent', models.CharField(blank=True, max_length=255)),
                ('metadata', models.JSONField(blank=True, default=dict)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('actor', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='consultation_audit_logs', to=settings.AUTH_USER_MODEL)),
                ('consultation', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='audit_logs', to='consultations.consultation')),
            ],
            options={
                'ordering': ['-created_at'],
                'indexes': [
                    models.Index(fields=['consultation', '-created_at'], name='consultatio_consult_081484_idx'),
                    models.Index(fields=['actor', '-created_at'], name='consultatio_actor_i_618221_idx'),
                    models.Index(fields=['action', '-created_at'], name='consultatio_action_1ee103_idx'),
                ],
            },
        ),
    ]
