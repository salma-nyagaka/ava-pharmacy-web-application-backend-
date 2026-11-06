import json
import os
import secrets
from pathlib import Path
from decimal import Decimal
from django.conf import settings
from django.db import transaction
from apps.accounts.models import User
from apps.lab.models import LabPartner, LabTechnicianProfile
from apps.products.models import Product, Variant, Store, StoreVariantListing, VariantInventory

assert settings.DEBUG, 'QA fixtures require a development environment'
assert settings.DATABASES['default']['HOST'] in ('localhost', '127.0.0.1', '::1'), 'Local database only'
credentials_path = Path('/private/tmp/ava-e2e-credentials-20261026.json')
credentials = json.loads(credentials_path.read_text()) if credentials_path.exists() else {}
created_users = []
with transaction.atomic():
    users = {}
    for role in [User.INVENTORY_STAFF, User.LAB_PARTNER, User.LAB_TECHNICIAN]:
        email = f'qa.e2e.{role}.20261026@avapharmacy.test'
        user, created = User.objects.get_or_create(email=email, defaults={
            'first_name': 'E2E QA', 'last_name': role, 'role': role,
            'status': User.STATUS_ACTIVE, 'is_active': True,
        })
        if created:
            password = secrets.token_urlsafe(24)
            user.set_password(password)
            user.save(update_fields=['password'])
            credentials[email] = password
            created_users.append({'id': user.pk, 'role': role})
        assert user.role == role
        users[role] = user
    partner, _ = LabPartner.objects.get_or_create(user=users[User.LAB_PARTNER], defaults={
        'name': 'E2E QA Laboratory 20261026', 'email': users[User.LAB_PARTNER].email,
        'phone': '', 'status': LabPartner.STATUS_VERIFIED, 'notes': 'Synthetic local E2E fixture',
    })
    LabTechnicianProfile.objects.get_or_create(user=users[User.LAB_TECHNICIAN], defaults={
        'partner': partner, 'name': 'E2E QA Technician', 'email': users[User.LAB_TECHNICIAN].email,
        'status': LabTechnicianProfile.STATUS_ACTIVE,
    })
    stores = []
    for number in [1, 2]:
        store, _ = Store.objects.get_or_create(code=f'e2e-qa-20261026-{number}', defaults={
            'name': f'E2E QA Store {number} 20261026', 'city': 'Nairobi',
        })
        stores.append(store)
    product, _ = Product.objects.get_or_create(sku='E2E-QA-20261026', defaults={
        'name': 'E2E QA Test Medicine', 'is_active': False,
        'description': 'Synthetic test fixture; not a real medicine listing.',
    })
    variants = []
    specs = [
        ('A', '500 mg tablets pack of 20', '100.00', (50, 30), False, False),
        ('B', '500 mg tablets pack of 100', '400.00', (15, 10), False, False),
        ('RX', 'Prescription test pack', '200.00', (10, 10), True, False),
        ('ZERO', 'Out of stock test pack', '100.00', (0, 0), False, False),
        ('LOW', 'Low stock test pack', '100.00', (2, 1), False, False),
        ('BACK', 'Backorder test pack', '100.00', (0, 0), False, True),
    ]
    for suffix, name, price, quantities, requires_rx, backorder in specs:
        variant, _ = Variant.objects.get_or_create(sku=f'E2E-QA-20261026-{suffix}', defaults={
            'product': product, 'name': name, 'price': Decimal(price), 'requires_prescription': requires_rx,
        })
        variants.append(variant)
        for store, quantity in zip(stores, quantities):
            listing, _ = StoreVariantListing.objects.get_or_create(store=store, variant=variant, defaults={'price': Decimal(price)})
            VariantInventory.objects.get_or_create(variant=variant, store_listing=listing, batch_number='E2E-20261026', defaults={
                'stock_quantity': quantity, 'low_stock_threshold': 5,
                'allow_backorder': backorder, 'max_backorder_quantity': 5 if backorder else 0,
                'source_name': 'Synthetic E2E setup; no POS mapping',
            })
    descriptor = os.open(credentials_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, 'w') as target:
        json.dump(credentials, target)

print(json.dumps({
    'created_users': created_users, 'credentials_file': str(credentials_path),
    'product_id': product.pk, 'product_active': product.is_active,
    'variants': [{'id': v.pk, 'sku': v.sku, 'price': str(v.price)} for v in variants],
    'stock': list(VariantInventory.objects.filter(variant__in=variants, store_listing__store__in=stores).values(
        'variant__sku', 'store_listing__store__code', 'stock_quantity', 'low_stock_threshold', 'allow_backorder',
    )),
}, indent=2))
