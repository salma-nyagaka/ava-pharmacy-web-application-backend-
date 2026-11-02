# ORD-06 — callback-delivery investigation

29 October 2026. **Still blocked / incomplete.** No Safaricom payment confirmation or receipt has arrived for test intents 47/48. Both remain `requires_action`; the KSh 1 and KSh 2 orders remain unpaid, with stock unchanged at 4.

## This continuation

1. Confirmed sandbox configuration: C2B 600980, API v2, registration previously accepted; current tunnel/gateway are running. No callback payload exists for either test intent.
2. Tested query-free callback URLs while retaining the same backend secret check. Public valid-credential probes reached validation and returned ResultCode 1 for the deliberately unknown reference; invalid credentials returned HTTP 403. Thus this was not an authentication bypass or a fake payment confirmation.
3. Safaricom rejected the alternate URL format with HTTP 500 / `500.003.1001` on both v2 and v1. The unused URL-format/routing changes were removed; the previously accepted query-authenticated URLs remain configured.
4. Daraja's signed-in URL Management view requires an additional M-PESA Business Admin/Manager username and OTP to reveal registered URLs. Daraja login alone does not expose that information. No organization credentials were entered and no URL deletion/update was performed through that portal.
5. Retried the original accepted configuration before another sandbox payment attempt. This registration call again returned HTTP 500 / `500.003.1001`, “Service is currently unreachable. Please try again later.” Request ID **135b-4679-8ea6-1c3dca88c6a4377025**. The script stopped before issuing a new payment simulation.
6. Retained credential redaction in gateway diagnostics and fixed lost diagnostic events when a client disconnects before reading the response. Callback routing and backend authentication remain unchanged.

Registration is **intermittent**: earlier provider responses explicitly accepted it, but this latest retry failed. The registration flag retains the earlier verified registration; it is not being used as evidence of payment confirmation. The absence of callbacks after earlier accepted simulations is still unresolved. A provider-side delivery trace or clarification of sandbox callback-hosting restrictions is needed; no definite root cause is inferred from the generic HTTP 500.

## Evidence

- [Latest original-format retry](providers/paybill-delivery-retry.json)
- [Query-free v2 rejection and authentication probes](providers/paybill-path-registration.json)
- [Query-free v1 rejection](providers/paybill-path-v1-registration.json)
- [Earlier accepted registration and simulation evidence](paybill-registration-recovered.md)
- [20 registration/authentication tests passed](providers/paybill-delivery-auth-tests.log)
- [5 gateway tests passed](providers/paybill-delivery-gateway-tests.log), including credential redaction and recording a disconnected client's result.
- [Support-ready draft](safaricom-c2b-support-draft.md). This is a local draft, not a submitted support case.

The dedicated synthetic product and zero-fee delivery option are inactive again. Existing unpaid order/intents remain for a late callback. No manual-paid fixture or fabricated callback was applied, and no provider-confirmed payment or stock-finalization pass is claimed. **ORD-06 stays unchecked.**
