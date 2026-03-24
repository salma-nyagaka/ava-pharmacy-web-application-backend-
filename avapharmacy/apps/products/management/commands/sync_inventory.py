from django.core.management.base import BaseCommand, CommandError

from apps.products.inventory_sync import sync_inventory_from_remote


class Command(BaseCommand):
    help = 'Pull inventory from the configured external POS/ERP endpoint.'

    def handle(self, *args, **options):
        try:
            results = sync_inventory_from_remote()
        except Exception as exc:
            raise CommandError(str(exc)) from exc

        updated = sum(1 for row in results if row.get('matched'))
        missing = sum(1 for row in results if not row.get('matched'))
        self.stdout.write(self.style.SUCCESS(f'Synced inventory rows: {updated}'))
        if missing:
            self.stdout.write(self.style.WARNING(f'Rows skipped (unmatched products): {missing}'))
