# PPB gap implementation and verification

**Date: 5 November 2026 — software controls implemented; production/clinical compliance sign-off remains pending.**

This follows the [4 November baseline audit](../2026-11-04/ppb-compliance-audit.md). The supplied guideline remains the requirement source. This report records implementation, not PPB approval or proof of professional competence.

**Pending-state recheck:** [Current findings and evidence](pending-review/pending-status.md) confirm the operational blockers remain and identify pharmacist credential-expiry enforcement as an additional software follow-up.

## What changed

| Finding | Implemented control | Evidence or practice still required |
|---|---|---|
| PPB-01 | Explicit unreviewed/medicine/non-medicine classification; current registration, supplier, professional classification and PIL checks at purchase and stock commitment. Medicine supply also requires traceable, unexpired, supplier-identified batches; unallocated medicine backorders cannot be committed. | Verify actual classifications, PPB registration/retention and suppliers. Existing catalogue data was not fabricated or automatically approved. |
| PPB-02 | Controlled classification blocks supply independently of the Rx checkbox and product name. Prescription classification independently requires prescription authorization. | Superintendent validates controlled/high-risk classifications and operating procedures. |
| PPB-03 | Rx discounts, coupon eligibility, promotional metadata and public price comparisons are blocked. Direct public banner/CMS links and product-targeted promotions pointing to Rx/unreviewed products are withheld. | Review images, free-text claims, external links and all advertisements professionally; code cannot certify their clinical/legal content. |
| PPB-04 | Classification-driven OTC questionnaire and attributed professional assessment. Decision, suitability, counselling, intervention, quantity, customer and questionnaire digest are recorded. Approval expires, refusals supersede approvals, and an assessment is reserved for one order. | Validate questionnaire, contraindication/interactions/red-flag policy, clinical suitability and actual counselling. An authorized administrative role is not evidence of a professional licence. |
| PPB-05 | Successful delivery requires recipient verification, identity/name and package evidence. Temperature-sensitive medicines require configured limits, an intact cold chain and an in-range reading. Latest failed/returned events block completion. Model guards cover normal admin saves too. | Courier identity checks, actual readings, calibrated equipment, packaging and excursion/return procedures. |
| PPB-06 | Prescription/file/audit preservation, immutable approved prescription versions, minimum clinical retention, protected cascades and PostgreSQL delete/update triggers. Administrative account removal deactivates access. | Approved retention/legal-hold policy, separate database owner/runtime roles, storage protection, restores and destruction approvals. Privileged DB administrators/storage owners remain outside these app guards. |
| PPB-07 | Current verified Kenyan clinician eligibility is checked in active selection, booking/provider actions and prescription issue. | Verify actual registrations, jurisdiction, expiry and professional practice. |
| PPB-08 | Structured prescriber verification, dates/validity, authenticity evidence and accountable reviewer. Seven-working-day original follow-up, original receipt/reference and overdue supply hold. Weekends and configured holidays are excluded. | Provide an approved current Kenyan holiday calendar, verify originals and confirm PPB treatment of newer electronic-prescription arrangements. |
| PPB-09 | Removed unsupported registration badges; stopped presenting general support hours as pharmacist hours. Genuine configured superintendent/registration/safety-code values render in transactional patient emails. | Populate and independently verify actual identifiers, hours, postal address and current regulator contacts. Blank fields remain blank/pending. |
| PPB-10 | Professional catalogue curation, PIL provenance/version/reviewer/time, required safety fields and patient-facing contraindications/adverse effects/storage/PIL display. | Qualified review of actual medicine information; scraped descriptions/images are not regulatory verification. |
| PPB-11 | Recall hold, conservative affected-order tracing, notifications after recall commit, retry without falsely claiming queue success, acknowledgements/disposition and closure checks. Immutable batch/allocation history survives inventory release. | Perform a real recall drill and verify contact/delivery outcomes. Old orders without reliable lot evidence are conservatively included; missing historic lots are not invented. |
| PPB-12 | Removed unsupported encryption/HIPAA/retention assertions. Private rights-request intake/history, owner scoping, identity-verification step, explained decisions/lawful basis and immutable attributed change history. Account changes hide prior request history. | Privacy owner approves the final notice, lawful bases, legal identity, processors/transfers, rights-response deadlines, minimization and retention schedule. An erasure request never silently deletes clinical records. |
| PPB-13 | Encrypted PostgreSQL + media backup command, offsite copy/check, fail-closed tool/config checks and truthful `restore_tested: false` output. | Provision approved storage, public encryption recipients/private-key custody, daily scheduling/monitoring and an isolated successful restore. Tool availability and production execution are not claimed. |
| PPB-14 | Independent evidence verification with expiry/reference, restricted downloads, edit-invalidated verification and readiness gates. | Actual PPB/ODPC/hosting/TLS/SLA/control evidence; a saved upload does not prove validity. |
| PPB-15 | Owned review schedules, procedures, evidence/findings/corrective actions and completion validation. Exact twelve 12.1(a–l) audit areas are available, plus operational review areas. Inspectors have read-only access. | Approved SOPs, staffing/training, clinical audit, equipment validation/calibration and witnessed exercises/reports. |
| PPB-16 | Customer return submission and saved history wired to the real API; quarantine/non-resale controls retained; unsupported refund timing/payment promises removed. | Approve and operate written counselling, delivery, complaints, return and refund procedures. A recorded refund status is not proof of an external transfer. |
| PPB-17 | Production bot enforcement, verified-authorisation medicine gate, strong-secret/calendar checks and deployment readiness command before Apache reload. OpenAPI export validates without errors; untyped action routes are explicitly generic rather than omitted. | Actual secrets, CAPTCHA, public HTTPS origins, TLS/private-media and target-host verification. Legacy field-level schema typing still needs improvement; schema warnings are disclosed. |
| PPB-18 | Longitudinal frequency/quantity triage, recorded review events and accountable intervention requirement alongside existing abuse/Rx-reuse guards. | Superintendent validates thresholds and clinical review/refusal policy across channels. Thresholds are triage, not automatic clinical clearance. |

