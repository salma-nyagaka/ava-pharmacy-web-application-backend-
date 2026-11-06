# ORD-05: M-Pesa STK retry — 29 October 2026

Status: **PASSED — KSh 1 sandbox STK payment confirmed and checkout finalized.** Earlier failed attempts are retained below as history. Sandbox only; no real payment or medicine delivery.

- [x] Initiate real Safaricom sandbox STK for KES 350, order ORD-819DBAE3 (2001), intent 43.
- [x] Receive genuine provider callback: ResultCode 1037, “No response from user.”
- [x] Mark payment and intent failed; reject unpaid checkout finalization (HTTP 400).
- [x] Preserve variant stock at 50/30; no inventory committed and no payment receipt sent.
- [x] Fix restored checkout losing payment failure state; browser now displays the provider failure and disables order completion.
- [x] Fix address saving without consent; 16 address/checkout regression tests passed.
- [x] Frontend production build passed.
- [x] Cancel both synthetic draft orders (2000/2001), remove only this run's cart/address fixtures, restore QA product inactive. Retain genuine failed payment history.
- [x] Obtain successful Safaricom confirmation, match amount/reference, commit exact variant/location stock, and verify customer receipt (see completion evidence below).

The earlier cancelled attempt still returned 4999 (processing) in a read-only provider preflight query. It was not treated as paid. The local authenticated gateway probe used nonexistent IDs and is routing evidence only.

No synthetic success callback or manual-paid update was used. The provider's failure reason does not establish why the sandbox number failed to respond; successful payment needs a provider-supported responding test flow.

## Evidence

- [Provider result and stock/finalization checks](ord05-retry/result.json)
- [Restored failure screenshot](ord05-retry/provider-failure.png)
- [Checkout regression results](ord05-retry/checkout-tests.log)
- [Frontend build results](ord05-retry/frontend-build.log)

## User-requested phone retry

A single additional sandbox STK request was accepted for the user-specified phone ending 8457: order 2002 (ORD-798237B8), intent 44, KES 350. Initial status requires_action. Awaiting genuine provider result; no successful payment or stock allocation claimed. This run's synthetic cart/product fixtures remain available while the payment attempt is pending and require cleanup after its terminal result.

## KSh 1 testing preference

The user requested KSh 1 for testing. The prior intent 44/order 2002 was cancelled locally and its synthetic cart was removed. A new isolated synthetic item and free QA pickup method produce an actual KSh 1 order total, with no payment amount override or changes to regular catalog prices/fees. Order 2003 (ORD-7FF17F50), intent 45, phone ending 8457: sandbox initiation accepted (HTTP 201), requires_action. Successful provider confirmation is still pending. Fixtures remain for this pending attempt; cleanup is required on terminal result. Future payment tests should use KSh 1 unless the user requests otherwise.

[Request metadata](ord05-retry/one-shilling.json)

## ORD-05 completion

The genuine callback for intent 45 returned ResultCode 0 and receipt UJTI203HXA. Callback amount, payment intent and order total all match KSh 1; request identifiers and phone match. Order 2003 (ORD-7FF17F50) is paid and finalized through the customer browser.

Variant 23505 deducted one unit from branch inventory row 64279 (2 → 1). The exact allocation is stored on the order item; repeating finalization returned HTTP 200 with stock still 1. This synthetic inventory row uses branch location without a store listing. The customer receipt page shows PAID, KSh 1, and the correct order/item. An email send timestamp is recorded; external inbox delivery was not independently verified.

The QA product and free QA shipping option are now inactive. The paid sandbox order, successful payment and one-unit stock movement remain as truthful evidence; no refund transfer or real medicine supply was performed. Earlier pending/failed descriptions above are historical and superseded by this successful run.

- [Matched callback/order/stock evidence](ord05-retry/one-shilling-success.json)
- [Customer receipt screenshot](ord05-retry/one-shilling-paid.png)
