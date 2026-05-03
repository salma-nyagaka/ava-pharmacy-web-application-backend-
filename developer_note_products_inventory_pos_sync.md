# AvaPharmacy Target Design: Variant-Only Inventory

## Purpose

This note explains the intended architecture for AvaPharmacy so external developers understand the direction the system is moving toward.

The intended model is variant-only inventory.

## Core Model

The target structure should be:

1. `Product`
2. `ProductVariant`
3. variant-level inventory
4. POS sync

## Product Layer

The parent product should be a catalogue record only.

It should contain:

- name
- category
- brand
- description
- prescription flag
- catalogue presentation fields

It should not be the source of truth for stock.

## Variant Layer

The variant should be the real sellable stock-bearing unit.

Examples:

- tablets
- syrup
- sachets
- strength options
- pack size options

Each variant should carry:

- SKU
- barcode
- POS product ID
- stock quantity
- low stock threshold
- allow backorder
- max backorder quantity

## Inventory Direction

Inventory should be managed on variants only.

If location-based stock is required, it should still be attached to variants rather than the parent product.

## POS Integration Direction

The POS integration should support:

- matching the correct variant
- updating variant stock
- sending source/store information if relevant
- using a shared identifier such as SKU, barcode, or POS product ID

## Intended Flow

1. Create the parent product.
2. Create the variants.
3. Assign inventory to variants.
4. Sync stock to variants from the external system.

## Summary

The intended AvaPharmacy model is:

- product = catalogue shell
- variant = sellable item
- inventory = variant-level only
- POS sync = variant-level stock sync
