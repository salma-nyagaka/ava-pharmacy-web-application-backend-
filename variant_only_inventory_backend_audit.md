# Backend Audit: Moving AvaPharmacy to Variant-Only Inventory

## Goal

Move AvaPharmacy from mixed product-and-variant inventory to variant-only inventory.

## Exact Backend Areas That Need to Change

### 1. Product model inventory facade

The `Product` model still behaves like a stock-bearing object through:

- `stock_source`
- `stock_quantity`
- `low_stock_threshold`
- `allow_backorder`
- `max_backorder_quantity`
- `available_quantity`
- `inventory_status`

Required change:

- parent product should become catalogue-only
- stock-bearing behavior should move fully to variants

### 2. ProductInventory ownership

`ProductInventory` currently belongs to `Product`.

Required change:

- replace product-level inventory with variant-level inventory, or
- introduce `VariantInventory` and migrate the logic there

### 3. Product serializers

Product serializers still accept and save:

- `branch_inventory`
- `warehouse_inventory`
- flat product stock fields

Required change:

- remove product-level stock writes
- make variant inventory the only editable stock layer

### 4. Cart and checkout

Cart creation still allows product-only purchase without variant selection in some flows.

Required change:

- require `product_variant_id` whenever a product has active variants
- stop checking sellable stock directly on parent products

### 5. Stock reservation and release

Order stock logic still supports:

- product inventory consumption
- variant stock consumption

Required change:

- reserve, commit, and release stock only from variants
- phase out product-level stock allocation helpers

### 6. Admin inventory endpoints

Current admin inventory endpoints still mutate product stock directly.

Required change:

- block product-level stock edits for products with variants
- add or expand variant-focused inventory workflows

### 7. POS refresh and sync

POS refresh and sync currently support both products and variants.

Required change:

- sync variants only
- skip product-level stock updates for products with variants

### 8. Webhooks and import payloads

Inventory webhook and import logic can still match to products.

Required change:

- support matching to variants as the primary path
- skip parent-level stock updates where variants are authoritative

### 9. Tests and seed data

Tests and seed data still create product inventory directly.

Required change:

- update tests to stock variants
- update seed data to stock variants

## Safe First Refactor Steps

1. Require variant selection for products with variants.
2. Block product-level stock edits for products with variants.
3. Skip product-level POS refresh/sync for products with variants.
4. Update documentation to establish variant-only inventory as the intended design.

## Medium Refactor Steps

1. Add proper variant inventory endpoints.
2. Move stock reservation and release to variant-only operations.
3. Refactor availability checks to be variant-first.
4. Update frontend admin inventory screens to manage variant inventory.

## Final Structural Refactor

1. Introduce a dedicated variant inventory model if location-based stock is required.
2. Migrate existing product inventory behavior.
3. Remove product-level inventory writes entirely.
4. Remove product-level POS stock handling entirely.
