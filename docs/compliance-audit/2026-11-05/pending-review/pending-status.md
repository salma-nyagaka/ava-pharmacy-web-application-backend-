# Recheck of still-pending items

**Checked: 5 November 2026. Release remains blocked.** This recheck used the local application database, source and local host. It did not inspect a production host or verify documents held elsewhere. No business records, credentials or professional decisions were changed.

## Current findings

| Pending item | What was verified | What is needed to close it |
|---|---|---|
| Public pharmacy details | Seven required fields are still missing: postal address, health safety code, premises registration, online pharmacy licence, superintendent name/registration and pharmacist hours. | Supply genuine values, verify them and check storefront/patient-document display. |
| Catalogue curation | All **22,733** active non-synthetic variants are still `unreviewed`. **4,183** Rx/control-flagged or classified variants lack registration, supplier, clinical safety/PIL review data and current registration-expiry information. | Authorized classification of all items; genuine regulatory and clinical review of applicable medicines. This does not mean all 22,733 items are medicines. |
| Batch traceability | **6,007** stocked inventory rows for those Rx/control variants lack at least one batch/supplier/current-expiry field. | Reconcile physical batches and actual supplier/expiry records. Do not invent lot history. |
| Clinician eligibility | Of **8** active profiles with active accounts, **0** satisfy the current complete application eligibility predicate. **1** has an expired licence date, **5** have no expiry date, and **1** is unverified; reasons can overlap. | Verify each real clinician's registration, country/board, status, expiry and practice eligibility before enabling service. |
| Pharmacist credential validity — software follow-up | All **6** pharmacist profiles have a recorded licence number. The pharmacist model has **no licence-expiry verification field**; a number alone cannot establish current validity. | Add current credential verification/expiry and appropriate server enforcement for clinical review/supply; have the professional owner verify real credentials. Administrative permissions are not professional verification. |
| Genuine compliance evidence | **1** evidence record exists in `review_due`; **0** current verified records. All eight configured evidence categories lack current verified evidence. | Provide and independently review PPB authorization, ODPC, Kenya hosting, certificate, SLA, backup, information-security control and QA evidence. A document elsewhere may exist but was not verified here. |
| Management QA and SOPs | **0** scheduled operational reviews and **0** completed reviews; **0/12** exact guideline QA areas have completion records. Zero overdue records is not a pass when nothing is scheduled. | Assign owners/dates/procedures, perform reviews, attach current evidence/findings and resolve corrective actions. |
| Backups/restore | Local `pg_dump` and `rclone` are available; **`age` is missing**. No current verified backup evidence or completed restore review is recorded. | Provision approved encryption/key custody/storage, schedule and monitor daily backups, then demonstrate isolated restoration. Production tool availability was not inspected. |
| Runtime database privileges | The local connection is a **superuser**, can create databases/roles and can truncate the prescription table. | Verify a separate restricted production runtime role and protected storage. PostgreSQL retention triggers do not constrain a privileged administrator. Production credentials were not inspected. |
| Production configuration | The local production-settings check still fails with **6 errors and 1 warning**. | Resolve disclosures, CAPTCHA secret, development CORS origins, public HTTPS frontend URL, approved holiday calendar and strong production secret. Do not print or commit secrets. |
| Clinical/operational practices | No completed genuine review records establish validated clinical questions, counselling, advertising review, cold-chain/recipient handling, complaints, returns/non-resale or recall drills. Zero recalls/privacy requests is not proof those workflows were exercised. | Professional approval and witnessed exercises with actual evidence; synthetic drills must remain labelled. |
| Privacy/hosting/security | No current verified ODPC, hosting, certificate or SLA evidence is recorded. | Privacy-owner notice/lawful-basis/retention approval plus actual target-host and processor verification. Code settings cannot prove encryption, location or hosting controls. |
| API documentation | Last validated schema has **0 validation errors**, but **1,415 warning occurrences (836 unique)** and explicitly generic legacy/action payload contracts. | Complete precise request/response/status typing and resolve relevant warnings before relying on strict generated clients. Route coverage is not complete field-level typing. |
| Browser/release acceptance | Previous browser checks covered public pages/sign-in boundaries; authenticated staff writes were API-tested, not accepted in a logged-in browser. No production release was performed. | Isolated logged-in staff/customer acceptance, target-host verification and required operational sign-off. |

Counts are local recorded-state observations, not clinical determinations or evidence that external licences/documents do not exist. Product counts exclude product names containing “synthetic”, consistent with the baseline audit.

## Evidence and check results

- [Aggregate current state](current-state.json) — no patient records, credential values or staff names exported.
- [Readiness check](readiness.log) — failed as expected; records every outstanding category/area.
- [Production-settings security check](production-security.log) — six errors and one warning; run against local environment values.
- [Source consistency](source-consistency.json) — all 590 recorded code/template/deployment files match the last verified source snapshot. Prior test results were not relabelled as a new test run.

The previous implementation report documents implemented controls; it does **not** close pharmacist credential-validity enforcement, precise legacy API typing, authenticated browser acceptance or operational verification.
