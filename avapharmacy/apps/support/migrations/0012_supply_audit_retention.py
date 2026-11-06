from django.db import migrations


def install(apps, schema_editor):
    if schema_editor.connection.vendor != 'postgresql':
        return
    for name in ['SupplyAllocation', 'ComplianceEvent']:
        table = schema_editor.quote_name(apps.get_model('support', name)._meta.db_table)
        schema_editor.execute(f"CREATE TRIGGER ava_retention BEFORE DELETE OR UPDATE ON {table} FOR EACH ROW EXECUTE FUNCTION ava_clinical_retention('created_at')")


def uninstall(apps, schema_editor):
    if schema_editor.connection.vendor == 'postgresql':
        for name in ['SupplyAllocation', 'ComplianceEvent']:
            table = schema_editor.quote_name(apps.get_model('support', name)._meta.db_table)
            schema_editor.execute(f'DROP TRIGGER IF EXISTS ava_retention ON {table}')


class Migration(migrations.Migration):
    dependencies = [('support', '0011_supplyallocation_complianceevent')]
    operations = [migrations.RunPython(install, uninstall)]
