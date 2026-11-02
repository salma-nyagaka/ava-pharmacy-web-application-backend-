Superseded payment scope: [M-Pesa-only policy](mpesa-only.md). Card and COD are excluded by the user; the Flutterwave URL update below is no longer required. Previous provider results are retained as test history.

# Provider payment follow-up — 29 October 2026

**Orders: 15/18 scenarios passed at the recorded application/browser/API layers. ORD-05 (STK), ORD-06 (Paybill) and ORD-14 (real POS) remain blocked.** Card checkout now has a real provider-confirmed **sandbox** transaction, rather than only a mocked application test. Production payments and actual refunds are not signed off.

## Card checkout — ORD-07 passed

- Synthetic order **ORD-FBEAE0E8 / 1996**, payment intent **41**, transaction **10580035**.
- Flutterwave V3 **test** key created a hosted checkout. The provider page explicitly stated that all transactions in that environment are mocked. Its documented test card, test PIN and test OTP were used; the card was not saved.
- Native controls could not interact with the hosted iframe, so its visible frame URL was opened directly in a browser tab. The card authorization completed there. This is recorded because it affected the return behavior.
- A direct Flutterwave verification by the exact stored merchant reference returned **successful**, **KES 350**, transaction **10580035**, with a matching reference. No guessed transaction ID, locally fabricated success notification or manual-paid provider was used.
- The browser return omitted transaction parameters. Recovery now resolves the stored intent and queries Flutterwave by its reference, then verifies the returned transaction ID, reference, amount and currency. Regression tests reject recovery of an unrelated reference.
- The corrected return displayed **Payment made successfully**, the two exact variant packs, the saved delivery address, KSh 200 subtotal, KSh 150 shipping and KSh 350 total. Screenshot: [paid review](../2026-10-28/providers/card-paid-review.png).
- A subsequent browser finalization attempt exposed client-side shipping validation clearing an already-paid order's saved area. The frontend now preserves paid-order shipping details and uses the saved order for finalization. Build passed. The provider order was finalized through the live authenticated API. A separate, explicitly simulated paid-order fixture **ORD-3F3589D1 / 1999** then verified the corrected browser button end to end: saved city was retained and **Complete & Place Order** reached `/order-confirmation`. This extra UI fixture is not a second provider payment. [Browser confirmation](providers/ui-recovery-confirmation.png).
- API finalization succeeded; A/store 1 changed **50→48**, A/store 2 stayed **30**. A repeated finalize returned 200 and made no additional stock deduction. [Finalization evidence](providers/card-finalization.json).
- Synthetic cancellation restored **50/30** with one sale of -2 and one release of +2. The confirmed test payment remains recorded as paid; no refund transfer is claimed. [Cleanup](providers/cleanup.json).

Provider verification metadata: [card-provider-verification.json](../2026-10-28/providers/card-provider-verification.json).

## HTTPS callbacks and webhook status

A loopback-only gateway in [payment_callback_proxy.py](../../../scripts/payment_callback_proxy.py) forwards only these payment routes:

- POST `/callbacks/mobile/stk/`, `/callbacks/mobile/validate/`, `/callbacks/mobile/confirm/` → existing authenticated M-Pesa handlers.
- POST `/api/orders/payments/flutterwave/callback/` → existing signature-checked card handler.
- GET `/api/orders/payments/flutterwave/redirect/` → verified card return handler.

All other paths/methods are denied. It does not forward browser login cookies or Authorization headers. Body sizes are limited; query strings, callback secrets, headers and bodies are omitted from gateway logs. Ngrok request inspection is disabled. Current live probes returned **403 for unsigned mobile/card callbacks and 404 for `/admin/`**. Three gateway tests pass.

Safaricom rejected the original callback path because it contained the word `MPESA`; neutral gateway aliases resolved that validation error without changing backend authentication.

**Temporary local callback base:** `https://b865-41-79-237-222.ngrok-free.app`. The earlier free address expired after the interruption and could not be restored on the free plan. No plan upgrade was made. The local gateway and tunnel must be running for callbacks to work; this is not permanent hosting.

The user confirmed saving Flutterwave's test webhook URL and matching secret on 28 October. **The URL must now be updated to the current address, keeping that secret unchanged.** The update was requested during this follow-up. Browser controls were subsequently located in the original runtime, but the provider session is signed out, so the dashboard URL update still needs sign-in. Provider-generated signed webhook delivery remains unverified until that update and a provider resend succeed. This pending delivery check is separate from the successful server-side verification of the card payment.

## M-Pesa — still blocked

- Consumer credentials were verified with Safaricom sandbox OAuth. No production credentials were used.
- STK order **ORD-A6BC700E / 1997**, intent **42**, was accepted by the provider, but no successful callback arrived. Status queries were deferred after provider rate-limit responses. **Accepted initiation is not successful payment evidence.** No new STK charge was initiated during the 29 October continuation.
- Paybill registration on the current neutral callback URLs returned **HTTP 500**, error `500.003.1001`, **Service is currently unreachable. Please try again later**. A second API-version diagnostic returned the same provider error; registration is not marked complete. [Responses](providers/paybill-registration.json).
- M-Pesa retries were stopped to respect provider throttling. STK and unused Paybill test orders/intents were cancelled locally during cleanup. Neither consumed stock.
- No POS provider has been selected, as confirmed by the user; real POS remains blocked.

## Validation and cleanup

- **196 tests passed** across accounts, products/inventory and orders: [log](providers/backend-tests.log).
- **3 gateway tests passed:** [log](providers/gateway-tests.log).
- Frontend production build passed: [log](providers/frontend-build.log). Django system checks and whitespace checks passed.
- All three provider-test orders and the separate simulated browser-regression order are cancelled. Product 22366 is inactive again. A/store stock is **50/30**. Card payment evidence is retained; no test record was relabelled as an actual refund.
- `.env` remains ignored by Git and owner-readable only. Provider keys and webhook secrets are absent from this report. Local private fixture files contain access credentials and must not be committed.
