from avapharmacy.test_compliance_fixtures import clinician_fixture
from asgiref.sync import async_to_sync
from channels.db import database_sync_to_async
from channels.testing import WebsocketCommunicator
from django.test import TransactionTestCase
from django.urls import re_path
from channels.routing import URLRouter
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import MFACredential, User
from apps.accounts import mfa
from apps.consultations.consumers import ConsultationConsumer
from apps.consultations.models import ClinicianProfile, Consultation


class ConsultationSocketIntegrationTests(TransactionTestCase):
    def setUp(self):
        self.patient = User.objects.create_user(email='socket-patient@example.test', role='customer')
        self.other = User.objects.create_user(email='socket-other@example.test', role='customer')
        self.user = User.objects.create_user(email='socket-doctor@example.test', role='doctor')
        self.provider = ClinicianProfile.objects.create(user=self.user, provider_type='doctor', status='active', name='QA',**clinician_fixture(exclude=('user', 'provider_type', 'status', 'name')))
        self.consultation = Consultation.objects.create(patient=self.patient, clinician=self.provider, patient_name='QA', issue='Synthetic QA')
        self.application = URLRouter([re_path(r'^ws/consultations/(?P<pk>\d+)/$', ConsultationConsumer.as_asgi())])

    def socket(self, user):
        refresh = RefreshToken.for_user(user)
        if mfa.required(user):
            credential, _ = MFACredential.objects.get_or_create(user=user, defaults={'enabled': True, 'version': 'socket-test-version'})
            refresh['mfa_version'] = credential.version
            refresh['amr'] = ['pwd', 'otp']
        token = str(refresh.access_token)
        return WebsocketCommunicator(self.application, f'/ws/consultations/{self.consultation.pk}/?token={token}')

    def test_unrelated_user_and_invalid_token_are_rejected(self):
        other = self.socket(self.other)
        invalid = WebsocketCommunicator(self.application, f'/ws/consultations/{self.consultation.pk}/?token=invalid')
        async def run():
            self.assertEqual(await other.connect(), (False, 4403))
            self.assertEqual(await invalid.connect(), (False, 4401))
            await other.disconnect()
            await invalid.disconnect()
        async_to_sync(run)()

    def test_doctor_password_only_token_is_rejected(self):
        token = str(RefreshToken.for_user(self.user).access_token)
        socket = WebsocketCommunicator(self.application, f'/ws/consultations/{self.consultation.pk}/?token={token}')
        async def run():
            self.assertEqual(await socket.connect(), (False, 4401))
            await socket.disconnect()
        async_to_sync(run)()

    def test_mfa_reset_closes_connected_doctor_socket(self):
        socket = self.socket(self.user)
        async def run():
            self.assertTrue((await socket.connect())[0])
            await database_sync_to_async(MFACredential.objects.filter(user=self.user).delete)()
            await socket.send_json_to({'type': 'typing.indicator'})
            self.assertEqual((await socket.receive_output())['code'], 4403)
            await socket.disconnect()
        async_to_sync(run)()

    def test_participants_receive_live_typing_and_revocation_closes_socket(self):
        patient, provider = self.socket(self.patient), self.socket(self.user)
        async def run():
            self.assertTrue((await patient.connect())[0])
            self.assertTrue((await provider.connect())[0])
            await patient.send_json_to({'type': 'typing.indicator'})
            event = await provider.receive_json_from()
            self.assertEqual(event['type'], 'typing.indicator')
            self.assertEqual(event['payload']['user_id'], self.patient.pk)
            await patient.receive_json_from()
            await database_sync_to_async(ClinicianProfile.objects.filter(pk=self.provider.pk).update)(status='suspended')
            await provider.send_json_to({'type': 'typing.indicator'})
            self.assertEqual((await provider.receive_output())['code'], 4403)
            await patient.disconnect()
            await provider.disconnect()
        async_to_sync(run)()
