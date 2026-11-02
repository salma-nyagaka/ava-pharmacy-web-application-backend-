from datetime import date, timedelta
from decimal import Decimal
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, TestCase

from apps.products.legacy_catalog import iter_product_rows
from apps.products.models import (
    Category,
    Product,
    Promotion,
    Store,
    StoreFulfillmentPolicy,
    StoreVariantListing,
    Variant,
    VariantInventory,
)


COLUMNS = (
    'product_id', 'p_name', 'description', 'code', 'sold', 'left_p', 'price',
    'reorder', 'system', 'category', 'company', 'buying', 'vat', 'package',
    'minimum', 'status', 'size', 'main', 'promotion', 'promo', 'prom', 'start',
    'end', 'kra',
)


def sql_dump(*rows):
    columns = ', '.join(f'`{column}`' for column in COLUMNS)
    values = ',\n'.join(rows)
    return f"INSERT INTO `products` ({columns}) VALUES\n{values};\n"


def sql_row(
    product_id,
    name,
    *,
    price='500.00',
    stock='5',
    buying='300.00',
    category='SKIN CARE',
    status='ACTIVE',
    code='1234567890123',
):
    escaped_name = name.replace("'", "''")
    return (
        f"({product_id}, '{escaped_name}', '{escaped_name}', '{code}', 0, {stock}, "
        f"{price}, 2, '', '{category}', '', {buying}, 16, 0, {price}, "
        f"'{status}', 1, 0, 0, 0, 0, '0000-00-00', '0000-00-00', '')"
    )


class LegacySQLParserTests(SimpleTestCase):
    def test_parser_handles_repeated_inserts_quotes_and_backslash_escapes(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / 'gtc.sql'
            path.write_text(
                sql_dump(sql_row(1, "CHILD'S LOTION"))
                + sql_dump(sql_row(2, r'C:\\STORE\\ITEM')),
                encoding='latin-1',
            )

            rows = list(iter_product_rows(path))

        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]['p_name'], "CHILD'S LOTION")
        self.assertEqual(rows[1]['p_name'], r'C:\STORE\ITEM')
        self.assertEqual(rows[0]['price'], 500)


