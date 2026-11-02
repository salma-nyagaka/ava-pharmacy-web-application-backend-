# Accounts follow-up: fixes and verification

Date: 26 October 2026. Scope: finish the accounts checklist and repair failures found while testing. This follows [the initial setup/accounts run](setup-and-accounts.md).

## Current sign-off

**Accounts is not yet signed off as fully browser-tested.** All **59 automated account/consultation tests**, 17 live HTTP professional checks and the frontend build pass; four credential-entry website steps require the user's completion. These are deliberately not marked passed based on API tests or an acknowledgement alone.

The user approved synthetic payment-method saving/removal and submitting the synthetic professional application. No real payment was made and no real professional identity documents were used.

## Environment

- Frontend remains on **port 3000**, as requested. Its QA process uses `VITE_API_URL=http://127.0.0.1:8002/api`.
- QA backend: `127.0.0.1:8002`, separate PostgreSQL database `ava_accounts_qa_20261026`.
- Local SMTP receiver: `127.0.0.1:8025`; inbox UI: `http://127.0.0.1:8026/`. Messages were sent through actual SMTP and their links followed in the website. This verifies local delivery, not external-provider deliverability.
- `localhost:3000` holds customer sessions; `127.0.0.1:3000` was used for a separate admin session. Both use the same QA backend.
- The original backend on port 8000 and original application data were not used for these follow-up mutations.
- A QA-only `.env.local` was created in the frontend directory. `.env.development` takes precedence, so the running QA Vite process also uses an explicit environment override. Remove the QA-only file and restart Vite without the process override when this run is finished.
- The QA stack remains available for the required user credential-entry steps. Do not restore the original API connection while those steps are pending.

## Account acceptance matrix

| Scenario | Result and evidence |
|---|---|
| ACC-01 Registration → verification → login | Backend and actual HTTP registration pass, including duplicate rejection and denial before verification. Actual SMTP verification link opened in the website; success and token reuse rejection observed. **Pending:** user enters the new credential and submits the prefilled `browser.signup@avapharmacy.test` website form; then verify that account's email and login. |
| ACC-02 Invalid/duplicate input | Automated validation tests pass; live duplicate registration returns 400; unverified login returns 403. Invalid/deactivated login displays `Invalid credentials.` in the website. Negative coverage combines API checks with representative browser validation; not every negative payload was entered manually. |
| ACC-03 Profile persistence | Initial browser save/reload check passed, including the complete-profile response regression. Original QA name was restored. |
| ACC-04 Address/payment management | Browser address create, edit, reload and deletion passed. Fake card and M-Pesa references saved, edited, default switched, reloaded and removed. Deleting the default M-Pesa reference made the remaining card default; final removal persisted. Cross-customer read/write/delete restrictions pass in API tests. [Payment evidence before cleanup](accounts-follow-up/payment-methods.png). |
| ACC-05 Password change | API checks pass for wrong current password, password change, old-login denial, new login and refresh revocation. **Pending:** user completes the website form for `other@avapharmacy.test`; new credentials must be entered by the user. Current test password was prefilled. |
| ACC-06 Forgot/reset password | API email/reset, expiry/reuse rejection and password policy pass. Browser reset request submitted for `smtp.signup@avapharmacy.test`, message received over SMTP, link opened to the new-password screen. **Pending:** user enters/submits a new password; then verify new login and link reuse. [Reset request confirmation](accounts-follow-up/reset-email-sent.png). |
| ACC-07 Refresh/logout | API refresh/logout/refresh-reuse tests pass; browser sign-out observed. Naturally expired admin tokens exposed a frontend bug, now fixed and retested: admin page loaded again after a successful refresh request. |
| ACC-08 Permissions | API ownership, admin access and self-promotion checks pass. Opening admin user management as the customer redirected to the storefront rather than rendering admin controls. |
| ACC-09 Suspend/reactivate | Browser Cancel preserved state; confirmed Suspend showed Suspended; confirmed Activate showed Active. Live HTTP confirmed old access and refresh denied after suspension, fresh login permitted after reactivation, old refresh still denied. [Reactivated state](accounts-follow-up/admin-reactivated.png). |
| ACC-10 Professional onboarding | Full website doctor application completed through all seven steps, six marked synthetic documents uploaded, Terms/submission explicitly approved by user, success page and admin application/documents verified. Admin approval created an inactive linked account. Local SMTP interruption exposed a recovery defect; activation resend UI was added and succeeded. Received activation link opened to the password/Terms form. **Pending:** user completes that form and signs in; then verify dashboard and replay rejection. Doctor and pediatrician application → approval → activation → role dashboard already pass through API tests and 17 actual HTTP checks. |
| ACC-11 Account deletion/deactivation | Browser Keep account cancelled the action; confirming deactivation on the disposable QA customer signed it out. Old credentials were rejected in the website and API. Existing access/refresh denial covered by API tests. This is the existing **soft deactivation** feature, with retained service records; the UI now states that truthfully and no longer promises an unimplemented 30-day anonymization job. [Denied login](accounts-follow-up/deactivated-login-blocked.png). |

