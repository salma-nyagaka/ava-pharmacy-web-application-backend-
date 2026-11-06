# Catalog categories and subcategories — 5 November 2026

All 23,411 local product items now have a category and subcategory. The database has 23 active main categories and 148 active subcategories. Every item's category matches its subcategory's parent; missing categories, missing subcategories and mismatched parents are all zero.

The former 29 flat category records were reorganized by reusing and renaming 20 roots, adding 3 roots, and retiring 9 empty legacy roots. Retired records remain inactive with their original IDs and slugs; none was deleted. Thus the database-wide admin KPI correctly reports 32 total categories: 23 active and 9 inactive.

See [the complete hierarchy](hierarchy.md) or [hierarchy CSV](hierarchy.csv) for the names, parent links and item counts.

## How assignments were made

The classifier reads each exact item name, its original department and its existing brand label. Specific product forms take priority over legacy catch-all departments: fragrances, personal care, food, self-test kits, orthopaedic supports and medical supplies are separated from the old OTC groups. Medicines are grouped mainly by route or form; a vitamin-C facial serum remains skincare rather than an oral vitamin. Nicotine replacement products and vape liquids/devices have separate subcategories under Smoking & Vaping.

These are merchandising placements. Prescription requirements, regulatory scope, licences, clinical information, product activation and dispensing controls were not changed.

Every item was assigned, including inactive items and discontinued listings. 2,978 broad placements are flagged in [review.csv](review.csv), mainly medicines whose names omit a dosage form, assorted accessories and unclear internal legacy entries. They have valid category/subcategory links, but need manual refinement; classification is inferred rather than pharmacist-verified. Internal entries such as telephone expenses remain identifiable in Store Supplies & Accessories / Unspecified Catalog Entries.

## Audit and recovery

- `assignments.json`: all 23,411 item IDs/SKUs, original category IDs, new category/subcategory IDs, reasons and review flags.
- `summary.json`: per-category and per-subcategory counts, created records, renamed roots and retired root IDs.
- `verification.json`: SHA-256 fingerprints before and after the transaction.
- `review.csv`: the 2,978 broad assignments needing review.

The validated PostgreSQL backup is `/private/tmp/ava-catalog-taxonomy-20261105T161959Z/database.dump`. It is a temporary local recovery artifact; retain a durable copy if long-term rollback is needed.

Fingerprint comparisons confirm that all Product records (including brands), prices, SKUs, clinical/regulatory fields, store listings and 64,094 stock rows are unchanged. Total physical stock remains 10,342,456 units. Existing order/prescription item tables were unchanged; they are empty in this local dataset.

## Application changes and verification

The item API now returns the assigned subcategory ID and rejects a category/subcategory pair belonging to different parents. Supplying a subcategory alone derives its parent. Moving a subcategory through the API also moves its linked items' category pointers. The item form starts with no arbitrary subcategory and filters choices by category.

Legacy imports resolve renamed roots through their preserved slugs and retain existing item subcategories instead of resetting them. The taxonomy command marks its assignments and skips already-classified items, including later valid manual refinements. A repeat dry run skipped all 23,411 items with zero new assignments.

35 focused tests passed, covering representative placements, parent consistency, stock and clinical-field preservation, repeat execution, legacy reimport, item APIs, filters and database-wide counts. Frontend TypeScript/Vite production build passed. Local category lists, product detail, subcategory filtering and KPI APIs returned HTTP 200. Django reported no pending model migrations; the existing Category/Subcategory foreign keys support this hierarchy.

Preview future uncategorized imports with:

```sh
venv/bin/python manage.py organize_catalog_taxonomy --report-dir /private/tmp/taxonomy-preview
```

Add `--apply` to assign those items. Use a new report directory per run to retain earlier audit files. The current update applies only to the local configured database.
