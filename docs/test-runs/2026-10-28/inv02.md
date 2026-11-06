# INV-02 — exact store stock deduction and cancellation

28 October 2026 · **Pass for the application flow with a controlled simulated payment notification.** Real M-Pesa/provider confirmation is not established by this run and remains in ORD-05/ORD-06 payment testing. No real payment, goods delivery or refund took place.

Frontend: `http://localhost:3000`; backend: existing local API on port 8000. Order: **ORD-83D5AC44**, ID 1993. Customer: dedicated `setup28.customer@avapharmacy.test`. Product/variants are clearly labelled synthetic QA fixtures. External order push was verified unconfigured before testing.

## Browser journey and evidence

1. Signed into the existing QA customer and selected exact variant A, SKU `MODULE2-QA-20261027-A`, quantity 2. Completed synthetic OTC screening and shipping details.
2. Created the checkout draft in the browser. Verified stock remained at its baseline before finalization.
3. Prepared a test payment-intent fixture and delivered a normal local payment-webhook request. Payload and receipt explicitly identify `INV-02` and `QA-INV02-SIMULATED-20261028`; this was a controlled test notification, **not a Safaricom confirmation**. No production payment bypass or new public simulation endpoint was introduced.
4. Recovered the paid order through `/checkout?order_id=1993`. The browser displayed the two purchased packs and the saved order totals even though payment processing had removed the cart entries. Selected shipping method fee was KSh 150; subtotal KSh 200; total KSh 350.
5. Clicked **Complete & Place Order**. Browser displayed confirmation for ORD-83D5AC44. Verified database allocation to the exact store row.
6. Opened the order from My Orders. Tested **Keep order**, reopened cancellation, then confirmed cancellation. Browser displayed **Order cancelled**, and the cancel action disappeared.
7. Repeated cancellation and finalization via authenticated HTTP: both returned 400 for the cancelled order; no further stock changes occurred.

| Stock record | Before | Finalized | Cancelled |
|---|---:|---:|---:|
| Variant A / store 1 | 50 | **48** | **50** |
| Variant A / store 2 | 30 | 30 | 30 |
| Variant B / store 1 | 20 | 20 | 20 |
| Variant B / store 2 | 10 | 10 | 10 |

Stock movement history contains exactly one sale of -2 and one release of +2 for this order, both against A/store 1. Final `inventory_committed` is false. There is no durable pre-finalization stock hold; availability is checked again at finalization.

## Defects fixed

- **Repeated finalization cleared a newer cart and repeated side effects.** Already-committed eligible orders now return their saved representation before stock revalidation, cart clearing, events or fulfillment actions. Regression verifies a newer B cart item survives and only one finalization event exists.
- **Delivery quote differed from the submitted method.** Checkout showed the site-wide KSh 300 fee while the submitted method charged KSh 150. This also made draft comparison continually fail. The quote now respects the selected method and its own free-delivery threshold; paid recovery uses saved order totals.
- **Duplicate draft requests.** Checkout now shares an in-flight draft request instead of issuing concurrent replacements.
- **Paid checkout depended on an emptied cart.** Confirmed order review now uses saved order-item snapshots and supports an explicit owned order ID for recovery; the API retains ownership checks.
- **Restoration lost confirmed payment state.** Payment-method initialization no longer resets an already-paid order to idle.
- **Unchecked address saving was ignored for the first address.** Checkout now respects the save/default-address choices.
- **Native cancellation prompt blocked reliable interaction.** Replaced with an in-page Keep order/Confirm cancellation control; both paths exercised.

## Validation

**118 product/order tests pass**, including a new complete checkout/payment-notification/finalization/cancellation regression. It checks pre-confirmation denial, invalid webhook-secret denial, repeated notifications, exact stock balances, paid-finalization replay, preservation of a newer cart, one finalization event, and cancellation replay. External payment is simulated in this regression.

Frontend TypeScript/production build, Django checks and scoped whitespace checks pass.

- [Backend log](inv02/backend-tests.log)
- [Frontend build log](inv02/frontend-build.log)
- [Baseline](inv02/before.json)
- [Explicit payment-test origin and pre-finalization stock](inv02/payment-fixture.json)
- [Exact committed allocation](inv02/committed.json)
- [Final state, movements and replay responses](inv02/final-state.json)
- [Paid order review](inv02/review.png)
- [Browser confirmation](inv02/confirmation.png)
- [Browser cancellation](inv02/cancelled.png)

## Cleanup

Stock restored to A=50/30 and B=20/10; synthetic product deactivated and test cart cleared. Two replacement drafts created while reproducing the quote bug were cancelled, and three temporary synthetic addresses were removed. The labelled cancelled test order and its simulated payment record remain as evidence. No real refund is claimed.

Products and inventory now has **14/15 application checks passed**. INV-08 remains blocked at the user's request. Real payment-provider completion stays unverified under the Orders/payment module rather than being inferred from this inventory test.
