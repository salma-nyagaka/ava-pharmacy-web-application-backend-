import hashlib
import hmac
import json
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.products.models import Product, VariantInventory


class InventorySyncTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_user(
            email='inventory-admin@example.com',
            password='testpass123',
            first_name='Inventory',
            last_name='Admin',
            role=User.ADMIN,
            is_staff=True,
        )
        self.product = Product.objects.create(
            sku='SYNC-001',
            pos_product_id='POS-001',
            name='Synced Product',
            price='500.00',
            is_active=True,
        )
        self.variant = self.product.variants.create(
            sku='SYNC-001-TAB',
            pos_product_id='POS-001',
            name='Tablets',
            price='500.00',
            is_active=True,
        )
        VariantInventory.objects.update_or_create(
            variant=self.variant,
            location=Product.STOCK_BRANCH,
            defaults={'stock_quantity': 8, 'low_stock_threshold': 2},
        )

    def _signature(self, body, secret):
        return hmac.new(secret.encode('utf-8'), body, hashlib.sha256).hexdigest()

    @override_settings(INVENTORY_SYNC_SECRET='sync-secret')
    def test_inventory_webhook_updates_variant_location_stock(self):
        payload = {
            'items': [
                {
                    'sku': self.variant.sku,
                    'location': 'warehouse',
                    'quantity_on_hand': 14,
                    'low_stock_threshold': 3,
                    'allow_backorder': True,
                    'max_backorder_quantity': 5,
                    'next_restock_date': '2026-03-31',
                }
            ]
        }
        body = json.dumps(payload).encode('utf-8')

        response = self.client.generic(
            'POST',
            reverse('inventory-webhook'),
            body,
            content_type='application/json',
            HTTP_X_SYNC_SIGNATURE=self._signature(body, 'sync-secret'),
        )

        self.assertEqual(response.status_code, 200)
        inventory = VariantInventory.objects.get(variant=self.variant, location=Product.STOCK_WAREHOUSE)
        self.assertEqual(inventory.stock_quantity, 14)
        self.assertTrue(inventory.allow_backorder)
        self.assertEqual(inventory.max_backorder_quantity, 5)

    def test_product_availability_detail_returns_location_breakdown(self):
        VariantInventory.objects.update_or_create(
            variant=self.variant,
            location=Product.STOCK_WAREHOUSE,
            defaults={'stock_quantity': 5, 'next_restock_date': '2026-03-31'},
        )

        response = self.client.get(reverse('product-availability-detail', args=[self.product.id]))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['in_stock'])
        self.assertEqual(response.data['quantity'], 13)
        self.assertEqual(len(response.data['location_stock']), 2)

    @override_settings(INVENTORY_SYNC_URL='https://inventory.example.com/sync')
    @patch('apps.products.inventory_sync.request.urlopen')
    def test_sync_inventory_command_pulls_remote_inventory(self, mock_urlopen):
        class _Response:
            def __enter__(self_inner):
                return self_inner

            def __exit__(self_inner, exc_type, exc, tb):
                return False

            def read(self_inner):
                return json.dumps({
                    'items': [{'sku': 'SYNC-001-TAB', 'location': 'branch', 'quantity_on_hand': 22}]
                }).encode('utf-8')

        mock_urlopen.return_value = _Response()

        call_command('sync_inventory')

        inventory = VariantInventory.objects.get(variant=self.variant, location=Product.STOCK_BRANCH)
        self.assertEqual(inventory.stock_quantity, 22)

    @override_settings(INVENTORY_SYNC_SECRET='sync-secret')
    def test_inventory_webhook_matches_variant_when_product_has_variants(self):
        payload = {
            'items': [
                {
                    'sku': self.variant.sku,
                    'location': 'warehouse',
                    'quantity_on_hand': 14,
                }
            ]
        }
        body = json.dumps(payload).encode('utf-8')

        response = self.client.generic(
            'POST',
            reverse('inventory-webhook'),
            body,
            content_type='application/json',
            HTTP_X_SYNC_SIGNATURE=self._signature(body, 'sync-secret'),
        )

        self.assertEqual(response.status_code, 200)
        results = response.data['updated']
        self.assertTrue(results[0]['matched'])
        inventory = VariantInventory.objects.get(variant=self.variant, location=Product.STOCK_WAREHOUSE)
        self.assertEqual(inventory.stock_quantity, 14)
