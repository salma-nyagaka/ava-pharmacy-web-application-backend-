# PPB remediation and verification checklist

**Historical baseline.** See the [5 November implementation and verification report](../2026-11-05/implementation-and-verification.md) and [current remediation checklist](../2026-11-05/ppb-remediation-checklist.md) for subsequent changes and remaining evidence.

Audit: 4 November 2026. These are open items, not completed changes. Review the full audit and clause matrix before implementing. Use an isolated test environment for reproduction; do not execute the demonstrated gaps with real patients, medicines or payments.

## Before real medicine supply

- [ ] **PPB-14 / operational owner:** Provide and verify actual pharmacy/online authorization, registered premises and superintendent, ODPC certificate, Kenya hosting, current required certificate and third-party agreements.
- [ ] **PPB-09 / admin + frontend:** Populate genuine public registration/safety code, superintendent, postal address and consultation hours. Remove unsupported accreditation claims. Include responsible identity in patient documentation and test every sale page.
- [ ] **PPB-01 / backend + pharmacy:** Verify medicine classification, PPB registration/retention and authorized supplier data. Block missing/suspended/withdrawn/expired medicine eligibility across purchase and supply paths.
- [ ] **PPB-02 / backend + pharmacy:** Block controlled medicines independently of product names and the Rx boolean. Reject inconsistent classifications and validate high-risk medicine safeguards.
- [ ] **PPB-03 / backend + content:** Exclude POM/controlled medicines from all public promotions, discount metadata, banners and advertising feeds, including mixed-variant products.
- [ ] **PPB-04 / backend + pharmacist:** Replace keyword-only screening with medicine-class-driven patient assessment and an attributable professional supply decision. Record counselling, suitability, refusal/referral and responsible identity.
- [ ] **PPB-07 / backend + credential owner:** Enforce current verified Kenyan prescriber eligibility and license expiry across relevant booking, issue, review and supply paths.
- [ ] **PPB-08 / backend + pharmacist:** Record prescription authenticity/validity, preserve originals and implement the seven-working-day original follow-up required by the supplied PDF, with PPB-approved handling of newer e-prescription arrangements.

## Clinical records, delivery and information

- [ ] **PPB-06 / backend + infrastructure:** Enforce at least five-year retention and required permanent copies, immutable/versioned history and legal holds across API/admin/commands/storage; prevent premature clinical record deletion.
- [ ] **PPB-05 / backend + logistics:** Enforce recipient verification, required package/temperature evidence and cold-chain exception/hold handling across admin/webhook/fulfillment paths; demonstrate actual courier process.
- [ ] **PPB-11 / backend + inventory:** Implement lot recall/stop-sale, immutable batch traceability, affected-order/patient identification, notifications/acknowledgements, returns and closure; complete a recall drill.
- [ ] **PPB-10 / pharmacy + content:** Populate and review PIL-aligned medicine information, contraindications and adverse effects with authoritative provenance and review/version dates; verify storefront display.
- [ ] **PPB-12 / privacy owner + backend/frontend:** Replace unsupported privacy claims and implement complete Kenya data-subject notices/requests, processing controls and retention-aware decisions. Verify at-rest/transit protection and key management.
- [ ] **PPB-16 / frontend + superintendent:** Wire saved return requests/history and publish accurate counselling, delivery, return and complaint procedures. Do not describe an unexecuted external refund as money returned.
- [ ] **PPB-18 / pharmacy + backend:** Validate medicine-specific excessive/frequent-order alerts, holds, professional review/refusal and longitudinal/cross-channel monitoring.

## Deployment and operational evidence

- [ ] **PPB-13 / infrastructure:** Demonstrate monitored daily secure offsite backups for database and private files, retention/access controls and a successful restore test.
- [ ] **PPB-15 / superintendent + operations:** Approve SOPs, clinical service/communications audits, staffing/training, equipment maintenance/calibration, capacity and disruption plans; supply actual recurring audit schedules/reports.
- [ ] **PPB-17 / infrastructure + API team:** Resolve release security check errors/warning, finish useful API declarations, provision appropriate inspector access and verify target-host TLS/private-media controls. Do not copy development settings into production.

## Retest and approval

- [ ] Convert audit probes that currently reproduce a gap into tests requiring the corrected safe behavior.
- [ ] Test canonical routes and all aliases plus alternate cart/wishlist/merge/stock/admin/webhook paths affected by each fix.
- [ ] Repeat all application suites, build, migration and deployment checks; retain logs and cross-role browser/clinical evidence.
- [ ] Reconcile data curation and outstanding Paybill/POS/refund obligations separately from code changes.
- [ ] Have the superintendent and relevant regulatory/privacy/infrastructure owners verify operational documents and complete sign-off. Record accepted limits without labelling unperformed obligations passed.
