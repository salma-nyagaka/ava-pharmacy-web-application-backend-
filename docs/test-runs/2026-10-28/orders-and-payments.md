Follow-up: [29 October — card sandbox payment verified; current result 15/18](../2026-10-29/provider-payment-follow-up.md). Earlier results below are retained as history.

# Orders and payments — 28 October 2026

**14/18 local application scenarios passed at the layers below. Four real integration checks remain blocked. This is not full payment-provider or production sign-off.**

Frontend: `http://localhost:3000`; development API: port 8000. Automated tests use the separate Django test database. Live browser work used only the existing synthetic setup customer, medicine and inventory fixtures. No real payment, medicine supply, external refund or POS push occurred.

## Results

| Check | Result and evidence |
|---|---|
| ORD-01 | Pass — browser increase 2→3 (KSh 600 including fallback shipping), decrease 3→2, refresh retained quantity, Remove produced an empty cart. API quantity/remove/clear/persistence passed. |
| ORD-02 | Pass — API exact-variant merge and all-or-nothing rejection. Invalid items no longer disappear silently. Frontend retains the local cart and displays a merge warning without treating successful login as failed. |
| ORD-03 | Pass — API/service valid/expired/minimum/usage-limit coupons, coupon replacement rather than stacking two coupons, removal, exact-SKU promotion targeting, promotion stacking and order minimums. Promotion-adjusted prices now agree between variant, cart and order snapshot. Unpaid drafts do not consume coupon usage. Coupons apply to the promotion-adjusted subtotal. |
| ORD-04 | Pass — independently checked totals and scoped checkout shipping. A different cart item cannot incorrectly qualify a scoped prescription checkout for free shipping. Browser delivery-method calculation and saved-order totals were also established in INV-02. |
| ORD-05 | **Blocked** — actual Safaricom sandbox payment confirmation remains unverified. Existing credentials alone do not establish completion. Callback authentication secret is currently absent; public authenticated callback setup is needed. Sandbox amount overrides now have no effect in production. |
| ORD-06 | **Blocked** — Paybill configuration/registration incomplete. Controlled callback tests match references and reject wrong amounts. These are not real provider confirmation. |
| ORD-07 | **Blocked** — no configured Flutterwave key or webhook secret. Mocked initiation, redirect, verification and webhook tests pass. Verification now binds amount, currency, transaction ID and stored payment-intent reference. |
| ORD-08 | Pass — API COD checkout commits stock and remains payment-pending; electronic payment is not falsely recorded. |
| ORD-09 | Pass — API cancellation, terminal payment protection, failed-provider response and retry on the same order. A retry creates one new active intent, preserving the failed attempt. |
| ORD-10 | Pass — controlled callback replay yields one success event/notification/push; late failure cannot reverse success. Finalization and stock commitment are idempotent. The earlier INV-02 browser recovery and cancellation evidence remains applicable. |
| ORD-11 | Pass — customer manual-payment bypass closed; unsigned/misconfigured generic and M-Pesa callbacks rejected; another transaction's card reference cannot pay this order; cross-customer payment actions rejected. |
| ORD-12 | Pass — API/service prices re-read from the catalog and inactive parent products rejected. Browser stock removal caused a clear rejection while retaining the previous quantity and total. |
| ORD-13 | Pass — API processing/shipping/delivery, tracking events and notifications. Staff cannot fulfill unpaid electronic orders, fulfill an uncommitted item order, or reopen a terminal order. Trusted status webhooks use the same guards. |
| ORD-14 | **Blocked for real integration at user's request.** Mocked failed outbound-push listing/retry and scheduled retry-command tests pass; no real external order was sent. |
| ORD-15 | Pass — API and previous INV-02 browser cancellation release exact allocated stock once. Staff cancellation now uses the release logic too. Shipped-order cancellation and terminal-order reopening are rejected. Cancelling an already-paid order does not claim a money refund. |
| ORD-16 | Pass for the supported administrative workflow — scoped customer return, invalid refund amount rejection, staff approval, quarantine/non-resale requirement, external refund record, closure and replay protection. Refunds of dispatched/delivered medicines do not return them to saleable stock. No automated provider refund transfer is implemented or claimed. |
| ORD-17 | Pass — API finance payment list/detail, reconciliation and invoices; protected CSV download matches order total/payment state. Refund reasons are saved in the same transaction as the record. |
| ORD-18 | Pass — API unrelated-customer order/tracking/payment/cart actions denied; finance downloads are staff-only. Browser lookup of another synthetic customer's order shows delivery progress but hides medicine, payment and address details. Public events omit internal metadata. Owner login permits full order details. |

## Defects fixed

