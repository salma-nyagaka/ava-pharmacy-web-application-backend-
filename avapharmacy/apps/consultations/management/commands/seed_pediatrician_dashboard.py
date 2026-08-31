from decimal import Decimal

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.accounts.models import User
from apps.consultations.models import (
    ClinicianEarning,
    ClinicianPrescription,
    ClinicianProfile,
    Consultation,
    ConsultationMessage,
    ConsultationPaymentIntent,
)
from apps.notifications.models import Notification


class Command(BaseCommand):
    help = 'Seed pediatrician dashboard QA data across queue, messages, consents, prescriptions, profiles, and earnings.'

    def handle(self, *args, **options):
        pediatrician = self._pediatrician()
        families = self._families()

        created_consultations = 0
        updated_consultations = 0
        created_prescriptions = 0
        created_earnings = 0

        cases = [
            {
                'key': 'fever',
                'family': families[0],
                'child_name': 'Amani Otieno',
                'child_age': 3,
                'weight_kg': Decimal('14.20'),
                'issue': 'High fever, reduced appetite, and mild cough since yesterday',
                'status': Consultation.STATUS_WAITING,
                'priority': Consultation.PRIORITY_PRIORITY,
                'consent_status': 'pending',
                'dosage_alert': True,
                'messages': [
                    ('guardian', 'Her temperature reached 39.1 last night and she is not eating well.'),
                    ('clinician', 'Please keep giving fluids and share the last dose of paracetamol, if any.'),
                ],
                'prescriptions': [],
                'earning': None,
            },
            {
                'key': 'wheeze',
                'family': families[1],
                'child_name': 'Baraka Mwangi',
                'child_age': 5,
                'weight_kg': Decimal('18.40'),
                'issue': 'Night cough with wheezing and chest tightness',
                'status': Consultation.STATUS_IN_PROGRESS,
                'priority': Consultation.PRIORITY_PRIORITY,
                'consent_status': 'granted',
                'dosage_alert': False,
                'messages': [
                    ('guardian', 'He coughs more after running and at night.'),
                    ('clinician', 'I am reviewing for wheeze. Please confirm whether he has blue lips or severe breathing difficulty.'),
                    ('guardian', 'No blue lips, but he sounds noisy when breathing out.'),
                ],
                'prescriptions': [
                    {
                        'reference_key': 'wheeze-salbutamol',
                        'status': ClinicianPrescription.STATUS_SENT,
                        'notes': 'Consultation wheeze: Wheeze action plan and inhaler technique counselling.',
                        'items': [
                            {
                                'drug_name': 'Salbutamol inhaler',
                                'dose': '100mcg',
                                'frequency': '2 puffs every 4-6 hours as needed',
                                'duration': '5 days',
                                'quantity': 1,
                                'catalog_fallback': True,
                            },
                            {
                                'drug_name': 'Spacer device',
                                'dose': 'Use with inhaler',
                                'frequency': 'Every inhaler dose',
                                'duration': 'Ongoing',
                                'quantity': 1,
                                'catalog_fallback': True,
                            },
                        ],
                    },
                ],
                'earning': Decimal('1.00'),
            },
            {
                'key': 'eczema',
                'family': families[2],
                'child_name': 'Nia Kamau',
                'child_age': 8,
                'weight_kg': Decimal('25.70'),
                'issue': 'Itchy rash on elbows and behind knees, worse at night',
                'status': Consultation.STATUS_COMPLETED,
                'priority': Consultation.PRIORITY_ROUTINE,
                'consent_status': 'granted',
                'dosage_alert': False,
                'messages': [
                    ('guardian', 'The rash comes and goes. We uploaded a photo earlier.'),
                    ('clinician', 'This looks consistent with eczema flare. Avoid scented soaps and moisturize twice daily.'),
                ],
                'prescriptions': [
                    {
                        'reference_key': 'eczema-care',
                        'status': ClinicianPrescription.STATUS_DISPENSED,
                        'notes': 'Consultation eczema: Emollient therapy and short antihistamine course.',
                        'items': [
                            {
                                'drug_name': 'Cetirizine syrup',
                                'dose': '5ml',
                                'frequency': 'At night',
                                'duration': '5 days',
                                'quantity': 1,
                                'catalog_fallback': True,
                            },
                            {
                                'drug_name': 'Aqueous cream',
                                'dose': 'Apply thin layer',
                                'frequency': 'Twice daily',
                                'duration': '14 days',
                                'quantity': 1,
                                'catalog_fallback': True,
                            },
                        ],
                    },
                ],
                'earning': Decimal('1.00'),
            },
            {
                'key': 'nutrition',
                'family': families[3],
                'child_name': 'Lulu Achieng',
                'child_age': 1,
                'weight_kg': Decimal('8.90'),
                'issue': 'Nutrition follow-up, low appetite after recent diarrhoea',
                'status': Consultation.STATUS_WAITING,
                'priority': Consultation.PRIORITY_ROUTINE,
                'consent_status': 'pending',
                'dosage_alert': False,
                'messages': [
                    ('guardian', 'She is drinking but eating less than usual.'),
                    ('clinician', 'Please share the number of wet diapers today and whether there is vomiting.'),
                ],
                'prescriptions': [
                    {
                        'reference_key': 'nutrition-ors',
                        'status': ClinicianPrescription.STATUS_DRAFT,
                        'notes': 'Consultation nutrition: Draft ORS and zinc plan pending review.',
                        'items': [
                            {
                                'drug_name': 'Oral rehydration salts',
                                'dose': 'Small frequent sips',
                                'frequency': 'After each loose stool',
                                'duration': '3 days',
                                'quantity': 6,
                                'catalog_fallback': True,
                            },
                            {
                                'drug_name': 'Zinc syrup',
                                'dose': '10mg',
                                'frequency': 'Once daily',
                                'duration': '10 days',
                                'quantity': 1,
                                'catalog_fallback': True,
                            },
                        ],
                    },
                ],
                'earning': None,
            },
        ]

        for case in cases:
            consultation, was_created = self._consultation(pediatrician, case)
            if was_created:
                created_consultations += 1
            else:
                updated_consultations += 1
            self._messages(consultation, pediatrician, case)
            self._payment(consultation, pediatrician, case)
            created_prescriptions += self._prescriptions(consultation, pediatrician, case)
            if case['earning'] is not None:
                _, earning_created = ClinicianEarning.objects.get_or_create(
                    clinician=pediatrician,
                    consultation=consultation,
                    description=f"Pediatric consultation fee - {case['child_name']}",
                    defaults={'amount': case['earning']},
                )
                if earning_created:
                    created_earnings += 1

        if pediatrician.user_id:
            Notification.objects.get_or_create(
                recipient=pediatrician.user,
                type=Notification.NEW_CONSULTATION,
                title='Pediatric QA dashboard data ready',
                defaults={
                    'message': 'Dummy pediatric queue, messages, consents, prescriptions, profiles, and earnings have been seeded.',
                    'data': {'pediatrician_id': pediatrician.id, 'reference': pediatrician.reference},
                },
            )

        self.stdout.write(self.style.SUCCESS('Seeded pediatrician dashboard QA data.'))
        self.stdout.write(f'Pediatrician: {pediatrician.name} <{pediatrician.email}>')
        self.stdout.write('Login: qa.pediatrician@avapharmacy.test / AvaQA123!')
        self.stdout.write(f'Consultations created: {created_consultations}')
        self.stdout.write(f'Consultations updated: {updated_consultations}')
        self.stdout.write(f'Prescriptions created: {created_prescriptions}')
        self.stdout.write(f'Earnings created: {created_earnings}')

    def _pediatrician(self):
        user, _ = User.objects.update_or_create(
            email='qa.pediatrician@avapharmacy.test',
            defaults={
                'first_name': 'QA',
                'last_name': 'Pediatrician',
                'phone': '+254790000020',
                'role': User.PEDIATRICIAN,
                'status': User.STATUS_ACTIVE,
                'is_active': True,
            },
        )
        user.set_password('AvaQA123!')
        user.save(update_fields=['password', 'updated_at'])

        profile, _ = ClinicianProfile.objects.update_or_create(
            user=user,
            defaults={
                'provider_type': ClinicianProfile.TYPE_PEDIATRICIAN,
                'name': 'Dr. QA Pediatrician',
                'specialty': 'Pediatrics',
                'email': user.email,
                'phone': user.phone,
                'license_number': 'KMPDC-PED-QA-001',
                'license_board': 'Kenya Medical Practitioners and Dentists Council',
                'facility': 'Ava Pediatric Telehealth',
                'availability': 'Mon-Fri 08:00-17:00',
                'languages': ['English', 'Swahili'],
                'consult_modes': ['Chat'],
                'years_experience': 9,
                'status': ClinicianProfile.STATUS_ACTIVE,
                'is_verified': True,
                'commission': Decimal('15.00'),
                'consult_fee': Decimal('1.00'),
                'rating': Decimal('4.8'),
                'currency': 'KES',
                'background_consent': True,
                'compliance_declaration': True,
                'agreed_to_terms': True,
                'verified_at': timezone.now(),
            },
        )
        return profile

    def _families(self):
        rows = [
            ('qa.guardian.amani@avapharmacy.test', 'Grace', 'Otieno', '+254790000021'),
            ('qa.guardian.baraka@avapharmacy.test', 'Peter', 'Mwangi', '+254790000022'),
            ('qa.guardian.nia@avapharmacy.test', 'Faith', 'Kamau', '+254790000023'),
            ('qa.guardian.lulu@avapharmacy.test', 'Diana', 'Achieng', '+254790000024'),
        ]
        users = []
        for email, first_name, last_name, phone in rows:
            user, _ = User.objects.update_or_create(
                email=email,
                defaults={
                    'first_name': first_name,
                    'last_name': last_name,
                    'phone': phone,
                    'role': User.CUSTOMER,
                    'status': User.STATUS_ACTIVE,
                    'is_active': True,
                },
            )
            if not user.has_usable_password():
                user.set_password('AvaQA123!')
                user.save(update_fields=['password', 'updated_at'])
            users.append(user)
        return users

    def _consultation(self, pediatrician, case):
        patient = case['family']
        consultation, was_created = Consultation.objects.update_or_create(
            clinician=pediatrician,
            issue=case['issue'],
            child_name=case['child_name'],
            defaults={
                'patient': patient,
                'patient_name': patient.full_name,
                'patient_email': patient.email,
                'patient_phone': patient.phone,
                'patient_age': 32,
                'status': case['status'],
                'priority': case['priority'],
                'channel': 'chat',
                'scheduled_at': timezone.now(),
                'is_pediatric': True,
                'guardian_name': patient.full_name,
                'child_age': case['child_age'],
                'weight_kg': case['weight_kg'],
                'consent_status': case['consent_status'],
                'dosage_alert': case['dosage_alert'],
                'last_message_at': timezone.now(),
            },
        )
        return consultation, was_created

    def _messages(self, consultation, pediatrician, case):
        for sender_type, message in case['messages']:
            if sender_type == 'clinician' and pediatrician.user_id:
                sender = pediatrician.user
                sender_name = pediatrician.name
            else:
                sender = consultation.patient
                sender_name = consultation.guardian_name
            ConsultationMessage.objects.get_or_create(
                consultation=consultation,
                message=message,
                defaults={
                    'sender': sender,
                    'sender_name': sender_name,
                    'message_type': ConsultationMessage.TYPE_TEXT,
                },
            )

    def _payment(self, consultation, pediatrician, case):
        ConsultationPaymentIntent.objects.update_or_create(
            consultation=consultation,
            defaults={
                'initiated_by': consultation.patient,
                'clinician': pediatrician,
                'provider': ConsultationPaymentIntent.PROVIDER_PAYBILL,
                'status': ConsultationPaymentIntent.STATUS_SUCCEEDED,
                'amount': pediatrician.consult_fee or Decimal('1.00'),
                'currency': pediatrician.currency or 'KES',
                'phone_number': consultation.patient_phone,
                'processed_at': timezone.now(),
                'consultation_payload': {
                    'issue': case['issue'],
                    'is_pediatric': True,
                    'child_name': case['child_name'],
                    'guardian_name': consultation.guardian_name,
                },
            },
        )

    def _prescriptions(self, consultation, pediatrician, case):
        created = 0
        for prescription in case['prescriptions']:
            _, was_created = ClinicianPrescription.objects.update_or_create(
                clinician=pediatrician,
                consultation=consultation,
                notes=prescription['notes'],
                defaults={
                    'patient_name': case['child_name'],
                    'items': prescription['items'],
                    'status': prescription['status'],
                    'sent_at': timezone.now() if prescription['status'] in {
                        ClinicianPrescription.STATUS_SENT,
                        ClinicianPrescription.STATUS_DISPENSED,
                    } else None,
                    'dispensed_at': timezone.now() if prescription['status'] == ClinicianPrescription.STATUS_DISPENSED else None,
                    'digital_signature': f'{pediatrician.name} / {pediatrician.license_number}',
                },
            )
            if was_created:
                created += 1
        return created