## Important behavior on existing data

New catalogue records and existing records migrated into the new field are **unreviewed**. They cannot enter supply until an authorized reviewer classifies them. Medicines additionally need genuine regulatory, supplier, safety and batch data. A reviewer must not classify a medicine as non-medicine to bypass these checks.

Production medicine supply additionally checks required pharmacy disclosures and current independently reviewed PPB authorization. The current local data does **not** satisfy those gates. No real licensing, PIL, supplier, original receipt or certificate evidence was invented. Local additive schema migrations were applied; no production deployment, genuine payment/refund/transfer or recall message was executed for this implementation.

Clinical assessment uses existing authorized professional/admin permissions. Actual staff qualifications, credential governance and clinical judgment remain operational sign-off duties; administrative access alone does not establish professional qualification.

## Screens and workflow

- Staff: `/compliance`; admin navigation: `/admin/compliance`.
- Catalogue: search name/SKU, select the exact variant and enter verified classification, registration, supplier and reviewed PIL data. Receive real batches through the existing inventory workspace.
- OTC: customer supplies their questionnaire; authorized reviewer selects the cart item, records suitability, counselling and decision; customer proceeds only with a current matching decision.
- Prescriptions: select the prescription and record prescriber/authenticity/date evidence. Then use the existing pharmacist approval workspace. Record an original as received only when actually received, with its reference.
- Recalls: create a recall for the exact variant; all variant supply is conservatively held, even for a batch-specific case. Review affected orders, actual contact outcomes and quarantine/disposition; close only with resolution and closure evidence. Historical allocation snapshots remain inspectable.
- Privacy: customer uses `/privacy`; administrator verifies identity and records an explained response/lawful basis. Sensitive exports/corrections/erasure require appropriate human review; submission does not execute them automatically.
- Returns: customer uses `/returns`, selects an owned order and saves a request; history shows the recorded status.
- Evidence: upload through existing settings/evidence tools. A different administrator verifies current evidence. Any edit clears verification.
- Operational reviews: assign an owner/procedure/date, then complete with current reviewed evidence and findings. Completed work and the next scheduled review are separate records.

