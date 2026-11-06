from django.db import migrations

# Ordinary application credentials must not be able to delete retained records by bulk SQL.
TABLES = {
    ('prescriptions', 'Prescription'): None,
    ('prescriptions', 'PrescriptionFile'): None,
    ('prescriptions', 'PrescriptionAuditLog'): None,
    ('prescriptions', 'PrescriptionReviewDecision'): None,
    ('support', 'MedicineAssessment'): 'created_at',
    ('consultations', 'Consultation'): 'created_at',
    ('consultations', 'ConsultationMessage'): 'sent_at',
    ('consultations', 'ClinicianPrescription'): 'created_at',
    ('consultations', 'ConsultationAuditLog'): 'created_at',
    ('lab', 'LabRequest'): 'requested_at',
    ('lab', 'LabResult'): 'uploaded_at',
    ('lab', 'LabAuditLog'): 'timestamp',
    ('orders', 'Order'): 'created_at',
    ('orders', 'OrderEvent'): 'created_at',
    ('orders', 'DeliveryAudit'): 'recorded_at',
}
APPEND_ONLY = {('prescriptions', 'PrescriptionAuditLog'), ('prescriptions', 'PrescriptionReviewDecision'),
               ('support', 'MedicineAssessment'), ('consultations', 'ConsultationAuditLog'),
               ('lab', 'LabAuditLog'), ('orders', 'OrderEvent'), ('orders', 'DeliveryAudit')}


def install(apps, schema_editor):
    if schema_editor.connection.vendor != 'postgresql':
        return
    schema_editor.execute('''CREATE OR REPLACE FUNCTION ava_clinical_retention() RETURNS trigger AS $$
    BEGIN
      IF TG_OP = 'UPDATE' THEN
        RAISE EXCEPTION 'Clinical audit records are append-only';
      END IF;
      IF TG_ARGV[0] = 'permanent' OR
         (to_jsonb(OLD)->>TG_ARGV[0])::timestamptz >= CURRENT_TIMESTAMP - INTERVAL '1830 days' OR
         COALESCE((to_jsonb(OLD)->>'legal_hold')::boolean, false) THEN
        RAISE EXCEPTION 'Clinical retention prevents deletion';
      END IF;
      RETURN OLD;
    END; $$ LANGUAGE plpgsql''')
    for key, field in TABLES.items():
        table = schema_editor.quote_name(apps.get_model(*key)._meta.db_table)
        event = 'DELETE OR UPDATE' if key in APPEND_ONLY else 'DELETE'
        schema_editor.execute(f"CREATE TRIGGER ava_retention BEFORE {event} ON {table} FOR EACH ROW EXECUTE FUNCTION ava_clinical_retention('{field or 'permanent'}')")


def uninstall(apps, schema_editor):
    if schema_editor.connection.vendor != 'postgresql':
        return
    for key in TABLES:
        table = schema_editor.quote_name(apps.get_model(*key)._meta.db_table)
        schema_editor.execute(f'DROP TRIGGER IF EXISTS ava_retention ON {table}')
    schema_editor.execute('DROP FUNCTION IF EXISTS ava_clinical_retention()')


class Migration(migrations.Migration):
    dependencies = [('support', '0007_medicinerecall_and_more'), ('prescriptions', '0009_prescription_authenticity_evidence_and_more'), ('consultations', '0015_consultationauditlog'), ('lab', '0001_initial')]
    operations = [migrations.RunPython(install, uninstall)]
