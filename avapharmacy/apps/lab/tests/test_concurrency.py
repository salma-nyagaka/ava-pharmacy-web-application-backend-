from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from django.db import connections
from django.contrib.auth.hashers import make_password
from django.test import TransactionTestCase, skipUnlessDBFeature
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
from rest_framework.test import APIClient
from apps.lab.models import LabRequest, LabAuditLog, LabResult
from . import test_workflow_security as fixtures


class LabConcurrencyTests(TransactionTestCase):
    make_user = staticmethod(fixtures.LabWorkflowSecurityTests.make_user)

    def setUp(self):
        fixtures.LabWorkflowSecurityTests.setUp(self)

    def race(self, path, payload):
        barrier=Barrier(2)
        def call(_):
            try:
                client=APIClient();client.force_authenticate(self.technician)
                barrier.wait(timeout=5)
                return client.post(path,payload,format='json').status_code
            finally:connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:return list(pool.map(call,range(2)))

    @skipUnlessDBFeature('has_select_for_update')
    def test_collection_code_consumed_once_under_concurrency(self):
        self.request.status='awaiting_sample';self.request.collection_verification_code_hash=make_password('123456');self.request.collection_code_expires_at=timezone.now()+timedelta(hours=1);self.request.save()
        self.assertEqual(sorted(self.race(reverse('lab-verify-collection',args=[self.request.pk]),{'code':'123456'})),[200,400])
        self.assertEqual(LabAuditLog.objects.filter(request=self.request,action__startswith='Home collection verified').count(),1)

    @skipUnlessDBFeature('has_select_for_update')
    def test_result_published_once_under_concurrency(self):
        barrier=Barrier(2)
        def upload(_):
            try:
                client=APIClient();client.force_authenticate(self.technician)
                barrier.wait(timeout=5)
                return client.post(reverse('lab-result-create',args=[self.request.pk]),{'summary':'SYNTHETIC QA structured result'},format='multipart').status_code
            finally:connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:outcomes=list(pool.map(upload,range(2)))
        self.assertEqual(sorted(outcomes),[201,400])
        self.assertEqual(LabResult.objects.filter(request=self.request).count(),1)
