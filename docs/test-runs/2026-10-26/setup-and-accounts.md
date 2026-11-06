# Setup and accounts test run — 26 October 2026

Follow-up: [account fixes and completion status](accounts-completion.md). The results below describe the initial run and are retained as history.

## Result

**33/33 backend account tests passed.** Browser checks passed for incorrect/correct login, profile save and reload, address creation/edit/reload, opening payment methods, and sign-out. Two defects were found, fixed, and retested. Full browser account coverage is still incomplete; see the pending checks below. Other modules have not been executed in this run.

Checklist: [end-to-end test checklist](../../end-to-end-test-checklist.md).

## Environment and evidence

| Detail | Observed value |
|---|---|
| Frontend | http://localhost:3000; repository commit `925e5b6` |
| Backend | http://127.0.0.1:8000; repository commit `c47b265` plus existing local changes and this run's fixes |
| Database | Local PostgreSQL; all current migrations applied |
| Django system check | No issues |
| Automated test isolation | Separate `test_avapharmacy` database, created/migrated and destroyed by Django |
| Automated email | Django in-memory test outbox; no real inbox delivery established |
| Development email | SMTP configured; delivery not exercised |
| Background services | PostgreSQL and Redis listening; configured Celery broker is `memory://`. Separate worker/scheduled-task behavior not established |
| Bot challenge | Disabled in local development; configured challenge and honeypot paths covered by existing isolated tests |
| Browser account | Existing synthetic `qa.customer@avapharmacy.test` |
| Backend evidence | [test log](accounts-tests.log) |
| Setup baseline | [fixture references and stock](setup-fixtures.json) |
| Browser evidence | [successful profile save](profile-save.png) |

Re-run backend tests:

```sh
venv/bin/python manage.py test avapharmacy.apps.accounts.tests --noinput --verbosity 2
```

The suite includes 22 existing tests and 11 added journey/regression tests in `avapharmacy/apps/accounts/tests/test_account_journeys.py`. Tests use actual JWT login where relevant; some existing tests authenticate directly. This is API integration coverage, not a claim of 33 browser journeys.

## Setup progress

| Scenario | Outcome | Evidence / remaining work |
|---|---|---|
| SET-01 | Partial | Frontend, API, PostgreSQL, migrations and browser/API connection verified. Background jobs and scheduled execution remain unverified. |
| SET-02 | Prepared; role login coverage partial | Existing QA admin, customers, pharmacists, doctors and pediatricians found. Created missing synthetic inventory, lab-partner and lab-technician users: IDs 67, 68, 69. Created linked lab profiles. Browser login checked for QA customer; isolated tests cover admin/pharmacist login. Other dashboard logins remain to be exercised. |
| SET-03 | Partial | Existing pending doctor/pediatrician profiles found. Suspended/active account transitions exercised in isolated tests; a dedicated persistent suspended professional fixture remains to be prepared. |
| SET-04 | Pass: data preparation | Created two dedicated test stores and one inactive test product with separate variant/store inventory rows. See baseline below. This does not establish stock-deduction behavior. |
| SET-05 | Pass: data preparation | Prepared ordinary, prescription-required, zero-stock, low-stock and backorder variants. Product remains inactive until catalog testing. |
| SET-06 | Partial | Account tests generate synthetic files in isolation. Shared prescription/lab upload files, coupons and delivery fixtures for later browser journeys remain to be prepared. |
| SET-07 | Partial | Test variant prices and stock baselines recorded. Shipping, consultation, promotion, payout and external payment/POS test configuration still require verification in their respective stages. |

The local fixture preparation script is retained as [prepare-local-fixtures.py](prepare-local-fixtures.py). It checks development mode/local database, creates only named QA records, and uses `get_or_create` without resetting existing stock or credentials. To reuse it from the repository root:

```sh
venv/bin/python manage.py shell -c "exec(open('docs/test-runs/2026-10-26/prepare-local-fixtures.py').read())"
```

Generated passwords are stored only in `/private/tmp/ava-e2e-credentials-20261026.json`, with mode 0600; credentials are not included in this report or the repository. The script creates fixtures directly; it does not prove application onboarding or admin approval flows.

### Inventory baseline prepared for the next stage

Inactive product ID: `22365`, SKU `E2E-QA-20261026`.

| Variant SKU suffix | ID | Price (KES) | Test store 1 | Test store 2 | Purpose |
|---|---:|---:|---:|---:|---|
| A | 23495 | 100.00 | 50 | 30 | 500 mg tablets, pack of 20 |
| B | 23496 | 400.00 | 15 | 10 | 500 mg tablets, pack of 100 |
| RX | 23497 | 200.00 | 10 | 10 | Prescription required |
| ZERO | 23498 | 100.00 | 0 | 0 | Out of stock |
| LOW | 23499 | 100.00 | 2 | 1 | Below threshold of 5 |
| BACK | 23500 | 100.00 | 0 | 0 | Backorders enabled, maximum 5 per inventory row |

All variant SKUs start with `E2E-QA-20261026-`. Store codes are `e2e-qa-20261026-1` and `e2e-qa-20261026-2`. Prices and medicine descriptions are synthetic fixtures.

