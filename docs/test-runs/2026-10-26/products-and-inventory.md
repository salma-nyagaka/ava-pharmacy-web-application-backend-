# Module 2: Products and inventory

Date: 27 October 2026 · Status: Superseded by the execution report

Latest results: [27 October execution report](../2026-10-27/products-and-inventory.md). 13 scenarios passed; browser payment completion and real POS integration remain blocked. Historical preparation notes follow.

**A product groups the medicine. A variant is the exact item sold. Stock belongs to that variant at a specific store/location.**

Flow: create product → add variants → stock each store → browse → select variant → purchase → verify stock.

## Test setup

- [ ] Confirm port 3000 uses the isolated QA backend/database before changing data.
- [ ] Prepare an admin, inventory staff member and two customers.
- [ ] Use one synthetic product with two variants and two stores.
- [ ] Record prices, stock rules and starting quantities below.

| Variant | Store 1 stock | Store 2 stock | Price |
|---|---:|---:|---|
| A — strength/pack size 1 | 50 | 30 | Record before testing |
| B — strength/pack size 2 | 20 | 10 | Record before testing |

## Checks — work in this order

Leave boxes empty until verified. Refresh after saving. Record API and browser evidence separately.

| Done | ID | Check | Expected result |
|---|---|---|---|
| [ ] | CAT-01 | Create brand, category/subcategory, product, images and two variants. | Correct details and images appear in the storefront. |
| [ ] | CAT-02 | Search and filter; open product details. | Results, price and availability match the selected variant/store. |
| [ ] | CAT-03 | Switch strength/pack size and add to cart. | Cart contains the exact variant, quantity and price selected. |
| [ ] | CAT-04 | Add/remove wishlist items; move one to cart. | Changes persist after refresh and stay private to the customer. |
| [ ] | CAT-05 | Submit/view a review; try invalid input and another user's review. | Valid reviews save; validation and ownership rules apply. |
| [ ] | CAT-06 | Publish/edit banners, promotions, FAQs and content. | Correct storefront content and visibility dates. |
| [ ] | INV-01 | Save the stock quantities above. | Each variant/store has a separate stock record. |
| [ ] | INV-02 | Complete an order for 2 packs of A from store 1. | At the configured deduction stage: A/store 1 = 48, A/store 2 = 30; B unchanged. Reserved/available stock agrees. |
| [ ] | INV-03 | Adjust stock as authorized staff. | Correct balance and history with quantity, reason and actor. |
| [ ] | INV-04 | Reserve, release and cancel; repeat the action. | Stock restores once to the correct store. |
| [ ] | INV-05 | Buy above available stock. | Rejected or handled by the configured backorder rule; no unintended negative stock. |
| [ ] | INV-06 | Have two customers buy the last unit concurrently. | Only one succeeds unless backorders explicitly allow both. |
| [ ] | INV-07 | Cross the low-stock threshold. | Configured low-stock indicator/alert appears. |
| [ ] | INV-08 | Sync POS stock; repeat, use unknown mappings and simulate downtime. | Correct variant/store updated; safe retries and clear errors. |
| [ ] | INV-09 | Try customer stock edits, invalid quantities and mismatched records. | Unauthorized/invalid writes rejected; inactive listings excluded from availability. |

## Results and fixes

Testing began on 27 October. Fresh automated runs passed: 71 product tests and 14 order/stock tests (85 total). These verify catalog administration, variant/store separation, availability, wishlist/reviews, mocked POS synchronization, stock allocation and release. Logs: [catalog](../2026-10-27/products-inventory/catalog-tests.log), [stock](../2026-10-27/products-inventory/stock-tests.log). They do not establish full browser acceptance or real POS integration.

Browser finding: port-3000 homepage and catalog route open, but the catalog remains on “Loading products…” during initial observation. The live port-8000 catalog API returns HTTP 200 and reports 22,735 items. The listing requests all pages before displaying items, with a 99-follow-up-page cap. This needs further investigation and a fix/retest before CAT-02 can pass. No catalog data was changed in this initial run. The frontend retains its existing port-8000 API configuration.

| ID | Pass / Fail / Blocked / N/A | Evidence / record | Fix and retest |
|---|---|---|---|
| | | | |

For each failure: reproduce → fix → retest → record evidence. Mark unavailable POS/payment integrations blocked. The order/payment steps here verify stock; the full payment module follows separately.

## Completion

- [ ] Every check has a recorded result; blocked/N/A items have reasons.
- [ ] Broken/missing behavior is fixed and retested, or explicitly listed as unresolved.
- [ ] Final stock balances match orders and movement history.
- [ ] Test records are cleaned up or documented for the next module.

Accounts carry-over: the user confirmed ACC-01, ACC-05, ACC-06 and ACC-10 passed on 27 October. Recorded as user-verified browser results. See [account report](accounts-completion.md).

Full application checklist: [end-to-end plan](../../end-to-end-test-checklist.md).
