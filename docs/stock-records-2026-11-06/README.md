# Unified stock records — 6 November 2026

Manage stock now renders the same store/batch record table with or without a product query parameter. The general view is server-paginated (20 records) and supports product/SKU/batch/store search, store selection, prescription filtering and quantity filters. KPIs cover all stock records in the database. Selected-product view shows all stock records for that product.

Each row shows store, batch, expiry, quantity, threshold, status, Added by and Date added. Changes expands that stock record's paginated movement history inline, with actor/date and before/after quantities. The separate Stock history tab is removed; historical movement data and its API remain intact. Old history URLs render Manage stock.

Add stock on the general page includes a searchable product selector. Existing records support Edit and Receive more. POS-synced records remain read-only. Receipts add quantities atomically, write Stock In movements and invalidate catalog caches after commit. Corrections write Adjustment movements.

Migration 0074 adds nullable creator/updater references to stock records. New stock captures the signed-in actor; quantities, existing dates and product assignments were not changed. attribution-recovery.json records three creators recovered from explicit additions made within ten seconds of row creation, each with its source movement ID. Other historical creators remain unknown, displayed as Not recorded.

Verification: frontend TypeScript/production build, stock API tests, flat product tests; browser verified the general page's 64,097 stock records, all-record KPIs and inline movement details. No inventory quantities were changed during browser verification.
