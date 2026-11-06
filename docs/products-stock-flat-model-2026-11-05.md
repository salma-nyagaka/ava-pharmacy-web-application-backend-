# Products & Stock — flat sellable items

Implemented locally on 5 November 2026 following the decision to use one flat record per sellable variant.

## User workflow

Open `/admin/products-stock`. The single sidebar entry contains Items, Stock by store and Stock history. Add item creates the item, its price and optional opening store/batch stock in one atomic request. Edit item changes details and price; stock adjustments retain the individual store/batch balance and movement history. The former products and inventory URLs redirect to this workspace, preserving query parameters. Inventory staff retain their existing management route.

KPI totals come from all database records, independently of table pagination. Search and table filters do not replace these database-wide totals.

## Models and existing records

Each Product now represents one exact sellable SKU, including strength and pack identity. A unique database constraint permits only one Variant detail extension per Product. Existing Variant IDs remain the stable foreign-key targets used by orders, prescriptions, cart items, reviews, store listings and inventory. Store/batch stock remains in separate rows because locations, batch expiry and stock movements must remain independently traceable.

Product SKU and active status synchronize with the detail extension. Barcode and POS identifiers live on that extension. `catalog_family_key` preserves the original import grouping. Importing the legacy source again updates the same SKU owners and stock rows instead of recreating grouped parents.

Applied migrations:

- 0070: move any unambiguous parent identifiers to the SKU detail and remove redundant parent columns; reject ambiguous legacy identifiers.
- 0071: split shared parents into exact item records, copy shared metadata/gallery and expand product promotions; align prescription convenience pointers to their existing exact variant.
- 0072: align 31 inherited parent active flags with already inactive SKU details.
- 0073: use the exact SKU on each Product, retaining the former family reference separately.

Local verified counts after migration:

| Record | Count |
| --- | ---: |
| Product items | 23,411 |
| SKU detail extensions | 23,411 |
| Store listings | 64,094 |
| Store/batch stock rows | 64,094 |
| Physical stock units | 10,342,456 |
| Active items | 22,733 |
| Inactive items | 678 |

Stock row IDs, values and store listings were checked with SHA-256 fingerprints before and after migration. Existing SKU details were unchanged apart from their new product owner links during the split. The final SKU migration left every SKU detail, stock row, listing, order item and prescription item fingerprint unchanged. The local database currently has no order items, prescription items or stock movements; the migration tests verify non-empty SKU and inventory relationships, while non-empty live clinical/order histories could not be verified from this local dataset.

## Backups and verification

Pre-change PostgreSQL custom backups, each validated with `pg_restore --list`:

- `/private/tmp/ava-products-stock-20261105T120346Z/database.dump`
- `/private/tmp/ava-flat-products-stock-20261105T121329Z/database.dump`
- `/private/tmp/ava-final-flat-sku-20261105T123427Z/database.dump`

The final two folders contain `migration-result.json` with counts and fingerprints. These are local temporary backups; copy them to durable storage if retained recovery artifacts are needed.

36 focused tests passed across flat catalog models/migration, atomic item create/edit, store stock preservation, read APIs, import idempotence and database-wide admin counts. `makemigrations --check --dry-run` found no outstanding model changes. Frontend TypeScript/Vite production build passed. Browser checks verified the combined workspace, exact SKU rows, database-wide total of 23,411 and the opening-stock form without creating synthetic live records.

Deployment elsewhere requires the normal code deployment and `manage.py migrate`; only the local configured database has been migrated here.
