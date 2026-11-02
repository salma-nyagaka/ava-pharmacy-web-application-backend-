# Pediatric journey follow-up — 30 October 2026

## Current outcome

**PED-01–07 now pass at the recorded layers. PED-02 has a genuine provider-confirmed KSh 1 sandbox payment.** The newly paid guardian → child → consent → consultation → prescription → completion journey is complete. Medicine checkout/payment for this new prescription was not requested and is not claimed; the broader E2E-04 medicine-order chain remains partial.

Receipt **UJUI207MTB** matches consultation payment intent **51**, genuine callback ResultCode **0**, callback amount **KSh 1**, merchant/checkout request IDs and the approved phone ending **8457**. The provider created exactly one linked consultation: **38 / CONS-8AF578**, guardian **75**, child **6**, pediatrician **31**, with consent **granted**. No payment was manually marked paid.

The clinician started and completed this booking in the browser. Both participants viewed and messaged the same booking. Draft prescription **30 / PED-RX-3517FD** was edited without a new identity, sent, and linked to dispensing prescription **48**, which a review pharmacist approved for exact synthetic variant **23512**, quantity 1. The PDF was downloaded, rendered and visually checked. The guardian's saved record shows **completed**, and exactly one earning (**12 / KSh 0.90**) exists after repeated completion. Repeated paid finalization returns consultation 38.

| Attempt | Authorization / result |
|---|---|
| Intent 49 / KSh 1 | Initial authorized request failed with “DS timeout user cannot be reached”; no linked consultation. |
| Intent 50 / KSh 1 | User-requested resend remains unconfirmed (`requires_action`), with no receipt or linked consultation. Retained for reconciliation; not used to establish this pass. |
| Intent 51 / KSh 1 | User explicitly requested another resend. Genuine success callback and supplied receipt UJUI207MTB matched; consultation CONS-8AF578 completed. |

[Provider match](pediatric/provider-confirmed.json), [live handoff](pediatric/paid-handoff.json), [completion / idempotency](pediatric/paid-completion.json), [cleanup](pediatric/paid-cleanup.json), [browser earnings](pediatric/paid-earnings.png), [guardian completed booking and approved prescription](pediatric/guardian-completed.png).

The earlier failure/processing artifacts remain historical evidence. `provider_reference=0` on an acknowledgement is not a payment receipt. This pass uses the genuine receipt and callback for intent 51. The QA clinician stays active while earlier intent 50 remains outstanding, allowing normal handling of a genuine late provider outcome. Cancelled identity fixtures 36/37 are unrelated and unpaid. Regular clinician fees remain unchanged.

## Fixes and verification

- **Child identity and history:** clinical profiles, consultation history, prescription history, and conversation grouping now use child/consultation IDs rather than matching names. Browser verification shows two identically named children separately: child 6 is age 4, 16 kg / 102 cm; child 7 is age 7, 24 kg / 120 cm. Opening the younger child's history does not show the sibling's record. The most recent profile snapshot is retained when grouping repeated consultations.
- **Guardian consent:** the checked consent is submitted as `guardian_consent` in the pediatric payment payload and preserved through payment confirmation and finalization. It no longer relies on a separate, silently ignored post-payment request. API bookings without affirmative consent still remain pending consent; pediatric prescription issue remains blocked until granted.
- **Clinician selection:** added a visible pediatrician selector with the clinician's own fee. The waiting screen now describes the selected pediatrician accurately instead of claiming that all pediatricians were notified.
- **Message ownership:** assigned pediatrician lists now include the guarded guardian ID, and chat identifies the guardian by sender ID instead of display-name equality. The open doctor queue still redacts this identifier.
- **Earnings precision:** net earnings retain cents. KSh 1 less 10% commission produces **KSh 0.90**, rather than rounding up to KSh 1.
- **Provider transport recovery:** an actual upstream connection drop caused a payment-status HTTP 500. Token/payment transport errors are now converted to recoverable provider errors. Status sync retains the pending payment and returns HTTP 202 rather than claiming success or failing the page.
- **History display:** retained raw consultation timestamps so dates display 30 October 2026 instead of being reparsed as 2001. Unknown vaccination schedules display “Not recorded,” not an invented vaccine-due count.

## Evidence by scenario

| Scenario | Result / layer |
|---|---|
| PED-01 | Existing guardian child creation/edit/reload checks retained; browser selected the correct registered child from four synthetic profiles. |
| PED-02 | **Passed — genuine provider confirmation.** Receipt UJUI207MTB and KSh 1 amount matched intent 51; both dashboards show consultation 38 with child 6 and granted consent. |
| PED-03 | Browser demonstrates separate same-name profiles with distinct measurements and histories. Automated paid finalization checks preserve child/guardian snapshots. |
| PED-04 | Automated missing/invalid child details, consent persistence, absent-consent handling and prescription restriction pass. Unpaid finalization remains denied. |
| PED-05 | Earlier live simulated consultation → prescription → pharmacy/checkout → completion evidence remains valid. Added an isolated full pediatric application regression: authenticated simulated callback → correct child and consent → participant chat → exact prescription/guardian handoff → completion twice → one KSh 0.90 earning. **This automated callback is not evidence for live intent 50.** |
| PED-06 | Same-name child grouping and separate histories verified in browser and backend tests; repeated records use stable child IDs. |
| PED-07 | Existing other-guardian and unrelated-pediatrician access-denial regressions pass. |

## Validation

- **124 consultation/order tests passed**, including the new pediatric journey, consent, same-name history, earnings precision and provider-disconnection regressions. [Log](pediatric/regression-tests.log).
- Frontend TypeScript and production build passed. [Log](pediatric/frontend-build.log).
- No database migration is required.
- [Redacted fixture metadata](pediatric/fixture.json), [payment state](pediatric/payment-state.json), [authorized resend](pediatric/resend.json), [latest status sync](pediatric/resend-sync.json).
- Browser evidence: [guardian booking](pediatric/guardian-booking.png), [first payment failure](pediatric/payment-failed.png), [same-name child history](pediatric/same-name-child-history.png).

## Fixture boundaries

Guardian 75 owns children 6 and 7, which deliberately have identical names and different ages/measurements. Cancelled consultations 36/37 were created explicitly as **unpaid identity/history fixtures**; neither is linked to intent 49 or 50. They were not issued prescriptions or earnings. Existing completed pediatric consultation 35 / CONS-DC28FB and its simulated medicine order remain separate historical application evidence.

Provider-confirmed pediatric booking, live prescription handoff and completion now pass using intent 51. Synthetic catalog product 22371 is inactive again; its stock remains 2 because no medicine purchase was made. Earlier intent 50 remains outstanding and must be reconciled separately. Doctor CON-04 and Paybill ORD-06 remain unchanged. The new prescription has not gone through medicine checkout, so E2E-04 remains partial. No production deployment or payout transfer is claimed.