- Customers could self-confirm payment using the manual provider.
- Generic payment webhooks were open when their secret was empty; raw M-Pesa callbacks lacked authentication.
- The M-Pesa alias returned fabricated success on provider failure, accepted a client amount, allowed requests on terminal orders and created duplicate active requests.
- A production environment could use the sandbox STK amount override.
- Replayed/late notifications repeated paid side effects or reversed a paid order to failed.
- Card verification did not bind the transaction to its payment-intent reference.
- Authenticated cart mutation errors appeared as successful local updates; the cart now reports the server rejection. Loading no longer flashes an empty cart.
- Guest-cart merge silently skipped invalid items; validation is now atomic and the frontend preserves failed merges.
- Catalog promotions were missing from cart/order prices and could leak across sibling SKU pricing.
- Unpaid drafts consumed coupon limits; scoped shipping used unrelated cart items.
- Paid checkout recovery cleared newly added cart items.
- Parent product deactivation was not checked when validating its variant.
- General staff fulfillment updates bypassed payment/finalization/terminal-state guards and cancellation stock release.
- Delivered refunds restocked saleable inventory and repeat refund actions failed instead of returning the existing result.
- Order-scoped return creation ignored the URL order; invalid return amounts and unsupported order states were accepted.
- Returns could be marked refunded without a corresponding order refund record.
- Refund UI implied a provider transfer. It now explicitly records an external refund and saves its reason atomically.
- Public tracking disclosed medicine, contact, address, finance and internal event data after a contact lookup.

## Integration setup still needed

- Set a random `MPESA_CALLBACK_SECRET` in local deployment configuration. The M-Pesa client appends its token to STK and C2B callback URLs automatically. Keep these URLs and server access logs private; use HTTPS. Existing C2B callback URLs must be re-registered after changing the token. Empty configuration deliberately disables callback acceptance and payment initiation readiness.
- Complete authenticated public sandbox callback setup and independently verify an STK sandbox payment and Paybill confirmation. An accepted STK request or a controlled local notification is insufficient.
- Configure the test card provider key and verification secret, then complete its hosted test checkout.
- Keep real POS blocked as requested until a test endpoint and authentication are available.

## Validation

- **193 tests passed** across accounts, products/inventory and orders after the final fixes. This includes provider simulations; it does not establish a real payment.
- Frontend production build passed. Django system checks and backend/frontend whitespace checks passed.
- Logs: [backend tests](orders/backend-tests.log), [frontend build](orders/frontend-build.log).

## Evidence and cleanup

Automated regressions are in `orders/tests/test_payment_security.py`, `orders/tests/test_module_acceptance.py`, the existing order workflow tests, and the inventory acceptance tests. Test/build logs are saved in [orders/](orders/).

Browser evidence: [quantity and total](orders/cart-quantity.png), [stock rejection](orders/cart-stock-rejection.png), [item removal](orders/cart-removed.png), [restricted public tracking](orders/public-tracking.png). Earlier paid checkout/finalization/cancellation evidence: [INV-02](inv02.md), using a controlled simulated notification.

Synthetic variant A's two store rows were restored to **50/30**, the setup customer's cart is empty and the synthetic product is deactivated again. No live test order or payment was created in this run. The tracking order was the pre-existing synthetic review fixture `ORD-B8DA328B`.


## Follow-up — Daraja credentials retrieved

The user signed into Daraja and authorized retrieving the existing `avapharmacy-test` sandbox app credentials. Consumer key, consumer secret, passkey and shortcode were saved to the ignored local `.env`; a random callback-authentication secret is now configured. The file has owner-only permissions. A direct Safaricom sandbox OAuth request succeeded; no token or secret is included in this report. Existing app credentials were retrieved rather than rotated.

**ORD-05 and ORD-06 remain unchecked:** credential authentication does not prove callback delivery or a completed payment. Public HTTPS callback setup and sandbox provider confirmation remain outstanding. Flutterwave still requires the user's sign-in. The user confirmed there is no POS provider/account yet, so ORD-14 remains blocked until one is selected.

Evidence: [credential verification metadata](orders/daraja-credential-verification.json).


## Follow-up — Flutterwave test key retrieved

The user signed into Flutterwave. The existing **V3 Test API key** was retrieved, saved to ignored local `.env` with owner-only permissions, and verified with a successful read-only `GET /v3/banks/KE` request. No key regeneration, live key use, payment or transfer occurred.

The provider's **test webhook URL and secret-hash fields are empty**. There is no existing webhook hash to retrieve. **ORD-07 remains unchecked** until a hosted test checkout and server-confirmed result are established; webhook delivery also needs an HTTPS endpoint and matching verification secret. The earlier missing-API-key blocker is now resolved.

Evidence: [Flutterwave verification metadata](orders/flutterwave-credential-verification.json).
