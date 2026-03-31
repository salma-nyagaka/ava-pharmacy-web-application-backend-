# Target Design: Variant-Only Inventory in AvaPharmacy

## Overview

Going forward, AvaPharmacy should treat inventory as variant-only.

That means:

- the parent `Product` is a catalogue shell
- the `ProductVariant` is the actual sellable stock unit
- inventory should belong to variants, not to products
- POS sync should update variant stock, not parent product stock

## Product

The parent product should hold catalogue information such as:

- product name
- description
- category
- brand
- prescription requirement
- marketing and display content

The parent product should not be the stock source of truth.

## Variant

The variant should represent the exact sellable item, for example:

- tablets
- syrup
- sachets
- 250mg
- 500mg
- pack size variations

Each variant should carry its own:

- SKU
- barcode
- POS product ID
- stock quantity
- low stock threshold
- backorder rules

## Inventory

Inventory should belong to variants only.

If location-based stock is needed, it should still be variant-based, for example:

- variant stock in main shop
- variant stock in POS store

This keeps stock accurate at the exact sellable level.

## POS Sync

POS sync should mainly handle:

- product matching to the correct variant
- stock quantity updates for variants
- source/store identification
- stock availability updates

This POS sync is not mainly about payments.

## Intended Flow

The intended flow going forward should be:

1. Save the main product first.
2. Create one or more variants under that product.
3. Manage stock only on the variants.
4. Manage thresholds and backorder rules on the variants.
5. Sync variant stock from the external system.

## Why This Design Is Better

This removes ambiguity.

With variant-only inventory:

- there is one stock source of truth
- checkout deducts from the correct sellable unit
- POS sync updates the correct record
- low stock alerts are attached to the actual item being sold
- backorder rules are applied to the correct item

## Conclusion

The correct target design for AvaPharmacy is:

- `Product` = catalogue shell
- `ProductVariant` = actual sellable unit
- inventory = variant-only
- POS sync = variant-level sync

So the long-term direction should be:

- save product
- create variants
- manage stock on variants only
- sync stock on variants only
