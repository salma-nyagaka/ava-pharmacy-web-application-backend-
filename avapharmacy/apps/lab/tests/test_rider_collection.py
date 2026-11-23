from datetime import timedelta
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase
from apps.lab.models import LabRequest, LabAuditLog
from .test_workflow_security import LabWorkflowSecurityTests


class RiderCollectionTests(APITestCase):
    setUp = LabWorkflowSecurityTests.setUp
    make_user = staticmethod(LabWorkflowSecurityTests.make_user)
    authenticate = LabWorkflowSecurityTests.authenticate

    def collection(self):
        return LabRequest.objects.create(test=self.test, patient=self.patient, patient_name='Patient', patient_phone='0700000000', channel='collection', collection_address='Test address', assigned_partner=self.partner, laboratory=self.facility)

    def dispatch(self, request):
        self.authenticate(self.admin)
        return self.client.post(reverse('admin-lab-rider-dispatched', args=[request.pk]), {}, format='json')

    def test_admin_dispatch_patient_code_admin_collection_without_technician(self):
        request = self.collection()
        self.authenticate(self.patient)
        self.assertEqual(self.client.post(reverse('lab-collection-code', args=[request.pk]), {}, format='json').status_code, 400)
        self.assertEqual(self.dispatch(request).status_code, 200)
        self.assertEqual(self.dispatch(request).status_code, 200)
        self.assertEqual(LabAuditLog.objects.filter(request=request, action='Rider dispatched for home sample collection').count(), 1)
        self.authenticate(self.patient)
        issued = self.client.post(reverse('lab-collection-code', args=[request.pk]), {}, format='json')
        self.assertEqual(issued.status_code, 200)
        self.authenticate(self.admin)
        verified = self.client.post(reverse('lab-verify-collection', args=[request.pk]), {'code': issued.data['code']}, format='json')
        self.assertEqual(verified.status_code, 200)
        request.refresh_from_db()
        self.assertEqual(request.status, 'sample_collected')
        self.assertEqual(request.collection_verified_by, self.admin)
        self.assertIsNone(request.assigned_technician_id)
        self.assertEqual(self.client.post(reverse('lab-verify-collection', args=[request.pk]), {'code': issued.data['code']}, format='json').status_code, 400)

    def test_only_admin_can_dispatch_or_verify(self):
        request = self.collection()
        for user in [self.patient, self.partner_user, self.technician]:
            self.authenticate(user)
            self.assertEqual(self.client.post(reverse('admin-lab-rider-dispatched', args=[request.pk]), {}, format='json').status_code, 403)
            self.assertEqual(self.client.post(reverse('lab-verify-collection', args=[request.pk]), {'code': '123456'}, format='json').status_code, 403)

    def test_expired_and_incorrect_codes_do_not_collect(self):
        request = self.collection()
        self.dispatch(request)
        self.authenticate(self.patient)
        issued = self.client.post(reverse('lab-collection-code', args=[request.pk]), {}, format='json')
        self.authenticate(self.admin)
        wrong = '000000' if issued.data['code'] != '000000' else '111111'
        self.assertEqual(self.client.post(reverse('lab-verify-collection', args=[request.pk]), {'code': wrong}, format='json').status_code, 400)
        request.refresh_from_db()
        self.assertEqual(request.collection_verification_attempts, 1)
        request.collection_code_expires_at = timezone.now() - timedelta(seconds=1)
        request.save()
        self.assertEqual(self.client.post(reverse('lab-verify-collection', args=[request.pk]), {'code': issued.data['code']}, format='json').status_code, 400)
        request.refresh_from_db()
        self.assertEqual(request.status, 'awaiting_sample')

    def test_partner_and_technician_assigned_together(self):
        request = self.collection()
        request.assigned_partner = None
        request.laboratory = None
        request.save()
        self.authenticate(self.admin)
        self.assertEqual(self.client.patch(reverse('lab-request-update', args=[request.pk]), {'assigned_partner': self.partner.pk}, format='json').status_code, 400)
        response = self.client.patch(reverse('lab-request-update', args=[request.pk]), {'assigned_partner': self.partner.pk, 'assigned_technician': self.technician.pk}, format='json')
        self.assertEqual(response.status_code, 200)
        request.refresh_from_db()
        self.assertEqual(request.assigned_partner, self.partner)
        self.assertEqual(request.assigned_technician, self.technician)
        self.assertIsNone(request.laboratory)
        self.authenticate(self.partner_user)
        response = self.client.patch(reverse('lab-request-update', args=[request.pk]), {'laboratory': self.facility.pk}, format='json')
        self.assertEqual(response.status_code, 200)
        request.refresh_from_db()
        self.assertEqual(request.assigned_technician, self.technician)

    def test_cross_partner_technician_rejected(self):
        request = self.collection()
        self.authenticate(self.admin)
        self.assertEqual(self.client.patch(reverse('lab-request-update', args=[request.pk]), {'assigned_partner': self.partner.pk, 'assigned_technician': self.other_technician.pk}, format='json').status_code, 400)

    def test_partner_can_assign_collected_sample_before_processing(self):
        request = self.collection()
        request.status = 'sample_collected'
        request.samples_sent_at = timezone.now()
        request.save()
        self.authenticate(self.partner_user)
        self.assertEqual(self.client.patch(reverse('lab-request-update', args=[request.pk]), {'assigned_technician': self.technician.pk}, format='json').status_code, 200)
        request.refresh_from_db()
        self.assertEqual(request.assigned_technician, self.technician)
        request.status = 'processing'
        request.save()
        self.assertEqual(self.client.patch(reverse('lab-request-update', args=[request.pk]), {'assigned_technician': None}, format='json').status_code, 400)

    def test_sample_dispatch_receipt_processing_progress_visible_to_patient(self):
        request = self.collection()
        request.status = 'sample_collected'
        request.assigned_technician = self.technician
        request.save()
        self.authenticate(self.partner_user)
        self.assertEqual(self.client.post(reverse('lab-samples-received', args=[request.pk]), {}, format='json').status_code, 400)
        self.authenticate(self.admin)
        sent = self.client.post(reverse('admin-lab-samples-sent', args=[request.pk]), {}, format='json')
        self.assertEqual(sent.status_code, 200)
        self.assertEqual(sent.data['status'], 'samples_sent')
        self.authenticate(self.patient)
        self.assertEqual(self.client.get(reverse('lab-request-detail', args=[request.pk])).data['status'], 'samples_sent')
        self.authenticate(self.technician)
        self.assertEqual(self.client.get(reverse('lab-request-detail', args=[request.pk])).data['status'], 'samples_sent')
        self.assertEqual(self.client.patch(reverse('lab-request-update', args=[request.pk]), {'status': 'processing'}, format='json').status_code, 400)
        self.authenticate(self.partner_user)
        received = self.client.post(reverse('lab-samples-received', args=[request.pk]), {}, format='json')
        self.assertEqual(received.status_code, 200)
        self.assertEqual(received.data['status'], 'sample_received')
        self.assertIsNotNone(received.data['samples_received_at'])
        self.assertEqual(self.client.post(reverse('lab-samples-received', args=[request.pk]), {}, format='json').status_code, 200)
        self.assertEqual(LabAuditLog.objects.filter(request=request, action__startswith='Samples received at').count(), 1)
        self.authenticate(self.patient)
        self.assertEqual(self.client.get(reverse('lab-request-detail', args=[request.pk])).data['status'], 'sample_received')
        self.authenticate(self.admin)
        self.assertEqual(self.client.patch(reverse('lab-request-update', args=[request.pk]), {'status': 'processing'}, format='json').status_code, 403)
        self.authenticate(self.technician)
        processing = self.client.patch(reverse('lab-request-update', args=[request.pk]), {'status': 'processing'}, format='json')
        self.assertEqual(processing.status_code, 200)
        self.assertEqual(processing.data['status'], 'processing')
        self.authenticate(self.patient)
        self.assertEqual(self.client.get(reverse('lab-request-detail', args=[request.pk])).data['status'], 'processing')

    def test_receipt_only_by_assigned_partner(self):
        request = self.collection()
        request.status = 'samples_sent'
        request.samples_sent_at = timezone.now()
        request.save()
        for user, expected in [(self.patient, 403), (self.technician, 403), (self.admin, 403), (self.other_partner_user, 404)]:
            self.authenticate(user)
            self.assertEqual(self.client.post(reverse('lab-samples-received', args=[request.pk]), {}, format='json').status_code, expected)
