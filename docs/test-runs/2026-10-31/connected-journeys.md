# Connected journeys - 31 October 2026

In progress. Awaiting authorization to send sandbox prompts. No new payment requests or simulated successful payments in this run.

- E2E-01: synthetic customer 87 registered, verified and logged in; exact variant 23514 in order 2012 / ORD-7B791366, draft/pending, KSh 1 with free QA pickup. Browser total matches saved order. Stock unchanged before payment.
- E2E-02: prescription 49 / RX-7E5CC4 uploaded, clarification requested/replied, pharmacist approved exact variant 23516. Order 2013 / ORD-599F53F7, draft/pending, KSh 1.
- E2E-03: isolated synthetic doctor 32 prepared with KSh 1 fee; regular fees unchanged. Booking/payment pending.
- E2E-04: existing genuine consultation and prescription 48 retained. Medicine is in guardian cart; replacement draft paused by rapid-checkout safeguard. No new payment sent.
- E2E-05: prior local lab evidence retained; no new completion claim.
- E2E-06: awaiting authorization for first prompt decline followed by approved retry on order 2012. Original unpaid drafts 2009-2011 cancelled without consuming stock.

Checkout ignored saved shipping service and could display a different quote. Fixed restoration of the saved active shipping method for the selected delivery type. Frontend production build passed; browser retest shows KSh 1 and free pickup.

Sandbox OAuth and callback routing preflight passed. Failure-only unmatched callback probes do not establish successful provider payment. Fulfillment, stock/finance matching and final sign-off remain pending.

Evidence: [prepared records](connected-journeys/prepared-drafts.json), [preflight](connected-journeys/provider-preflight.json), [build](connected-journeys/frontend-build.log), [checkout](connected-journeys/new-customer-checkout.png).

## 1 November sandbox resend result

User authorized cancellation and one fresh KSh 1 request. Local intent 51 was cancelled; replacement intent 52 / PAY-4CA0D5235B7B was accepted. User reported no prompt on both attempts. Provider status now confirms intent 52 failed with "No response from user." No successful payment confirmed. No further prompt sent. Genuine payment-dependent connected journeys remain blocked by sandbox prompt delivery; no simulated success substituted. [Status evidence](connected-journeys/new-customer-resend-status.json).

## Genuine customer payment and synthetic fulfillment confirmed

Intent 53 / PAY-93CC7B6C3A17 succeeded for KSh 1 with provider receipt UK1I20HYZ4. Order 2012 / ORD-7B791366 has exactly one successful payment; intent 52 failed and 51 was cancelled. Two finalization calls succeeded with one finalization event. Exact variant 23514 inventory 64284 moved 4 to 3 once. Synthetic fulfillment progressed processing, shipped, delivered; customer reads delivered/paid and committed stock. Seven-day finance CSV includes the order; one-day export correctly excluded its earlier creation date. No real medicine supplied or delivered. E2E-01 local application journey passes with genuine sandbox payment and controlled registration verification mailbox. E2E-06 payment failure/retry portion passes; return/refund/support portion remains pending. Prescription order payment approval requested next.

[Provider evidence](connected-journeys/new-customer-approved-status.json), [fulfillment evidence](connected-journeys/customer-fulfillment.json).

## Genuine prescription payment and completion

RX-7E5CC4 / 49 clarification and pharmacist approval led to order ORD-599F53F7 / 2013. Intent 54 succeeded for KSh 1 with provider receipt UK1I20IJMO. Two finalizations produced one finalization event; exact variant 23516 inventory 64285 decreased 4 to 3 once. Order delivered/paid and prescription dispatch delivered, using synthetic fulfillment only. Finance export includes the order. E2E-02 rerun now has genuine sandbox payment proof. Pediatric draft 2014 / ORD-1DD38A84 is ready at KSh 1 after normal risk cooldown; no pediatric medicine prompt sent yet. [Evidence](connected-journeys/prescription-completion.json).

## Pediatric medicine payment and completion

Intent 55 / PAY-4BABA616879B succeeded for KSh 1 with genuine provider receipt UK1I20IVWS. Guardian 75, child 6, granted consent, completed consultation CONS-8AF578 / 38, clinician prescription 30 and dispensing prescription RX-7D2A2E / 48 remain linked to order ORD-1DD38A84 / 2014. Existing genuine consultation payment UJUI207MTB retained. Medicine order paid/delivered, prescription dispatch delivered, finance export matched. Two finalization calls produced one finalization event and one stock deduction: exact variant 23512 inventory 64283 moved 2 to 1. One existing clinician earning 12 for KSh 0.90; no duplicate earning. Fulfillment synthetic; no real medicine supply/delivery. Prior child/sibling identity isolation evidence remains in the pediatric journey report. [Payment and fulfillment](connected-journeys/pediatric-completion.json), [identity and earnings](connected-journeys/pediatric-linkage.json).

## Genuine doctor booking payment

Doctor intent 52 / CPAY-FE562DABC31D succeeded for KSh 1 with provider receipt UK1I20IYUB. Normal payment finalization created CONS-83F95C / 39 for isolated QA doctor 32 and patient 75. Chat/prescription/medicine completion and earnings reconciliation remain in progress. [Payment proof](connected-journeys/doctor-payment-confirmation.json).

## Doctor medicine, completion and payout reconciliation

Medicine intent 56 succeeded for KSh 1 with receipt UK1I20J2W8. CONS-83F95C → clinician Rx 31 → dispensing Rx 50 → ORD-43CBF6BB / 2015 completed with paid/delivered order, delivered prescription dispatch and exact stock 4→3 once. Consultation completed with one earning 13 / KSh 0.90. Payout 5 / PAY-25D0E1 recorded paid and matched using separate maker/checker QA roles. This is explicitly an administrative record; no actual payout transfer occurred. [Medicine evidence](connected-journeys/doctor-medicine-completion.json), [payout evidence](connected-journeys/doctor-payout.json).

## Return and support follow-through

Customer order ORD-7B791366 return 1 approved then received into non-resale quarantine; saleable stock remains 3. Support ticket 3 is in progress with a public note explaining external refund is pending. No refund executed or falsely recorded as paid. E2E-06 remains incomplete pending genuine external refund proof and support resolution. The current refund endpoint records external refunds administratively and does not execute a provider refund. [Evidence](connected-journeys/return-support.json).