class LegacyCatalogImportCommandTests(TestCase):
    def _write_sources(self, directory):
        gtc = Path(directory) / 'gtc.sql'
        karen = Path(directory) / 'karen.sql'
        nyali = Path(directory) / 'nyali.sql'
        gtc.write_text(
            sql_dump(
                sql_row(10, 'SAVLON ANTISEPTIC LIQUID 125ML', price='500.00', stock='7'),
                sql_row(
                    11,
                    'SAVLON ANTISEPTIC LIQUID 500ML',
                    price='900.00',
                    stock='-4',
                    buying='-10.00',
                    code='.',
                ),
            ),
            encoding='latin-1',
        )
        karen.write_text(
            sql_dump(
                sql_row(20, 'SAVLON ANTISEPTIC LIQUID 125ML', price='520.00', stock='4'),
            ),
            encoding='latin-1',
        )
        nyali.write_text(
            sql_dump(
                sql_row(
                    30,
                    'AMOXICILLIN 500MG TABLETS',
                    price='50.00',
                    stock='12',
                    category='DISPENSARY',
                ),
            ),
            encoding='latin-1',
        )
        return gtc, karen, nyali

    def test_dry_run_does_not_change_database(self):
        with TemporaryDirectory() as directory:
            sources = self._write_sources(directory)
            output = StringIO()

            call_command(
                'import_legacy_catalog',
                *(str(path) for path in sources),
                dry_run=True,
                stdout=output,
            )

        self.assertEqual(Product.objects.count(), 0)
        self.assertIn('Dry run complete', output.getvalue())

    def test_import_creates_products_variants_and_store_specific_inventory(self):
        Promotion.objects.create(
            title='Dummy catalog promotion',
            value=Decimal('10.00'),
            start_date=date.today(),
            end_date=date.today() + timedelta(days=7),
        )
        with TemporaryDirectory() as directory:
            sources = self._write_sources(directory)

            call_command(
                'import_legacy_catalog',
                *(str(path) for path in sources),
                replace_catalog=True,
                stdout=StringIO(),
            )

        self.assertEqual(Store.objects.count(), 3)
        self.assertEqual(StoreFulfillmentPolicy.objects.count(), 3)
        self.assertEqual(Category.objects.count(), 2)
        self.assertEqual(Product.objects.count(), 2)
        self.assertEqual(Variant.objects.count(), 3)
        self.assertEqual(StoreVariantListing.objects.count(), 4)
        self.assertEqual(VariantInventory.objects.count(), 4)
        self.assertEqual(Promotion.objects.count(), 0)

        savlon = Variant.objects.get(name='SAVLON ANTISEPTIC LIQUID 125ML')
        self.assertEqual(savlon.store_listings.count(), 2)
        self.assertEqual(
            set(savlon.store_listings.values_list('price', flat=True)),
            {500, 520},
        )
        self.assertEqual(
            set(savlon.inventories.values_list('source_name', flat=True)),
            {'GTC Westlands', 'The Hub Karen'},
        )

        negative_stock = VariantInventory.objects.get(
            variant__name='SAVLON ANTISEPTIC LIQUID 500ML'
        )
        self.assertEqual(negative_stock.stock_quantity, 0)
        self.assertEqual(negative_stock.variant.barcode, '')
        self.assertIsNone(negative_stock.variant.cost_price)
        self.assertIsNone(negative_stock.store_listing.cost_price)
        source_value = negative_stock.store_listing.raw_data['rows'][0]['left_p']
        self.assertEqual(source_value, -4)
        self.assertEqual(
            negative_stock.store_listing.raw_data['rows'][0]['buying'],
            '-10.00',
        )
        self.assertEqual(
            negative_stock.store_listing.data_quality_flags,
            ['missing_or_invalid_barcode', 'negative_cost', 'negative_stock'],
        )
        self.assertEqual(
            negative_stock.store_listing.review_status,
            StoreVariantListing.REVIEW_NEEDS_REVIEW,
        )

        amoxicillin = Variant.objects.get(name='AMOXICILLIN 500MG TABLETS')
        self.assertTrue(amoxicillin.requires_prescription)
        self.assertEqual(
            amoxicillin.prescription_classification,
            Variant.PRESCRIPTION_REQUIRED,
        )
        self.assertEqual(
            amoxicillin.prescription_review_status,
            Variant.REVIEW_INFERRED,
        )
        self.assertEqual(
            amoxicillin.product.family_review_status,
            Product.FAMILY_REVIEW_INFERRED,
        )

    def test_import_requires_all_three_nonempty_store_dumps(self):
        with TemporaryDirectory() as directory:
            sources = self._write_sources(directory)

            with self.assertRaisesMessage(CommandError, 'requires all three'):
                call_command(
                    'import_legacy_catalog',
                    *(str(path) for path in sources[:2]),
                    dry_run=True,
                    stdout=StringIO(),
                )

            sources[2].write_text('-- no products rows\n', encoding='latin-1')
            with self.assertRaisesMessage(CommandError, 'contains no products rows'):
                call_command(
                    'import_legacy_catalog',
                    *(str(path) for path in sources),
                    dry_run=True,
                    stdout=StringIO(),
                )

    def test_duplicate_store_names_become_distinct_barcode_matched_variant_slots(self):
        barcode_a = '1234567890123'
        barcode_b = '2234567890123'
        with TemporaryDirectory() as directory:
            sources = []
            source_rows = {
                'gtc': (
                    sql_row(10, 'DUPLICATE ITEM 10ML', price='100.00', code=barcode_a),
                    sql_row(11, 'DUPLICATE ITEM 10ML', price='200.00', code=barcode_b),
                    sql_row(100, 'ORDINAL ITEM 20ML', price='300.00', code='.'),
                    sql_row(101, 'ORDINAL ITEM 20ML', price='400.00', code='.'),
                ),
                # Product IDs deliberately put B before A. Barcode matching must
                # take precedence over the deterministic ordinal fallback.
                'karen': (
                    sql_row(
                        20,
                        'DUPLICATE ITEM 10ML',
                        price='210.00',
                        code=barcode_b,
                        category='DISPENSARY',
                    ),
                    sql_row(21, 'DUPLICATE ITEM 10ML', price='110.00', code=barcode_a),
                    sql_row(200, 'ORDINAL ITEM 20ML', price='310.00', code='.'),
                    sql_row(201, 'ORDINAL ITEM 20ML', price='410.00', code='.'),
                ),
                'nyali': (
                    sql_row(30, 'DUPLICATE ITEM 10ML', price='220.00', code=barcode_b),
                    sql_row(31, 'DUPLICATE ITEM 10ML', price='120.00', code=barcode_a),
                    sql_row(300, 'ORDINAL ITEM 20ML', price='320.00', code='.'),
                    sql_row(301, 'ORDINAL ITEM 20ML', price='420.00', code='.'),
                ),
            }
            for store_code, rows in source_rows.items():
                path = Path(directory) / f'{store_code}.sql'
                path.write_text(sql_dump(*rows), encoding='latin-1')
                sources.append(path)

            call_command(
                'import_legacy_catalog',
                *(str(path) for path in sources),
                replace_catalog=True,
                stdout=StringIO(),
            )

        self.assertEqual(Variant.objects.count(), 4)
        self.assertEqual(StoreVariantListing.objects.count(), 12)
        self.assertFalse(
            StoreVariantListing.objects.filter(raw_data__source_row_count__gt=1).exists()
        )

        barcode_a_variant = Variant.objects.get(barcode=barcode_a)
        barcode_b_variant = Variant.objects.get(barcode=barcode_b)
        self.assertEqual(
            set(barcode_a_variant.store_listings.values_list('external_product_id', flat=True)),
            {'10', '21', '31'},
        )
        self.assertEqual(
            set(barcode_b_variant.store_listings.values_list('external_product_id', flat=True)),
            {'11', '20', '30'},
        )
        self.assertFalse(barcode_a_variant.requires_prescription)
        self.assertTrue(barcode_b_variant.requires_prescription)
        self.assertEqual(barcode_b_variant.category.name, 'SKIN CARE')

        ordinal_variants = Variant.objects.filter(name='ORDINAL ITEM 20ML').order_by('sku')
        ordinal_listing_id_sets = {
            frozenset(variant.store_listings.values_list('external_product_id', flat=True))
            for variant in ordinal_variants
        }
        self.assertEqual(
            ordinal_listing_id_sets,
            {frozenset({'100', '200', '300'}), frozenset({'101', '201', '301'})},
        )
