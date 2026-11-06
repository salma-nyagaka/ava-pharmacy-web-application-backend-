from django.db import migrations


def install(apps, schema_editor):
    if schema_editor.connection.vendor != 'postgresql':
        return
    table = schema_editor.quote_name(apps.get_model('prescriptions', 'PrescriptionVersion')._meta.db_table)
    schema_editor.execute(f"CREATE TRIGGER ava_retention BEFORE DELETE OR UPDATE ON {table} FOR EACH ROW EXECUTE FUNCTION ava_clinical_retention('permanent')")


def uninstall(apps, schema_editor):
    if schema_editor.connection.vendor == 'postgresql':
        table = schema_editor.quote_name(apps.get_model('prescriptions', 'PrescriptionVersion')._meta.db_table)
        schema_editor.execute(f'DROP TRIGGER IF EXISTS ava_retention ON {table}')


class Migration(migrations.Migration):
    dependencies = [('support', '0009_alter_medicineassessment_cart_item'), ('prescriptions', '0010_prescriptionversion')]
    operations = [migrations.RunPython(install, uninstall)]
