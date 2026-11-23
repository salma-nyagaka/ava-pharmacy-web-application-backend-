from django.core.management.base import BaseCommand
from apps.notifications.tasks import send_clinical_and_stock_reminders


class Command(BaseCommand):
    help = 'Send due prescription refill reminders and new low inventory alerts.'

    def handle(self, *args, **options):
        self.stdout.write(f'Created {send_clinical_and_stock_reminders()} notifications.')
