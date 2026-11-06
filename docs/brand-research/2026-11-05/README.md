# Product brand research and assignments — 5 November 2026

The local database now has 13,956 branded products out of 23,411. This update linked 5,199 previously unbranded items and created 1,314 missing brand labels, bringing the brand total from 157 to 1,471. Original assignments on 8,757 products were preserved.

9,455 products remain unassigned. They include generic medicines, ordinary supplies, internal abbreviations and trade names without an unambiguous match in the checked sources. This is not a completed attribution of every product. Package photographs, supplier SKU/brand mappings, manufacturer barcodes or additional product-specific sources are needed to resolve them reliably. No placeholder “Generic” brand or guessed manufacturer was added.

## Evidence and matching

Research used the [Kenyan PPB registered product list](https://products.pharmacyboardkenya.org/ppb_admin/pages/public_view_retention_products.php), [PPB retained product list](https://products.pharmacyboardkenya.org/ppb_admin/pages/public_view_retention_products_gbt_retention.php), manufacturer and brand websites, and the [Goodlife Kenya brand directory](https://www.goodlife.co.ke/brands/). Each assignment records its supporting source URL and reason in `assignments.json` and on the product's curation notes. Reusing an exact existing catalog label is explicitly identified separately.

Rules match complete leading labels at word boundaries, prefer longer specific labels, and leave uncertain abbreviations and generic ingredients unmatched. A retailer directory also contains generic names and ordinary supplies, so these were excluded rather than treating every directory entry as a brand. An ambiguous shared label such as Trek was excluded. Existing catalog labels are reused case-insensitively with punctuation normalization.

“Brand” here is the product's marketed trade label or explicit manufacturer label, consistent with the existing Brand model. PPB entries verify the trade label only; they do not establish the current licensing status or the manufacturer/marketing-authorisation holder of a particular pack. No clinical metadata was changed. New brands have no invented logo; logo assets remain empty until supplied or separately verified.

## Audit files

- `assignments.json`: 5,199 item IDs, SKUs, prior/new brand IDs and source evidence.
- `unresolved.csv`: current 9,455 unmatched items for follow-up research or supplier reconciliation.
- `summary.json`: counts, created brand IDs and backup paths.
- `verification.json`: before/after SHA-256 fingerprints proving preservation of all non-brand item data, SKU details, inventory and store listings.
- `first-pass/` and `directory-pass/`: original reports for each transaction.

The two validated PostgreSQL backups are in `/private/tmp/ava-brand-linking-20261105T155210Z/database.dump` and `/private/tmp/ava-brand-linking-20261105T155458Z/database.dump`. Copy temporary backups to durable storage if long-term recovery is required.

## Verification and reuse

19 focused brand, stock, admin API and database-count tests passed. The final expanded evidence rules were rechecked with the focused brand suite. Local admin product detail, brand list and brand KPI endpoints each returned HTTP 200; both the list and KPI reported 1,471 brands. The tested ZzzQuil item returns its new brand. Cache generation was invalidated after each successful transaction. Django reported no pending model migrations.

The command is dry-run by default:

```sh
venv/bin/python manage.py link_researched_brands --report-dir /private/tmp/brand-preview
```

Add `--apply` to link newly unbranded records using the checked evidence rules. It never overwrites an existing product brand. Future research can extend `avapharmacy/apps/products/data/researched_brands.json`; each new researched rule requires an HTTPS source. Re-running against the same unchanged catalog makes no further assignments and creates no duplicate brands.

This work changed only the locally configured database; other deployments require the code/data file and a separately run command.
