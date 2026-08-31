from decimal import Decimal

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.accounts.models import User
from apps.consultations.models import (
    ClinicianProfile,
    Consultation,
    ConsultationMessage,
    ConsultationPaymentIntent,
)
from apps.notifications.models import Notification


class Command(BaseCommand):
    help = 'Create reusable QA consultations for every active doctor and pediatrician.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--include-inactive',
            action='store_true',
            help='Also create consultations for pending, suspended, or inactive clinicians.',
        )

    def handle(self, *args, **options):
        customer = self._qa_user(
            email='qa.customer@avapharmacy.test',
            first_name='QA',
            last_name='Customer',
            phone='+254790000002',
        )
        guardian = self._qa_user(
            email='qa.guardian@avapharmacy.test',
            first_name='QA',
            last_name='Guardian',
            phone='+254790000003',
        )

        clinicians = ClinicianProfile.objects.filter(
            provider_type__in=[
                ClinicianProfile.TYPE_DOCTOR,
                ClinicianProfile.TYPE_PEDIATRICIAN,
            ],
        ).select_related('user').order_by('provider_type', 'id')
        if not options['include_inactive']:
            clinicians = clinicians.filter(status=ClinicianProfile.STATUS_ACTIVE)

        created = 0
        updated = 0
        for clinician in clinicians:
            was_created = self._seed_consultation(clinician, customer, guardian)
            if was_created:
                created += 1
            else:
                updated += 1

        self.stdout.write(self.style.SUCCESS('Seeded clinician consultations.'))
        self.stdout.write(f'Created: {created}')
        self.stdout.write(f'Updated: {updated}')
        self.stdout.write(
            'Doctor consultations: '
            f'{Consultation.objects.filter(clinician__provider_type=ClinicianProfile.TYPE_DOCTOR).count()}'
        )
        self.stdout.write(
            'Pediatrician consultations: '
            f'{Consultation.objects.filter(clinician__provider_type=ClinicianProfile.TYPE_PEDIATRICIAN).count()}'
        )

    def _qa_user(self, *, email, first_name, last_name, phone):
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
        return user

    def _seed_consultation(self, clinician, customer, guardian):
        is_pediatric = clinician.provider_type == ClinicianProfile.TYPE_PEDIATRICIAN
        patient = guardian if is_pediatric else customer
        issue = f'QA dashboard consultation for {clinician.name}'
        consultation, was_created = Consultation.objects.update_or_create(
            clinician=clinician,
            issue=issue,
            defaults={
                'patient': patient,
                'patient_name': patient.full_name,
                'patient_email': patient.email,
                'patient_phone': patient.phone,
                'patient_age': 7 if is_pediatric else 34,
                'status': Consultation.STATUS_IN_PROGRESS,
                'priority': Consultation.PRIORITY_ROUTINE,
                'is_pediatric': is_pediatric,
                'guardian_name': patient.full_name if is_pediatric else '',
                'child_name': 'QA Child' if is_pediatric else '',
                'child_age': 7 if is_pediatric else None,
                'weight_kg': Decimal('24.50') if is_pediatric else None,
                'consent_status': 'granted' if is_pediatric else 'pending',
                'scheduled_at': timezone.now(),
            },
        )
        ConsultationMessage.objects.get_or_create(
            consultation=consultation,
            sender=patient,
            message='QA patient message: I need help with these symptoms.',
            defaults={'sender_name': patient.full_name, 'message_type': ConsultationMessage.TYPE_TEXT},
        )
        if clinician.user_id:
            ConsultationMessage.objects.get_or_create(
                consultation=consultation,
                sender=clinician.user,
                message='QA clinician reply: I have joined this consultation and will review your symptoms.',
                defaults={'sender_name': clinician.user.full_name, 'message_type': ConsultationMessage.TYPE_TEXT},
            )
            Notification.objects.get_or_create(
                recipient=clinician.user,
                type=Notification.NEW_CONSULTATION,
                title=f'QA consultation assigned to {clinician.name}',
                defaults={
                    'message': f'A QA consultation is available for {clinician.name}.',
                    'data': {
                        'consultation_id': consultation.id,
                        'reference': consultation.reference,
                        'sensitive': True,
                    },
                },
            )

        ConsultationPaymentIntent.objects.update_or_create(
            consultation=consultation,
            defaults={
                'initiated_by': patient,
                'clinician': clinician,
                'provider': ConsultationPaymentIntent.PROVIDER_PAYBILL,
                'status': ConsultationPaymentIntent.STATUS_SUCCEEDED,
                'amount': clinician.consult_fee or Decimal('1.00'),
                'currency': clinician.currency or 'KES',
                'processed_at': timezone.now(),
                'consultation_payload': {'issue': issue},
            },
        )
        return was_created
