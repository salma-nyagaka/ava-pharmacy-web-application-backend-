# AvaPharmacy audit against PPB internet pharmacy guidelines

**Historical baseline.** See the [5 November implementation and verification report](../2026-11-05/implementation-and-verification.md) and [current remediation checklist](../2026-11-05/ppb-remediation-checklist.md) for subsequent changes and remaining evidence.

**Audit date:** 4 November 2026. **Overall finding: full compliance is not established; material software gaps and missing operational evidence prevent sign-off.** Do not use earlier feature-test passes as a claim that every regulatory obligation is satisfied.

The system has functioning access controls, prescription authorization/quantity rules, payment integrity, records, and service workflows. It also permits several states contrary to the supplied guideline's safety controls. This report identifies what was demonstrated, what is incomplete, and what cannot be verified from source code.

## 1. Basis, scope and method

- Primary requirement source: the user-supplied **Guidelines for Internet Pharmacy Services in Kenya, Version 2, April 2023**, reference PRA/LPP/GPP/GUD/033, Revision 02. The PDF has 28 file pages including preliminary pages and numbered content pages 1–19. Printed page 4 is PDF file page 12. The 2026 text in the uploaded filename is not the document's revision date.
- Recommended source citation: Republic of Kenya, Ministry of Health, Pharmacy and Poisons Board, Guidelines for Internet Pharmacy Services in Kenya Version 2, 2023.
- The [official PPB download page](https://web.pharmacyboardkenya.org/download/guidelines-on-internet-pharmacy-services/) was checked on the audit date. Its metadata records an October 2023 update. This audit is specifically against the supplied April 2023 document; it does not claim that all later Kenyan health/privacy rules or professional standards were audited. The [Ministry's October 2026 GPP implementation notice](https://health.go.ke/ministry-ppb-and-kpa-agree-practical-rollout-good-pharmacy-practice-standards) is separate context, not substituted requirements.
- Source PDF SHA-256: `a8365cd0e1e379822878301426bd545578de387071ade1d4017337e455eb9eed`. Source read and relevant requirement/ICT pages visually checked. Requirements below are paraphrased, not a reproduction of the PDF.
- Backend base commit `c47b265` plus current workspace; sibling frontend source reviewed/built. Runtime inspected: local development environment, not a remotely audited production deployment.
- **301 canonical `/api/` routes** inventoried: 298 application routes and 3 schema/documentation routes. The application routes are also mounted under `/api/v1/`, `/avapharmacy/api/` and `/avapharmacy/api/v1/`. Aliases share handlers and need deployment consistency. WebSocket consultation authorization and Django-admin paths were also inspected where they affect the obligations.
- **All 364 existing application tests passed.** **14 additional isolated audit probes completed**: 10 gap observations across 8 distinct findings, plus 4 demonstrated protections. A passing *audit probe* means the reported behavior was reproduced; the 10 AUDIT_GAP observations are not compliance passes.
- Frontend TypeScript/Vite production build passed. Migration check: no changes detected. Production security-only check with the current environment: **5 errors and 1 warning**, detailed below.
- Source/permission/data-flow review and targeted regression are not an exhaustive penetration test or every possible request to every endpoint. Route inventory does not imply 100% branch/payload coverage. Physical premises, staff competence, certificates, supplier legitimacy, real logistics, production infrastructure and clinical correctness require evidence outside the repository.
- No live business data, permissions, fees, stock or clinical records were changed. No real payment, refund, payout or message was sent. Audit-specific state existed only in discarded test databases. Test logs contain synthetic fault-injection messages; those alone are not new production incidents.

[Full 123-item clause matrix](requirements-matrix.md) · [Complete API inventory](api-inventory.md) · [Aggregate data evidence](live-data-quality.json) · [Reproduction results](probe-results.json).

## 2. Most urgent findings and fixes

### PPB-01 — Critical: no authoritative medicine registration/supplier gate

**Clauses:** 3/1.16; 5.1.1; 6.1.2. The model stores PPB registration, marketing authorization, regulatory state, expiry and supplier fields, but central cart/availability/stock code checks activity and stock rather than regulatory eligibility. A synthetic variant with blank registration and unknown approval reached cart **201** and checkout draft **201**. Setting regulatory status to suspended still permitted cart **201**. This does not execute a payment, but proves the missing pre-supply eligibility control.

The live aggregate audit found **4,183 active Rx-flagged or prescription-classified variants**; all 4,183 have blank PPB registration, no approved regulatory status and blank authorized supplier. Those flags are catalog classifications, not an independent clinical determination of every imported product. Other categories include non-medicines and should not be indiscriminately treated as PPB medicines. Supplier/batch free text does not prove an authorized Kenyan supplier.

**Required:** verified medicine classification and authoritative registration/retention/supplier checks; fail-closed listing/supply for missing, suspended, withdrawn or expired authorization, with governed exceptions only where lawful. Apply one shared policy across cart, merge, wishlist move, prescription supply, payment/finalization, admin and POS paths. Test status changes after draft creation. Real supplier/PPB verification remains an operational duty.

**Source:** [catalogue fields](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/products/models.py:1051); [checkout validation](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/orders/views.py:305); [cart entry](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/orders/views.py:1194); [rx authorization](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/prescriptions/dispensing.py:5).

### PPB-02 — Critical: controlled classification is not a universal stop-supply rule

**Clauses:** 3/1.15; 11.4.2(a). Rx review/dispensing has keyword/item guards. However, a synthetic neutral-name variant with `prescription_classification=controlled` and `requires_prescription=False` was accepted into cart **201**. The live catalog had zero such mismatches in this audit; this is a reproduced latent control gap, not proof a controlled medicine was sold.

**Required:** one authoritative controlled/high-risk classification policy independent of optional text keywords and the boolean Rx flag. Validate consistent classification at curation and enforce at all publication/cart/supply/fulfillment paths. Add alerts and additional clinically governed safeguards for high-risk medicines identified by the guideline.

**Source:** [cart entry](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/orders/views.py:1194); [rx authorization](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/prescriptions/dispensing.py:5); [catalogue fields](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/products/models.py:1051).

### PPB-03 — High: prescription-only promotional pricing reaches the public

**Clauses:** 2.1.6(iv); 3/1.4(ii)(e); 6.1.5. A synthetic prescription-only product received an active all-products promotion: anonymous detail request **200**, promotional metadata and a **70.0000** discount on its test price. Featured-product exclusion is useful but does not protect product detail, general promotions or all catalog surfaces.

**Required:** server-enforced POM/controlled exclusion from public promotional pricing, codes, deal lists, banners and recommendation/advertisement feeds; approved publication policy for professional-only content. Apply to mixed-variant products and future status changes. Do not equate every factual medicine listing with advertising; this finding is specifically the demonstrated promotional discount/metadata.

**Source:** [rx promotion](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/products/services.py:74); [public product api](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/products/views.py:292).

### PPB-04 — Critical: OTC screening is incomplete and not a professional supply decision

**Clauses:** 3/1.4(i); 5.1.3–5.1.8; 8.3.3–8.3.5. OTC screening is selected by name/category keywords or non-empty advice fields. A classified OTC variant with a neutral name and no advice fields accepted cart **201** without screening. A keyword-detected medicine with patient-supplied questionnaire/acknowledgement reached draft **201** without an attributable pharmacist assessment. A patient acknowledging generic text is not evidence a professional rationalized that patient's medicine request.

**Required:** classification-driven screening; sufficiently structured patient/guardian/condition information; responsible professional identity, suitability decision, interventions, counselling/referral/refusal and timestamps before supply. Define clinical red-flag/interaction/pregnancy/age policies with the superintendent. Do not automatically treat every cosmetic/accessory as a medicine.

**Source:** [otc selector](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/orders/views.py:410); [otc check](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/orders/views.py:426); [otc ui](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-frontend/src/pages/ProductDetail/ProductDetailPage.tsx:322).

### PPB-05 — High: recipient and cold-chain fields are optional evidence rather than enforced controls

**Clauses:** 7.1.1–7.1.5. A synthetic temperature-sensitive order accepted a delivered audit with `recipient_verified=False` and `cold_chain_intact=False` (**201**), then allowed delivered status (**200**). Existing finalized/paid fulfillment guards do not cover these safety requirements.

**Required:** enforce recipient verification, package condition, required temperature evidence/ranges and permitted exceptions for sensitive items, including webhook/admin paths. Failure must create accountable hold/return/quarantine rather than a normal successful delivery. Validate courier contracts, packaging, temperature equipment and actual handling outside software.

**Source:** [delivery serializer](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/orders/serializers.py:160); [order transition](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/orders/serializers.py:340); [delivery api](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/orders/views.py:3435).

### PPB-06 — High: five-year/permanent clinical record preservation is not enforced

**Clauses:** 3/1.4(ii)(b); 3/1.13; 8.4. A prescription created during the isolated test was permitted to be deleted by the registered Django admin and was then absent. Records/files generally exist, but there is no demonstrated record-age retention guard or complete immutable/legal-hold strategy. Soft customer deactivation is useful; it does not protect all admin, cascade, file-storage or maintenance paths.

**Required:** retention rules of at least the supplied guideline's periods, controlled legal holds, protected originals/version history and audit immutability; disable ordinary premature deletion/change across Django admin, APIs, commands and storage lifecycle. Preserve historical patient/professional identity snapshots. Test recent and older records and restoration, not only account deactivation.

**Source:** [clinical retention](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/prescriptions/admin.py:23); [account delete](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/accounts/views.py:486); [rx decision record](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/prescriptions/models.py:164).

### PPB-07 — High: expiry/verification of prescribing clinicians is not checked consistently

**Clauses:** 3/1.4(ii)(d); 5.1.11. A synthetic active clinician with expired license and `is_verified=False` was accepted by the booking serializer. The local aggregate audit found **two active clinician profiles with expired license dates**; this is a data observation, not proof they delivered real clinical care. Uploaded prescriptions also lack structured authoritative prescriber verification.

**Required:** current licensed professional/jurisdiction verification and expiry monitoring; use the same eligibility predicate in public selection, booking, claim, messaging, prescription issue and review as appropriate. Treat booking eligibility as one control, not the complete legal authenticity check.

**Source:** [clinician validation](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/consultations/serializers.py:532); [clinician eligibility](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/consultations/views.py:281).

### PPB-08 — High: electronic prescription authenticity and original follow-up lifecycle missing

**Clauses:** 3/1.4(ii)(a,c,d); 5.1.2; 5.1.11. Pharmacist approval accepted **200** for a synthetic pending prescription with blank prescriber identity and no required authenticity/original-receipt evidence. The approval actor/history is recorded, but does not establish authenticity. No original-received field, seven-working-day due date/follow-up or overdue exception process was found.

**Required:** structured prescriber identity/validity, authenticity method/evidence, prescription dates/validity and professional assessment; preserve the source. Implement the original-prescription follow-up required by this PDF with working-day handling and accountable exceptions. Confirm with PPB how any newer electronic-prescription rules apply before replacing this requirement with an assumption.

**Source:** [rx approval](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/prescriptions/views.py:547); [rx decision record](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/prescriptions/models.py:164).

### PPB-09 — High: required public identifiers and patient-document disclosures are empty

**Clauses:** 2.1.3; 3/1.4(iii); 10.1–10.2.3. Health safety code, premises registration, online license, superintendent name/registration, pharmacist consultation hours and postal address are all blank locally. Footer placeholders and a generic PPB link are not the required identifiers. The homepage still claims PPB registration when values are missing. Order email context/templates do not include the required superintendent identity/registration.

There is a useful existing production system check (`ava.E001`) that detects missing disclosure settings when deploy checks are run; that is not a verification of the underlying license or an enforcement point for all live supply.

**Required:** genuine current values and verification link, clear identity across medicine sale pages and applicable patient documents; remove unsupported accreditation claims until substantiated. Verify physical premises/business links and professional governance separately. Contact defaults copied from the PDF must be checked against current official PPB contacts rather than assumed reachable.

**Source:** [disclosure fields](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/support/models.py:5); [footer disclosures](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-frontend/src/components/Footer/Footer.tsx:140); [home registration claim](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-frontend/src/pages/HomePage/HomePage.tsx:1034); [production checks](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/support/checks.py:44).

### PPB-10 — High: medicine information is not sufficiently populated/validated

**Clauses:** 6.1.1–6.1.3. All **4,183** Rx-flagged/classified active variants have empty contraindication and side-effect fields in the aggregate audit. Regulatory/PIL fields exist but are optional. Product detail renders directions/warnings; that does not guarantee complete, current PIL-aligned safety information. Retailer-scraped descriptions and visually matched images do not establish medication authorization, safety content or clinical approval.

**Required:** authoritative medicine data with marketing authorization/PIL provenance/version, qualified reviewer and review dates; relevant contraindications/side effects and usage/storage/disposal information must be visible. Gate publication where required safety data is missing and audit both old imported catalog data and new enrichment.

**Source:** [catalogue fields](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/products/models.py:1051); [otc ui](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-frontend/src/pages/ProductDetail/ProductDetailPage.tsx:322); [data completeness](live-data-quality.json).

### PPB-11 — High: batch recall is not an implemented end-to-end workflow

**Clause:** 7.1.7. Inventory has batch/expiry/supplier fields and stock movements/order allocation row references. No dedicated recall case, affected-batch stop-sale, patient-order trace, notifications/acknowledgements, return/quarantine and closure process was found. Allocation IDs reference mutable rows rather than a complete immutable historical lot snapshot.

**Required:** recalled-batch quarantine/stop-sale at all purchasing/fulfillment paths; immutable batch/expiry provenance through dispensing; affected patient/order trace, notifications, response tracking and recall drill evidence.

**Source:** [stock traceability](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/orders/stock.py:83); [API inventory](api-inventory.md).

### PPB-12 — High: privacy notice and rights process are incomplete and overclaim security

**Clauses:** 9.1–9.3; 13.2–13.4. The public privacy page claims end-to-end encryption, specific 7/10-year retention and HIPAA alignment without supporting implementation/evidence. Health records are ordinary server-readable database fields; the optional application encryption field is used for a payout account, not a general clinical-record E2E scheme. Infrastructure disk/backup encryption may exist outside code but was not established. HTTPS is not the same as end-to-end clinical-record encryption.

Profile updates, account-scoped reads and soft deactivation do not establish a complete data-subject request process, purpose/lawful-basis notices, restrictions/objections, processor disclosures, incident procedures or retention-aware handling.

**Required:** accurate Kenya-focused privacy/rights notice and rights-request workflow with identity verification, decisions, timelines and legally justified retention; data protection governance, access reviews, incident response and verified encryption/key controls. Remove unsupported security/retention assertions while preserving required lawful clinical records.

**Source:** [privacy notice](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-frontend/src/pages/Legal/PrivacyPage.tsx:3); [encryption fallback](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/fields.py:10); [account delete](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/accounts/views.py:486).

### PPB-13 — High: daily secure offsite backup/restore evidence unavailable

**Clause:** 9.4. The evidence model can hold backup evidence, but none is loaded. No actual daily backup scheduler/configuration, protected offsite storage or successful recovery test was found in the reviewed repository. Log rotation is not a patient-data backup. This is an evidence gap; it does not prove infrastructure backups do not exist elsewhere.

**Required:** demonstrate encrypted daily DB/private-file backups, offsite/fire-protected storage, access controls, completion alerts, retention and a tested restore with recovery objectives.

### PPB-14 — High: operational registrations, hosting and third-party evidence unverified

**Clauses:** 2; 3/1.1–1.3; 9; 10.2.5; 13.1; 13.5–13.6. Local compliance evidence contains only **one synthetic QA audit record in review_due state**. No actual PPB/ODPC certificate, Kenya data-center ownership/contract, qualifying current domain X.509/EV certificate evidence or third-party SLA is supplied in that store. A blank evidence store is not proof the business lacks these documents elsewhere.

**Required:** verify current premises/online authorization, accountable superintendent, ODPC registration/renewal as applicable, specified Kenya hosting, certificate type/validity and all relevant processor/platform contracts. Inspector access must be operationally provisioned and least-privileged; do not publish inspector credentials in reports. Uploaded `active` evidence status alone is not validation of a certificate.

**Source:** [compliance evidence](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/support/models.py:78); [live aggregate](live-data-quality.json); [official PPB source](https://web.pharmacyboardkenya.org/download/guidelines-on-internet-pharmacy-services/).

### PPB-15 — Medium/high: quality assurance, SOPs and equipment validation not evidenced

**Clauses:** 3/1.11–1.12; 4.1; 11; 12. Feature tests are useful, but no approved recurring management-audit schedule covering all 12 areas, staff competency/training register, complete SOP suite, equipment calibration/service history, representative load/capacity report or exercised continuity/restore plan was supplied.

**Required:** superintendent-led SOPs, staffing/counselling quality audits, communication/delivery/privacy/content audits, training, corrective-action closure, equipment validation and inspector-readable controlled reports.

### PPB-16 — Medium: public service policies and return submission are incomplete

**Clauses:** 3/1.6; 7.1.6; 10.2.4. Working support tickets/contact help, return API quarantine and privacy controls are strengths. However the public `/returns` page contains a plain form without a submission handler; no saved request follows from its UI alone. Complete new/repeat/OTC counselling policies, delivery/return procedures and complaints escalation/response policy are not demonstrated by generic help text. Refund time/original-method promises on the return page are not evidence of an external refund executor.

**Required:** wire and test actual customer return creation/history; publish superintendent-approved accurate procedures; distinguish administrative refund recording from actual money returned. Keep unresolved refund inquiries open until settled.

**Source:** [return ui](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-frontend/src/pages/Returns/ReturnsPage.tsx:20); [prior live E2E-06 evidence](../../test-runs/2026-11-01/e2e06.md).

### PPB-17 — Medium: target deployment is not release-ready under current environment

**Clauses:** 9.3; 11; 13.5(c–d)/13.6(c–d). Production security-only check against the current local environment reports:

- `ava.E001`: seven required compliance fields missing.
- `ava.E011`: Turnstile secret not configured.
- `ava.E012`: required bot challenge disabled.
- `ava.E030`: development CORS origins still present.
- `ava.E031`: frontend origin is not public HTTPS.
- `security.W009`: Django secret-key strength/default-prefix warning. The key itself is not included in this audit.

These are current local configuration findings evaluated with the production settings module, not observations of a remote server. Existing code intentionally reports these release blockers. No secret was rotated or production policy weakened by this audit. The initial unrestricted deploy-check log also contains many OpenAPI introspection warnings; those are not hundreds of separate regulatory failures. Several APIViews lack sufficiently declared serializers, so auto-generated OpenAPI cannot be treated as a complete inventory. The resolver-based inventory avoids that blind spot.

**Required:** provide deployment-specific configuration, run clean release checks, complete API documentation where needed, verify active TLS/WSS/third-party transport and demonstrate actual hosted private-media denials. PPB's required certificate/hosting evidence remains separate from a passing Django check.

**Source:** [production checks](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/support/checks.py:44); [production https](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/settings/production.py:19); [security check](security-deployment-check.log); [full check including schema warnings](deployment-check.log).

### PPB-18 — Medium: medicine-abuse controls need clinical validation and longitudinal coverage

**Clauses:** 3/1.14; 5.1.8; 11.4.2. Quantity/frequency/IP/account-risk scoring, event logs and prescription reuse caps are implemented. These are a partial control, not evidence of complete medicine-specific abuse detection/refusal. Keyword-based medicine recognition and generic scoring thresholds can miss clinical risk; no demonstrated professional review disposition for all suspicious repeated medicine requests was found.

**Required:** superintendent-approved medicine-class/quantity/frequency rules, validated alarm/hold/refusal behavior, cross-order history and accountable review, with safeguards for legitimate patients. Test established/new accounts, multiple channels and renamed products. CAPTCHA alone cannot replace clinical monitoring.

**Source:** [risk scoring](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/accounts/bot_protection.py:213); [otc selector](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/orders/views.py:410); [rx authorization](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/avapharmacy/apps/prescriptions/dispensing.py:5).

## 3. Controls that are implemented and tested

- Role/ownership restrictions for customer records and professional dashboards; unrelated prescription read denied **404** in the targeted probe.
- Inspector prescription-register GET permitted **200**, write denied **403**; other inspector endpoints and protected evidence are present. Earlier audit-probe assumption that this GET was blocked was corrected; it is not an open defect.
- Unsigned M-Pesa callback denied **403** and unpaid finalization denied **400**; full regression includes payment replay/ownership and stock consistency checks.
- Approved exact-variant prescription matching, quantity/reservation checks and paid-item reuse protection; controlled flags/keywords are enforced within that Rx path, despite the independent classification gap.
- Private prescription grant/download, consultation/lab/evidence download checks and raw-media denial source rules. Hosted enforcement is still unverified.
- Transactional stock allocation, stock movement history, expiry/damaged-row exclusion, order events, consultation completion/earnings idempotency and lab collection/result controls.
- Patient/guardian child ownership, saved consent and separate same-name child histories.
- Return API quarantine/non-resale prerequisites and delivered-refund no-restock behavior; notification preferences/retry cap/ownership and public/private support-note visibility.
- Payout maker-checker and reconciliation logic, explicitly an administrative ledger. It is not evidence of an actual bank/M-Pesa transfer.
- Compliance evidence upload and inspector read-only access; evidence storage is a useful facility, not proof each legal/operational requirement is satisfied.

## 4. API/functionality coverage summary

| Area | Canonical routes | Inspected behavior and test coverage | Remaining issues |
|---|---:|---|---|
| Accounts | 37 | Registration/verification, login/JWT, reset/activation, role/admin/self profile, addresses/payment entries, deactivation, audit | Full subject-rights and retention governance; inspector operational provisioning |
| Products/inventory | 68 | Public listing/detail/search, brands/categories/content, images, admin variants/stores/batches/movements, wishlist/reviews, stock sync signature | Regulatory/supplier/medicine-class gates, POM promotions, PIL content, recall, public/internal data minimization review |
| Orders/payments | 66 | Cart/merge/checkout, provider callbacks/status/retry, finalize, fulfillment/tracking, reports, returns/delivery/POS | OTC professional decision, recipient/cold-chain enforcement, actual refund boundary, incomplete source/patient-document identity |
| Prescriptions | 15 | Upload/private files, queue/assignment/review, clarification, exact item cart/reuse, audit/register | Authenticity, prescriber eligibility, original within seven working days, retention protection |
| Consultations | 53 | Professional onboarding/status, paid booking/finalization, queue claim, chat/WebSocket/files, child/consent/history, PDF/Rx/earnings | License expiry/verification/jurisdiction, professional validation, five-year retention guarantees |
| Lab | 35 | Partner/facility/test/staff eligibility, quote snapshot, booking/cancel, code/processing, private results | Operational credentials/QA/retention; pay-later is the current payment scope |
| Support/settings/compliance | 8 | Settings public/write separation, newsletter, evidence/download, ticket notes/assignment/status | Empty disclosures, unsupported privacy claims, policies and current real evidence |
| Payouts | 8 | Source/recipient/amount, approvals, actions, ledger/reconciliation/private scope | Actual transfers are not implemented and cannot be inferred |
| Notifications | 8 | Inbox/read/preferences, delivery history, owner-scoped bounded retry | Independent external receipt, lawful marketing/processing evidence and clinical message governance |
| Schema/docs | 3 | Schema/UI route presence; resolver inventory covers omissions | OpenAPI declaration/introspection warnings and intended PPB access demonstration |

All nine application suites were run together. Passing functional tests prove their assertions at the tested layer; they do not prove all 301 endpoints implement all regulatory requirements. [Route-by-route list](api-inventory.md) includes handlers, methods, declared permissions, dynamic-permission marker and source location. Some AllowAny endpoints are intentionally public or enforce a secret/signature/token in the handler; AllowAny alone is not treated as a vulnerability.

## 5. Evidence and exact reproducibility

| Artifact | Result / meaning |
|---|---|
| [Existing regression log](full-regression.log) | 364 tests, 101.552 seconds, OK |
| [Targeted audit log](targeted-probes.log) | 14 observation probes, 8.910 seconds, OK; 10 gap observations + 4 protected controls |
| [Probe code](audit_probe_tests.py) | Disposable test DB fixtures; no real charge/care; assertions document current behavior, not expected future compliance |
| [Probe JSON](probe-results.json) | Machine-readable observations |
| [Live aggregate](live-data-quality.json) | Counts/field-population only; no patient record export; no live mutations |
| [Production security-only check](security-deployment-check.log) | Fails: 5 errors, 1 warning using current environment |
| [Migration check](migration-check.log) | No changes detected; no migration applied |
| [Frontend build](frontend-build.log) | TypeScript/Vite passed |
| [API resolver inventory](api-inventory.json) | All 301 canonical routes and alias-family description |
| [123-item requirements matrix](requirements-matrix.md) | Clause/page mapping with result, evidence and next action |
| [Source references](source-evidence.json) | 31 verified source file/line anchors |

Initial probe harness mistakes (missing required product ID, an unfinalized order fixture and an incorrect assumption about existing inspector read access) were corrected before interpreting the final results. Their first-run log is retained as diagnostic history, not counted as application defects. The initial full deploy check was sandbox-blocked from the DB; the final security-only check had database access and confirms the missing settings independently.

Reproduce from the backend workspace, with a configured disposable Django test DB:

```sh
venv/bin/python manage.py test apps.accounts apps.products apps.orders apps.prescriptions apps.consultations apps.lab apps.support apps.payouts apps.notifications --noinput
PYTHONPATH="$PWD/docs/compliance-audit/2026-11-04" venv/bin/python manage.py test audit_probe_tests --noinput
venv/bin/python manage.py check --deploy --tag security --settings=avapharmacy.settings.production
```

Do not run audit probes by manually reproducing them on real patient/stock/payment records. Future fixes must convert gap observations into tests requiring secure compliant behavior; keeping a test that merely reproduces a gap is not remediation.

## 6. Remediation order and acceptance

1. **Before real medicine supply:** verify business authorization/disclosures and real operational evidence; implement medicine registration/supplier and controlled-classification gates; remove public POM promotions; enforce professional supply decisions and valid prescribers/authentic prescriptions.
2. **Before release sign-off:** enforce retention/record integrity, safe delivery, original-prescription follow-up and recall; complete reviewed medicine safety information, accurate policies/rights workflows and release security configuration.
3. **Operational readiness:** demonstrate Kenya hosting/ODPC/current TLS and third-party contracts; daily offsite backups and restore, SOPs/staff competency, equipment maintenance, capacity/continuity drills and recurring superintendent QA audits.
4. Retest every finding across canonical/alias, customer/staff/inspector, direct and alternate paths. Run full regression, clinical/governance review and target-host smoke/security checks. Keep live Paybill/POS/external-refund limitations separate from compliance-code fixes.
5. The responsible superintendent and appropriate compliance/regulatory owners must review the matrix and underlying operational evidence. This technical audit does not grant PPB authorization, verify a certificate's authenticity or replace their sign-off.

**Current decision:** not ready to claim full adherence to the supplied guideline. Existing functionality can support compliance after the identified controls/data/evidence are completed; it does not establish compliance as it stands.
