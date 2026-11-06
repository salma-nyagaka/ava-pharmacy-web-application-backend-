# Legacy catalog import: GTC, Karen, and Nyali

## Source audit

The supplied files are MySQL/phpMyAdmin dumps and must not be executed directly
against the PostgreSQL application database. They contain one `products` table
with 24 columns and identify the store only through the filename.

| Source file | Store | Rows | Active rows | Rows with stock | Blank codes |
| --- | --- | ---: | ---: | ---: | ---: |
| `gtc.sql` | GTC Westlands | 21,886 | 21,211 | 9,751 | 845 |
| `karen.sql` | The Hub Karen | 20,947 | 20,245 | 9,399 | 819 |
| `nyali.sql` | Promenade Mall Nyali | 21,270 | 20,593 | 9,493 | 850 |

Across the three files there are 23,350 distinct non-blank item names. Repeated
same-name rows within a store are retained as separate deterministic slots,
producing 23,413 variants and 64,100 store listings from 64,100 named source
rows. The current product-name normalization groups them into approximately
22,194 parent product families. Exact item names still have 4,430 selling-price
conflicts and 5,938 buying-price conflicts across stores, so price and cost
cannot safely live only on the canonical `Variant` row.

Important source-quality findings:

- 2,514 rows have a blank `code`; many non-blank codes are placeholders such
  as `0`, `.`, `01`, or repeated all-zero-like barcodes.
- 27 rows have negative stock; imported on-hand stock is clamped to zero while
  the original value remains in raw import metadata.
- Three rows have negative `sold`; four rows have negative buying cost.
- 70 rows have a zero selling price, including 67 marked active.
- Three discontinued rows use `99,999,999.99` as a sentinel price.
- Two rows use VAT `460`, which is not a credible percentage.
- Nearly every promotion date is the MySQL zero date `0000-00-00`.
- `company` is blank on 64,100 of 64,103 rows, so it is not a usable brand
  source for almost the entire catalog.

## Source-to-database mapping

| SQL field | Target | Import handling |
| --- | --- | --- |
| `product_id` | `StoreVariantListing.external_product_id` | Kept per store; it is not globally unique. |
| `p_name` | `Variant.name`; derived `Product.name` | Whitespace/case normalized for matching; repeated names in one store are split by shared barcode first and deterministic source order second. Blank names are rejected. |
| `description` | `Variant.short_description` / `description` | Best non-blank value retained; every original value remains in raw metadata. |
| `code` | `Variant.barcode` when it resembles an 8-14 digit barcode | Never used as the internal SKU; blank, malformed, and all-one-digit placeholders are left out while every original value remains in raw metadata. |
| `sold` | `StoreVariantListing.raw_data` | Historical meaning is unclear; it is not treated as a stock movement. |
| `left_p` | `VariantInventory.stock_quantity` | Aggregated per store and clamped at zero. |
| `price` | `StoreVariantListing.price` | Store-specific value retained; the canonical variant uses the modal valid value. |
| `reorder` | `VariantInventory.reorder_level` and `low_stock_threshold` | Aggregated store setting. |
| `system` | `StoreVariantListing.raw_data` | Meaning/quality is unclear. |
| `category` | `Category` and `Variant.category` | Modal non-blank category across matching rows. |
| `company` | `StoreVariantListing.raw_data` | Nearly always missing, so no canonical `Brand` is created until the three populated values are validated. |
| `buying` | `StoreVariantListing.cost_price` | Store-specific non-negative value retained; invalid negative values remain only in raw metadata. The canonical variant uses the modal non-negative value. |
| `vat` | `StoreVariantListing.vat_rate` | Preserved exactly and flagged for review when implausible. |
| `package` | `StoreVariantListing.raw_data` | Always `0`; semantics are undocumented. |
| `minimum` | `StoreVariantListing.minimum_price` | Preserved per store; not assumed to be a discount/original price. |
| `status` | Listing/variant/product `is_active` | Only normalized `ACTIVE` is active; original spelling remains in raw metadata. |
| `size`, `main` | `StoreVariantListing.raw_data` | Semantics are undocumented. |
| `promotion`, `promo`, `prom`, `start`, `end` | `StoreVariantListing.raw_data` | Conflicting legacy flags are not converted into live promotions. |
| `kra` | `StoreVariantListing.raw_data` | Retained for later KRA/tax classification work. |