## Fixes made during the follow-up

1. **M-Pesa saves failed:** the website submitted zero card-expiry fields for M-Pesa, while backend card validation rejected them. M-Pesa now accepts/normalizes its non-card expiry; ordinary cards still require valid expiry, including when changing a saved method's type.
2. **No payment edit UI:** added editing for stored card/M-Pesa metadata, preserving the default flag. Editing uses saved last-four references and does not require the full original card number. Removed unused CVV collection and its misleading validation claim.
3. **Password reset weaker than signup:** reset now uses the configured Django password validators. Password change/reset revoke previous refresh sessions. Existing access tokens remain subject to their configured expiry; this change does not claim universal immediate access-token revocation.
4. **Missing account deactivation control:** added clear retained-record wording, a confirmation, cancellation, sign-out and useful error handling to Account Settings.
5. **Inconsistent API hosts:** account/professional services now use the shared client's configured base URL rather than independently choosing another host or environment-variable precedence.
6. **Expired admin sessions failed:** those services now use `apiFetch`, which delegates to the shared authenticated client for refresh/retry while preserving service-specific response/error processing. Retested against an actually expired admin session.
7. **Duplicate email verification submissions:** the website reuses its in-flight verification request across React development-effect reruns, avoiding a successful one-time token being followed by a duplicate failed submission.
8. **Suspended displayed as pending activation:** fixed status precedence in admin user management. Replaced blocking native status confirmations with an in-page confirmation; Cancel, Suspend and Activate retested.
9. **Incomplete professional application returned 500:** omitted licence expiry now produces validation errors rather than a missing-key exception.
10. **Pediatrician approval skipped activation provisioning:** approval now creates the correct pediatrician account in approved/pending-activation state, using the same activation gate as doctors. Role and dashboard regressions pass.
11. **SMTP failure could partially approve/provision:** doctor/pediatrician approval is transactional. A simulated delivery failure now rolls back approval/account creation and a subsequent retry succeeds. Added an activation-email resend action for already-linked pending accounts, and hid duplicate provisioning for linked accounts. The previously partial QA account was recovered through that UI action.
12. **Validation/copy defects:** Account Settings now reads standard API error messages; doctor onboarding no longer shows lab-organisation-only instructions.

The initial reset-email plain-text URL and profile-save response fixes remain in place and covered by regressions.

## Evidence and verification commands

- [Latest backend account/consultation log](accounts-follow-up/backend-tests.log).
- [Frontend TypeScript/production build log](accounts-follow-up/frontend-build.log).
- [Actual HTTP professional checks](accounts-follow-up/http-professional-checks.json): 17 successful assertions covering doctor and pediatrician application, approval, activation, login, dashboard access and admin denial.
- [Actual HTTP registration and SMTP check](accounts-follow-up/http-registration-checks.json).
- [Suspension checks](accounts-follow-up/suspension-checks.json) and [reactivation/deactivation checks](accounts-follow-up/lifecycle-checks.json).
- [Email verification screenshot](accounts-follow-up/email-verified.png).

```sh
venv/bin/python manage.py test avapharmacy.apps.accounts.tests avapharmacy.apps.consultations.tests --noinput --verbosity 2
venv/bin/python manage.py check
```

