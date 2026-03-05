from django.db import migrations


def forwards(apps, schema_editor):
    DoctorProfile = apps.get_model('consultations', 'DoctorProfile')
    DoctorDocument = apps.get_model('consultations', 'DoctorDocument')
    PediatricianProfile = apps.get_model('consultations', 'PediatricianProfile')
    PediatricianDocument = apps.get_model('consultations', 'PediatricianDocument')
    Consultation = apps.get_model('consultations', 'Consultation')
    DoctorPrescription = apps.get_model('consultations', 'DoctorPrescription')
    DoctorEarning = apps.get_model('consultations', 'DoctorEarning')

    pediatrician_rows = list(DoctorProfile.objects.filter(type='pediatrician'))

    for row in pediatrician_rows:
        pediatrician = PediatricianProfile.objects.create(
            reference=row.reference,
            user_id=row.user_id,
            name=row.name,
            specialty=row.specialty,
            email=row.email,
            phone=row.phone,
            license_number=row.license_number,
            license_board=row.license_board,
            license_country=row.license_country,
            license_expiry=row.license_expiry,
            id_number=row.id_number,
            facility=row.facility,
            availability=row.availability,
            bio=row.bio,
            languages=row.languages,
            consult_modes=row.consult_modes,
            years_experience=row.years_experience,
            county=row.county,
            references=row.references,
            document_checklist=row.document_checklist,
            payout_method=row.payout_method,
            payout_account=row.payout_account,
            background_consent=row.background_consent,
            compliance_declaration=row.compliance_declaration,
            agreed_to_terms=row.agreed_to_terms,
            status=row.status,
            status_note=row.status_note,
            rejection_note=row.rejection_note,
            commission=row.commission,
            consult_fee=row.consult_fee,
            rating=row.rating,
            verified_at=row.verified_at,
            submitted_at=row.submitted_at,
            updated_at=row.updated_at,
        )

        for document in DoctorDocument.objects.filter(doctor_id=row.id):
            PediatricianDocument.objects.create(
                pediatrician_id=pediatrician.id,
                name=document.name,
                file=document.file,
                status=document.status,
                note=document.note,
                uploaded_at=document.uploaded_at,
            )

        Consultation.objects.filter(doctor_id=row.id).update(
            pediatrician_id=pediatrician.id,
            doctor_id=None,
            is_pediatric=True,
        )
        DoctorPrescription.objects.filter(doctor_id=row.id).update(
            pediatrician_id=pediatrician.id,
            doctor_id=None,
        )
        DoctorEarning.objects.filter(doctor_id=row.id).update(
            pediatrician_id=pediatrician.id,
            doctor_id=None,
        )

        DoctorDocument.objects.filter(doctor_id=row.id).delete()
        row.delete()


def backwards(apps, schema_editor):
    DoctorProfile = apps.get_model('consultations', 'DoctorProfile')
    DoctorDocument = apps.get_model('consultations', 'DoctorDocument')
    PediatricianProfile = apps.get_model('consultations', 'PediatricianProfile')
    PediatricianDocument = apps.get_model('consultations', 'PediatricianDocument')
    Consultation = apps.get_model('consultations', 'Consultation')
    DoctorPrescription = apps.get_model('consultations', 'DoctorPrescription')
    DoctorEarning = apps.get_model('consultations', 'DoctorEarning')

    pediatricians = list(PediatricianProfile.objects.all())

    for row in pediatricians:
        doctor = DoctorProfile.objects.create(
            reference=row.reference,
            user_id=row.user_id,
            name=row.name,
            type='pediatrician',
            specialty=row.specialty,
            email=row.email,
            phone=row.phone,
            license_number=row.license_number,
            license_board=row.license_board,
            license_country=row.license_country,
            license_expiry=row.license_expiry,
            id_number=row.id_number,
            facility=row.facility,
            availability=row.availability,
            bio=row.bio,
            languages=row.languages,
            consult_modes=row.consult_modes,
            years_experience=row.years_experience,
            county=row.county,
            references=row.references,
            document_checklist=row.document_checklist,
            payout_method=row.payout_method,
            payout_account=row.payout_account,
            background_consent=row.background_consent,
            compliance_declaration=row.compliance_declaration,
            agreed_to_terms=row.agreed_to_terms,
            status=row.status,
            status_note=row.status_note,
            rejection_note=row.rejection_note,
            commission=row.commission,
            consult_fee=row.consult_fee,
            rating=row.rating,
            verified_at=row.verified_at,
            submitted_at=row.submitted_at,
            updated_at=row.updated_at,
        )

        for document in PediatricianDocument.objects.filter(pediatrician_id=row.id):
            DoctorDocument.objects.create(
                doctor_id=doctor.id,
                name=document.name,
                file=document.file,
                status=document.status,
                note=document.note,
                uploaded_at=document.uploaded_at,
            )

        Consultation.objects.filter(pediatrician_id=row.id).update(
            doctor_id=doctor.id,
            pediatrician_id=None,
        )
        DoctorPrescription.objects.filter(pediatrician_id=row.id).update(
            doctor_id=doctor.id,
            pediatrician_id=None,
        )
        DoctorEarning.objects.filter(pediatrician_id=row.id).update(
            doctor_id=doctor.id,
            pediatrician_id=None,
        )

        PediatricianDocument.objects.filter(pediatrician_id=row.id).delete()
        row.delete()


class Migration(migrations.Migration):

    dependencies = [
        ('consultations', '0004_alter_doctorprofile_type_pediatricianprofile_and_more'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
