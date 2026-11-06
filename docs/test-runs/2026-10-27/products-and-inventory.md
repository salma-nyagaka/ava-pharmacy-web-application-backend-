# Products and inventory — 27 October 2026

Follow-up: [28 October — INV-02 passed with simulated payment notification](../2026-10-28/inv02.md). Current application-check result is 14/15; real POS remains blocked. The original run below is retained as history.

Status: **13 scenarios passed at the recorded test layers; 2 remain blocked for full end-to-end sign-off.** The module is not fully signed off. Browser checkout payment completion and real POS integration have not passed.

Environment: existing frontend `http://localhost:3000`, development backend `http://localhost:8000/api`, local PostgreSQL. Only newly created, clearly labelled Module 2 synthetic records were changed in the live database. Automated tests used a separate Django test database. No production deployment or commit was made.

## Results

| ID | Result | Evidence and limits |
|---|---|---|
| CAT-01 | Pass — HTTP + browser | Created synthetic brand/logo, category/image, subcategory, product/image and two active variants through HTTP. Explicitly published brand/category/product. Both exact variants appeared in storefront search; image and category link rendered on detail. Product 22366, variants 23502/23503, stores 11/12. |
| CAT-02 | Pass — browser + API regressions | Catalog loads one page rather than downloading the whole catalog. Next page displayed 13–24; search returned the three ZYRTEC variants and then the two synthetic variants. Price, brand, rating, availability, ordering and pagination are covered by fresh API tests. Stock breakdown is available through API; the storefront has no shopper store chooser. |
| CAT-03 | Pass — browser | Added the missing strength/pack selector. Switching A→B changed SKU and KSh 100→400. Cart persisted exact variants and prices after reload. Fixed cart's zero-price response/mapping. |
| CAT-04 | Pass — browser + HTTP | Saved B, reloaded favourites, moved it to cart, saved and removed it again. Other customer deletion of the wishlist record returned 404; automated ownership checks pass. |
| CAT-05 | Pass — browser + API | Seeded a separate synthetic delivered purchase solely to enable review testing. B review saved and reloaded as verified purchase. Fixed submission to use exact variant, and separated variant rating/count displays. Invalid rating and another customer's attempted review mutation are denied. The seeded delivered record is not evidence of paid fulfillment. |
| CAT-06 | Pass — browser + API | Published/edited synthetic banner and FAQ; both visible. Synthetic brand promotion showed its discount on the storefront. Added the missing homepage CMS display for `home_content`; edited block appeared and disappeared when disabled. Active/expired/future promotion dates and inactive banner/CMS visibility pass API tests. Banners/CMS have active flags, not scheduled visibility fields. All temporary content was unpublished after testing. Full promotion/payment reconciliation belongs to the Orders module and is not claimed here. |
| INV-01 | Pass — HTTP + database | Separate rows: A store 1=50, A store 2=30; B store 1=20, B store 2=10. Store-specific selectors saved each row separately. |
| INV-02 | **Partial / blocked browser purchase** | Live order-stock service test deducted 2 A from store 1: 50→48; store 2 stayed 30; B stayed 20/10. Full automated COD order-creation checks pass. Browser shipping, screening, totals and sandbox STK initiation worked, but provider confirmation did not arrive; Complete & Place Order stayed disabled. Draft ORD-0B167328 remained uncommitted and the sandbox attempt was cancelled. No successful browser purchase or provider-confirmed payment is claimed. |
| INV-03 | Pass — browser + database | Fixed inventory screen searching/pagination beyond its original first 20 items; added explicit store/batch selection. Browser changed only A/store 1 to 49 with threshold 100. Movement recorded -1, reason `Admin inventory update`, and actor `module2.admin@avapharmacy.test`. Store 2 and B unchanged. Restored 50/threshold 5 through the browser. |
| INV-04 | Pass applicable commitment/cancellation behavior — API/service + browser cancellation | Repeated order commitment and release do not deduct/restore twice; exact allocation rows restored. Fixed unsafe arbitrary release/deduct endpoints. Reserve endpoint is explicitly an availability check: **no durable stock hold exists before checkout finalization**. Removed the false 30-minute cart reservation promise. Browser cancellation of the unconfirmed sandbox attempt left stock unchanged. |
| INV-05 | Pass — transactional automated tests | Buying 81 against A's 80 fails and rolls back all row changes. Configured backorder capacity is consumed/restored without negative stock; capacity cannot be exceeded. |
| INV-06 | Pass — concurrent database test | Two customers compete for one unit using separate database connections/threads: one commits, one is rejected; stock ends at zero and exactly one order is committed. |
| INV-07 | Pass — browser + API | Raising A/store 1's threshold crossed aggregate stock below threshold; inventory displayed Low Stock. Baseline restored. Low-stock API and backorder filters pass. |
| INV-08 | **Partial / blocked real POS** | Mocked POS mapping, repeated absolute update, unknown mapping and downtime pass. Repeating quantity 45 creates one movement and changes only the correct store. `POS_INVENTORY_LOOKUP_URL` and `INVENTORY_SYNC_URL` are unconfigured. No real POS request/response or integration sign-off is claimed. |
| INV-09 | Pass — API/database regressions | Customer writes denied; invalid quantities and mismatched listing/variant targets rejected; inactive listing stock excluded. Fixed positive/integer validation on availability checks and strict bulk quantities. Added a regression ensuring multiple reviews do not multiply stock totals through SQL joins. |