From the sibling frontend directory:

```sh
npm run build
```

The database and isolated API tests establish backend behavior; build success establishes compilation, not completion of the four pending browser credential steps.

## Required user completion

Browser tooling requires user handoff before new credential entry, confirmation and submission. The prepared steps are:

1. **Account Settings → Password**, `other@avapharmacy.test`: current synthetic password `AccountsQA123!`; enter a new test-only password and submit.
2. **Set new password**, `smtp.signup@avapharmacy.test`: reset link came from the local SMTP inbox; enter/confirm a test-only password and submit.
3. **Activate Doctor Account**, `browser.doctor@avapharmacy.test`: received link is open; enter/confirm a test-only password, review Terms and activate.
4. **Create your account**, `browser.signup@avapharmacy.test`: non-credential fields prefilled; enter/confirm a test-only password and complete signup/Terms.

The user's “kk” acknowledged this handoff; it is not evidence that any form was submitted. At the last backend check the first two accounts still used their initial test password, the browser doctor was inactive, and the browser signup account did not exist. Do not mark these checks passed until actual results are verified.

The prepared automation tabs were subsequently closed before credential entry was confirmed. Reopen Account Settings and signup on `http://localhost:3000`; reset and activation links are available in the local SMTP inbox at `http://127.0.0.1:8026/`. The account-settings test login is `other@avapharmacy.test` with its initial test password above. For browser signup use the synthetic email above, name Browser QA, phone +254700099101, and a synthetic Nairobi delivery address.

After completion, verify the relevant success screens, new logins, old-password denial, token replay denial, then update the checklist and restore the original port-3000 API connection. Raw activation/reset tokens and captured SMTP message bodies are kept outside the repository.

The user subsequently requested generated test passwords and delivery to their specified Gmail address. Four instructions emails (change password, reset, professional activation and signup) were accepted by the application's configured Gmail SMTP service. These contain generated passwords to enter in the browser; sending them did not apply the passwords or complete the pending checks. A fresh professional activation link was issued: use the latest emailed link, not an earlier captured copy. The password-bearing temporary send script was removed after delivery; generated passwords are not stored in this repository.

After the user confirmed a corrected recipient spelling, all four emails were resent successfully to that confirmed address, with fresh reset/activation links where applicable. SMTP accepted all four corrected-recipient messages. Use the newest emails; earlier activation links were superseded. The temporary resend script containing credentials was removed.

The user then requested branded versions matching the site. Four reusable HTML QA templates, a shared branded frame, a plain-text fallback, an inline AVA logo and a reusable multipart sender were added under `templates/accounts/emails/qa/` and `apps/accounts/qa_emailing.py`. Four email tests passed (all variants, links, escaping and MIME/logo structure); browser layout checks found no overflow or broken images at desktop and narrow mobile widths. Placeholder-only previews and screenshots are under `output/email-previews/`. All four branded messages were accepted by the configured Gmail SMTP service for the confirmed recipient; the temporary credential-bearing send script was removed. Email delivery still does not complete the pending credential-entry checks.


## 27 October: registration required fields

Date of birth is now required in the form/API; future dates are rejected. Every visible registration field requires a value (gender includes an explicit Prefer not to say option). Blank submission displays a specific inline message for all ten fields and does not submit registration. Backend checks reject missing, blank and whitespace values. All 47 account tests and the frontend build pass. Browser empty-form validation was verified on port 3000; credential-entry checks remain pending.


## 27 October: active backend restored to port 8000

At the user’s direction, removed the QA-only frontend `.env.local` override and restarted port 3000 without the port-8002 process override. The frontend uses its existing development API configuration, `http://localhost:8000/api`. The registration endpoint on port 8000 responds (GET returns 405, as expected for POST-only registration). Earlier isolated QA data and email links refer to the old QA environment and do not establish account state on port 8000.


## 27 October: user acceptance

The user explicitly confirmed that all four remaining credential-entry steps passed and requested moving to the next module. ACC-01, ACC-05, ACC-06 and ACC-10 are now recorded as user-verified browser passes, supported by the earlier automated/API checks. This confirmation supersedes the pending handoff status above; no new independent browser verification is claimed.
