# Lab services acceptance — 30 October 2026

All nine LAB scenarios and E2E-05 pass at the layers below in the local development environment. Synthetic QA accounts, facilities, appointments, documents and results only; no clinical service or online lab payment was performed. The proposal was used alongside the checklist to assess the implemented booking and collection workflow.

## Evidence by scenario

| Check | Layer and result |
| --- | --- |
| LAB-01 | Automated public partner application with required documents/consents, admin verification, account provisioning and activation passed. Live API facility submission, synthetic document upload, verification and re-verification passed using existing verified QA partner 5. New partner onboarding was not repeated manually in the browser. |
| LAB-02 | Live API approved facility 4 with test 8 and technician profile 8; customer browser showed the approved test at KSh 150. Automated tests reject missing/incorrect offerings, cross-partner/facility assignments and revoked staff access. |
| LAB-03 | Live API walk-in request **LAB-217755 / id 2**: correct patient, test, saved KSh 150 quote, facility 4, technician user 83, pending payment and reference. Progressed through collection, processing, result publication and completion. |
| LAB-04 | Customer browser home request **LAB-395DA4 / id 1**, synthetic address/instructions and preferred 3 November 2026 11:00; admin API assigned facility 4, pharmacist 79 and technician 83. Technician browser displayed the matching details. |
| LAB-05 | Patient browser generated a code; assigned technician browser verified it, creating the collection audit and notification. Automated tests cover wrong/expired/other-request/replayed codes, persistent five-attempt lockout, regeneration and concurrent verification. Only one concurrent attempt succeeds. |
| LAB-06 | Home journey passed in technician browser: awaiting sample → sample collected through code verification → processing → result ready through upload → completed. Audit history identifies each actor and transition. Latest audit entries now appear immediately in update responses. |
| LAB-07 | Technician browser published `synthetic-lab-result.pdf` with explicit synthetic summary/recommendation. Patient browser viewed and downloaded it. Both API and browser downloads match source SHA-256 **12875f77f7733fa82de66e5b9e464e932943523d78590248c26ea736e2a9fae1**. Two result notifications match the two completed references. New notification links open `/account/lab-tests`. Notification creation was verified; external email receipt was not independently confirmed. |
| LAB-08 | Patient browser exercised Keep request and Confirm cancellation for **LAB-C7A5D5 / id 3**; status cancelled and payment pending. Automated tests reject paid/collected self-cancellation, invalid transitions and completion without a result; suspended facilities cannot collect/publish. Admin payment changes are audited explicitly as administrative records. Online lab payment is not offered in this implementation; the form now explains payment is arranged after booking. No provider-success claim or refund is inferred. |
| LAB-09 | Automated object access checks deny another patient, partner and unrelated/same-facility technician; coordinators do not receive clinical results. Invalid MIME, disguised PDF content, oversized files and duplicate/concurrent uploads are rejected. Raw result and professional-document media routes return 404; authorized document/result downloads use protected endpoints. |

## Fixes and additions

- Saved the booking's quoted test price so later catalog edits do not change it; added lab migration **0012_labrequest_quoted_test_price**, applied locally. Legacy bookings with no saved quote retain their existing fallback because their original price cannot be reconstructed reliably.
- Limited public tests and new bookings to approved active offerings and partners; tightened assignment, queue privacy, nested result access and suspension checks.
- Added protected technician-document downloads and denied direct public media paths for lab results and partner/facility/technician documents. Apache staging/production source configurations were updated; deployment enforcement has not been verified on a hosted server.
- Added database row locks to serialize code use and result publication; persisted failed code attempts and invalidated codes on reassignment/cancellation.
- Preserved staff/offering history on partner/facility suspension instead of deleting it.
- Added patient cancellation with an inline confirmation, accurate cancelled copy, payment-policy copy, administrative payment audit entries, current audit responses and correct notification destinations.
- Added acceptance/security/concurrency tests covering the fixes. Existing unrelated workspace changes were preserved.

## Validation and artifacts

- [Regression output](lab/regression-tests.log): **28 tests passed** in the full lab suite plus notifications discovery; PostgreSQL-backed concurrency checks included.
- [Frontend build](lab/frontend-build.log): TypeScript/Vite production build passed.
- `manage.py makemigrations lab --check --dry-run`: no missing lab migrations.
- [Live API evidence](lab/live-api-evidence.json), [patient completed result](lab/patient-completed.png), [technician completion and audit](lab/technician-completed.png).

Temporary catalog test 8 is now inactive. Facility 4 and the three historical requests/results remain for inspection; shared QA staff and partner were retained. E2E-05 is signed off for this local pay-later application journey, with partner onboarding covered by automated tests and facility approval by live API. Production deployment, real lab operations and external notification delivery remain outside this sign-off. Existing doctor CON-04, Paybill ORD-06 and POS blockers are unchanged.
