# Consultations: doctor and pediatrician

**30 October follow-up:** Pediatric payment is now genuinely confirmed by receipt UJUI207MTB / intent 51. CONS-8AF578 completed with an approved prescription and one KSh 0.90 earning. Current consultation sign-off is 17/18, including all 7 pediatric checks at their documented layers; doctor CON-04 remains pending. [Latest evidence](../2026-10-30/pediatric-journey.md). Earlier results below are historical.

Testing started 29 October and continued 30 October 2026 (Africa/Nairobi).

## Result

16 of 18 checklist scenarios passed at the layers described below. CON-04 and PED-02 remain blocked on successful provider payment confirmation. Local application journeys used explicitly labelled simulated payments; these do not establish a successful Safaricom payment.

Safaricom accepted a genuine sandbox STK request for KES 500 (consultation payment intent 48). Status sync subsequently returned **“No response from user.”** The intent is failed and has no consultation. The public callback route was reachable: unsigned requests returned 403 and authenticated incomplete requests returned 400. This consultation result is separate from the existing ORD-06 Paybill confirmation block.

## Verification

- **40 consultation tests passed**, including a real two-thread database claim race and ASGI WebSocket membership/revocation checks. See `consultations/final-consultation-tests.log`.
- **137 combined consultation, order, and prescription tests passed** before the final consultation-only additions; the final 40-test run covers the subsequent consultation changes. See `consultations/final-regression-tests.log`.
- **1 onboarding test passed**, exercising both doctor and pediatrician application, approval/provisioning, activation, login, and dashboard access. See `consultations/onboarding-tests.log`.
- **6 restricted callback gateway tests passed**. See `consultations/gateway-tests.log`.
- Frontend TypeScript and production build passed. See `consultations/frontend-build.log`.
- Both generated prescription PDFs were rendered and visually inspected after fixing clipping. Full names, instructions, quantities, signatures, and consultation references are readable; pediatric output includes the guardian. A regression test verifies long content and multiple pages.

## Checklist evidence

| Scenario | Result | Evidence layer |
|---|---|---|
| CON-01 | Passed | Automated profile/documents/availability/payout; both roles approved, provisioned, activated and logged in through API tests |
| CON-02 | Passed | Automated/API booking and public selection eligibility; inactive accounts and pending/suspended clinicians restricted |
| CON-03 | Passed | Configured fee KES 500; browser pediatric fee and genuine doctor STK request amount agree |
| CON-04 | Blocked | Simulated paid finalization is idempotent; unpaid and foreign intent access denied. Successful provider confirmation remains unverified |
| CON-05 | Passed | Authenticated callback amount/replay tests, repeated finalization, real failed STK status sync; no unpaid consultation created |
| CON-06 | Passed | Automated specialty routing and two concurrent doctors competing for one claim; one winner, losing clinician denied |
| CON-07 | Passed | Live API text/files in both directions for both specialties; pediatric customer/clinician browser uploads and authenticated downloads; persistence and ASGI event/access tests |
| CON-08 | Passed | Both live API drafts edited and sent; exact variant retained; notification records; PDF download/render inspection |
| CON-09 | Passed with simulated checkout payment | Both prescriptions approved by pharmacist and carried through customer checkout/finalization with exact order links |
| CON-10 | Passed | Both completed twice; exactly one KES 450 earning each. Doctor browser shows KES 450 |
| CON-11 | Passed | Unrelated access denied; revoked/ineligible clinician restrictions; protected files and WebSocket membership; public profile redaction |
| PED-01 | Passed | Two live guardian profiles displayed; separate edits persisted through API reload and other-guardian access denied |
| PED-02 | Blocked | Child selection, measurements and guardian consent pass; successful provider payment remains pending |
| PED-03 | Passed | Correct Alpha child and guardian shown in pediatrician browser; saved 21.5 kg / 110.5 cm used; snapshot tests |
| PED-04 | Passed | Missing child/age and invalid age/date/measurements rejected; UI consent gates booking; server consent required before prescription issue |
| PED-05 | Passed with simulated payments | Pediatric browser/API chat/files, prescription/pharmacist/checkout linkage, completion and one earning |
| PED-06 | Passed | Automated repeated bookings group by child ID and keep sibling history separate |
| PED-07 | Passed | Other guardian cannot read/use child; unrelated pediatrician cannot access child history |

