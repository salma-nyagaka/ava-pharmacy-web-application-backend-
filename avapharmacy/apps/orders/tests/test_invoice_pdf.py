from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from apps.accounts.models import User
from apps.orders.models import Order, OrderItem


class InvoicePDFTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(email='invoice-owner@example.test')
        self.other = User.objects.create_user(email='invoice-other@example.test')
        self.admin = User.objects.create_user(email='invoice-admin@example.test', role='admin')
        self.order = Order.objects.create(customer=self.owner, subtotal='3575.00', total='3575.00', payment_status='paid')
        OrderItem.objects.create(order=self.order, product_name='A long product name with <br> & special text ' * 3, quantity=1, unit_price='3575.00')
        self.url = reverse('order-invoice-pdf', args=[self.order.pk])
        self.client = APIClient()

    def test_owner_downloads_a_real_pdf_attachment(self):
        self.client.force_authenticate(self.owner)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertTrue(response.content.startswith(b'%PDF-'))
        self.assertIn('.pdf', response['Content-Disposition'])
        self.assertIn('no-store', response['Cache-Control'])

    def test_other_customer_cannot_download_invoice(self):
        self.client.force_authenticate(self.other)
        self.assertEqual(self.client.get(self.url).status_code, 404)

    def test_admin_can_download_invoice(self):
        self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.get(self.url).status_code, 200)

    def test_anonymous_access_is_denied(self):
        self.assertEqual(self.client.get(self.url).status_code, 401)
