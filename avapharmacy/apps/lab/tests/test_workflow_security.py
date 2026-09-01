from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.lab.models import (
    LabPartner,
    LaboratoryFacility,
    FacilityLabTest,
    LaboratoryFacilityDocument,
    LabRequest,
    LabResult,
    LabTechnicianProfile,
    LabTest,
)


class LabWorkflowSecurityTests(APITestCase):
    def setUp(self):
        self.admin = self.make_user('admin@example.com', User.ADMIN)
        self.patient = self.make_user('patient@example.com', User.CUSTOMER)
        self.other_patient = self.make_user('other-patient@example.com', User.CUSTOMER)
        self.pharmacist = self.make_user('pharmacist@example.com', User.PHARMACIST)
        self.other_pharmacist = self.make_user('other-pharmacist@example.com', User.PHARMACIST)

        self.partner_user = self.make_user('partner@example.com', User.LAB_PARTNER)
        self.partner = LabPartner.objects.create(
            user=self.partner_user,
            name='Ava Diagnostics',
            email='partner@example.com',
            phone='0700000001',
            status=LabPartner.STATUS_VERIFIED,
        )
        self.other_partner_user = self.make_user('other-partner@example.com', User.LAB_PARTNER)
        self.other_partner = LabPartner.objects.create(
            user=self.other_partner_user,
            name='Other Diagnostics',
            email='other-partner@example.com',
            phone='0700000002',
            status=LabPartner.STATUS_VERIFIED,
        )

        self.technician = self.make_user('tech@example.com', User.LAB_TECHNICIAN)
        self.technician_profile = LabTechnicianProfile.objects.create(
            user=self.technician,
            partner=self.partner,
            name='Assigned Technician',
            email=self.technician.email,
            status=LabTechnicianProfile.STATUS_ACTIVE,
        )
        self.other_technician = self.make_user('other-tech@example.com', User.LAB_TECHNICIAN)
        self.other_technician_profile = LabTechnicianProfile.objects.create(
            user=self.other_technician,
            partner=self.other_partner,
            name='Other Technician',
            email=self.other_technician.email,
            status=LabTechnicianProfile.STATUS_ACTIVE,
        )

        self.test = LabTest.objects.create(
            name='Complete Blood Count',
            category=LabTest.CATEGORY_BLOOD,
            price='1500.00',
            turnaround='24 hours',
            sample_type='Blood',
        )
        self.facility = LaboratoryFacility.objects.create(
            partner=self.partner,
            name='Westlands Laboratory',
            phone='0700000011',
            county='Nairobi',
            address='Westlands, Nairobi',
            license_number='FAC-001',
            supported_counties=['Nairobi'],
            status=LaboratoryFacility.STATUS_VERIFIED,
        )
        self.facility.technicians.add(self.technician_profile)
        FacilityLabTest.objects.create(
            facility=self.facility,
            test=self.test,
            price=self.test.price,
            turnaround=self.test.turnaround,
        )
        self.other_facility = LaboratoryFacility.objects.create(
            partner=self.other_partner,
            name='Other Laboratory',
            phone='0700000012',
            county='Nairobi',
            address='Nairobi',
            license_number='FAC-002',
            status=LaboratoryFacility.STATUS_VERIFIED,
        )
        self.other_facility.technicians.add(self.other_technician_profile)
        FacilityLabTest.objects.create(
            facility=self.other_facility,
            test=self.test,
            price=self.test.price,
            turnaround=self.test.turnaround,
        )
        self.request = LabRequest.objects.create(
            test=self.test,
            patient=self.patient,
            patient_name='Patient One',
            patient_phone='0711111111',
            patient_email=self.patient.email,
            channel=LabRequest.CHANNEL_COLLECTION,
            collection_address='12 Riverside Drive, Nairobi',
            assigned_partner=self.partner,
            laboratory=self.facility,
            assigned_pharmacist=self.pharmacist,
            assigned_technician=self.technician,
            status=LabRequest.STATUS_PROCESSING,
        )

    @staticmethod
    def make_user(email, role):
        return User.objects.create_user(
            email=email,
            password='StrongPass123!',
            first_name='Test',
            last_name=role.replace('_', ' ').title(),
            role=role,
            status=User.STATUS_ACTIVE,
        )

    def authenticate(self, user):
        self.client.force_authenticate(user)

    @staticmethod
    def list_items(response):
        if isinstance(response.data, list):
            return response.data
        return response.data.get('results', response.data.get('data', []))

    @staticmethod
    def error_details(response):
        return response.data.get('error', {}).get('details', response.data)

    def test_home_collection_requires_an_address_and_defaults_to_digital_results(self):
        self.authenticate(self.patient)
        payload = {
            'test': self.test.pk,
            'patient_name': 'Patient One',
            'patient_phone': '0711111111',
            'channel': LabRequest.CHANNEL_COLLECTION,
            'scheduled_at': '2026-09-02T09:00:00+03:00',
        }
        missing_address = self.client.post(reverse('lab-requests'), payload, format='json')
        self.assertEqual(missing_address.status_code, 400)
        self.assertIn('collection_address', self.error_details(missing_address))

        payload['collection_address'] = 'Westlands, Nairobi'
        created = self.client.post(reverse('lab-requests'), payload, format='json')
        self.assertEqual(created.status_code, 201)
        self.assertEqual(created.data['result_delivery_method'], LabRequest.RESULT_DIGITAL)
        self.assertEqual(created.data['collection_address'], 'Westlands, Nairobi')

    def test_patient_and_staff_lists_are_scoped(self):
        unassigned = LabRequest.objects.create(
            test=self.test,
            patient=self.other_patient,
            patient_name='Other Patient',
            patient_phone='0722222222',
        )
        other_partner_request = LabRequest.objects.create(
            test=self.test,
            patient=self.other_patient,
            patient_name='Other Partner Patient',
            patient_phone='0733333333',
            assigned_partner=self.other_partner,
            laboratory=self.other_facility,
            assigned_technician=self.other_technician,
        )

        self.authenticate(self.patient)
        patient_response = self.client.get(reverse('lab-requests'))
        self.assertEqual({item['id'] for item in self.list_items(patient_response)}, {self.request.id})

        self.authenticate(self.technician)
        technician_response = self.client.get(reverse('lab-requests'))
        self.assertEqual({item['id'] for item in self.list_items(technician_response)}, {self.request.id})

        self.authenticate(self.other_technician)
        other_technician_response = self.client.get(reverse('lab-requests'))
        self.assertEqual(
            {item['id'] for item in self.list_items(other_technician_response)},
            {other_partner_request.id},
        )

        self.authenticate(self.other_pharmacist)
        pharmacist_response = self.client.get(reverse('lab-requests'))
        pharmacist_items = self.list_items(pharmacist_response)
        self.assertIn(unassigned.id, {item['id'] for item in pharmacist_items})
        self.assertNotIn(self.request.id, {item['id'] for item in pharmacist_items})

    def test_assignment_requires_verified_matching_partner_and_technician(self):
        self.authenticate(self.admin)
        mismatch = self.client.patch(
            reverse('lab-request-update', args=[self.request.pk]),
            {
                'assigned_partner': self.partner.pk,
                'assigned_technician': self.other_technician.pk,
            },
            format='json',
        )
        self.assertEqual(mismatch.status_code, 400)
        self.assertIn('assigned_technician', self.error_details(mismatch))

        self.request.assigned_pharmacist = None
        self.request.save(update_fields=['assigned_pharmacist'])
        self.authenticate(self.pharmacist)
        assigned = self.client.patch(
            reverse('lab-request-update', args=[self.request.pk]),
            {
                'assigned_pharmacist': self.pharmacist.pk,
                'assigned_partner': self.partner.pk,
            },
            format='json',
        )
        self.assertEqual(assigned.status_code, 200)
        self.assertEqual(assigned.data['assigned_pharmacist'], self.pharmacist.pk)

    def test_invalid_status_transition_is_rejected(self):
        self.authenticate(self.technician)
        response = self.client.patch(
            reverse('lab-request-update', args=[self.request.pk]),
            {'status': LabRequest.STATUS_COMPLETED},
            format='json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('status', self.error_details(response))

    def test_result_access_and_download_are_object_scoped(self):
        result = LabResult.objects.create(
            request=self.request,
            summary='Within reference range.',
            file=SimpleUploadedFile(
                'result.pdf',
                b'%PDF-1.4 test result',
                content_type='application/pdf',
            ),
            filename='result.pdf',
            reviewed_by=self.technician,
        )

        self.authenticate(self.patient)
        own_detail = self.client.get(reverse('lab-result-detail', args=[result.pk]))
        self.assertEqual(own_detail.status_code, 200)
        self.assertNotIn('file', own_detail.data)
        self.assertTrue(own_detail.data['download_url'].endswith(f'/lab/results/{result.pk}/download/'))
        own_download = self.client.get(reverse('lab-result-download', args=[result.pk]))
        self.assertEqual(own_download.status_code, 200)
        self.assertEqual(own_download['Cache-Control'], 'private, no-store')

        self.authenticate(self.pharmacist)
        coordinated_request = self.client.get(reverse('lab-request-detail', args=[self.request.pk]))
        self.assertEqual(coordinated_request.status_code, 200)
        self.assertIsNone(coordinated_request.data['result'])
        self.assertEqual(
            self.client.get(reverse('lab-result-detail', args=[result.pk])).status_code,
            404,
        )

        self.authenticate(self.other_patient)
        self.assertEqual(
            self.client.get(reverse('lab-result-detail', args=[result.pk])).status_code,
            404,
        )
        self.assertEqual(
            self.client.get(reverse('lab-result-download', args=[result.pk])).status_code,
            404,
        )

        self.authenticate(self.other_technician)
        self.assertEqual(
            self.client.get(reverse('lab-result-detail', args=[result.pk])).status_code,
            404,
        )

    def test_only_assigned_technician_can_upload_result(self):
        payload = {
            'summary': 'No abnormal findings.',
            'flags': '["reviewed", "normal"]',
            'is_abnormal': False,
        }
        self.authenticate(self.other_technician)
        denied = self.client.post(
            reverse('lab-result-create', args=[self.request.pk]),
            payload,
            format='multipart',
        )
        self.assertEqual(denied.status_code, 404)

        self.authenticate(self.technician)
        created = self.client.post(
            reverse('lab-result-create', args=[self.request.pk]),
            payload,
            format='multipart',
        )
        self.assertEqual(created.status_code, 201)
        self.assertEqual(created.data['flags'], ['reviewed', 'normal'])
        self.request.refresh_from_db()
        self.assertEqual(self.request.status, LabRequest.STATUS_READY)

    def test_partner_registers_facility_and_admin_verifies_it(self):
        self.authenticate(self.partner_user)
        created = self.client.post(
            reverse('lab-partner-facilities'),
            {
                'name': 'Karen Collection Centre',
                'email': 'karen@example.com',
                'phone': '0712345678',
                'county': 'Nairobi',
                'address': 'Karen Road, Nairobi',
                'license_number': 'FAC-003',
                'supported_counties': ['Kajiado'],
                'home_collection_enabled': True,
                'physical_result_pickup_enabled': True,
                'test_ids': [self.test.pk],
                'test_offerings': [{
                    'test': self.test.pk,
                    'price': '1750.00',
                    'turnaround': '12 hours',
                    'home_collection_available': True,
                }],
                'technician_ids': [self.technician_profile.pk],
            },
            format='json',
        )
        self.assertEqual(created.status_code, 201)
        self.assertEqual(created.data['status'], LaboratoryFacility.STATUS_PENDING)
        self.assertEqual(created.data['supported_counties'], ['Nairobi', 'Kajiado'])
        self.assertEqual(created.data['offerings'][0]['test'], self.test.pk)
        self.assertEqual(created.data['offerings'][0]['price'], '1750.00')

        uploaded = self.client.post(
            reverse('lab-partner-facility-documents', args=[created.data['id']]),
            {
                'name': 'Facility licence',
                'file': SimpleUploadedFile(
                    'facility-licence.pdf',
                    b'%PDF-1.4 facility licence',
                    content_type='application/pdf',
                ),
            },
            format='multipart',
        )
        self.assertEqual(uploaded.status_code, 201)
        self.assertNotIn('file', uploaded.data)

        self.authenticate(self.admin)
        verified = self.client.post(
            reverse('admin-lab-facility-action', args=[created.data['id']]),
            {'action': 'verify'},
            format='json',
        )
        self.assertEqual(verified.status_code, 200)
        self.assertEqual(verified.data['status'], LaboratoryFacility.STATUS_VERIFIED)
        document = LaboratoryFacilityDocument.objects.get(facility_id=created.data['id'])
        document.refresh_from_db()
        self.assertEqual(document.status, LaboratoryFacilityDocument.STATUS_VERIFIED)
        downloaded = self.client.get(reverse('lab-facility-document-download', args=[document.pk]))
        self.assertEqual(downloaded.status_code, 200)
        self.assertEqual(downloaded['Cache-Control'], 'private, no-store')

        self.authenticate(self.partner_user)
        changed = self.client.patch(
            reverse('lab-partner-facility-detail', args=[created.data['id']]),
            {'address': 'Updated Karen Road, Nairobi'},
            format='json',
        )
        self.assertEqual(changed.status_code, 200)
        self.assertEqual(changed.data['status'], LaboratoryFacility.STATUS_PENDING)

    def test_request_assignment_requires_facility_test_and_capability(self):
        unsupported_test = LabTest.objects.create(
            name='Unsupported Test',
            category=LabTest.CATEGORY_WELLNESS,
            price='900.00',
            turnaround='8 hours',
            sample_type='Blood',
        )
        unsupported_request = LabRequest.objects.create(
            test=unsupported_test,
            patient=self.patient,
            patient_name='Patient One',
            patient_phone='0711111111',
            channel=LabRequest.CHANNEL_COLLECTION,
            collection_address='Nairobi',
        )
        self.authenticate(self.admin)
        response = self.client.patch(
            reverse('lab-request-update', args=[unsupported_request.pk]),
            {'laboratory': self.facility.pk},
            format='json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('laboratory', self.error_details(response))

    def test_patient_collection_code_verifies_assigned_collector_and_collects_sample(self):
        collection = LabRequest.objects.create(
            test=self.test,
            patient=self.patient,
            patient_name='Patient One',
            patient_phone='0711111111',
            channel=LabRequest.CHANNEL_COLLECTION,
            collection_address='Nairobi',
            assigned_partner=self.partner,
            laboratory=self.facility,
            assigned_technician=self.technician,
            status=LabRequest.STATUS_AWAITING,
        )
        self.authenticate(self.patient)
        issued = self.client.post(reverse('lab-collection-code', args=[collection.pk]), {}, format='json')
        self.assertEqual(issued.status_code, 200)
        self.assertRegex(issued.data['code'], r'^\d{6}$')

        self.authenticate(self.technician)
        wrong = self.client.post(
            reverse('lab-verify-collection', args=[collection.pk]),
            {'code': '000000'},
            format='json',
        )
        self.assertEqual(wrong.status_code, 400)

        verified = self.client.post(
            reverse('lab-verify-collection', args=[collection.pk]),
            {'code': issued.data['code']},
            format='json',
        )
        self.assertEqual(verified.status_code, 200)
        self.assertEqual(verified.data['status'], LabRequest.STATUS_COLLECTED)
        self.assertIsNotNone(verified.data['collection_verified_at'])
        collection.refresh_from_db()
        self.assertEqual(collection.collection_verified_by, self.technician)
        self.assertEqual(collection.collection_verification_code_hash, '')
