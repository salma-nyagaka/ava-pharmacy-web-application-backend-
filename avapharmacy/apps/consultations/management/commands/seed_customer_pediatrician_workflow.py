import hashlib
from datetime import date
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import Customer, Pharmacist, User
from apps.consultations.models import (
    ChildPatient,
    ClinicianEarning,
    ClinicianPrescription,
    ClinicianProfile,
    Consultation,
    ConsultationMessage,
    ConsultationPaymentIntent,
)
from apps.consultations.views import _clinician_net_earning_amount, _finalize_succeeded_payment_intent
from apps.notifications.utils import create_notification
from apps.prescriptions.models import Prescription, PrescriptionAuditLog, PrescriptionItem
from apps.products.models import Product, Variant, VariantInventory


PASSWORD = 'AvaQA123!'


class Command(BaseCommand):
    help = 'Seed complete QA data for the customer/guardian pediatrician consultation workflow.'

    @transaction.atomic
    def handle(self, *args, **options):
        guardian = self._user(
            email='qa.guardian.pediatric.workflow@avapharmacy.test',
            first_name='Mary',
            last_name='Otieno',
            phone='+254790000110',
            role=User.CUSTOMER,
            address='Kilimani, Nairobi',
        )
        Customer.objects.update_or_create(
            user=guardian,
            defaults={'notes': 'QA guardian with multiple child patients for pediatric workflow testing.'},
        )

        pediatrician_user = self._user(
            email='qa.pediatrician.workflow@avapharmacy.test',
            first_name='Amina',
            last_name='Pediatrician',
            phone='+254790000111',
            role=User.PEDIATRICIAN,
            address='Ava Pediatric Telehealth',
        )
        pharmacist_user = self._user(
            email='qa.pharmacist.pediatric.workflow@avapharmacy.test',
            first_name='Paul',
            last_name='Reviewer',
            phone='+254790000112',
            role=User.PHARMACIST,
            address='Ava Pharmacy Main Branch',
        )
        Pharmacist.objects.update_or_create(
            user=pharmacist_user,
            defaults={
                'license_number': 'QA-PHARM-PED-001',
                'branch_location': 'Main Branch',
                'position': 'Prescription Review Pharmacist',
                'permissions': [
                    Pharmacist.PERMISSION_PRESCRIPTION_REVIEW,
                    Pharmacist.PERMISSION_DISPENSE_ORDERS,
                ],
            },
        )

        pediatrician = self._pediatrician_profile(pediatrician_user)
        child_mika = self._child(
            guardian=guardian,
            first_name='Mika',
            last_name='Otieno',
            date_of_birth=date(2022, 4, 14),
            age_years=4,
            gender=ChildPatient.GENDER_MALE,
            weight_kg=Decimal('16.20'),
            allergies=['Penicillin rash reported by guardian'],
            chronic_conditions=['Mild eczema'],
            current_medications=['Paracetamol syrup PRN'],
            vaccination_notes='Routine immunisations up to date.',
            notes='QA child used for completed paid consultation and prescription handoff.',
        )
        child_zuri = self._child(
            guardian=guardian,
            first_name='Zuri',
            last_name='Otieno',
            date_of_birth=date(2018, 8, 2),
            age_years=8,
            gender=ChildPatient.GENDER_FEMALE,
            weight_kg=Decimal('25.30'),
            allergies=[],
            chronic_conditions=['Seasonal allergic rhinitis'],
            current_medications=['Cetirizine syrup occasionally'],
            vaccination_notes='Guardian unsure about last influenza vaccine.',
            notes='QA child used for active in-progress consultation.',
        )
        product, variant = self._catalog_item()

        completed_consultation = self._paid_consultation(
            guardian=guardian,
            pediatrician=pediatrician,
            child=child_mika,
            issue='Fever up to 38.8 C, reduced appetite, and mild cough since last night.',
            priority=Consultation.PRIORITY_PRIORITY,
            status=Consultation.STATUS_COMPLETED,
            consent_status='granted',
        )
        active_consultation = self._paid_consultation(
            guardian=guardian,
            pediatrician=pediatrician,
            child=child_zuri,
            issue='Sneezing, itchy eyes, and blocked nose for three days. Guardian requests pediatric allergy advice.',
            priority=Consultation.PRIORITY_ROUTINE,
            status=Consultation.STATUS_IN_PROGRESS,
            consent_status='granted',
        )

        self._messages(completed_consultation, pediatrician)
        self._messages(active_consultation, pediatrician)
        clinician_prescription, dispensing_prescription = self._sent_prescription(
            consultation=completed_consultation,
            pediatrician=pediatrician,
            product=product,
            variant=variant,
            pharmacist=pharmacist_user,
        )
        self._earning(completed_consultation, pediatrician)
        self._notifications(
            guardian=guardian,
            pediatrician=pediatrician,
            pharmacist=pharmacist_user,
            consultation=completed_consultation,
            prescription=dispensing_prescription,
        )

        self.stdout.write(self.style.SUCCESS('Seeded complete customer-pediatrician workflow sample records.'))
        self.stdout.write('')
        self.stdout.write('Login accounts:')
        self.stdout.write(f'  Guardian/customer: {guardian.email} / {PASSWORD}')
        self.stdout.write(f'  Pediatrician:      {pediatrician_user.email} / {PASSWORD}')
        self.stdout.write(f'  Pharmacist:        {pharmacist_user.email} / {PASSWORD}')
        self.stdout.write('')
        self.stdout.write('Seeded records:')
        self.stdout.write(f'  Guardian: {guardian.full_name} (id={guardian.id})')
        self.stdout.write(f'  Children: {child_mika.full_name} ({child_mika.reference}), {child_zuri.full_name} ({child_zuri.reference})')
        self.stdout.write(f'  Pediatrician profile: {pediatrician.name} ({pediatrician.reference}, id={pediatrician.id})')
        self.stdout.write(f'  Completed consultation: {completed_consultation.reference} (id={completed_consultation.id})')
        self.stdout.write(f'  Active consultation: {active_consultation.reference} (id={active_consultation.id})')
        self.stdout.write(f'  Clinician prescription: {clinician_prescription.reference} (id={clinician_prescription.id})')
        self.stdout.write(f'  Pharmacy review prescription: {dispensing_prescription.reference} (id={dispensing_prescription.id})')
        self.stdout.write(f'  Pediatric catalog variant: {variant} (id={variant.id})')
        self.stdout.write('')
        self.stdout.write('Useful API checks:')
        self.stdout.write('  GET  /api/guardian/children/')
        self.stdout.write(f'  GET  /api/pediatrician/patients/{child_mika.id}/')
        self.stdout.write('  GET  /api/pediatrician/consultations/')
        self.stdout.write('  GET  /api/pediatrician/catalog/variants/')
        self.stdout.write(f'  POST /api/pediatrician/prescriptions/{clinician_prescription.id}/send/')

    def _user(self, *, email, first_name, last_name, phone, role, address=''):
        user = User.objects.filter(email=email).first()
        defaults = {
            'first_name': first_name,
            'last_name': last_name,
            'phone': phone,
            'role': role,
            'status': User.STATUS_ACTIVE,
            'is_active': True,
            'address': address,
        }
        if user is None:
            user = User.objects.create_user(email=email, password=PASSWORD, **defaults)
        else:
            for field, value in defaults.items():
                setattr(user, field, value)
            user.set_password(PASSWORD)
            user.save()
        return user

    def _pediatrician_profile(self, user):
        profile, _ = ClinicianProfile.objects.update_or_create(
            user=user,
            defaults={
                'provider_type': ClinicianProfile.TYPE_PEDIATRICIAN,
                'name': 'Dr Amina Pediatric Workflow',
                'gender': ClinicianProfile.GENDER_FEMALE,
                'specialty': 'Pediatrics',
                'email': user.email,
                'phone': user.phone,
                'license_number': 'KMPDC-PED-WORKFLOW-001',
                'license_board': 'Kenya Medical Practitioners and Dentists Council',
                'facility': 'Ava Pediatric Telehealth',
                'availability': 'Mon-Fri 08:00-17:00',
                'availability_schedule': [
                    {'day': 'Monday', 'start_time': '08:00', 'end_time': '17:00'},
                    {'day': 'Wednesday', 'start_time': '08:00', 'end_time': '17:00'},
                ],
                'bio': 'QA pediatrician for end-to-end guardian and child workflow testing.',
                'languages': ['English', 'Swahili'],
                'consult_modes': ['chat'],
                'years_experience': 11,
                'county': 'Nairobi',
                'status': ClinicianProfile.STATUS_ACTIVE,
                'is_verified': True,
                'commission': Decimal('15.00'),
                'consult_fee': Decimal('1.00'),
                'rating': Decimal('4.9'),
                'currency': 'KES',
                'background_consent': True,
                'compliance_declaration': True,
                'agreed_to_terms': True,
                'verified_at': timezone.now(),
            },
        )
        return profile

    def _child(self, **kwargs):
        guardian = kwargs.pop('guardian')
        first_name = kwargs.get('first_name')
        last_name = kwargs.get('last_name', '')
        child, _ = ChildPatient.objects.update_or_create(
            guardian=guardian,
            first_name=first_name,
            last_name=last_name,
            defaults=kwargs,
        )
        return child

    def _catalog_item(self):
        product, _ = Product.objects.update_or_create(
            sku='PED-WORKFLOW-AMOX-125',
            defaults={
                'slug': 'pediatric-workflow-amoxicillin-125',
                'name': 'Pediatric Workflow Amoxicillin',
                'is_active': True,
            },
        )
        variant, _ = Variant.objects.update_or_create(
            sku='PED-WORKFLOW-AMOX-125-SUSP',
            defaults={
                'product': product,
                'name': '125mg/5ml suspension',
                'strength': '125mg/5ml',
                'price': Decimal('320.00'),
                'cost_price': Decimal('220.00'),
                'short_description': 'QA pediatric suspension used for prescription workflow testing.',
                'description': 'Seeded product variant for pediatric e-prescription handoff.',
                'dosage_quantity': '5',
                'dosage_unit': 'ml',
                'dosage_frequency': 'three_times_daily',
                'dosage_notes': 'After meals',
                'requires_prescription': True,
                'is_active': True,
            },
        )
        VariantInventory.objects.update_or_create(
            variant=variant,
            location=Product.STOCK_BRANCH,
            batch_number='PED-WORKFLOW-BATCH-001',
            defaults={
                'stock_quantity': 25,
                'low_stock_threshold': 5,
                'status': VariantInventory.STATUS_IN_STOCK,
                'shelf_location': 'QA-PEDS-A1',
            },
        )
        return product, variant

    def _paid_consultation(self, *, guardian, pediatrician, child, issue, priority, status, consent_status):
        existing = Consultation.objects.filter(
            patient=guardian,
            clinician=pediatrician,
            child_patient=child,
            issue=issue,
        ).first()
        if existing is not None:
            existing.status = status
            existing.consent_status = consent_status
            existing.priority = priority
            existing.ended_at = timezone.now() if status == Consultation.STATUS_COMPLETED else None
            existing.save(update_fields=['status', 'consent_status', 'priority', 'ended_at', 'updated_at'])
            return existing

        payload = {
            'pediatrician': pediatrician.id,
            'patient_name': guardian.full_name,
            'patient_email': guardian.email,
            'patient_phone': guardian.phone,
            'patient_age': 34,
            'issue': issue,
            'priority': priority,
            'scheduled_at': timezone.now().isoformat(),
            'is_pediatric': True,
            'child_patient_id': child.id,
            'guardian_name': guardian.full_name,
            'child_name': child.full_name,
            'child_age': child.age_years,
            'weight_kg': str(child.weight_kg or ''),
        }
        intent = ConsultationPaymentIntent.objects.create(
            initiated_by=guardian,
            clinician=pediatrician,
            provider=ConsultationPaymentIntent.PROVIDER_PAYBILL,
            status=ConsultationPaymentIntent.STATUS_SUCCEEDED,
            external_reference=f'CONSULT-{timezone.now().strftime("%Y%m%d%H%M%S")}-{child.id}',
            phone_number=guardian.phone,
            amount=pediatrician.consult_fee,
            currency=pediatrician.currency or 'KES',
            processed_at=timezone.now(),
            consultation_payload=payload,
            callback_payload={
                'BillRefNumber': 'QA-PEDIATRIC-WORKFLOW',
                'TransID': f'QA{child.id}{timezone.now().strftime("%H%M%S")}',
                'TransAmount': str(pediatrician.consult_fee),
                'MSISDN': guardian.phone,
            },
        )
        consultation = _finalize_succeeded_payment_intent(intent)
        consultation.status = status
        consultation.consent_status = consent_status
        consultation.ended_at = timezone.now() if status == Consultation.STATUS_COMPLETED else None
        consultation.save(update_fields=['status', 'consent_status', 'ended_at', 'updated_at'])
        return consultation

    def _messages(self, consultation, pediatrician):
        rows = [
            (consultation.patient, consultation.guardian_name, 'Please review my child. The symptoms started yesterday evening.'),
            (pediatrician.user, pediatrician.name, 'I have reviewed the child profile and will use the weight recorded for dosing.'),
            (consultation.patient, consultation.guardian_name, 'Consent granted. Please send the prescription to Ava Pharmacy if needed.'),
        ]
        for sender, sender_name, message in rows:
            ConsultationMessage.objects.get_or_create(
                consultation=consultation,
                message=message,
                defaults={
                    'sender': sender,
                    'sender_name': sender_name,
                    'message_type': ConsultationMessage.TYPE_TEXT,
                },
            )
        consultation.last_message_at = timezone.now()
        consultation.save(update_fields=['last_message_at', 'updated_at'])

    def _sent_prescription(self, *, consultation, pediatrician, product, variant, pharmacist):
        items = [
            {
                'drug_name': product.name,
                'product_id': product.id,
                'variant_id': variant.id,
                'dose': '5ml',
                'frequency': 'Three times daily',
                'duration': '5 days',
                'quantity': 1,
                'instructions': 'Give after meals. Stop and call clinician if rash or breathing difficulty occurs.',
            },
            {
                'drug_name': 'Paracetamol syrup',
                'dose': '7.5ml',
                'frequency': 'Every 6 hours if fever persists',
                'duration': '2 days',
                'quantity': 1,
                'instructions': 'Do not exceed four doses in 24 hours.',
            },
        ]
        clinician_prescription, _ = ClinicianPrescription.objects.update_or_create(
            clinician=pediatrician,
            consultation=consultation,
            notes='QA pediatric e-prescription. Pharmacist should review before checkout.',
            defaults={
                'patient_name': consultation.child_name,
                'items': items,
                'status': ClinicianPrescription.STATUS_SENT,
                'sent_at': timezone.now(),
                'digital_signature': hashlib.sha256(
                    f'{pediatrician.license_number}:{consultation.reference}'.encode('utf-8')
                ).hexdigest(),
            },
        )
        dispensing_prescription, _ = Prescription.objects.update_or_create(
            clinician_prescription=clinician_prescription,
            defaults={
                'patient': consultation.patient,
                'patient_name': consultation.child_name,
                'doctor_name': pediatrician.name,
                'source': Prescription.SOURCE_E_PRESCRIPTION,
                'status': Prescription.STATUS_PENDING,
                'dispatch_status': Prescription.DISPATCH_NOT_STARTED,
                'notes': clinician_prescription.notes,
                'pharmacist': None,
            },
        )
        dispensing_prescription.items.all().delete()
        for item in items:
            PrescriptionItem.objects.create(
                prescription=dispensing_prescription,
                name=item['drug_name'],
                product_id=item.get('product_id'),
                variant_id=item.get('variant_id'),
                dose=item.get('dose', ''),
                frequency=item.get('frequency', ''),
                quantity=item.get('quantity') or 1,
            )
        PrescriptionAuditLog.objects.get_or_create(
            prescription=dispensing_prescription,
            action='E-prescription submitted for pharmacist review',
            defaults={
                'notes': f'Seeded by {pediatrician.name} from pediatric consultation {consultation.reference}.',
                'performed_by': pediatrician.user,
            },
        )
        create_notification(
            recipient=pharmacist,
            notification_type='prescription_status',
            title=f'E-prescription needs review: {dispensing_prescription.reference}',
            message=f'{pediatrician.name} sent a prescription for {consultation.child_name}. Review it before checkout.',
            data={
                'prescription_id': dispensing_prescription.id,
                'reference': dispensing_prescription.reference,
                'consultation_id': consultation.id,
                'consultation_reference': consultation.reference,
                'is_pediatric': True,
                'child_patient_id': consultation.child_patient_id,
                'sensitive': True,
            },
        )
        return clinician_prescription, dispensing_prescription

    def _earning(self, consultation, pediatrician):
        ClinicianEarning.objects.update_or_create(
            clinician=pediatrician,
            consultation=consultation,
            defaults={
                'amount': _clinician_net_earning_amount(pediatrician),
                'description': f'Pediatric consultation fee - {consultation.child_name}',
            },
        )

    def _notifications(self, *, guardian, pediatrician, pharmacist, consultation, prescription):
        create_notification(
            recipient=guardian,
            notification_type='prescription_status',
            title='New pediatric e-prescription',
            message=f'{pediatrician.name} sent prescription {prescription.reference} for {consultation.child_name}.',
            data={
                'prescription_id': prescription.id,
                'reference': prescription.reference,
                'consultation_id': consultation.id,
                'consultation_reference': consultation.reference,
                'is_pediatric': True,
                'child_patient_id': consultation.child_patient_id,
                'sensitive': True,
            },
        )
        create_notification(
            recipient=pediatrician.user,
            notification_type='consultation',
            title=f'Pediatric workflow seed ready: {consultation.reference}',
            message=f'{consultation.child_name} has a paid consultation, messages, prescription, and pharmacy handoff records.',
            data={
                'consultation_id': consultation.id,
                'consultation_reference': consultation.reference,
                'is_pediatric': True,
                'child_patient_id': consultation.child_patient_id,
            },
        )
        create_notification(
            recipient=pharmacist,
            notification_type='prescription_status',
            title='Pediatric QA pharmacy queue item ready',
            message=f'{prescription.reference} is pending pharmacist review.',
            data={'prescription_id': prescription.id, 'reference': prescription.reference, 'sensitive': True},
        )
