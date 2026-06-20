from django.db import migrations, models


def backfill_requested_specialty(apps, schema_editor):
    Consultation = apps.get_model('consultations', 'Consultation')
    marker = 'Preferred specialty:'
    for consultation in Consultation.objects.filter(requested_specialty='').iterator():
        issue = consultation.issue or ''
        for line in issue.splitlines():
            if marker.lower() in line.lower():
                specialty = line.split(':', 1)[1].strip()
                if specialty:
                    Consultation.objects.filter(pk=consultation.pk).update(requested_specialty=specialty)
                break


class Migration(migrations.Migration):

    dependencies = [
        ('consultations', '0016_alter_clinicianprofile_user'),
    ]

    operations = [
        migrations.AddField(
            model_name='consultation',
            name='requested_specialty',
            field=models.CharField(blank=True, max_length=200),
        ),
        migrations.AddIndex(
            model_name='consultation',
            index=models.Index(fields=['requested_specialty', 'status'], name='consultatio_request_8d77c7_idx'),
        ),
        migrations.RunPython(backfill_requested_specialty, migrations.RunPython.noop),
    ]
