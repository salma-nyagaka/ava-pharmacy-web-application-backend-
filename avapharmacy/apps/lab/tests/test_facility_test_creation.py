from rest_framework.test import APITestCase
from django.urls import reverse
from apps.lab.tests import test_workflow_security as fixtures
from apps.lab.models import LabTest, FacilityLabTest


class FacilityTestCreationTests(APITestCase):
    setUp = fixtures.LabWorkflowSecurityTests.setUp
    make_user = staticmethod(fixtures.LabWorkflowSecurityTests.make_user)
    authenticate = fixtures.LabWorkflowSecurityTests.authenticate

    def payload(self):
        return {'name': 'SYNTHETIC Facility Test', 'category': 'blood', 'price': '2500.50', 'turnaround': '48 hours', 'sample_type': 'Blood', 'description': 'QA only'}

    def test_new_test_belongs_only_to_selected_laboratory(self):
        self.authenticate(self.admin)
        response = self.client.post(reverse('admin-lab-facility-tests', args=[self.facility.pk]), self.payload(), format='json')
        self.assertEqual(response.status_code, 201, response.content)
        test = LabTest.objects.get(name='SYNTHETIC Facility Test')
        offering = FacilityLabTest.objects.get(test=test)
        self.assertEqual(offering.facility_id, self.facility.pk)
        self.assertEqual(str(offering.price), '2500.50')
        self.assertEqual(offering.turnaround, '48 hours')
        self.assertFalse(FacilityLabTest.objects.filter(test=test, facility=self.other_facility).exists())
        self.assertIn(test.pk, [row['test'] for row in response.data['offerings']])

    def test_unapproved_laboratory_and_invalid_price_create_no_orphan(self):
        self.authenticate(self.admin)
        url = reverse('admin-lab-facility-tests', args=[self.facility.pk])
        count = LabTest.objects.count()
        self.facility.status = 'pending'; self.facility.save()
        self.assertEqual(self.client.post(url, self.payload(), format='json').status_code, 400)
        self.facility.status = 'verified'; self.facility.save()
        self.assertEqual(self.client.post(url, {**self.payload(), 'price': '0'}, format='json').status_code, 400)
        self.assertEqual(LabTest.objects.count(), count)

    def test_partner_cannot_use_admin_creation_endpoint(self):
        self.authenticate(self.partner_user)
        self.assertEqual(self.client.post(reverse('admin-lab-facility-tests', args=[self.facility.pk]), self.payload(), format='json').status_code, 403)

    def test_verified_partner_can_configure_tests_not_yet_publicly_offered(self):
        test = LabTest.objects.create(name='SYNTHETIC Unlisted Definition', price='1200', turnaround='24 hours', sample_type='Blood')
        self.authenticate(self.partner_user)
        result = self.client.get(reverse('lab-partner-test-catalogue'))
        self.assertEqual(result.status_code, 200, result.content)
        self.assertIn(test.pk, [row['id'] for row in result.data])
        self.authenticate(self.patient)
        self.assertEqual(self.client.get(reverse('lab-partner-test-catalogue')).status_code, 403)
        self.authenticate(self.partner_user)
        self.partner.status = 'suspended'; self.partner.save()
        self.assertEqual(self.client.get(reverse('lab-partner-test-catalogue')).status_code, 403)

    def test_partner_publishes_clinician_orders_then_partner_assigns_lab(self):
        self.authenticate(self.partner_user)
        created = self.client.post(reverse('lab-partner-facility-tests', args=[self.facility.pk]), self.payload(), format='json')
        self.assertEqual(created.status_code, 201, created.content)
        self.facility.refresh_from_db()
        self.assertEqual(self.facility.status, 'verified')
        test = LabTest.objects.get(name='SYNTHETIC Facility Test')
        test.price = '9999.00'; test.save()  # Booking must use this lab's offering price.
        self.authenticate(self.patient)
        public = self.client.get(reverse('lab-tests'))
        rows = public.data.get('results', []) if isinstance(public.data, dict) else public.data
        listed = next(row for row in rows if row['id'] == test.pk)
        self.assertEqual(listed['laboratories'][0]['id'], self.facility.pk)
        doctor, consultation = fixtures.ordering_consultation(self)
        self.authenticate(doctor)
        booking = self.client.post(reverse('lab-requests'), {'test': test.pk, 'consultation':consultation.pk, 'assigned_partner':self.partner.pk, 'patient_name': 'QA Patient', 'patient_phone': '0700000900', 'channel': 'walk_in'}, format='json')
        self.assertEqual(booking.status_code, 201, booking.content)
        from apps.lab.models import LabRequest
        saved = LabRequest.objects.get(pk=booking.data['id'])
        self.assertIsNone(saved.laboratory_id)
        self.assertEqual(saved.assigned_partner_id, self.partner.pk)
        self.authenticate(self.partner_user)
        self.assertEqual(self.client.get(reverse('lab-request-detail', args=[saved.pk])).status_code, 200)
        self.authenticate(self.pharmacist)
        self.assertEqual(self.client.patch(reverse('lab-request-update', args=[saved.pk]), {'laboratory': self.facility.pk}, format='json').status_code, 403)
        self.authenticate(self.admin)
        assignment = self.client.patch(reverse('lab-request-update', args=[saved.pk]), {'assigned_partner': self.partner.pk}, format='json')
        self.assertEqual(assignment.status_code, 200, assignment.content)
        saved.refresh_from_db()
        self.assertIsNone(saved.laboratory_id)
        self.authenticate(self.partner_user)
        chosen = self.client.patch(reverse('lab-request-update', args=[saved.pk]), {'laboratory': self.facility.pk}, format='json')
        self.assertEqual(chosen.status_code, 200, chosen.content)
        saved.refresh_from_db()
        self.assertEqual(saved.laboratory_id, self.facility.pk)
        from apps.notifications.models import Notification
        self.assertTrue(Notification.objects.filter(recipient=self.admin, data__url=f'/admin/lab-partners?view=requests&request={saved.pk}').exists())
        self.assertEqual(saved.assigned_partner_id, self.partner.pk)
        self.assertEqual(str(saved.quoted_test_price), '2500.50')
        from apps.notifications.models import Notification
        self.assertTrue(Notification.objects.filter(recipient=self.partner_user, data__request_id=saved.pk).exists())
        self.authenticate(self.partner_user)
        self.assertEqual(self.client.get(reverse('lab-request-detail', args=[saved.pk])).status_code, 200)
        self.authenticate(self.other_partner_user)
        self.assertEqual(self.client.get(reverse('lab-request-detail', args=[saved.pk])).status_code, 404)


    def test_partner_cannot_publish_for_another_partner_or_an_unverified_lab(self):
        self.authenticate(self.partner_user)
        count = LabTest.objects.count()
        result = self.client.post(reverse('lab-partner-facility-tests', args=[self.other_facility.pk]), self.payload(), format='json')
        self.assertEqual(result.status_code, 404)
        self.facility.status = 'pending'; self.facility.save()
        result = self.client.post(reverse('lab-partner-facility-tests', args=[self.facility.pk]), self.payload(), format='json')
        self.assertEqual(result.status_code, 400)
        self.assertEqual(LabTest.objects.count(), count)

    def test_catalogue_updates_stay_live_but_identity_changes_require_review(self):
        self.authenticate(self.partner_user)
        url = reverse('lab-partner-facility-detail', args=[self.facility.pk])
        response = self.client.patch(url, {'test_ids': [self.test.pk], 'test_offerings': [{'test': self.test.pk, 'price': '2200.00', 'turnaround': '12 hours'}]}, format='json')
        self.assertEqual(response.status_code, 200, response.content)
        self.facility.refresh_from_db(); self.assertEqual(self.facility.status, 'verified')
        response = self.client.patch(url, {'address': 'Different QA branch'}, format='json')
        self.assertEqual(response.status_code, 200)
        self.facility.refresh_from_db(); self.assertEqual(self.facility.status, 'pending')

    def test_customer_cannot_book_test_at_a_lab_that_does_not_offer_it(self):
        self.authenticate(self.partner_user)
        self.client.post(reverse('lab-partner-facility-tests', args=[self.facility.pk]), self.payload(), format='json')
        test = LabTest.objects.get(name='SYNTHETIC Facility Test')
        self.authenticate(self.patient)
        doctor, consultation = fixtures.ordering_consultation(self)
        self.authenticate(doctor)
        result = self.client.post(reverse('lab-requests'), {'test': test.pk, 'consultation':consultation.pk, 'assigned_partner':self.partner.pk, 'laboratory': self.other_facility.pk, 'patient_name': 'QA', 'patient_phone': '0700000900', 'channel': 'walk_in'}, format='json')
        self.assertEqual(result.status_code, 400)

    def test_admin_dispatch_requires_partner_lab_selection_and_is_recorded_once(self):
        from apps.lab.models import LabRequest
        request = LabRequest.objects.create(test=self.test, patient=self.patient, patient_name='Synthetic QA', patient_phone='0700000900', channel='walk_in', assigned_partner=self.partner, status='sample_collected')
        url = reverse('admin-lab-samples-sent', args=[request.pk])
        self.authenticate(self.admin)
        self.assertEqual(self.client.post(url).status_code, 400)
        self.authenticate(self.partner_user)
        wrong = self.client.patch(reverse('lab-request-update', args=[request.pk]), {'laboratory': self.other_facility.pk}, format='json')
        self.assertEqual(wrong.status_code, 400)
        selected = self.client.patch(reverse('lab-request-update', args=[request.pk]), {'laboratory': self.facility.pk}, format='json')
        self.assertEqual(selected.status_code, 200, selected.content)
        self.assertEqual(self.client.post(url).status_code, 403)
        self.authenticate(self.admin)
        premature = self.client.patch(reverse('lab-request-update', args=[request.pk]), {'status':'processing'}, format='json')
        self.assertEqual(premature.status_code, 403)
        sent = self.client.post(url)
        self.assertEqual(sent.status_code, 200, sent.content)
        self.assertIsNotNone(sent.data['samples_sent_at'])
        self.assertEqual(self.client.post(url).status_code, 409)
        self.authenticate(self.partner_user)
        self.assertEqual(self.client.patch(reverse('lab-request-update', args=[request.pk]), {'laboratory': None}, format='json').status_code, 400)

    def test_partner_adds_technician_directly_to_its_laboratory(self):
        from apps.lab.models import LabTechnicianProfile
        self.authenticate(self.partner_user)
        data = {'name':'Synthetic Lab Team', 'email':'lab-team@example.test', 'phone':'0700000991', 'specialty':'QA', 'laboratory':self.facility.pk}
        result = self.client.post(reverse('lab-partner-techs'), data, format='json')
        self.assertEqual(result.status_code, 201, result.content)
        technician = LabTechnicianProfile.objects.get(pk=result.data['id'])
        self.assertEqual(technician.partner_id, self.partner.pk)
        self.assertTrue(self.facility.technicians.filter(pk=technician.pk).exists())
        self.assertFalse(self.other_facility.technicians.filter(pk=technician.pk).exists())
        result = self.client.post(reverse('lab-partner-techs'), {**data, 'email':'wrong-lab-team@example.test', 'phone':'0700000992', 'laboratory':self.other_facility.pk}, format='json')
        self.assertEqual(result.status_code, 400)
        self.assertFalse(LabTechnicianProfile.objects.filter(email='wrong-lab-team@example.test').exists())
