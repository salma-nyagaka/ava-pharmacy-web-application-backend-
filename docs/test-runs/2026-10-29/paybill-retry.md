# ORD-06 — Paybill registration retry, 29 October 2026

**Historical initial retry — superseded by [registration recovery and callback-delivery results](paybill-registration-recovered.md).**

**Still pending / blocked. No provider-confirmed Paybill payment occurred.** Registration was retried against the existing configured sandbox app and callback tunnel. No production transaction, new sandbox payment, fake callback or manual-paid fixture was submitted in this run.

## Verified

- Environment is sandbox; configured C2B shortcode is `174379`. The STK shortcode is also `174379`. Whether this is the C2B shortcode assigned to this app remains to be checked in the authenticated Daraja simulator; a documentation example is not proof of this app's allocation.
- Existing public tunnel is running and targets the restricted local callback gateway, rather than the full backend.
- Unsigned requests to both public validation and confirmation paths returned **403**, confirming reachability and callback authentication.
- Current configured v1 registration returned HTTP 500, **500.003.1001**, “Service is currently unreachable. Please try again later.” Provider request ID: `135b-4679-8ea6-1c3dca88c6a4370790`.
- A bounded diagnostic against the currently documented v2 endpoint returned the same HTTP 500 and provider message. Provider request ID: `135b-4679-8ea6-1c3dca88c6a4370838`.
- `MPESA_C2B_URLS_REGISTERED` remains **False**. Neither failed response was treated as registration success.

## Code correction

The [official Safaricom C2B documentation](https://developer.safaricom.co.ke/apis/CustomerToBusiness), read in the browser, currently identifies `/mpesa/c2b/v2/registerurl` as the registration endpoint. The client now defaults to v2 through `MPESA_C2B_API_VERSION`; explicit v1 compatibility is retained. Registration now requires an explicit zero success code rather than accepting a response that lacks one. `.env.example` distinguishes the assigned C2B simulator shortcode from the STK shortcode. Existing secrets and the configured shortcode were not changed.

[Registration/payment security regression log](providers/paybill-retry-tests.log). See the end of the log for the final result.

## What is needed next

The Daraja portal is signed out. Its login page is open in the Codex browser, and the user has been asked to sign in or provide the **C2B test shortcode assigned to this app's simulator**. Consumer API credentials already work for the registration request; the app's simulator allocation/product configuration is the unresolved check. It is not yet established whether the provider error reflects service availability, app provisioning, the shortcode, or a callback URL policy.

After verifying that allocation: retry registration once with the verified settings. Only after provider acceptance, mark registration configured and use Safaricom's sandbox simulator to generate a provider callback for a dedicated QA order. Verify exact reference, amount, idempotency, and stock; test incorrect and unmatched references without marking orders paid. ORD-06 remains unchecked until this evidence exists.

Evidence: [v1 retry and callback probes](providers/paybill-registration-retry.json), [v2 diagnostic](providers/paybill-v2-retry.json). No callback secret, access token or consumer credential is included.
