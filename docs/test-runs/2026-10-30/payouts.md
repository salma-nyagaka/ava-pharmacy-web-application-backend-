# Payout acceptance — 30 October 2026

All seven PAY scenarios pass at the documented local browser/API/automated layers. This implementation is an **administrative payout ledger**: approval, processing, recorded payment, reversal and reconciliation do not execute or reverse a bank/M-Pesa transfer. Every payment reference created in this run is explicitly SYNTHETIC QA. No actual payout was sent and no external receipt is claimed.

## Scenario results

| Check | Evidence and outcome |
| --- | --- |
| PAY-01 | Admin browser saved a temporary Doctor reference rate of KSh 500. Browser created **PAY-2442FD / id 1** for synthetic doctor user 80, source **CONS-EE8CBC**, recorded gross 500 − commission 50 − withholding 0 − deductions 0 = **net 450**. Source matches completed consultation 34, its succeeded simulated payment intent and clinician earning 10. API recovery fixture independently checked 500 − 50 − 20 − 10 = **420** for QA lab partner user 82. Rules are manual reference rates; they do not generate payouts. Consultation payouts use recorded payment/earning values. |
| PAY-02 | Browser creation/submission passed. Browser correctly rejected creator user 77 approving their own payout. Separate existing QA admin user 71 approved via live API. Browser processing, payment recording and reconciliation passed. Creator, reviewer, approver, submitter, timestamps and all six main audit actions were verified. |
| PAY-03 | Main record **PAY-2442FD** is paid/matched, net KSh 450, reference **SYNTHETIC-QA-NO-TRANSFER-30**, correct recipient and source. Doctor browser earnings show October 2026 revenue 450, recorded paid status, payment date and pending 0. Recipient-scoped API returns exactly their own payout. Actual funds receipt is not inferred. |
| PAY-04 | Automated source/idempotency duplicate checks and PostgreSQL concurrent duplicate creation passed. Same payment reference across payout records, across payment/provider fields, with case changes or legacy lowercase data is rejected. Concurrent payment actions leave one paid record and one payment audit. Repeated live payment/reconciliation actions return 409. Cancelled/reversed sources and references remain reserved. |
| PAY-05 | Live API **PAY-0FA556 / id 2** passed hold → release → reapproval → processing → failure → retry → recorded paid → matched → reversed/exception. Net remains 420 and retry count 1. **PAY-038A60 / id 3** cancelled with reason. Automated checks cover invalid transitions, missing reasons, repeated retry/reversal, future/pre-request payment times and mandatory reapproval after release. Reversal records an administrative exception; no funds move. |
| PAY-06 | Automated and live API checks deny customer/professional admin ledger access and actions. Recipient-scoped listing excludes other recipients, customers see no payout data and anonymous access is denied. Suspended admins/recipients are blocked. Consultation source validation rejects another clinician's source. Django admin payout editing/add/delete is disabled to preserve workflow controls. |
| PAY-07 | Code inspection and live response `execution_mode=administrative_record` confirm no transfer execution adapter is invoked. Admin and clinician screens now state the record/transfer distinction. Actual-provider transfer confirmation is not applicable to this configured implementation. |

## Bugs fixed and missing workflow added

- Negative deductions and negative task rates no longer increase payouts. Gross/deduction bounds and KES currency validation are enforced.
- Payouts require a real active recipient with matching role; the server uses the account's name. The browser now loads account-backed recipients for all five professional roles and sends the chosen user ID instead of creating an unlinked name-only record.
- Added consultation-source validation against a completed consultation, succeeded payment intent and recorded earning. Gross/commission must match their historical amounts; a consultation reference cannot bypass validation as a manual adjustment.
- Added source selection, commission/withholding/other-deduction inputs, net preview, audit details, usable API error messages and visible action progress to the admin form.
- Fixed payment timestamps to include the browser's timezone and reject future/pre-request times.
- Added duplicate-reference normalization/case checks, cross-field protection and transaction advisory locks for concurrent reference use. Database uniqueness conflicts return 409 without breaking the surrounding transaction.
- Release from hold clears prior approval and requires approval again. Failed payouts use the counted retry action. Duplicate reconciliation transitions return 409.
- Added recipient-scoped `payouts/mine/` and admin `admin/payout-recipients/` endpoints. Clinician earnings include their linked payout record; the browser no longer labels every earning as merely scheduled after payment is recorded.
- Removed misleading automatic-transfer claims. Existing rules are reference rates for manual entries; saving a rule does not create/pay records. Notifications are scheduled after the financial transaction commits, keeping delivery outside locked database work; their messages and metadata identify administrative records rather than claiming a transfer.
- Preserved existing unrelated workspace changes. No payout model migration is required.

## Verification and retained evidence

- [Regression log](payouts/regression-tests.log): **64 tests passed** — 19 payout and 45 consultation tests, including PostgreSQL concurrency cases.
- [Baseline](payouts/baseline-tests.log): original four payout tests passed before fixes. Their arbitrary source fixtures now explicitly use manual adjustment references because real consultation sources are validated.
- [Frontend build](payouts/frontend-build.log): TypeScript/Vite production build passed.
- `manage.py makemigrations payouts --check --dry-run`: no missing migrations. Patch formatting check passed.
- [Main reconciliation, recipient scope and cleanup](payouts/live-reconciliation-evidence.json).
- [Recovery/cancellation actions and audits](payouts/live-recovery-evidence.json).
- [Admin reconciliation and audit screenshot](payouts/admin-reconciled.png), [professional earnings screenshot](payouts/professional-earnings.png).

The temporary Doctor rule is inactive again; before this run there were no payout rules. Three labelled synthetic ledger records remain for review. Source earnings were not changed. No actual provider transfer, hosted deployment or external notification delivery was verified.

The doctor connected journey E2E-03 remains partial: its administrative payout/reconciliation now passes, but the earlier consultation and medicine payments were simulated. This does not close genuine doctor payment CON-04, Paybill ORD-06 or POS blockers.