## Account scenario results

“API pass” means the backend portion passed; unexecuted browser/email steps remain pending even if that portion passed.

| Scenario | Backend outcome | Browser outcome / limitation |
|---|---|---|
| ACC-01 Register, verify, login | Pass: pending registration, blocked pre-verification login, emailed token, activation and successful login; used/expired verification rejected | Existing QA customer login passed. Registration screen opens and incomplete form disables submission. New website registration through a delivered email has not been completed. |
| ACC-02 Invalid/duplicate input | Pass: duplicate registration, invalid required details, weak password and incorrect credentials covered | Incorrect credentials display `Invalid credentials.` Full registration validation not exercised in browser. |
| ACC-03 Profile save/persistence | Pass, including complete profile response from both profile endpoints | Pass after fix: changed QA first name, saved, reloaded and observed persistence. Restored original first name, then saved again; name and membership details stay visible. |
| ACC-04 Addresses/payment entries | Pass: own address/payment creation/update/removal/default handling; another user's records reject GET/PATCH/DELETE | Synthetic address added, edited and confirmed after reload; payment methods screen opens. Address deletion and payment-entry creation/edit/deletion were not executed in the browser. |
| ACC-05 Password change | Pass: wrong old password rejected; old credentials fail after successful change and new login succeeds | Not executed in browser; browser credential changes require user handoff. No existing QA password was changed. |
| ACC-06 Forgot/reset password | Pass after fix: reset email URL used successfully; old login, reused link and expired link rejected | Actual inbox delivery and browser reset flow unverified. |
| ACC-07 Refresh/logout | Pass: refresh succeeds, logout succeeds, logged-out refresh reuse rejected | Sign-out returns to login with protected account-page redirect. |
| ACC-08 Role restrictions | Pass: customer cannot access admin users or self-promote through profile/registration fields | Broader staff navigation checks pending. |
| ACC-09 Suspension/reactivation | Pass: admin suspends customer, existing access/refresh fail, login denied; reactivation permits fresh login but old refresh stays blocked | Admin UI workflow not exercised. |
| ACC-10 Professional application/activation | Pass for covered paths: doctor application/documents/resubmission, pharmacist provisioning/activation/login, expired/reused activation rejection | Complete professional website application → admin approval → activation → dashboard journey pending. Doctor/pediatrician end-to-end onboarding remains part of consultation testing. |
| ACC-11 Account deletion | Pass: soft deletion blocks existing access and refresh; synthetic account email is anonymized by the current implementation | Browser deletion not exercised. Long-term 30-day retention/anonymization behavior is not established by the immediate soft-delete test. |

## Defects fixed

### ACC-BUG-01 — malformed plain-text password-reset link

- Evidence: new reset journey could not parse the `token` query parameter in the actual test email because the separator was `&amp;token=`.
- Cause: HTML autoescaping applied to the plain-text reset URL.
- Fix: disable escaping only for the generated URL in `templates/accounts/emails/password_reset.txt`. HTML email escaping remains unchanged.
- Retest: reset journey now consumes the emailed URL, changes the password, logs in successfully, and rejects reuse/expiry. Full account suite passes.

### ACC-BUG-02 — saving profile clears account name on screen

- Reproduction: sign in as QA customer → Account Settings → Save changes. Account header becomes `Your account`, sidebar becomes `My Account`, membership information disappears. Saved first name survives reload, but shared sidebar name is lost from frontend state.
- Cause: PATCH returned only writable profile fields; the website replaces its profile with that response and expects fields such as `full_name`, ID, role and joining date.
- Fix: both profile endpoints validate with the write serializer and return the complete read profile. `AccountProfileView` reuses `MeView` so both routes behave consistently.
- Retest: regression test checks PATCH matches subsequent GET for both routes. Browser save now retains `QA Customer` in the header/sidebar and the membership date. [Screenshot](profile-save.png) records successful save feedback.

## Remaining work before declaring full account E2E complete

- Use an approved test inbox to establish real email receipt, link navigation and delivered activation/reset emails. In-memory email tests establish generated content only.
- Complete website signup with user approval of the Terms action. Browser tooling requires confirmation at the time of accepting Terms.
- Complete browser password-change/reset credential entry through user handoff, as required by browser tooling. API behavior is already covered in an isolated test database.
- Exercise remaining address/payment-entry browser actions and professional/admin dashboard flows. Saving payment data and permanent browser deletion have additional browser confirmation requirements; neither was performed.
- Verify pending setup dependencies before the module that needs them. External payment/POS services and background jobs are not marked passed.

## Local data changes left for continued testing

- Three new synthetic QA staff users and linked lab profiles.
- Two dedicated test stores, one inactive test product, six variants and twelve stock rows, with references saved in the baseline JSON.
- One customer address labelled `E2E Test 20261026`, street `Synthetic QA Address Updated`, retained as a named QA fixture.
- QA customer's first name restored to `QA`; browser signed out.

Existing unrelated worktree edits were retained. No real payment, medicine order, provider transfer, or external POS update was executed.