The canonical variant SKU and parent product SKU are deterministic internal
hash-based identifiers. This avoids treating unreliable legacy barcodes or
store-local product IDs as global unique keys.

## Fields absent or not reliable in the SQL files

These fields need curation or a business decision before they can be populated
reliably. The database now has nullable/unknown fields and review states for
them; the import does not invent unavailable values:

1. **Product-family identifier** — there is no explicit key linking several
   sizes/strengths/flavours to one parent product. The importer uses the
   existing name heuristic and preserves the original names for review.
2. **Reliable barcode and internal SKU** — codes are often blank, duplicated,
   or placeholders. Internal SKUs are generated; barcode cleanup remains.
3. **Brand/manufacturer** — `company` is effectively empty. Brand name, logo,
   manufacturer, and marketing-authorisation holder need another source.
4. **Structured strength, dosage form, pack size, colour/flavour** — these are
   embedded in free-text names rather than supplied as separate fields.
5. **Images and gallery images** — no image paths or URLs are supplied.
6. **Subcategory hierarchy and health concerns** — only a flat legacy category
   is supplied.
7. **Prescription requirement** — there is no explicit flag. The importer
   conservatively marks the legacy `DISPENSARY` category as prescription-only;
   this requires pharmacist review.
8. **Dosage, directions, warnings, contraindications, side effects, and
   features** — none are supplied.
9. **PPB/regulatory data** — PPB registration, marketing authorisation number,
   PIL version, authorised supplier, KRA classification meaning, and licence
   status are absent or unclear.
10. **Batch inventory detail** — batch number, expiry date, supplier, shelf
    location, damaged/expired status, and next restock date are absent.
11. **Storage/cold-chain data** — temperature sensitivity and storage
    instructions are absent.
12. **Promotion semantics** — the three promotion flags and legacy dates are
    not documented and are mostly zero values.
13. **Per-store fulfilment policy** — the dumps provide stock by store, but do
    not state which store should fulfil an online order, transfer rules, or the
    customer-facing store selection policy.

## Curation fields now available

- `Product` stores an optional master product ID, manufacturer, marketing-
  authorisation holder, family review status, and curation notes. Imported
  heuristic families are marked `inferred`.
- `Variant` stores structured dosage form, pack size, colour, flavour,
  prescription classification and review status, PPB/regulatory status and
  expiry, KRA classification, temperature bounds, and curation notes.
  `DISPENSARY` inference is represented as `prescription` + `inferred`; all
  other imported variants remain `unknown` + `pending`, rather than being
  incorrectly asserted to be over-the-counter.
- `StoreVariantListing` stores deterministic data-quality flags, a review
  status, and review notes. Flags cover invalid barcodes, active zero prices,
  sentinel prices, negative cost/stock, implausible VAT, unmapped legacy
  promotions, and non-blank unmapped KRA values.
- `StoreFulfillmentPolicy` stores online fulfilment, pickup and transfer
  switches, priority, lead time, capacity, service areas, and notes. A disabled
  policy is created for every imported store so no fulfilment behaviour is
  silently assumed.

## Resulting ownership

- `Product`: canonical parent/family and optional brand.
- `Variant`: canonical sellable item, category, description, and fallback
  storefront price.
- `Store`: GTC Westlands, The Hub Karen, and Promenade Mall Nyali.
- `StoreVariantListing`: store-local legacy ID, selling price, buying cost,
  minimum price, VAT, status, and complete raw source data.
- `VariantInventory`: stock and reorder threshold linked to the store listing.

This separation avoids overwriting one branch's price, cost, status, or source
ID with another branch's value while keeping the existing variant-first cart
and order model intact.

Until the business selects a customer-facing store/fulfilment policy, checkout
continues to use the canonical variant's modal source price and allocates stock
deterministically across active store rows. Exact inventory-row allocations are
recorded on each order item so cancellation returns units to the same store.
Store-specific prices remain available on the listing and inventory APIs, but
should not be presented as the checkout price until a store is selected in the
cart/order flow.