## New API contracts

All paths below share the existing four API mounts. Examples use `/api/`. Authentication and active-account checks apply; inspectors can read permitted staff registers but cannot write. Customer privacy/return records are owner-scoped. Query/list pagination follows existing API conventions.

| Path | Methods and purpose |
|---|---|
| `/compliance/catalogue/`, `/compliance/catalogue/{id}/` | GET/search catalogue; PATCH regulatory/safety fields with an attributed review. |
| `/compliance/assessment-queue/` | GET customer medicine cart items and screening for authorized review. |
| `/compliance/medicine-assessments/` | GET/POST attributed decisions; server binds customer, variant, quantity, digest, reviewer and expiry. |
| `/compliance/recalls/`, `/compliance/recalls/{id}/` | GET/POST recall; PATCH closure with evidence and resolved affected orders. |
| `/compliance/recalls/{id}/affected-orders/` | GET affected-order register. |
| `/compliance/recall-orders/{id}/` | PATCH acknowledgement, disposition and resolution evidence. |
| `/privacy/requests/`, `/privacy/requests/{id}/` | Customer GET/POST own requests; administrator PATCH explained outcome. |
| `/privacy/requests/{id}/verify/` | POST secure identity-verification reference; does not publish identity documents. |
| `/compliance/evidence/{id}/verify/` | POST independent external-verification reference for current evidence. |
| `/compliance/reviews/`, `/compliance/reviews/{id}/` | Schedule and complete evidence-backed operational/QA reviews. |
| `/compliance/readiness/` | GET missing disclosures/evidence and overdue recorded reviews; not regulatory approval. |

Example assessment payload:

```json
{"cart_item":123,"decision":"approved","suitability":"Actual patient assessment","counselling":"Actual safe-use, storage and disposal counselling","intervention":"Actual intervention where needed"}
```

Prescription evidence fields: `doctor_name`, `prescriber_registration`, `prescriber_verification_reference`, `prescribed_on`, `valid_until`, `authenticity_method`, `authenticity_evidence`, optionally `original_received_at` and `original_receipt_reference`. Reviewer/time and the original deadline are server assigned. Evidence must be genuine; these examples are contracts, not ready-to-submit clinical decisions.

## Verification

See the retained logs, [current API inventory](api-inventory.md), [validated OpenAPI export](openapi.yml) and [route/schema coverage](schema-coverage.json). A schema export covering operations does not imply exhaustive branch/payload penetration testing. Legacy/action contracts explicitly marked generic do not claim complete field typing. Schema validation warnings remain and must be considered before generating strict SDKs.

**Catalogue compatibility: 85 tests passed. Full regression: 405 tests passed. Final safety retest: 43 tests passed, including two additional cases added after the full run (407 distinct tests covered).** Final catalogue compatibility and all logs are recorded in [verification-summary.json](verification-summary.json). Tests use discarded PostgreSQL databases and explicitly fictional credentials/medicine metadata. New negative tests intentionally omit or invalidate those fields. No test helper is imported by application code. Original audit gap-reproduction tests remain historical evidence and should not be treated as current expected behavior.

Browser checks: privacy and return pages rendered; `/compliance` and `/admin/compliance` redirected unauthenticated users to sign-in. Authenticated staff writes were verified through API tests, not a logged-in browser session. Frontend TypeScript/Vite build passed.

## Production blockers and handover

Use [the operational verification runbook](operational-verification-runbook.md). Production remains blocked by missing genuine disclosures/evidence, catalogue/batch curation, approved QA/SOP records, current holiday calendar, production secret, CAPTCHA secret and public HTTPS-origin settings in the inspected environment. The current deployment checks intentionally fail. Passing application tests does not remove these blockers.
