"""Explicit fictional credentials for pre-existing business-flow tests only.
Never import this module from application code or use these values to curate live data.
Gap tests intentionally construct incomplete records without these helpers.
"""
from datetime import timedelta
from django.utils import timezone


def reviewer():
    from apps.accounts.models import User
    user = User.objects.get_or_create(email='synthetic-compliance-fixture@example.invalid', defaults={
        'role': 'admin', 'is_active': True, 'status': 'active', 'first_name': 'Synthetic reviewer'})[0]
    grant_clinical_credentials(user)
    return user


def catalogue_fixture(*, medicine=False, exclude=()):
    values = {'regulatory_scope': 'non_medicine'}
    if medicine:
        values = {'regulatory_scope': 'medicine', 'prescription_classification': 'prescription',
            'prescription_review_status': 'verified', 'regulatory_status': 'approved',
            'is_ppb_registered': True, 'ppb_registration_number': 'SYNTHETIC-TEST-NOT-A-LICENCE',
            'authorized_supplier': 'Synthetic supplier', 'ppb_license_expiry_date': timezone.localdate()+timedelta(days=365),
            'pil_version': 'SYNTHETIC v1', 'pil_source_url': 'https://example.invalid/synthetic-pil',
            'pil_reviewed_at': timezone.now(), 'pil_reviewed_by': reviewer(),
            'contraindications': 'Synthetic contraindication', 'side_effects': 'Synthetic adverse effect',
            'directions': 'Synthetic directions', 'warnings': 'Synthetic warning'}
    return {k: v for k, v in values.items() if k not in exclude}


def clinician_fixture(*, exclude=()):
    values = {'is_verified': True, 'license_number': 'SYNTHETIC-TEST-ONLY', 'license_board': 'KMPDC',
              'license_country': 'Kenya', 'license_expiry': timezone.localdate()+timedelta(days=365)}
    return {k: v for k, v in values.items() if k not in exclude}


def prescription_fixture(*, exclude=()):
    values = {'doctor_name': 'Synthetic prescriber', 'prescriber_registration': 'SYNTHETIC-TEST-ONLY',
        'prescriber_verification_reference': 'Synthetic test fixture', 'prescribed_on': timezone.localdate(),
        'valid_until': timezone.localdate()+timedelta(days=30), 'authenticity_method': 'Synthetic test fixture',
        'authenticity_evidence': 'Synthetic test fixture, not real verification', 'verified_by': reviewer(), 'verified_at': timezone.now()}
    return {k: v for k, v in values.items() if k not in exclude}


def prescription_payload():
    return {k: v for k, v in prescription_fixture().items() if k not in {'verified_by', 'verified_at'}}


def delivery_fixture(order, actor=None):
    from apps.orders.models import DeliveryAudit
    return DeliveryAudit.objects.create(order=order, event_type='delivered', recipient_verified=True,
        recipient_name='Synthetic recipient', package_condition='Synthetic intact pack', recorded_by=actor)


def inventory_fixture(*, exclude=()):
    values = {'batch_number': 'SYNTHETIC-TEST-BATCH', 'supplier': 'Synthetic supplier',
              'expiry_date': timezone.localdate()+timedelta(days=365)}
    return {k:v for k,v in values.items() if k not in exclude}


def credential_fixture(*, exclude=(), license_number=None):
    """Fictional current professional evidence for isolated tests, never live curation."""
    import uuid
    from apps.accounts.models import User
    from apps.support.models import ComplianceEvidence
    verifier=User.objects.get_or_create(email='synthetic-independent-verifier@example.invalid', defaults={'role':'admin','is_active':True,'status':'active'})[0]
    number=license_number or ('SYNTHETIC-'+uuid.uuid4().hex[:12])
    evidence=ComplianceEvidence.objects.create(evidence_type='professional_credential',title='SYNTHETIC credential fixture', reference_number=number, external_url='https://example.invalid/synthetic-credential', issued_at=timezone.localdate(),expires_at=timezone.localdate()+timedelta(days=365),status='active',verified_by=verifier,verified_at=timezone.now(),verification_reference='SYNTHETIC fixture, not genuine evidence')
    values={'license_number':number,'license_country':'Kenya','license_board':'PPB','license_expiry':evidence.expires_at,'credential_evidence':evidence,'credential_status':'verified','credential_verified_at':timezone.now(),'credential_verified_by':verifier,'credential_verification_reference':'SYNTHETIC fixture'}
    return {k:v for k,v in values.items() if k not in exclude}


def grant_clinical_credentials(user):
    from apps.accounts.models import Pharmacist
    existing=Pharmacist.objects.filter(user=user).first()
    if existing and existing.credential_is_current:
        return existing
    fields=credential_fixture(license_number=existing.license_number if existing and existing.license_number else None)
    fields['permissions'] = [Pharmacist.PERMISSION_PRESCRIPTION_REVIEW,Pharmacist.PERMISSION_DISPENSE_ORDERS]
    if existing:
        # This explicit fixture bootstrap is test-only. Application APIs cannot set verification stamps.
        Pharmacist.objects.filter(pk=existing.pk).update(**fields)
        return Pharmacist.objects.get(pk=existing.pk)
    return Pharmacist.objects.create(user=user,**fields)
