# Prescription acceptance completion — 29 October 2026

**RX-01 through RX-09 pass for the local application, with a controlled simulated payment for RX-06 and E2E-02.** This completes the application testing started in [the initial run](prescriptions.md). It does not establish a new provider-confirmed Paybill payment or a production deployment.

Environment: customer website `http://localhost:3000`, API `http://127.0.0.1:8000`, local PostgreSQL; backend base commit `c47b265` plus current workspace changes. Synthetic setup customer 75 and review pharmacist 79 were used. Frontend changes are in the sibling `ava-pharmacy-web-application-frontend` repository. No real patient information, payment transfer or POS fulfillment was used.

| Scenario | Result | Verification |
|---|---|---|
| RX-01 | Pass | Prescription **44 / RX-E1E8ED** uploaded through the customer browser, persisted after refresh, and appeared in the pharmacist browser queue with the correct patient, doctor, notes and attachment. Assignment and audit were verified. |
| RX-02 | Pass | Browser rejects unsupported text and >5 MB PDF with useful messages before submission. Missing required patient name/files, oversized/unsupported files are rejected by API regressions without creating a prescription. Client also enforces five-file maximum. Medication JSON is validated before records/files are created. |
| RX-03 | Pass | Pharmacist browser selected exact variant **23507 / RX-QA-20261029-A**, quantity 1, and approved RX-E1E8ED. API regression verifies assignment, catalog search, exact mappings, clinical instruction persistence and review decisions. Added dose/frequency/duration entry for newly selected variants. |
| RX-04 | Pass | Same prescription completed the pharmacist clarification → customer browser reply → pending review journey. Pharmacist browser displayed both messages. Separate upload/resubmit API regression passes. |
| RX-05 | Pass | Separate prescription **45 / RX-117495** rejected in pharmacist browser with “Illegible prescription”; customer browser showed the reason. Fixed dashboard request that previously omitted the reason. Pending/rejected cart access and checkout revalidation fail safely in regressions. |
| RX-06 | Pass — simulated payment | Customer browser added exact approved pack, quantity 1; checkout created **order 2004 / ORD-8D5C9C77**, KSh 1 item + KSh 150 delivery = **KSh 151**. Unpaid finalization returned 400. Intent **46** carries explicit reference **SIMULATED-RX-QA-20261029**, with `qa_only` metadata. After controlled confirmation, real HTTP finalization succeeded; repeating it succeeded without another stock deduction. No provider payment is claimed. |
| RX-07 | Pass | Browser increase beyond authorized quantity returned a useful error and kept quantity 1. Tests reject exact-variant substitution (including another variant on the same product), quantities reserved in another unpaid order, and paid-item reuse. Cancellation releases the unused allowance; stock release remains possible after approval revocation. Live paid-item reuse returned 400. |
| RX-08 | Pass | Staff HTTP order changes processing → shipped → delivered synchronized prescription queued → packed → dispatched → delivered. Customer browser showed **Paid / Delivered** after refresh. All four dispatch notifications exist. Audit contains actual dispatch transitions, order reference and pharmacist actor. Regression checks ordered manual transitions, approval requirement and no duplicate notification on repeated state. |
| RX-09 | Pass — local configuration | Restricted pharmacist detail/update/audit/register bypasses fixed. Unrelated customer detail returns 404 and list excludes RX-E1E8ED. Old public PDF URL returns 404. Current protected download succeeds in customer browser, preserves filename and matches original PDF bytes/hash. Tests reject unsigned, expired, unrelated-user and suspended-user grants. Each short-lived download grant is checked against current account/role/ownership; responses use `private, no-store`. Apache staging/production source configurations deny the prescription media directory; those configurations have not been deployed by this task. |

## Completed connected journey

**E2E-02 passes for the local application using the simulated payment fixture.** RX-E1E8ED was followed from customer upload through clarification, pharmacist browser approval, customer cart/checkout, controlled payment confirmation, safe finalization and delivery. Order/payment, exact prescription item and variant, stock and customer status match.

Dedicated inventory row **64280**, variant **23507**, moved **4 → 3** exactly once. Alternate synthetic pack 23508 was not ordered. Synthetic product **22368 / RX-QA-20261029** has been deactivated after verification. Test prescription, order, simulated payment, notifications, inventory movement and rejection fixture remain as evidence. Existing shared catalog fixtures and unrelated workspace changes were preserved.

## Fixes

- Blocked public prescription-media URLs and added five-minute user-bound signed download grants, current permission checks, attachment filenames and no-store responses. Customer download no longer opens an unnecessary new tab.
- Enforced exact approved variants, cumulative cart limits, unpaid-order reservation limits and paid-item reuse rules at cart/checkout and stock commitment. Checkout/stock locks serialize authorization checks. Finalization remains idempotent.
- Approval requires mapped active variants and positive quantities; controlled items are blocked consistently. Replacing items already linked to orders is rejected. Failed approval rolls back replacements.
- General review updates now retain reasons, clarification messages and review decisions. Pharmacist dashboard rejection sends the reason through the review API and reports save failures.
- Added clinical instruction inputs/persistence, client upload validation, exact variant/duration display, accurate selection labels, dispatch transition validation, actor history and customer notifications.

## Validation and evidence

- [Final regression log](prescriptions/completion-regressions.log): **112 tests passed** — 22 prescription, 72 order and 18 consultation tests.
- Frontend production build passed. Django checks and migration drift check passed; no new schema migration is required. Scoped whitespace checks passed.
- [Protected download/access HTTP retest](prescriptions/access-retest.json)
- [Browser download checksum](prescriptions/browser-download.json)
- [Checkout/finalization/dispensing HTTP trace](prescriptions/checkout-dispensing.json)
- [Final stock, staff audit and notification snapshot](prescriptions/final-snapshot.json)
- [Customer Paid / Delivered screenshot](prescriptions/customer-delivered.png)
- [Pharmacist rejection screenshot](prescriptions/pharmacist-rejection.png)
- [Oversized-upload browser message](prescriptions/oversize-error.png)

## Remaining integration boundary

The browser Paybill path still reports that provider callbacks are not registered; this is the existing **ORD-06** integration block. It was neither bypassed in configuration nor marked as a provider success. The local simulated confirmation was explicit, restricted to the synthetic order, and retained as such in the payment metadata/reference. ORD-06 and real POS blocks remain unchanged. External email inbox delivery and production Apache deployment were not independently tested here.
