from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from django.db import connections
from django.test import TransactionTestCase
from django.urls import reverse
from rest_framework.test import APIClient
from apps.payouts.models import Payout, PayoutAuditLog
from . import test_acceptance as fixtures


class PayoutConcurrencyTests(TransactionTestCase):
    setUp=fixtures.PayoutAcceptanceTests.setUp
    payload=fixtures.PayoutAcceptanceTests.payload

    def run_threads(self, jobs):
        barrier=Barrier(len(jobs))
        def work(job):
            connections.close_all()
            client=APIClient();client.force_authenticate(self.checker)
            barrier.wait(timeout=10)
            try:
                path,data=job
                response=client.post(path,data,format='json')
                return response.status_code
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=len(jobs)) as pool:
            return sorted(pool.map(work,jobs))

    def test_concurrent_duplicate_source_has_one_payout(self):
        path=reverse('admin-payouts');payload=self.payload()
        self.assertEqual(self.run_threads([(path,payload),(path,payload)]),[201,409])
        self.assertEqual(Payout.objects.count(),1)

    def test_concurrent_payment_reference_has_one_paid_record(self):
        rows=[Payout.objects.create(recipient=self.doctor,recipient_name='SYNTHETIC QA',role='doctor',period='QA',source_type='manual_adjustment',source_reference=str(i),gross_amount='500',amount='500',status='approved',created_by=self.maker,approved_by=self.checker) for i in range(2)]
        jobs=[(reverse('admin-payout-action',args=[p.pk]),{'action':'mark_paid','payment_reference':'SYNTHETIC-QA-CONCURRENT'}) for p in rows]
        self.assertEqual(self.run_threads(jobs),[200,409])
        self.assertEqual(Payout.objects.filter(status='paid').count(),1)
        self.assertEqual(PayoutAuditLog.objects.filter(action='mark_paid').count(),1)

    def test_cross_field_reference_race_cannot_pay_twice(self):
        rows=[Payout.objects.create(recipient=self.doctor,recipient_name='SYNTHETIC QA',role='doctor',period='QA',source_type='manual_adjustment',source_reference=str(i),gross_amount='500',amount='500',status='approved',created_by=self.maker,approved_by=self.checker) for i in range(2)]
        jobs=[(reverse('admin-payout-action',args=[rows[0].pk]),{'action':'mark_paid','payment_reference':'SYNTHETIC-ONE','provider_transaction_id':'SYNTHETIC-SHARED'}),(reverse('admin-payout-action',args=[rows[1].pk]),{'action':'mark_paid','payment_reference':'SYNTHETIC-SHARED','provider_transaction_id':'SYNTHETIC-TWO'})]
        self.assertEqual(self.run_threads(jobs),[200,409])
        self.assertEqual(Payout.objects.filter(status='paid').count(),1)
