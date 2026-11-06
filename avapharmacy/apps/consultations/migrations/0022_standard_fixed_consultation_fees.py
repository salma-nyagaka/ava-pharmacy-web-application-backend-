from django.db import migrations


def set_fixed_fees(apps, schema_editor):
    apps.get_model('consultations', 'ClinicianProfile').objects.all().update(consult_fee=1500, currency='KES')


class Migration(migrations.Migration):
    dependencies = [('consultations', '0021_consultation_agreed_clinician_share_and_more')]
    operations = [migrations.RunPython(set_fixed_fees, migrations.RunPython.noop)]
