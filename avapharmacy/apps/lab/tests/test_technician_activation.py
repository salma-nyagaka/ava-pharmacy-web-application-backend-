import re
from unittest.mock import patch
from django.core import mail
from django.test import override_settings
from django.urls import reverse
from rest_framework.test import APITestCase
from apps.lab.tests import test_workflow_security as fixtures
from apps.lab.models import LabTechnicianProfile, LabRequest
from apps.accounts.models import User


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class TechnicianActivationTests(APITestCase):
    setUp = fixtures.LabWorkflowSecurityTests.setUp
    make_user = staticmethod(fixtures.LabWorkflowSecurityTests.make_user)
    authenticate = fixtures.LabWorkflowSecurityTests.authenticate

    def payload(self):
        return {'name':'Synthetic New Technician', 'email':'new-tech@example.test', 'phone':'0700000988', 'specialty':'QA', 'laboratory':self.facility.pk}

    def test_creation_emails_activation_then_assigned_request_is_accessible(self):
        self.authenticate(self.partner_user)
        result = self.client.post(reverse('lab-partner-techs'), self.payload(), format='json')
        self.assertEqual(result.status_code, 201, result.content)
        technician = LabTechnicianProfile.objects.get(pk=result.data['id'])
        self.assertEqual(result.data['activation_status'], 'pending_activation')
        self.assertFalse(result.data['account_active'])
        self.assertIsNotNone(technician.user_id)
        self.assertFalse(technician.user.is_active)
        self.assertFalse(technician.user.has_usable_password())
        self.assertEqual(technician.user.role, 'lab_technician')
        message = next(item for item in mail.outbox if technician.email in item.to)
        self.assertIn('/labtech/dashboard', message.body)
        token = re.search(r'/activate/([^/\s]+)/', message.body).group(1)
        self.client.force_authenticate(None)
        activated = self.client.post(reverse('professional-activate'), {'token':token, 'new_password':'SyntheticTechPass123!', 'new_password_confirm':'SyntheticTechPass123!', 'accepted_terms':True}, format='json')
        self.assertEqual(activated.status_code, 200, activated.content)
        technician.user.refresh_from_db(); self.assertTrue(technician.user.is_active)
        from apps.lab.serializers import LabTechnicianProfileSerializer
        self.assertEqual(LabTechnicianProfileSerializer(technician).data['activation_status'], 'active')
        request = LabRequest.objects.create(test=self.test, patient=self.patient, patient_name='QA', patient_phone='0700000900', assigned_partner=self.partner, laboratory=self.facility, assigned_technician=technician.user, status='processing')
        self.authenticate(technician.user)
        self.assertEqual(self.client.get(reverse('lab-request-detail', args=[request.pk])).status_code, 200)
        uploaded = self.client.post(reverse('lab-result-create', args=[request.pk]), {'summary':'Synthetic QA result'}, format='multipart')
        self.assertEqual(uploaded.status_code, 201, uploaded.content)
        self.assertEqual(self.client.get(reverse('lab-request-detail', args=[self.request.pk])).status_code, 404)

    def test_existing_email_leaves_no_partial_technician(self):
        User.objects.create_user(email=self.payload()['email'], role='customer')
        self.authenticate(self.partner_user)
        result = self.client.post(reverse('lab-partner-techs'), self.payload(), format='json')
        self.assertEqual(result.status_code, 400)
        self.assertFalse(LabTechnicianProfile.objects.filter(email=self.payload()['email']).exists())

    def test_email_failure_rolls_back_account_and_technician(self):
        self.authenticate(self.partner_user)
        with patch('apps.accounts.serializers.send_pharmacist_activation_email', side_effect=RuntimeError('Synthetic email failure')):
            result = self.client.post(reverse('lab-partner-techs'), self.payload(), format='json')
        self.assertEqual(result.status_code, 500)
        self.assertFalse(User.objects.filter(email=self.payload()['email']).exists())
        self.assertFalse(LabTechnicianProfile.objects.filter(email=self.payload()['email']).exists())
