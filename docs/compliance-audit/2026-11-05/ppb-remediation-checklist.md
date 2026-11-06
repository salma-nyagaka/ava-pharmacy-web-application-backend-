# PPB remediation checklist — current implementation

5 November 2026. Checked software items require the retained test results. Unchecked operational items require genuine evidence and professional/production verification. The [implementation report](implementation-and-verification.md) gives the scope and limits for every original finding.

## Software controls

- [x] PPB-01/02: Shared regulatory/classification gate; controlled restrictions independent of the Rx checkbox.
- [x] PPB-01/11: Medicine batch/supplier/expiry checks before purchase; immutable allocation history.
- [x] PPB-03: Rx promotion/coupon/price-comparison restrictions and direct public advertisement-link filtering.
- [x] PPB-04: Classification-driven OTC screening and attributed, expiring, single-order professional assessment.
- [x] PPB-05: Recipient, package and temperature safeguards; failed delivery holds.
- [x] PPB-06: Retention/cascade guards, PostgreSQL triggers and preserved prescription versions; account deactivation.
- [x] PPB-07: Current verified Kenyan clinician eligibility for selection, booking/provider actions and prescription issue.
- [x] PPB-08: Prescriber/authenticity/date evidence, working-day original deadline and overdue hold.
- [x] PPB-09: Patient-email identifiers and truthful public missing-value displays.
- [x] PPB-10: Attributed PIL/safety curation and patient information display.
- [x] PPB-11: Recall holds, affected-order tracing, honest notification retry, disposition and closure.
- [x] PPB-12: Private owner-scoped rights requests, identity review, explained outcomes and immutable change logs.
- [x] PPB-13: Encrypted database/media backup and offsite verification tooling.
- [x] PPB-14: Independent evidence verification, expiry checks and invalidation after edits.
- [x] PPB-15: Owned schedules and exact twelve guideline QA areas, evidence-backed completion and inspector reads.
- [x] PPB-16: Working return submission/history and accurate refund/return wording.
- [x] PPB-17: Production security/readiness gates and validated schema export without omitted REST operations.
- [x] PPB-18: Longitudinal medicine-order triage and recorded intervention requirement.

## Still pending — software and acceptance

Rechecked on 5 November 2026: see [current pending status and evidence](pending-review/pending-status.md). None of the operational items below was closed by this recheck.

- [ ] Add pharmacist credential verification/expiry fields and appropriate server enforcement. Six profiles have licence numbers, but the current model cannot establish licence expiry/current validity.
- [ ] Improve legacy field-level OpenAPI typing before generating strict clients; generic contracts and warnings remain explicit.
- [ ] Complete logged-in browser acceptance of staff writes, then target-host release verification and required sign-off.

## Still pending — genuine evidence and operations

- [ ] Actual PPB/premises/online authorization and public identifiers, superintendent and pharmacist hours.
- [ ] Actual staff qualifications, registrations, scope, expiry and competence verification.
- [ ] Review and curate real catalogue classification, registrations, suppliers, safety information and batches. **Recheck: 22,733 active non-synthetic variants unreviewed; 4,183 Rx/control variants lack required medicine data; 6,007 stocked Rx rows lack one or more traceability/expiry fields.**
- [ ] Validate clinical questions, red flags, thresholds, suitability, counselling and original-prescription procedures.
- [ ] Review all free-text/image/external-link advertising and professional content.
- [ ] ODPC, controller/legal basis/processor/retention policies and final privacy notice approval.
- [ ] Kenya hosting, TLS/certificate requirements, at-rest encryption, contracts and private-media verification.
- [ ] Separate database owner/runtime permissions, protected file retention and approved deletion/legal holds.
- [ ] Provision keys/tools/storage and prove monitored daily offsite backups and an isolated restore. **Local `age` executable is missing; no current verified backup/restore evidence is recorded.**
- [ ] Approve SOPs and complete twelve-area management audits, equipment validation/calibration and continuity exercises. **Recheck: zero scheduled/completed operational reviews; 0/12 QA areas completed.**
- [ ] Demonstrate actual recipient/cold-chain delivery, failed delivery, complaints, returns/non-resale and recall drills.
- [ ] Configure production secrets, CAPTCHA, public HTTPS origins and approved current holiday calendar.

No operational checkbox may be completed merely because its upload/API/form exists. No real payment, refund, transfer, patient message or production deployment was used to close these software items.
