from avapharmacy.test_compliance_fixtures import clinician_fixture
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from django.db import connections
from django.test import TransactionTestCase, skipUnlessDBFeature
from rest_framework.exceptions import PermissionDenied

from apps.accounts.models import User
from apps.consultations.models import ClinicianProfile, Consultation
from apps.consultations.views import _assign_consultation_to_provider_if_open


class ConsultationQueueClaimTests(TransactionTestCase):
    @skipUnlessDBFeature('has_select_for_update')
    def test_two_concurrent_doctors_cannot_claim_the_same_open_consultation(self):
        patient = User.objects.create_user(email='claim-patient@example.test', role='customer')
        doctors = []
        for number in [1, 2]:
            user = User.objects.create_user(email=f'claim-doctor-{number}@example.test', role='doctor')
            doctors.append(ClinicianProfile.objects.create(user=user, provider_type='doctor', status='active', name=f'QA Doctor {number}', specialty='General Practice',**clinician_fixture(exclude=('user', 'provider_type', 'status', 'name', 'specialty'))))
        consultation = Consultation.objects.create(patient=patient, patient_name='QA', issue='Synthetic QA', requested_specialty='General Practice')
        barrier = Barrier(2)
        def claim(provider_id):
            try:
                stale = Consultation.objects.get(pk=consultation.pk)
                provider = ClinicianProfile.objects.get(pk=provider_id)
                barrier.wait(timeout=5)
                try:
                    assigned = _assign_consultation_to_provider_if_open(stale, provider)
                    return assigned.clinician_id
                except PermissionDenied:
                    return None
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(claim, [doctor.pk for doctor in doctors]))
        winners = [result for result in outcomes if result is not None]
        self.assertEqual(len(winners), 1)
        consultation.refresh_from_db()
        self.assertEqual(consultation.clinician_id, winners[0])
