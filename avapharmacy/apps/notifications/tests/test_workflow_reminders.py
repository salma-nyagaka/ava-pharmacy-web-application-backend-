from datetime import date, timedelta
from unittest.mock import patch
from django.test import TestCase
from django.utils import timezone
from apps.accounts.models import User
from apps.notifications.models import Notification
from apps.notifications.tasks import send_clinical_and_stock_reminders
from apps.prescriptions.models import Prescription, PrescriptionItem
from apps.prescriptions.reminders import next_due, schedule_refills
from apps.products.models import Product, Variant, VariantInventory
from avapharmacy.test_compliance_fixtures import prescription_fixture, inventory_fixture, catalogue_fixture


class WorkflowReminderTests(TestCase):
    def setUp(self):
        self.patient = User.objects.create_user(email='reminder@example.com', password='test123', role='customer', status='active')
        self.admin = User.objects.create_user(email='stock@example.com', password='test123', role='admin', status='active')

    def test_monthly_interval_handles_calendar_month_end(self):
        self.assertEqual(next_due(date(2026, 1, 31), 1, 'months'), date(2026, 2, 28))

    def test_refill_reminder_is_sent_once_and_rescheduled(self):
        rx = Prescription.objects.create(patient=self.patient, patient_name='Patient', status='approved', **prescription_fixture())
        item = PrescriptionItem.objects.create(prescription=rx, name='Medicine', is_refill=True, refill_interval=2, refill_unit='days')
        schedule_refills(rx)
        item.refresh_from_db()
        self.assertEqual(item.next_refill_at, timezone.localdate() + timedelta(days=2))
        item.next_refill_at = timezone.localdate()
        item.save()
        send_clinical_and_stock_reminders()
        send_clinical_and_stock_reminders()
        self.assertEqual(Notification.objects.filter(recipient=self.patient, title='Prescription refill reminder').count(), 1)
        item.refresh_from_db()
        self.assertEqual(item.next_refill_at, timezone.localdate() + timedelta(days=2))

    def test_low_inventory_notifies_admin_once_until_restock(self):
        product = Product.objects.create(name='Low stock fixture')
        variant = Variant.objects.create(product=product, name='Low stock variant', price=10, **catalogue_fixture())
        inventory = VariantInventory.objects.create(variant=variant, stock_quantity=2, low_stock_threshold=3, **inventory_fixture())
        self.assertIsNotNone(inventory)
        send_clinical_and_stock_reminders()
        send_clinical_and_stock_reminders()
        self.assertEqual(Notification.objects.filter(recipient=self.admin, title='Low inventory alert').count(), 1)
        VariantInventory.objects.filter(pk=inventory.pk).update(stock_quantity=10)
        send_clinical_and_stock_reminders()
        VariantInventory.objects.filter(pk=inventory.pk).update(stock_quantity=1)
        send_clinical_and_stock_reminders()
        self.assertEqual(Notification.objects.filter(recipient=self.admin, title='Low inventory alert').count(), 2)