Measurements are optional under the current form configuration. Supplied measurements must be positive; date of birth cannot be in the future and pediatric age must be 0–18. Consent can remain pending after API booking, but pediatric prescription issue is blocked until the guardian grants it.

## Defects fixed

1. WebSocket chat previously authenticated login without checking consultation membership. Connect, receive, and delivery now check current membership/account/profile eligibility; invalid tokens close cleanly and revoked access closes the socket.
2. Public clinician details exposed private profile, identity, payout and document fields. Public details now use safe booking fields and require active linked accounts; public lists exclude inactive accounts.
3. Chat serialization exposed raw media URLs. Both attachment fields now point to the authenticated endpoint. Raw consultation-message media is denied in development routing and Apache configuration sources. Suspended clinicians cannot download attachments.
4. Customer and clinician chats lacked attachment controls. Both doctor and pediatrician screens now provide shared-file uploads and authenticated downloads with a 10 MB limit enforced on client and server.
5. Decimal child measurements could prevent payment-intent JSON storage. All decimal measurement values are serialized safely.
6. Consultation STK callback overrides lacked callback authentication. Effective URLs now receive the secret and public-HTTPS validation. Added the consultation callback setting and a narrowly scoped gateway alias. Callback handlers authenticate, reject incomplete/mismatched success data, require receipts, and ignore replays after success.
7. Pediatric prescriptions could be issued without guardian consent. Server enforcement now matches the screen's restriction. Customers cannot set clinical status or grant consent through a generic clinical update.
8. Completing through PATCH could bypass earnings. Both completion paths now share transactional, idempotent completion, and earnings use the paid fee if the profile fee changes later.
9. Concurrent doctors could overwrite an open queue claim. Claiming now locks the row and rechecks eligibility/assignment; a competing clinician receives a denial.
10. Pediatrician workspace generated height, growth classification, contact and vaccination placeholders. It now uses saved measurements/snapshots and marks missing information as not recorded. Unsupported growth classification was removed. Doctor profile placeholders were also removed.
11. Dashboard prescription links depended on note text/reference parsing. Existing backend consultation IDs now determine the matching prescription.
12. Prescription PDFs clipped long lines, truncated medicine information and omitted quantities. Wrapped, paginated output includes quantities and full instructions.

No database migration is required. Apache configuration changes are prepared in the repository; deployment to live servers was not performed.

## Synthetic records and stock

| Role | Consultation | Clinician Rx | Dispensing Rx | Medicine order | Net earning |
|---|---|---:|---:|---|---:|
| Doctor | CONS-EE8CBC (34) | 28 | 46 | ORD-33DED1F4 (2007) | KES 450 |
| Pediatrician | CONS-DC28FB (35) | 29 | 47 | ORD-141616A6 (2008) | KES 450 |

Consultation intents 46/47 and the two medicine checkout payments are marked **SIMULATED QA ONLY**. No provider transfer was used for those journeys. Synthetic variant 23511 stock changed **4 → 2**, exactly one unit per order despite repeated finalization. The synthetic catalog product was hidden after testing. Records were retained for review.

Detailed evidence: `consultations/live-fixtures.json`, `live-completion.json`, `files-and-child-profiles.json`, `final-state.json`, and `provider-stk-check.json`.

Browser evidence: `consultations/pediatric-booking-form.png`, `pediatric-customer-chat.png`, `pediatric-clinician-chat.png`, and `doctor-earnings.png`.
