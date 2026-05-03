from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.accounts.models import User
from apps.products.models import Brand, Category, HealthConcern, Product, StockMovement, Subcategory


class Command(BaseCommand):
    help = "Backfill missing created_by and updated_by product audit fields with an admin user."

    def add_arguments(self, parser):
        parser.add_argument(
            "--user-id",
            type=int,
            help="Admin user ID to use for the backfill. Defaults to the first admin user.",
        )

    def handle(self, *args, **options):
        user_id = options.get("user_id")
        if user_id is not None:
            admin_user = User.objects.filter(id=user_id, role=User.ADMIN).first()
            if admin_user is None:
                raise CommandError(f"No admin user found with id={user_id}.")
        else:
            admin_user = User.objects.filter(role=User.ADMIN).order_by("id").first()
            if admin_user is None:
                raise CommandError("No admin user found to use for the backfill.")

        model_map = [
            ("Category", Category),
            ("Subcategory", Subcategory),
            ("HealthConcern", HealthConcern),
            ("Brand", Brand),
            ("Product", Product),
            ("StockMovement", StockMovement),
        ]

        summary = {}
        with transaction.atomic():
            for label, model in model_map:
                created_count = model.objects.filter(created_by__isnull=True).update(created_by=admin_user)
                updated_count = model.objects.filter(updated_by__isnull=True).update(updated_by=admin_user)
                summary[label] = {
                    "created_by_filled": created_count,
                    "updated_by_filled": updated_count,
                }

        self.stdout.write(
            self.style.SUCCESS(
                f"Backfilled product audit fields using admin user {admin_user.id} ({admin_user.email})."
            )
        )
        for label, counts in summary.items():
            self.stdout.write(
                f"{label}: created_by={counts['created_by_filled']}, updated_by={counts['updated_by_filled']}"
            )
