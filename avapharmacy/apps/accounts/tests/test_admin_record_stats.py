from datetime import timedelta
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient
from apps.accounts.models import User
from apps.consultations.models import ClinicianProfile
from apps.orders.models import Order
from apps.products.models import Brand, Promotion
from apps.support.models import SupportTicket


class AdminRecordStatsTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(email='stats-admin@example.test', role='admin')
        self.customer = User.objects.create_user(email='stats-customer@example.test', role='customer')
        self.client = APIClient()
        self.client.force_authenticate(self.admin)
        self.endpoint = reverse('admin-record-stats')

    def stats(self, section, **params):
        response = self.client.get(self.endpoint, {'section': section, **params})
        self.assertEqual(response.status_code, 200, response.data)
        return response.data

    def test_user_totals_span_pages_and_ignore_search_status_and_pagination(self):
        User.objects.bulk_create([
            User(email=f'stats-{i}@example.test', role='customer', status='active' if i % 2 == 0 else 'suspended', is_active=i % 2 == 0)
            for i in range(25)
        ])
        User.objects.create_user(email='stats-pharmacist@example.test', role='pharmacist')
        expected = {'total': 26, 'active': 14, 'pending': 0, 'suspended': 12}
        self.assertEqual(self.stats('users', scope='customer'), expected)
        self.assertEqual(self.stats('users', scope='customer', search='no-match', status='suspended', page=9, page_size=1), expected)
        self.assertEqual(self.stats('users')['total'], 28)
        self.assertEqual(self.stats('users', scope='pharmacist')['total'], 1)

    def test_brand_kpis_cover_inactive_records_beyond_twenty(self):
        Brand.objects.bulk_create([Brand(name=f'Stats brand {i}', slug=f'stats-brand-{i}', is_active=i < 23) for i in range(31)])
        self.assertEqual(self.stats('brands', search='none', is_active='true', page_size=1), {'total': 31, 'active': 23, 'inactive': 8})

    def test_order_and_invoice_counts_use_all_records(self):
        for status, payment in [('draft','pending'),('pending','pending'),('shipped','paid'),('delivered','paid')]:
            Order.objects.create(customer=self.customer, status=status, payment_status=payment)
        orders = self.stats('orders', status='pending', page_size=1)
        self.assertEqual((orders['total'], orders['pending'], orders['shipped'], orders['delivered']), (4, 1, 1, 1))
        invoices = self.stats('invoices', search='not-found', page_size=1)
        self.assertEqual((invoices['total'], invoices['paid'], invoices['unpaid']), (3, 2, 1))

    def test_clinician_menu_scope_does_not_accept_table_status_filters(self):
        for provider, status in [('doctor','active'),('doctor','pending'),('pediatrician','pending')]:
            ClinicianProfile.objects.create(name='Synthetic stats clinician', provider_type=provider, status=status)
        doctor = self.stats('doctors', scope='doctor', status='active')
        self.assertEqual((doctor['total'], doctor['active'], doctor['pending']), (2, 1, 1))
        self.assertEqual(self.stats('doctors', scope='pediatrician')['total'], 1)

    def test_support_totals_include_nonvisible_statuses(self):
        SupportTicket.objects.create(customer=self.customer, subject='Synthetic open', status='open', priority='high')
        SupportTicket.objects.create(customer=self.customer, subject='Synthetic resolved', status='resolved')
        counts = self.stats('support', status='open', search='unmatched')
        self.assertEqual((counts['total'], counts['open'], counts['highPriority'], counts['unassigned']), (2, 1, 1, 2))

    def test_deal_totals_ignore_active_table_filter(self):
        today = timezone.localdate()
        for title, status, start, end in [('active','active',today,today),('draft','draft',today,today),('future','active',today+timedelta(days=1),today+timedelta(days=2)),('expired','active',today-timedelta(days=2),today-timedelta(days=1))]:
            Promotion.objects.create(title=title, status=status, start_date=start, end_date=end, value=10, type='percentage', scope='all')
        result = self.stats('deals', status='active')
        self.assertEqual(result, {'total':4,'active':1,'draft':1,'scheduled':1,'expired':1})

    def test_staff_only_and_explicit_scope_validation(self):
        for params in [{'section':'unknown'},{'section':'users','scope':'invalid'},{'section':'doctors','scope':'invalid'}]:
            self.assertEqual(self.client.get(self.endpoint, params).status_code, 400)
        self.client.force_authenticate(self.customer)
        self.assertEqual(self.client.get(self.endpoint, {'section':'users'}).status_code, 403)

    def test_lab_test_totals_cover_every_database_category_record(self):
        from apps.lab.models import LabTest
        LabTest.objects.bulk_create([
            LabTest(name=f'Synthetic lab test {i}', reference=f'STATS-{i}', category='blood' if i < 25 else 'wellness', price='10.00', turnaround='24 hours', sample_type='Blood')
            for i in range(27)
        ])
        self.assertEqual(self.stats('lab_tests', category='blood', page_size=1), {'total': 27, 'category:Blood': 25, 'category:Wellness': 2})
