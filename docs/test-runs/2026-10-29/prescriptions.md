# Prescriptions — 29 October 2026

**Historical initial run — superseded by [prescription completion](prescriptions-completion.md).** The findings below describe the pre-fix state.

Initial acceptance run by Codex. **Module sign-off is incomplete.** Customer upload and clarification were exercised in the browser, with the prepared pharmacist using real authenticated HTTP API requests. Other results below are isolated Django API regressions, not full website passes.

Environment: frontend `http://localhost:3000`, backend `http://127.0.0.1:8000`, local PostgreSQL. Existing synthetic setup customer (ID 75) and setup pharmacist used. No real clinical data or payment was submitted. Browser upload: prescription **44 / RX-E1E8ED**. It remains pending after the clarification reply so the next review can continue from the same record.

| Scenario | Outcome | Evidence / remaining work |
|---|---|---|
| RX-01 | Pass — customer browser / pharmacist API | Uploaded shared synthetic PDF, received RX-E1E8ED, refreshed owner list and expanded its persisted file/doctor/notes. Pharmacist login, queue HTTP 200, assignment HTTP 200. Pharmacist queue browser interaction remains unverified. |
| RX-02 | API pass; browser validation incomplete | Unsupported text, >5 MB PDF, missing patient name and missing file each return 400 without creating a prescription. Browser validation/error presentation remains unverified. |
| RX-03 | API pass; browser review incomplete | Existing tests assign, search variants, approve exact mapping and record reviewer/decision. Live record assigned to setup pharmacist. Browser mapping remains unverified. |
| RX-04 | Pass — customer browser / pharmacist API | Pharmacist requested clarification over HTTP; customer opened thread and replied in browser. Status returned to pending. Pharmacist authenticated detail request confirms both messages and audit records. Separate resubmit regression passes. |
| RX-05 | API pass; browser rejection incomplete | Rejection reason visible to owner API, and pending/rejected items cannot be added to cart. Complete checkout rejection and browser rejection display require further acceptance work. |
| RX-06 | Incomplete | Approval → exact mapped item → cart API regression passes. No prescription-linked paid order was completed in this run. |
| RX-07 | Partial API pass | Excess quantity and cumulative cart quantity rejected; previously paid prescription item cannot be added again. Complete substitution, competing unpaid-order and dispensing-limit checks remain to run. |
| RX-08 | Partial API pass | queued → packed → dispatched → delivered persists and owner detail reflects final state; audit entries identify actor. Current audit action describes prescription approval status rather than the changed dispatch value, so individual dispatch history and customer notification coverage need further work. No full browser dispensing journey is claimed. |
| RX-09 | **Fail — public attachment access** | Restricted pharmacist API bypasses reproduced and fixed; unrelated customer API access regression passes. Unauthenticated GET of `/media/prescriptions/44/synthetic-prescription.pdf` returns HTTP 200, application/pdf, 1814 bytes. Prescription attachments still require protected serving and browser-compatible authorized downloads; API permission fixes alone are insufficient. |

## Fix and regression evidence

A pharmacist without `prescription_review` permission could read another patient's prescription through the general detail endpoint, approve it through the general update endpoint, and add arbitrary audit entries. These three regression subcases originally returned HTTP 200. Detail, update and audit now enforce the review permission; the alternate prescription register also enforces it while retaining inspector read access and active-admin access. Restricted staff cannot use the register to bypass the detail restriction.

Added upload validation, unrelated-customer access, pending/rejected cart, cumulative quantity, alternate pharmacist route, rejection visibility and dispatch persistence tests.

- [Regression log](prescriptions/regressions.log): **29 tests passed** (16 prescription tests and 13 existing checkout/order tests). Checkout tests do not establish a new provider-confirmed prescription payment.
- Django system checks and scoped `git diff --check` passed.
- [Live pharmacist queue / clarification evidence](prescriptions/live.json)
- [Unauthenticated attachment finding](prescriptions/file-access.json)
- [Customer clarification screenshot](prescriptions/customer-thread.png)

The public attachment finding is still open. Existing unrelated workspace changes were preserved. Do not treat this initial run as completion of RX-02/03/05–09 or E2E-02.
