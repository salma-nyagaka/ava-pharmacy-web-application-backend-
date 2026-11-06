# ORD-06 — registration recovered; provider confirmation pending

Latest follow-up: [callback-delivery investigation and renewed HTTP 500](paybill-delivery-investigation.md).

29 October 2026. **The original registration/setup block is fixed. ORD-06 remains incomplete because no provider payment callback arrived.** Safaricom accepted sandbox payment simulations; acceptance alone is not evidence of a completed payment.

## Setup corrections verified

The user signed in to Daraja. The selected `avapharmacy-test` app's consumer key matches the backend configuration (compared without storing credentials in evidence). Its C2B simulator supplies **600980**; the generic STK business shortcode remains **174379**. The backend had incorrectly reused 174379 for Paybill/C2B. `MPESA_C2B_SHORTCODE` and `MPESA_PAYBILL_NUMBER` now use 600980 in the sandbox; STK shortcode, passkey and consumer credentials are unchanged.

The old callback gateway/tunnel stopped during testing. The public URL returned **ERR_NGROK_3200**, with neither local gateway port 8033 nor ngrok API port 4040 running. Both were restored as detached local processes. The current callback base is **https://ac3f-41-79-237-222.ngrok-free.app**. Only the existing payment callback gateway is exposed; this does not expose Django's general API or admin UI. Inspection remains disabled. Public unsigned validation/confirmation probes return **403** and `/admin/` returns **404**. A separately labeled authenticated local probe returned HTTP 200 / ResultCode 1 for an intentionally unknown reference.

Both **v1 and v2 registration now succeed** on the restored URL with shortcode 600980. Safaricom returns **ResponseCode `00000000`, ResponseDescription `Success`**, with provider conversation IDs. The client now recognizes this explicit all-zero success code as well as `0`, and still rejects missing/nonzero codes. The configured version is **v2**, as identified in the [official C2B documentation](https://developer.safaricom.co.ke/apis/CustomerToBusiness); v1 remains an explicit compatibility option. `MPESA_C2B_URLS_REGISTERED=True` was set only after actual provider acceptance.

All three callback base URLs in the ignored `.env` now use the restored tunnel, including the STK callback address. Callback authentication remains enabled and its secret is absent from reports/log artifacts. This is temporary local test hosting, not a production deployment or permanent webhook service.

## Payment attempts and current result

| Scenario | Dedicated reference | Provider request | Actual application result |
|---|---|---|---|
| Correct payment | Order **2005 / ORD-20CDFB9E**, intent **47**, reference **AVA-ORD-20CDFB9E**, total **KSh 1** | Safaricom v1/v2 sandbox accepted a KSh 1 simulation using its virtual phone 254708374149. | **No callback payload or receipt received.** Order remains pending / requires_action; no stock allocation or finalization performed. |
| Incorrect amount | Order **2006 / ORD-874A0705**, intent **48**, reference **AVA-ORD-874A0705**, total **KSh 2** | Safaricom accepted a KSh 1 simulation, including a v2 diagnostic with numeric shortcode/phone types matching its sample. | **No callback payload received.** Order remains pending / requires_action; never falsely marked paid. Application mismatch rejection is independently covered by passing regressions. |
| Unmatched reference | **QA-NOMATCH-A9D827** | Safaricom accepted sandbox simulation. | No provider confirmation request reached the gateway; a full provider unmatched-callback pass is not claimed. Application rejection was verified with a labeled local validation probe and regression tests. |

Earlier accepted requests occurred while the old tunnel was offline. They were not counted as successful payments. Requests were then repeated against the restored, registered URL; both v1 and v2 simulation endpoints returned acceptance. Bounded delivery windows included 90-second and 120-second checks after recovery. Current gateway evidence contains our explicit reachability probes and **no provider confirmation delivery**. The unresolved cause of non-delivery is not established; registration success and public reachability do not prove Safaricom dispatched a callback.

No callback was fabricated, no manual-paid payment was substituted, and no provider conversation ID was presented as an M-Pesa receipt. The earlier prescription simulated payment, order 2004, remains separate from this provider test.

Dedicated product **22369 / PAYBILL-QA-20261029**, exact variant **23510**, inventory **64281** remains at **4**, with no deduction. Product and zero-fee QA delivery method **3** were deactivated after the run to remove temporary public test options. Unpaid orders/intents remain available for matching a late callback; reactivate the dedicated fixture before attempting stock finalization on a later retest. The restricted callback services remain running for testing.

## Evidence and validation

- [Assigned C2B simulator shortcode](providers/c2b-assigned-shortcode.png)
- [Restored gateway/tunnel probes and genuine v1 registration](providers/paybill-restored-registration.json)
- [Genuine v2 registration success](providers/paybill-live-v2-registration.json)
- [Provider v2 correct-amount simulation acceptance](providers/paybill-valid-provider-simulation-v2.json)
- [Provider negative simulation acceptances](providers/paybill-negative-provider-simulations-restored.json), [numeric v2 diagnostic](providers/paybill-v2-numeric-simulation.json)
- [Authenticated local reachability probe — not a payment](providers/paybill-auth-reachability.json)
- [Final delivery window](providers/paybill-delivery-result.json), [current orders/intents/stock](providers/paybill-current-state.json)
- [Gateway event evidence](providers/paybill-gateway-events.json)
- [**77 order/payment tests passed**](providers/paybill-final-regressions.log), [**3 gateway tests passed**](providers/paybill-gateway-tests.log). Django checks and scoped whitespace checks passed.

## Still pending under ORD-06

Receive a provider-generated confirmation, match its M-Pesa receipt, shortcode, exact reference and amount to the correct order, then finalize and verify stock idempotency. Verify provider-delivered mismatch and unmatched callbacks too. Do not check off ORD-06 until this evidence exists. No new user sign-in or additional permission is currently required; the remaining dependency is callback delivery/diagnosis with Safaricom and the callback hosting path.