## Fixes

- Server pagination/search/filtering on storefront; stale-request protection and visible retry errors.
- Complete brand options, preserved requested sort, exact variant selector and title.
- Exact variant cart unit prices and review routes/counts.
- Atomic, idempotent order stock commitment/release; recorded allocations control restoration. Release requires an existing cancelled/refunded order. The legacy deduct endpoint no longer performs arbitrary extra deductions; checkout owns commitment. These are deliberate API behavior changes.
- Availability-check responses no longer claim a reservation. Invalid quantities are rejected rather than clamped silently in bulk inputs.
- Inventory search/pagination across the full dataset; explicit store/batch adjustment; refresh preserves filters. Page-specific stock counters are labelled accordingly. New Stock searches parent products rather than waiting for the entire catalog download.
- Review aggregation uses subqueries so multiple reviews cannot multiply inventory sums.
- Published CMS homepage content now renders at placement `home_content`, with escaped text and restricted HTTP/relative CTA links. Existing CMS administration remains API-based.

## Verification

**116 backend tests passed**, including new transactional/concurrency regressions. Frontend TypeScript/production build passed; Django checks and scoped whitespace checks passed. Automated success does not substitute for the two blocked external/browser checks above.

- [Backend test log](products-inventory/backend-tests.log)
- [Frontend build log](products-inventory/frontend-build.log)
- [Live HTTP checks](products-inventory/http-checks.json)
- [Exact stock commitment/release](products-inventory/live-stock-checks.json)
- [Final balances, movements and payment state](products-inventory/final-state.json)
- [Cart prices](products-inventory/cart-prices.png)
- [Variant/review browser evidence](products-inventory/variant-review.png)
- [Low-stock browser evidence](products-inventory/low-stock.png)
- [Restored inventory](products-inventory/inventory-restored.png)
- [Published banner](products-inventory/banner-promotion.png)
- [Unconfirmed sandbox checkout](products-inventory/sandbox-payment-pending.png)

## Cleanup and remaining work

Final stock is A=50/30, B=20/10; thresholds are 5 per row. Synthetic product 22366 is deactivated, test customer cart cleared, and synthetic banner/FAQ/CMS/promotion unpublished. Synthetic users, media, stock history, cancelled/test orders and review fixtures remain labelled for retesting. A seeded delivered purchase exists only to test reviews. No real payment or goods delivery occurred; external order push is not configured. The frontend API configuration remains on port 8000.

Finish INV-02 with a successful sandbox confirmation and browser order finalization, then verify stock and cancel the test order. Finish INV-08 after a test POS endpoint/authentication is connected. The user explicitly requested leaving the real POS check blocked for now. INV-08 remains blocked until a test POS endpoint and authentication are connected; no real integration pass is claimed.
