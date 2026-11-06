# AvaPharmacy: your step-by-step manual testing checklist

Prepared **4 November 2026** from the current website routes and local acceptance records. This is a **new blank manual run**, not a copy of previously passed results. No test has been performed on your behalf by creating this guide.

Use the [interactive checklist](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/output/manual-testing/index.html) for checkboxes, case outcomes, notes, print and a JSON backup. Use this Markdown file if you prefer editing or printing a document. The existing [technical acceptance checklist](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/docs/end-to-end-test-checklist.md) remains separate.

## Start here

1. Complete preparation cases M01–M02 before paying or editing test records.
2. Follow customer sections 2–10 in order. Invite the named staff role when a handoff is needed. You can personally play each role using separate browser profiles.
3. Use sections 11–13 for staff, inventory, payout, notification and support checks. If you have only customer access, mark staff steps **Blocked — staff partner required**, rather than skipping them silently.
4. Repeat the main tasks on mobile using M52–M53. Finish with the six connected runs and reconciliation in M54–M56.
5. Tick a step only when you performed it and saw its expected result. A case can be **Not started, Pass, Fail, Blocked, Partial or N/A**. Failures need the actual result and evidence; N/A needs a scope reason.
6. After every save, payment, status update or permission change, refresh and reopen the record. For sensitive records also compare the other role's view. Keep one reference chain per journey.
7. Run payment failure, rejection, cancellation and deactivation branches on separate disposable fixtures unless the case explicitly says to retry the same draft. Do not consume the prescription/booking needed for a later case.

## Your run sheet

| Field | Fill in before starting |
|---|---|
| Run ID | MANUAL-QA-YYYYMMDD-yourinitials |
| Tester / date / timezone | ______ / ______ / Africa/Nairobi |
| Reviewer / date | ______ / ______ |
| Website / release or build | ______ / ______ |
| Desktop browser / version / operating system | ______ |
| Phone / browser / version | ______ |
| Customer A / Customer B / guardian labels | ______ (no passwords) |
| Pharmacist / doctor / pediatrician / lab partner / technician | ______ |
| Inventory / admin maker / admin checker | ______ |
| Payment environment / authorized phone suffix / per-payment budget | ______ / ______ / ______ |
| Email test mailbox or viewer | ______ |
| Evidence folder / known issues / staff contact | ______ |

## Page shortcuts

Replace the base URL with your agreed test website. These routes were checked in the current frontend source; a missing/inaccessible page in your running build must be recorded.

| Purpose | Path |
|---|---|
| Home / products / cart / checkout | `/` · `/products` · `/cart` · `/checkout` |
| Sign up / sign in / password reset request | `/register` · `/login` · `/auth/forgot-password` |
| Account details / addresses / payment entries / settings | `/account/edit` · `/account/addresses` · `/account/payment` · `/account/settings` |
| Orders / prescriptions / consultations / lab history | `/account/orders` · `/account/prescriptions` · `/account/consultations` · `/account/lab-tests` |
| Prescription upload / doctor / pediatric / lab booking | `/prescriptions` · `/doctor-consultation` · `/pediatric-consultation` · `/lab-tests` |
| Notifications / support / favourites | `/account/notifications` · `/account/support` · `/account/favourites` |
| Tracking / return form / contact | `/track-order` · `/returns` · `/contact` |
| Professional application | `/professional/register` |
| Pharmacist / doctor / pediatrician | `/pharmacist/dashboard` · `/doctor/dashboard` · `/pediatrician/dashboard` |
| Lab partner / lab technician | `/lab/dashboard` · `/labtech/dashboard` |
| Inventory staff | `/inventory/manage` |
| Admin products / inventory / orders / prescriptions | `/admin/products` · `/admin/inventory` · `/admin/orders` · `/admin/prescriptions` |
| Admin doctors / labs | `/admin/doctors` · `/admin/lab-partners` · `/admin/lab-tests` · `/admin/lab-requests` |
| Admin finance / payouts / reports / support / settings | `/admin/invoices` · `/admin/invoices?view=payouts` · `/admin/reports` · `/admin/support` · `/admin/settings` |
| Restricted compliance evidence | `/account/compliance` |

## Files and example data

- [Synthetic prescription PDF](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/output/pdf/qa-setup/synthetic-prescription.pdf).
- [Synthetic lab-result PDF](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/output/pdf/qa-setup/synthetic-lab-result.pdf).
- [Invalid text upload](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/output/pdf/qa-setup/invalid-upload.txt).
- Example address: `SYNTHETIC QA training address`, with a valid county/area selected from the actual form.
- Example complaint/message: `SYNTHETIC QA only — no real clinical request.`
- Example children: identical display names with distinct dates of birth; record child IDs, not names alone.
- [Recently enriched catalog products](/Users/salmanyagaka/Documents/ava-pharmacy-web-application-backend-/output/catalog-scrape/README.md) provide optional examples for checking descriptions, pack sizes and images.
- Ask the administrator for current account credentials and a current KSh 1 fixture; this guide intentionally contains no passwords, secrets or full payment phone number. Existing historic paid records are for reference, not fresh purchases.

## Known limits to record honestly

These are the latest recorded limits from 1 November plus the Returns form source inspection on 4 November. Recheck the running build; do not assume they are unchanged.

| Area | How to treat it in your manual run |
|---|---|
| Public return form | Current `/returns` form has no submission handler. A refresh without a saved return reference is a failed website step. Use support for assistance while keeping the UI gap recorded. |
| Paybill confirmation | Actual provider confirmation remains unverified. Mark Blocked if it cannot be demonstrated; STK success does not prove Paybill. |
| Real POS | Held at the user's request. Do not resume without an agreed authorized test environment. |
| External refunds | Current endpoint records an external refund; it does not execute one. Actual provider proof is needed before claiming money returned. |
| Payouts | Administrative ledger; no provider transfer adapter executes. Use explicit synthetic ledger references for ledger-only QA. |
| Lab payment | Pay-later; no online lab payment offered. A pending lab payment is not automatically a booking failure under this policy. |
| Card and cash on delivery | Excluded from current product scope. Mark those method-only tests N/A; report if the UI offers them as usable new methods. |
| External email/SMS | Backend acceptance/in-app notice does not prove recipient delivery. Observe the real test inbox/phone if required. |
| Hosted deployment | Prior local builds/private-media source changes do not prove deployed protection or production readiness. |
| Older pediatric intent 50 | Earlier requires_action KSh 1 request has no confirmed receipt/booking. Staff must reconcile it; do not resend, delete its fixtures or count it as paid from this guide. |

## How to record each case

For a failure, stop dependent payment/fulfillment work on that fixture and write the problem before moving on to an independent case. Never put passwords, PINs, tokens or real medical information into notes or screenshots. An API workaround can support diagnosis but does not turn an unavailable website step into a website pass.

Each case below includes the role, setup and acceptance-check references. The interactive copy has a result selector and notes box per case. In Markdown, fill the Result and Evidence lines. All boxes start empty.


## 1. Prepare your manual run


### M01. Confirm the environment and test accounts

**Role:** Tester; administrator. **Covers:** SET-01 SET-02 SET-03.

**Before starting:** Use a test environment prepared by the project owner.

- [ ] **M01.01** — Open the website URL recorded in your run sheet. Start with http://localhost:3000 only if testing on the same computer as the running application. **Expected:** Homepage loads and its product requests finish; no endless spinner or generic connection error.
- [ ] **M01.02** — Write the date, tester name, browser/version, device and website URL in the run sheet. Ask the administrator to record the release/build. **Expected:** The run can be reproduced against one identified environment.
- [ ] **M01.03** — Prepare Customer A, unrelated Customer B, guardian, pharmacist, doctor, pediatrician, lab partner, technician, inventory staff and two separate administrators. **Expected:** Each person has an individual test login and the correct dashboard; maker and checker are different people.
- [ ] **M01.04** — Prepare one pending and one suspended professional account. Do not suspend your only administrator. **Expected:** These accounts can be used for eligibility tests without disrupting the team.
- [ ] **M01.05** — Use separate browser profiles for different roles. Use two tabs within the same profile only for concurrency tests involving the same account. **Expected:** A customer session is not accidentally replaced by a staff login; private/incognito windows from one browser may still share one private session.
- [ ] **M01.06** — Open one customer account page and one staff dashboard, refresh, then sign out and back in. **Expected:** Each session shows the correct name and role and recovers after refresh.

**Result:** ______  **References / evidence:** ______  **Actual result / issue:** ______


### M02. Prepare products, files, amounts and a clean baseline

**Role:** Tester; administrator; inventory staff. **Covers:** SET-04 SET-05 SET-06 SET-07.

**Before starting:** Label all new fixtures MANUAL-QA-20261104 or your actual run date.

- [ ] **M02.01** — Prepare one non-prescription item, two variants of the same product, a prescription-only item, an out-of-stock item and a low-stock item. Record each exact SKU, strength, pack and price. **Expected:** You can tell the variants apart without relying on a shared product name.
- [ ] **M02.02** — Prepare stores S1 and S2 with variant A at 50 and 30 packs, plus a different stock balance for variant B. Record reserved and available quantities if shown. **Expected:** Every stock baseline identifies variant and store separately.
- [ ] **M02.03** — Ask the administrator for isolated KSh 1 payment fixtures and free QA pickup if you intend KSh 1 prompts. Record the displayed final total before each payment. **Expected:** Ordinary catalog and consultation fees remain separate; two units at KSh 1 each cost KSh 2 unless an authorized fixture produces a KSh 1 final total.
- [ ] **M02.04** — Prepare a valid and expired coupon, approved doctor/pediatrician with recorded fees, and approved lab facility/test/technician with recorded quote. **Expected:** Expected discounts, shipping, fees, commission and lab payment policy are written down.
- [ ] **M02.05** — Prepare the supplied synthetic prescription PDF, synthetic lab-result PDF, invalid text file, a valid JPG/PNG, a file over 5 MB, six small valid prescription files, and a chat file over 10 MB. **Expected:** Files contain synthetic information only and can exercise accepted and rejected uploads.
- [ ] **M02.06** — Prepare two child profiles with deliberately similar or identical names but different dates of birth/measurements. **Expected:** Identity mistakes can be detected by child ID and distinct measurements.
- [ ] **M02.07** — Check whether email is delivered to a real test mailbox or a local mail viewer; check the configured phone with its owner. **Expected:** You know where verification/reset/receipt messages should actually arrive.
- [ ] **M02.08** — Empty only your new test carts and record any existing pending payments separately. **Expected:** Old references and completed prescriptions are not accidentally reused as new test fixtures.

**Result:** ______  **References / evidence:** ______  **Actual result / issue:** ______


## 2. Public website and catalog


### M03. Visit public pages and navigation

**Role:** Visitor. **Covers:** CAT-02 CAT-06.

**Before starting:** Start signed out.

- [ ] **M03.01** — Open Home, Products, Categories, Brands, Offers, Conditions, Health services, Store locator, FAQs and Help from the visible menus. **Expected:** Each link opens the appropriate page; back navigation works.
- [ ] **M03.02** — Open About, Contact, Privacy, Terms, Cookies, Blog and Careers from the footer or menus. **Expected:** Content is readable and relevant; any offered form/action has a meaningful outcome. Record placeholders or dead links as failures.
- [ ] **M03.03** — Use search with an exact product name, a partial name, a misspelling and a name with no matches. **Expected:** Relevant results or a useful empty state appear; previous results do not masquerade as new results.
- [ ] **M03.04** — Combine and clear available category, brand, price and availability filters. Change sorting and pagination. **Expected:** Results, count and selected filters stay consistent; clearing filters restores the list.
- [ ] **M03.05** — Check offer start/end visibility using prepared fixtures with the administrator. **Expected:** Expired or future promotions do not appear active; published content changes reach the storefront after refresh.

**Result:** ______  **References / evidence:** ______  **Actual result / issue:** ______


### M04. Inspect exact variants, prices, stock and enriched content

**Role:** Customer A. **Covers:** CAT-02 CAT-03.

**Before starting:** Use a multi-variant product and one product from the recent enrichment report.

- [ ] **M04.01** — Open a product and read its brand, description, image, strength, pack size, price, prescription badge and availability. **Expected:** The displayed information describes the sellable item rather than a different strength or pack.
- [ ] **M04.02** — Select variant A, then variant B, and record the label, price, image and availability each time. **Expected:** Variant-specific information changes together; out-of-stock variants are not presented as immediately purchasable.
- [ ] **M04.03** — Add variant B to the cart and open the cart. **Expected:** The line contains variant B, its exact pack/strength, the selected quantity and the correct unit price.
- [ ] **M04.04** — Open an enriched item, such as Wisdom Travel Toothbrush Medium, and inspect its description/specifications/image on desktop and phone. **Expected:** Text is readable, the image shows that product, and a store logo or unrelated pack is not substituted.
- [ ] **M04.05** — Open an item still using a placeholder image. **Expected:** The placeholder is honestly identified and does not pretend to be an exact product photo.
- [ ] **M04.06** — Refresh the detail page and use back/forward navigation. **Expected:** The product remains accessible and selection/cart state does not silently change to another variant.

**Result:** ______  **References / evidence:** ______  **Actual result / issue:** ______


### M05. Wishlist and product reviews

**Role:** Customer A; Customer B. **Covers:** CAT-04 CAT-05.

**Before starting:** Use separate unrelated customer sessions.

- [ ] **M05.01** — Add a product to favourites, open /account/favourites, refresh and remove it. **Expected:** The saved entry appears once, persists and is removed when requested.
- [ ] **M05.02** — Add a favourite to the cart. **Expected:** Correct variant/selection rules apply; the cart does not receive an arbitrary strength.
- [ ] **M05.03** — Open Customer B favourites. **Expected:** Customer A favourites are absent.
- [ ] **M05.04** — Submit a valid test review where the interface allows it; reload the product. **Expected:** Rating/text appear according to the displayed review policy and remain attached to the correct product/variant.
- [ ] **M05.05** — Try an empty review, out-of-range rating if the control permits, and duplicate submission. **Expected:** Validation is useful and a double click does not create unintended duplicate reviews.
- [ ] **M05.06** — Try to edit/remove Customer A review as Customer B using available controls or a copied review link. **Expected:** Other users cannot change the review; record a missing review screen as a UI gap rather than assuming an API pass.

**Result:** ______  **References / evidence:** ______  **Actual result / issue:** ______


## 3. Accounts and sessions


### M06. Register and verify a new customer

**Role:** New Customer A. **Covers:** ACC-01 ACC-02.

**Before starting:** Use a new email address you can receive messages at; do not reuse completed QA accounts.

- [ ] **M06.01** — Open /register and submit an empty form. **Expected:** Required fields are identified next to the form without creating an account.
- [ ] **M06.02** — Enter invalid email, mismatched passwords and incomplete required details in separate attempts. **Expected:** Each error is explained; previously valid fields are retained where appropriate.
- [ ] **M06.03** — Enter valid synthetic details, review the displayed terms and submit once. **Expected:** Registration success and verification instructions appear; repeated clicking does not create duplicate accounts.
- [ ] **M06.04** — Before verification, try logging in. **Expected:** The configured verification restriction is enforced and guidance is clear.
- [ ] **M06.05** — Open the verification message in the configured mailbox and follow its link. **Expected:** The correct account is verified and can sign in.
- [ ] **M06.06** — Open the same verification link again; use an administrator-prepared expired link separately. **Expected:** Reused/expired links fail safely without changing another account.
- [ ] **M06.07** — Try registering the same email again and sign in with a wrong password once. **Expected:** Duplicate and invalid-login messages are useful and no private account details are exposed.

**Result:** ______  **References / evidence:** ______  **Actual result / issue:** ______


### M07. Edit profile, addresses and saved M-Pesa details

**Role:** Customer A; Customer B. **Covers:** ACC-03 ACC-04.

**Before starting:** Log in as Customer A.

- [ ] **M07.01** — Open /account/edit, change permitted profile fields, save, refresh and log out/in. **Expected:** Saved values persist and role/status cannot be promoted through profile controls.
- [ ] **M07.02** — Open /account/addresses, add two distinguishable synthetic addresses and make one default. **Expected:** Both appear with correct labels and the chosen default is clear.
- [ ] **M07.03** — Edit one address and reload; remove the other using the confirmation. **Expected:** Only the intended address changes or disappears.
- [ ] **M07.04** — Open /account/payment and add/edit/remove a permitted M-Pesa entry if that screen offers it. **Expected:** Phone validation and persistence work; non-card entries do not demand card expiry fields.
- [ ] **M07.05** — Try invalid phone/address values. **Expected:** Invalid data is rejected with an actionable message.
- [ ] **M07.06** — Open Customer B address and payment pages, then try Customer A copied record links. **Expected:** A details do not appear and cannot be changed by B.
- [ ] **M07.07** — Check available payment-entry methods. **Expected:** Card entry and cash-on-delivery are excluded by current product scope; report them if offered as usable new methods.

**Result:** ______  **References / evidence:** ______  **Actual result / issue:** ______


### M08. Password change, reset and logout

**Role:** Customer A. **Covers:** ACC-05 ACC-06 ACC-07.

**Before starting:** Use your own disposable test account; keep new passwords out of screenshots and reports.

- [ ] **M08.01** — Open account security/settings and attempt a change with the wrong current password. **Expected:** Change is denied and the existing password remains valid.
- [ ] **M08.02** — Change to a new password and sign out. Try the old password, then the new one. **Expected:** Old password fails and new password succeeds.
- [ ] **M08.03** — Open /auth/forgot-password, request a reset and inspect the configured mailbox. **Expected:** A reset message arrives or a recorded delivery problem is shown; the screen does not expose other users details.
- [ ] **M08.04** — Use the reset link, enter a new password and sign in. **Expected:** The new password works and the previous password fails.
- [ ] **M08.05** — Reuse the reset link and use an expired test link separately. **Expected:** Both are rejected safely.
- [ ] **M08.06** — Stay signed in long enough to exercise the configured session timeout/refresh, then revisit an account page. **Expected:** Session either renews normally or returns cleanly to sign-in; no infinite refresh loop.
- [ ] **M08.07** — Log out, press Back and refresh a private page. **Expected:** Private records cannot be loaded without authentication. Token revocation itself requires the technical evidence check in M56.

**Result:** ______  **References / evidence:** ______  **Actual result / issue:** ______


### M09. Role restrictions, suspension and account deactivation

**Role:** Customer A; Customer B; administrator. **Covers:** ACC-08 ACC-09 ACC-11.

**Before starting:** Use a dedicated disposable customer for deactivation.

- [ ] **M09.01** — As a customer, type /admin, /inventory, /doctor/dashboard, /pharmacist/dashboard, /lab/dashboard and /labtech/dashboard in the address bar. **Expected:** Staff records/actions are denied or redirected; customer role is unchanged.
- [ ] **M09.02** — Have the administrator suspend a disposable customer while it has an open session; refresh and attempt a protected action. **Expected:** Current status is enforced even with the old session.
- [ ] **M09.03** — Reactivate that customer and log in. **Expected:** Access resumes according to the restored status.
- [ ] **M09.04** — On a separate disposable account, open deletion/deactivation settings and first cancel the confirmation. **Expected:** Account stays active.
- [ ] **M09.05** — Repeat and confirm deactivation yourself, then try login and an old private bookmark. **Expected:** Access is removed; copy explains retained service records/soft deactivation rather than promising unsupported erasure.
- [ ] **M09.06** — Confirm Customer A and B remain unaffected. **Expected:** No unrelated profile, order or session is changed.

**Result:** ______  **References / evidence:** ______  **Actual result / issue:** ______


## 4. Shopping and checkout


### M10. Cart editing, persistence and guest merge

**Role:** Visitor; Customer A. **Covers:** ORD-01 ORD-02.

**Before starting:** Use ordinary and multi-variant test products.

- [ ] **M10.01** — As a visitor, add one item if guest carts are supported; sign in to an account that already has a different item. **Expected:** Both lines survive the supported merge without doubling quantities; if guest carts are not offered, record N/A with that reason.
- [ ] **M10.02** — Add two different variants of one product and another product. **Expected:** Separate variant lines appear with correct names, pack/strength and unit prices.
- [ ] **M10.03** — Increase/decrease quantity using the visible controls. **Expected:** Line totals and cart subtotal update consistently; zero/negative/overstock quantities cannot be accepted silently.
- [ ] **M10.04** — Refresh and reopen the cart after leaving the page. **Expected:** Intended contents and quantities persist for that customer.
- [ ] **M10.05** — Remove one line, then clear the cart using its confirmation. **Expected:** Only intended lines are removed and the empty state offers a useful next step.
- [ ] **M10.06** — Open Customer B cart. **Expected:** It is independent from A cart.

**Result:** ______  **References / evidence:** ______  **Actual result / issue:** ______


### M11. Coupons, shipping, totals and address consent

**Role:** Customer A. **Covers:** ORD-03 ORD-04.

**Before starting:** Write expected prices and shipping quotes before checkout.

- [ ] **M11.01** — Add known quantities and calculate subtotal yourself: sum of unit price × quantity. **Expected:** Cart subtotal equals your calculation.
- [ ] **M11.02** — Apply a valid coupon, remove it, try an expired coupon and a minimum-spend-ineligible coupon. **Expected:** Discount applies only when eligible, removal restores totals, errors explain rejection.
- [ ] **M11.03** — If another promotion is active, compare the result with the configured stacking rule. **Expected:** No unexplained double discount; record the rule used.
- [ ] **M11.04** — Open /checkout and choose an existing address, then enter a different unsaved address with Save address unchecked. **Expected:** Checkout uses the chosen details and does not silently save the new address.
- [ ] **M11.05** — Choose Save address explicitly and test again on a fresh draft. **Expected:** Address is saved only with consent and is available after refresh.
- [ ] **M11.06** — Select Doorstep delivery, record the quote, then select Store pickup and record that quote. **Expected:** Total equals subtotal minus allowed discount plus the selected service fee.
- [ ] **M11.07** — Reopen the same saved draft or refresh checkout. **Expected:** Selected shipping service, address, quantity and final total match the saved draft; a default fee does not replace a saved QA pickup quote.
- [ ] **M11.08** — Leave required county/area/address/phone fields empty or invalid, then correct them. **Expected:** Continue is blocked with useful validation until required details are valid.

**Result:** ______  **References / evidence:** ______  **Actual result / issue:** ______


### M12. Successful M-Pesa STK checkout

**Role:** Customer A. **Covers:** ORD-05.

**Before starting:** Use one new unpaid draft and an explicitly authorized payment amount/phone.

- [ ] **M12.01** — Write order reference, exact item/variant, final total, shipping quote and phone suffix before initiating. **Expected:** This is the amount and order you intend to pay; KSh 1 testing requires an actual KSh 1 displayed final total.
- [ ] **M12.02** — Click the STK initiation button once and watch the status. **Expected:** Request moves to a clear waiting state; acceptance alone is not displayed as paid.
- [ ] **M12.03** — Approve the prompt yourself on the authorized phone. Never enter the PIN into the website. **Expected:** Provider outcome/receipt is available independently on the phone where supported.
- [ ] **M12.04** — Wait for website confirmation, or use the visible Check status action after its cooldown. **Expected:** Provider-confirmed status appears; a timeout or acknowledgement is not treated as success.
- [ ] **M12.05** — Record the genuine receipt and final amount. **Expected:** Website payment record, phone/provider receipt and order total match.
- [ ] **M12.06** — Use the final order/checkout button once after confirmation. **Expected:** One completed checkout appears; unpaid finalization was not allowed.
- [ ] **M12.07** — Open /account/orders, select that reference and refresh. **Expected:** Correct items, amounts, payment status and customer confirmation/receipt persist.
- [ ] **M12.08** — Ask inventory staff to record exact variant/store balances before and after the finalization stage. **Expected:** Stock changes once at the configured stage; other variants/stores are unchanged.
- [ ] **M12.09** — Check the configured receipt email and in-app notification separately. **Expected:** Record actual external delivery, inbox delivery and backend-accepted status separately; do not infer mailbox delivery.

**Result:** ______  **References / evidence:** ______  **Actual result / issue:** ______


### M13. Failed prompt, cancellation, retry and duplicate protection

**Role:** Customer A; administrator. **Covers:** ORD-09 ORD-10.

**Before starting:** Use a separate new draft; decline one prompt intentionally.

- [ ] **M13.01** — Initiate one prompt and decline it, or allow its documented timeout. **Expected:** Status eventually reports failure/cancellation with a useful explanation; order is not fulfillable as paid.
- [ ] **M13.02** — Without a successful payment, try the final checkout button and refresh the draft. **Expected:** Completion remains blocked and unpaid stock has not been committed.
- [ ] **M13.03** — If no prompt arrives but the request is still processing, record it and check status after cooldown. **Expected:** No automatic overlapping prompts or invented success; escalate an unresolved request before resending.
- [ ] **M13.04** — After a terminal failure or the supported local-cancellation flow, initiate a fresh retry for the same draft and approve it. **Expected:** The application safely reuses the intended order; the new successful payment is distinguishable from the failed attempt.
- [ ] **M13.05** — After confirmed success, refresh, use Back/Forward and reopen the confirmation URL. On the test site, rapidly double-click a visible finalization control once if it remains enabled. **Expected:** One order/payment application and one stock deduction; the button should prevent or safely handle repeat submission.
- [ ] **M13.06** — Ask admin to inspect payment history and stock movement for the same reference. **Expected:** One successful attempt, failed/cancelled history retained and no duplicate receipt/stock allocation.
- [ ] **M13.07** — If you used Cancel Payment, check the phone/provider separately. **Expected:** A local cancellation is not misrepresented as cancellation or refund of money already processed by the provider.

**Result:** ______  **References / evidence:** ______  **Actual result / issue:** ______


### M14. Paybill matching and excluded payment methods

**Role:** Customer A; administrator. **Covers:** ORD-06 ORD-07 ORD-08.

**Before starting:** Current Paybill provider confirmation remains an unresolved integration; run only in the approved sandbox.

- [ ] **M14.01** — Select Paybill if available and record displayed Paybill number, account reference and amount. **Expected:** All fields belong to this draft; do not reuse historic example references.
- [ ] **M14.02** — With the authorized sandbox provider, submit the exact amount/reference and retain the independent receipt. **Expected:** Website becomes paid only after a verified matching provider confirmation.
- [ ] **M14.03** — Refresh and finalize only after confirmation. **Expected:** Correct order is paid once and correct stock is committed once.
- [ ] **M14.04** — Have the integration tester submit wrong-amount and unmatched-reference sandbox cases. **Expected:** Neither falsely pays this order; the user sees a pending/rejected result rather than false success.
- [ ] **M14.05** — If registration/provider callbacks fail or never arrive, stop and mark this case Blocked with the provider message. **Expected:** No administrator status edit or simulated callback is counted as genuine payment proof.
- [ ] **M14.06** — Check checkout for card and cash-on-delivery. **Expected:** These methods are unavailable under current scope; record their exclusions as N/A, not as untested enabled features.

**Result:** ______  **References / evidence:** ______  **Actual result / issue:** ______


### M15. Price changes, unavailable stock and stale carts

**Role:** Customer A; administrator; inventory staff. **Covers:** ORD-12 INV-05.

**Before starting:** Use a fresh draft and a staff-controlled synthetic item.

- [ ] **M15.01** — Add an item to cart, then ask staff to change its test price before checkout. **Expected:** Checkout revalidates and shows the current price or asks you to review the change.
- [ ] **M15.02** — Repeat with an item that staff deactivates or reduces below the requested quantity. **Expected:** Checkout blocks or applies the explicitly configured backorder policy; no negative stock.
- [ ] **M15.03** — Try the out-of-stock item and a quantity above available stock. **Expected:** The message and purchasability reflect the exact selected variant.
- [ ] **M15.04** — If backorders are enabled, test the configured maximum and a quantity above it. **Expected:** Limits and expected availability are clear. If disabled, record backorder-only steps N/A.
- [ ] **M15.05** — Ask staff to restore the original test price/status and reopen a clean cart. **Expected:** Ordinary catalog values are restored and no unintended order was paid.

**Result:** ______  **References / evidence:** ______  **Actual result / issue:** ______


## 5. Fulfillment, cancellations and returns


### M16. Order processing, delivery, receipt and reporting

**Role:** Customer A; administrator/pharmacist; inventory staff. **Covers:** ORD-13 ORD-17.

**Before starting:** Continue the same genuinely paid order from M12.

- [ ] **M16.01** — As staff, find the exact paid order reference and compare customer, items, address, delivery method and total. **Expected:** All match the customer order; do not process an order found only by a similar name.
- [ ] **M16.02** — Move it through the allowed Processing → Shipped/On the way → Delivered stages using synthetic fulfillment. **Expected:** Each transition has a timestamp/actor/history entry; terminal status is not silently reopened.
- [ ] **M16.03** — After each stage, refresh the customer order and open /track-order using the intended reference/details. **Expected:** Tracking, timestamps, notes and notifications agree with staff status and disclose only intended public information.
- [ ] **M16.04** — Open the customer receipt/confirmation and print/download if offered. **Expected:** Reference, paid amount, exact items and shipping match; no other customer data is included.
- [ ] **M16.05** — As finance/admin, find the order in invoices, reconciliation and orders/revenue reports where offered. **Expected:** Amount and payment status agree with the customer record.
- [ ] **M16.06** — Download a report with a date range including the original order creation date. **Expected:** The order appears once; a short range excluding that date is not mistaken for a missing-record bug.
- [ ] **M16.07** — Refresh both role views after completion. **Expected:** Status and stock stay stable. No real medicine shipment is made for a synthetic QA record.

**Result:** ______  **References / evidence:** ______  **Actual result / issue:** ______


### M17. Eligible cancellation and stock release

**Role:** Customer A; administrator; inventory staff. **Covers:** ORD-15 INV-04.

**Before starting:** Use one unpaid order and a separate eligible paid-but-unshipped synthetic order.

- [ ] **M17.01** — On the unpaid order, choose Cancel and first dismiss the confirmation. **Expected:** Order stays unchanged.
- [ ] **M17.02** — Choose Cancel again and confirm; refresh order/cart. **Expected:** Order is cancelled, no unpaid stock is deducted and further checkout finalization is blocked.
- [ ] **M17.03** — For a paid eligible order, record stock and payment status before cancelling with the authorized staff/customer flow. **Expected:** The configured cancellation policy is explained and payment/refund handling is visible.
- [ ] **M17.04** — If committed stock is released, ask inventory staff to verify exact variant/store balances. Repeat the cancellation action if it is still offered. **Expected:** Stock is released only once; no payment is falsely described as refunded.
- [ ] **M17.05** — Try customer cancellation after dispatch/delivery or outside the permitted policy. **Expected:** It is rejected with guidance to the return/support process.
- [ ] **M17.06** — If cancellation creates a refund obligation, record it as pending until external refund proof exists. **Expected:** Cancellation alone is not a receipt for money returned.

**Result:** ______  **References / evidence:** ______  **Actual result / issue:** ______


### M18. Return request, quarantine, refund and support closure

**Role:** Customer A; administrator; inventory staff. **Covers:** ORD-16 E2E-06.

**Before starting:** Use a delivered synthetic order with a genuine test payment. Current external refund execution is not implemented by the refund-record endpoint.

- [ ] **M18.01** — Open /returns and submit the visible form with your delivered order reference and a clear synthetic reason. **Expected:** A saved return reference should appear and persist after refresh. Current source has no submission handler: if it merely refreshes/no record appears, mark Failed/UI gap; do not mark return creation passed.
- [ ] **M18.02** — If the UI is unavailable, create an order-linked support ticket at /account/support and request staff assistance. **Expected:** Support reference and the missing return-screen behavior are recorded; a staff/API workaround does not convert the website step into a pass.
- [ ] **M18.03** — As staff, locate the saved return in the returns/finance workspace if offered; verify owner, order, item, reason and requested amount. **Expected:** The return is associated with the correct paid order. If no UI exists, mark that step Blocked and request a technical handoff.
- [ ] **M18.04** — Approve then receive the synthetic return with quarantine and non-resale acknowledgement plus a disposition note. **Expected:** It cannot be closed as received/refunded without required quarantine safeguards.
- [ ] **M18.05** — Ask inventory staff to compare saleable stock before and after receipt. **Expected:** Dispatched returned medicine is not put back into saleable stock; repeating receipt does not increase stock.
- [ ] **M18.06** — Attempt to close as refunded before external refund evidence exists. **Expected:** It is rejected; customer cannot perform staff refund actions.
- [ ] **M18.07** — Only after an authorized external refund actually completes, retain its independent reference/amount and have staff record it. **Expected:** Administrative recording is labelled accurately and is backed by a real refund, not an invented reference.
- [ ] **M18.08** — Have staff retry the recording/check the same operation after refresh, then close the return as refunded. **Expected:** One refund event/record and no duplicate restock; payment and finance reporting reflect the actual disposition.
- [ ] **M18.09** — Compare customer order/return history, original successful payment, refund evidence and report. **Expected:** Original charge remains traceable; recorded refund is not mistaken for a second charge.
- [ ] **M18.10** — Add a public support explanation and resolve only once the actual financial issue is settled; customer refreshes the ticket. **Expected:** Correct visible reply/status persists and internal notes remain private.
- [ ] **M18.11** — If an actual provider refund cannot be executed/confirmed, leave the live inquiry open and mark the full journey Blocked/Partial. **Expected:** Application-only simulated refund tests are recorded separately.

**Result:** ______  **References / evidence:** ______  **Actual result / issue:** ______


### M19. Order, payment and return ownership

**Role:** Customer A; unrelated Customer B; visitor. **Covers:** ORD-11 ORD-18.

**Before starting:** Copy A order detail/tracking/receipt/return URLs without putting secrets in your report.

- [ ] **M19.01** — Open A private order URL as B, then as a signed-out visitor. **Expected:** Private items/address/payment details cannot be read or changed.
- [ ] **M19.02** — Try A cancellation/return controls from B session if any record is exposed. **Expected:** No action succeeds; A order stays unchanged.
- [ ] **M19.03** — Enter A reference with incorrect verification details in public tracking. **Expected:** Tracking reveals only its intended limited information and does not expose full account or payment data.
- [ ] **M19.04** — Attempt to use a payment reference from a different order only through controls offered in the sandbox. **Expected:** It cannot satisfy this order payment. If no UI permits it, request the technical security check rather than inventing a browser pass.
- [ ] **M19.05** — Ask admin to check both original records after the attempts. **Expected:** No payment reassignment, stock movement or ownership change occurred.

**Result:** ______  **References / evidence:** ______  **Actual result / issue:** ______


## 6. Prescription upload and dispensing


### M20. Upload valid files and reject invalid files

**Role:** Customer A. **Covers:** RX-01 RX-02.

**Before starting:** Use fresh synthetic prescription files, not a real prescription or a previously dispensed fixture.

- [ ] **M20.01** — Open /prescriptions or Account → Prescriptions and choose the upload action. **Expected:** Form identifies the signed-in patient and offers supported upload types.
- [ ] **M20.02** — Submit without required details/files, then select the invalid text file. **Expected:** Clear validation; no incomplete prescription is created.
- [ ] **M20.03** — Try a file larger than 5 MB and then six small valid files. **Expected:** Current limits are enforced: PDF/JPG/PNG, up to 5 files, each at most 5 MB.
- [ ] **M20.04** — Upload the valid PDF with synthetic prescriber name and notes, then submit once. **Expected:** A new prescription reference appears with pending review status.
- [ ] **M20.05** — Refresh history and reopen its files. **Expected:** Correct patient, file names, notes and status persist; authenticated downloads display the original intended file.
- [ ] **M20.06** — Add the same file twice before submission. **Expected:** Duplicate selection is handled clearly and does not multiply attachments unexpectedly.

**Result:** ______  **References / evidence:** ______  **Actual result / issue:** ______


### M21. Pharmacist assignment, clarification and customer reply

**Role:** Pharmacist; administrator; Customer A. **Covers:** RX-03 RX-04.

**Before starting:** Continue M20 using the recorded prescription reference.

- [ ] **M21.01** — As authorized pharmacist/admin, open /pharmacist/dashboard or the prescription workspace and find that reference. **Expected:** Correct patient and files appear; review permission is required.
- [ ] **M21.02** — Assign the pharmacist if assignment is offered/required. Open the file and review the synthetic details. **Expected:** Assignment and actor are saved; no unrelated prescription is substituted.
- [ ] **M21.03** — Request clarification with a specific question. **Expected:** Customer status changes to clarification and receives the intended in-app notice.
- [ ] **M21.04** — As customer, open the notification and the prescription; reply to the question and resubmit/upload a replacement only if requested. **Expected:** Full exchange persists and returns to the configured review state.
- [ ] **M21.05** — As pharmacist, refresh and read the reply. **Expected:** Both messages, dates and authors appear; the panel does not repeatedly reopen after you close it.
- [ ] **M21.06** — Use Back/navigation after opening from a notification. **Expected:** You can close the detail panel and navigate normally.

**Result:** ______  **References / evidence:** ______  **Actual result / issue:** ______


### M22. Reject a prescription and block checkout

**Role:** Pharmacist; Customer A. **Covers:** RX-05.

**Before starting:** Create a separate synthetic prescription so the approval journey remains available.

- [ ] **M22.01** — Reject that prescription with a clear synthetic reason. **Expected:** Reason is mandatory/useful and saved with the review actor.
- [ ] **M22.02** — As customer, refresh history and open its notification/detail. **Expected:** Rejected status and the same reason are visible.
- [ ] **M22.03** — Try to add medicine from the rejected prescription or proceed from a previously open approval/cart link. **Expected:** Rejected authorization cannot purchase medicine.
- [ ] **M22.04** — Repeat the checkout attempt while another fresh prescription is still pending. **Expected:** Pending authorization is also blocked; no paid order or stock movement occurs.

**Result:** ______  **References / evidence:** ______  **Actual result / issue:** ______


### M23. Approve exact items, purchase and prevent unauthorized reuse

**Role:** Pharmacist; Customer A; inventory staff. **Covers:** RX-03 RX-06 RX-07 RX-08 E2E-02.

**Before starting:** Continue the clarified prescription; keep unrelated cart lines distinguishable.

- [ ] **M23.01** — As pharmacist, map each approved line to an active exact catalog variant; record medicine name, strength, pack, quantity and synthetic instructions. **Expected:** Approval cannot silently use the parent product or another strength.
- [ ] **M23.02** — Approve and refresh the prescription. **Expected:** Customer sees approved status, allowed quantities and the same clinical details.
- [ ] **M23.03** — As customer, add an approved item to cart. Try increasing beyond its allowance or substituting a different variant. **Expected:** Authorized quantity/variant rules hold and invalid additions are explained.
- [ ] **M23.04** — Create a prescription-scoped checkout with another unrelated line still in the cart. **Expected:** Only intended approved items are in this draft; unrelated lines are not unexpectedly removed.
- [ ] **M23.05** — Follow M11–M12 to confirm the displayed amount, pay once, record receipt and finalize once. **Expected:** Paid order links to this prescription and exact variants; stock changes once.
- [ ] **M23.06** — As staff, move the linked dispensing/order through the supported queued/packed/dispatched/delivered flow. **Expected:** Prescription dispatch, order tracking and notifications agree; use the controls actually available, not invented intermediate statuses.
- [ ] **M23.07** — Try adding/reusing the already fulfilled prescription beyond the remaining authorized amount. **Expected:** Reuse is denied according to dispensing limits.
- [ ] **M23.08** — Compare prescription reference, order reference, variants/quantities, receipt and stock after refresh. **Expected:** One traceable chain persists across customer and pharmacist views.

**Result:** ______  **References / evidence:** ______  **Actual result / issue:** ______


### M24. Prescription privacy and download access

**Role:** Customer A; Customer B; pharmacist without review permission. **Covers:** RX-09.

**Before starting:** Copy the test prescription detail and authenticated file links.

- [ ] **M24.01** — As B, open A prescription history/detail/file links. **Expected:** Record and file are denied or absent.
- [ ] **M24.02** — As a pharmacist without review permission, try the same review/detail actions. **Expected:** No review or private download succeeds.
- [ ] **M24.03** — As A, open the authorized file; sign out and try the same link again. **Expected:** Authorized access works and signed-out access fails; expired links should require fresh authorized access.
- [ ] **M24.04** — Ask technical tester to verify raw media URLs and hosted web-server configuration if this is a release test. **Expected:** A working authorized download alone is not counted as proof that raw media is protected.
- [ ] **M24.05** — As authorized reviewer, inspect the audit/history screen if offered. **Expected:** Upload, assignment, clarification, reply and decision have identifiable actors and timestamps; missing audit UI is recorded.

**Result:** ______  **References / evidence:** ______  **Actual result / issue:** ______


## 7. Professional applications


### M25. Apply, approve and activate professional accounts

**Role:** New professional; two administrators. **Covers:** ACC-10 CON-01 LAB-01.

**Before starting:** Use separate synthetic doctor, pediatrician and lab-partner applications; prepare required test documents.

- [ ] **M25.01** — Open /professional/register and select the intended professional type. **Expected:** Correct identity, role, facility/practice, documents and payout/availability fields are shown where applicable.
- [ ] **M25.02** — Attempt an incomplete submission and invalid file uploads. **Expected:** Missing fields and file errors are explicit; no incomplete approval is silently granted.
- [ ] **M25.03** — Fill the required steps, upload synthetic credentials and review the final summary. Accept terms yourself only when appropriate, then submit once. **Expected:** Application reference and pending status appear.
- [ ] **M25.04** — As admin, locate the exact application, inspect protected documents and request correction if supported. **Expected:** Application/document association and review history persist.
- [ ] **M25.05** — As applicant, follow the correction/resubmission process, then ask admin to approve and provision. **Expected:** Correct linked role account is created; repeated approval does not create duplicates.
- [ ] **M25.06** — Open the activation email and set the new password yourself. Sign in and verify the appropriate dashboard. **Expected:** Activated doctor, pediatrician or lab partner reaches only the permitted workspace.
- [ ] **M25.07** — Reuse the activation link, and use a prepared expired link separately. **Expected:** Both fail safely; resend delivers a fresh link if supported.
- [ ] **M25.08** — Repeat the application/approval/activation journey for the other two professional types. **Expected:** Each gets the correct role, scope and dashboard; record results separately.

**Result:** ______  **References / evidence:** ______  **Actual result / issue:** ______


### M26. Pending/suspended professionals and document privacy

**Role:** Pending/suspended professional; administrator; customer. **Covers:** CON-02.

**Before starting:** Use dedicated test professionals; retain a separate active professional for later bookings.

- [ ] **M26.01** — Try login/dashboard access with pending or suspended accounts. **Expected:** Access follows current eligibility and clear guidance is given.
- [ ] **M26.02** — As customer, browse doctor/pediatrician/lab selections. **Expected:** Ineligible providers/facilities are not offered for new service.
- [ ] **M26.03** — As admin, suspend an eligible test professional with an existing open session; have them refresh/attempt a protected action. **Expected:** Existing tokens/sessions do not retain revoked permissions.
- [ ] **M26.04** — Inspect a public clinician page. **Expected:** Only intended booking/profile details appear; private credentials, identity documents and payout details are absent.
- [ ] **M26.05** — Reactivate the disposable test professional through the permitted flow and recheck booking eligibility. **Expected:** Status changes restore only intended access and keep historical records.

**Result:** ______  **References / evidence:** ______  **Actual result / issue:** ______


## 8. Doctor consultation


### M27. Choose a doctor, pay and finalize exactly one booking

**Role:** Customer A; doctor. **Covers:** CON-03 CON-04 CON-05.

**Before starting:** Use an approved synthetic doctor and record the current fee.

- [ ] **M27.01** — Open /doctor-consultation, choose the doctor or supported routing option, and read the displayed specialty and fee. **Expected:** Selected clinician/routing and fee are clear; any schedule choice matches the form.
- [ ] **M27.02** — Enter synthetic complaint, required patient details and the authorized phone. Leave required fields empty once first. **Expected:** Validation is useful and no booking is created prematurely.
- [ ] **M27.03** — Initiate payment once, decline the first attempt on a separate test case, then approve a valid retry after failure. **Expected:** Waiting/failure/success are distinct; an unpaid booking cannot be finalized.
- [ ] **M27.04** — Approve the successful prompt yourself and retain the provider receipt. **Expected:** Consultation payment amount equals displayed fee; receipt is genuine.
- [ ] **M27.05** — Finalize, refresh and reopen the waiting/account page. **Expected:** One consultation reference appears in customer history and assigned clinician queue.
- [ ] **M27.06** — Reopen the payment return/finalize page and retry a visible finalization action if offered. **Expected:** No duplicate consultation or reused payment for a second booking.
- [ ] **M27.07** — As doctor, locate the same reference and compare patient, issue, payment eligibility and schedule. **Expected:** Correct patient and booking appear once; fee changes after payment do not rewrite the paid amount.

**Result:** ______  **References / evidence:** ______  **Actual result / issue:** ______


### M28. Open queue specialty routing and competing claims

**Role:** Customer A; two eligible doctors. **Covers:** CON-06.

**Before starting:** Run only if booking without a named doctor/open queue is offered.

- [ ] **M28.01** — Create a paid synthetic booking through the open queue and record requested specialty/routing. **Expected:** Queue description matches the selected mode; do not expect an already named doctor booking to be unassigned.
- [ ] **M28.02** — As eligible doctor 1 and doctor 2, open the same unclaimed consultation in separate sessions. **Expected:** Only permitted doctors can see/claim the case.
- [ ] **M28.03** — Coordinate a near-simultaneous Claim click in both sessions. **Expected:** Exactly one clinician is assigned; the other gets a useful denial/update.
- [ ] **M28.04** — Refresh both doctors and the patient view. **Expected:** One stable assignment is shown everywhere; an ineligible/suspended doctor cannot take over.
- [ ] **M28.05** — If open queue is unavailable, record N/A with the offered booking mode and request technical concurrency evidence separately. **Expected:** An unavailable website path is not falsely marked tested.

**Result:** ______  **References / evidence:** ______  **Actual result / issue:** ______


### M29. Chat, live updates and protected attachments

**Role:** Customer A; assigned doctor; unrelated clinician. **Covers:** CON-07 CON-11.

**Before starting:** Use the same paid consultation and two simultaneous role sessions.

- [ ] **M29.01** — Open the conversation as patient and clinician and exchange distinguishable synthetic messages. **Expected:** Messages appear on both sides with correct author and time.
- [ ] **M29.02** — Refresh both sides, leave the page, then return. **Expected:** Full history persists under the same consultation.
- [ ] **M29.03** — Upload a small permitted synthetic attachment from each side and download it from the other role. **Expected:** Correct file opens; no public raw file URL is required.
- [ ] **M29.04** — Try an unsupported file and a file larger than 10 MB. **Expected:** Both are rejected clearly without losing existing conversation history.
- [ ] **M29.05** — Disconnect one browser network briefly, reconnect, then send one test message. **Expected:** Connection state is understandable and history recovers without unintended duplicates.
- [ ] **M29.06** — As Customer B or an unrelated doctor, open the consultation/attachment URL. **Expected:** Message history and files are denied; revoked account access is also denied after refresh.

**Result:** ______  **References / evidence:** ______  **Actual result / issue:** ______


### M30. E-prescription, pharmacist handoff and medicine order

**Role:** Doctor; pharmacist; Customer A. **Covers:** CON-08 CON-09 E2E-03.

**Before starting:** Continue the same consultation; synthetic instructions only.

- [ ] **M30.01** — As doctor, draft a prescription selecting exact catalog variants and quantities with required instructions. Save, reopen and edit before sending. **Expected:** Draft details persist and remain linked to this consultation.
- [ ] **M30.02** — Send it and download the prescription PDF. **Expected:** Patient, clinician, consultation reference, exact items, quantities, full instructions and signature information are readable; long lines are not clipped.
- [ ] **M30.03** — As patient and pharmacist, follow the received notification. **Expected:** Both reach the correct new prescription rather than a similarly named record.
- [ ] **M30.04** — As pharmacist, review and approve exact mapped variants. As patient, add allowed items and create a separate medicine checkout. **Expected:** Consultation payment is not mistakenly reused to pay for medicine.
- [ ] **M30.05** — Pay the displayed medicine total through M12 and retain the second receipt. **Expected:** Medicine order, dispensing prescription and original clinician prescription link back to the same consultation.
- [ ] **M30.06** — Progress synthetic delivery and compare both role histories and stock. **Expected:** Paid/delivered/dispensing status matches, with one stock deduction and no unauthorized prescription reuse.

**Result:** ______  **References / evidence:** ______  **Actual result / issue:** ______


### M31. Complete consultation and verify one earning

**Role:** Doctor; Customer A; finance/admin. **Covers:** CON-10.

**Before starting:** Complete chat and prescription checks before ending the session.

- [ ] **M31.01** — As doctor, end/complete the consultation through its normal control. **Expected:** Completed status and end timestamp appear; patient history agrees after refresh.
- [ ] **M31.02** — Refresh and repeat an offered completion action or reopen a stale completed tab. **Expected:** No duplicate completion earning or duplicate financial notice.
- [ ] **M31.03** — Open doctor earnings and find the consultation reference. **Expected:** One earning is calculated from the fee actually paid and recorded commission, with stated rounding.
- [ ] **M31.04** — Ask admin to compare paid fee, commission and net. Example: KSh 1 less 10% commission gives KSh 0.90. **Expected:** Current profile fee changes do not change the historical paid-fee calculation.
- [ ] **M31.05** — Try another unrelated clinician view. **Expected:** This consultation/earning is not attributed to someone else.

**Result:** ______  **References / evidence:** ______  **Actual result / issue:** ______


## 9. Pediatric journey


### M32. Create two children and keep identity separate

**Role:** Guardian; second unrelated guardian. **Covers:** PED-01 PED-06 PED-07.

**Before starting:** Prepare similar or identical child names and distinct dates of birth/measurements.

- [ ] **M32.01** — Open /pediatric-consultation and the supported child-profile controls. Add child A with synthetic details, then child B with deliberately similar/same name. **Expected:** Two separate child records exist with distinct IDs or unambiguous profile details.
- [ ] **M32.02** — Edit A measurements/profile only, save and refresh. **Expected:** A changes persist while B stays unchanged.
- [ ] **M32.03** — Select A and inspect history, then select B. **Expected:** Records are grouped by child identity rather than name alone.
- [ ] **M32.04** — As an unrelated guardian, try a copied child/profile/history link. **Expected:** Neither child can be read, selected or edited.
- [ ] **M32.05** — If a repeated consultation is needed later, keep A and B IDs on your run sheet. **Expected:** Matching names cannot hide a wrong-patient booking.

**Result:** ______  **References / evidence:** ______  **Actual result / issue:** ______


### M33. Consent, measurements, fee and paid booking

**Role:** Guardian; pediatrician. **Covers:** PED-02 PED-03 PED-04.

**Before starting:** Use an approved pediatrician and select child A explicitly.

- [ ] **M33.01** — Select child A, selected pediatrician and required complaint/patient details. Compare the displayed fee with that clinician. **Expected:** Correct child and clinician fee are clear before payment.
- [ ] **M33.02** — Try proceeding without affirmative guardian consent. **Expected:** Required consent restriction/message appears; any permitted pending-consent state cannot issue a pediatric prescription.
- [ ] **M33.03** — Try a future birth date, negative or zero supplied measurements, and an out-of-range child age where editable. **Expected:** Invalid data is rejected; optional measurements are not invented when absent.
- [ ] **M33.04** — Enter distinct valid synthetic measurements, explicitly grant consent and review the summary. **Expected:** Child A, guardian, clinician, measurements and consent all match.
- [ ] **M33.05** — Approve the authorized payment prompt and finalize once using M27 payment checks. **Expected:** One paid pediatric consultation is linked to child A with consent retained through payment.
- [ ] **M33.06** — As pediatrician, open that consultation and compare guardian, child ID/name, age/date of birth, measurements and consent. **Expected:** Child B data is never substituted, and absent data is shown as not recorded.
- [ ] **M33.07** — Refresh both views. **Expected:** Consent and child identity persist, not only the client-side checkbox state.

**Result:** ______  **References / evidence:** ______  **Actual result / issue:** ______


### M34. Pediatric chat, prescription, delivery, completion and history

**Role:** Guardian; pediatrician; pharmacist; finance. **Covers:** PED-05 PED-06 E2E-04.

**Before starting:** Continue child A paid consultation; use the same references throughout.

- [ ] **M34.01** — Repeat the patient/clinician chat and attachment checks in M29. **Expected:** Authorized guardian/pediatrician see the correct child conversation and protected files.
- [ ] **M34.02** — Issue an exact-variant synthetic prescription and inspect its PDF. **Expected:** Child, guardian and consultation references are correct; no sibling substitution or unsupported measurement/clinical placeholders.
- [ ] **M34.03** — Complete pharmacist review, separate medicine checkout/payment and synthetic delivery using M23/M30. **Expected:** Paid medicine and dispensing remain linked to the same child A consultation.
- [ ] **M34.04** — Complete the pediatric consultation twice if the UI permits retry and inspect earnings. **Expected:** One correct earning; no duplicate completion or stock deduction.
- [ ] **M34.05** — Book a second authorized consultation for child A, then view A history and B history. **Expected:** Both A consultations group under A and never under B.
- [ ] **M34.06** — As unrelated guardian/pediatrician, try copied consultation, child-history and prescription/file links. **Expected:** Private records are denied; record provider payments and medicine payments separately.

**Result:** ______  **References / evidence:** ______  **Actual result / issue:** ______


## 10. Lab services


### M35. Partner approval, facility offerings and staff assignment

**Role:** Lab partner; administrator. **Covers:** LAB-01 LAB-02.

**Before starting:** Use an approved/provisioned partner from M25 and a synthetic facility.

- [ ] **M35.01** — As partner, open /lab/dashboard, add required facility details and synthetic supporting documents. **Expected:** Facility is associated with this partner and enters its approval workflow.
- [ ] **M35.02** — As admin, inspect facility and protected documents, then approve through /admin/lab-partners or the applicable workspace. **Expected:** Correct facility/partner becomes eligible, with review history.
- [ ] **M35.03** — As partner, add offered tests, prices, sample types/turnaround and assigned technicians. **Expected:** Only permitted active tests/staff can be assigned.
- [ ] **M35.04** — As customer, browse /lab-tests. **Expected:** Approved offered tests/facilities and correct price/availability are shown.
- [ ] **M35.05** — Try a technician from an unrelated partner/facility, and view pending/suspended facility offerings. **Expected:** Assignment is denied and ineligible services are not bookable.
- [ ] **M35.06** — Record facility, test, technician and quoted price in the run sheet. **Expected:** Later results can be matched to one request.

**Result:** ______  **References / evidence:** ______  **Actual result / issue:** ______


### M36. Walk-in booking and cancellation

**Role:** Customer A; lab technician/partner. **Covers:** LAB-03 LAB-08.

**Before starting:** Current lab flow is pay-later; no online lab payment is offered.

- [ ] **M36.01** — Open /lab-tests, choose Walk-in, facility and test. Enter required synthetic patient details. **Expected:** Selected test, facility and quote are shown before confirmation.
- [ ] **M36.02** — Submit once, open /account/lab-tests and refresh. **Expected:** One request reference appears with correct test/facility/quote and the stated payment arrangement.
- [ ] **M36.03** — Change the catalog test price with staff on a separate prepared test, then reopen this booking. **Expected:** Saved booking quote does not silently change with later catalog price.
- [ ] **M36.04** — Create a separate eligible uncollected request and choose Cancel; first keep it, then confirm cancellation. **Expected:** Keeping makes no change; confirming cancels the intended request with history.
- [ ] **M36.05** — Try cancellation after collection/processing where policy disallows it. **Expected:** Clear denial and support guidance; cancellation does not imply a provider refund.
- [ ] **M36.06** — Check customer and staff payment copy. **Expected:** Pay-later/pending status is honest; no fake online charge or automatic refund claim.

**Result:** ______  **References / evidence:** ______  **Actual result / issue:** ______


### M37. Home collection, code verification and processing

**Role:** Customer A; assigned lab technician. **Covers:** LAB-04 LAB-05 LAB-06.

**Before starting:** Use a new home-collection request and a small set of agreed invalid-code tests.

- [ ] **M37.01** — Book home collection with facility/test, synthetic address and permitted date/time/contact details. **Expected:** Request shows correct home details, saved quote and assignment.
- [ ] **M37.02** — As assigned technician, open /labtech/dashboard and locate the reference. **Expected:** Correct patient/test/address appears; unrelated requests are absent.
- [ ] **M37.03** — Customer retrieves the collection code and gives it to the assigned test technician through the intended handoff. **Expected:** Code belongs to this request and its validity is explained.
- [ ] **M37.04** — Try one wrong code and a code from another request, then the correct code. **Expected:** Wrong codes do not collect the sample; correct code changes the intended request once.
- [ ] **M37.05** — Try reusing the accepted code; separately use an expired/reassigned/cancelled request code with staff-prepared fixtures. **Expected:** Reuse and invalidated codes are rejected; stop if attempt limits trigger and record the result.
- [ ] **M37.06** — Move through awaiting sample, sample collected, processing, result ready and completed using allowed controls. **Expected:** Invalid skips are rejected; history records actor/time and customer status agrees.
- [ ] **M37.07** — Refresh after every transition. **Expected:** Status and collection verification persist without duplicated events.

**Result:** ______  **References / evidence:** ______  **Actual result / issue:** ______


### M38. Result upload, notification, download and privacy

**Role:** Assigned lab technician; Customer A; unrelated users. **Covers:** LAB-07 LAB-09 E2E-05.

**Before starting:** Use the collected/processing home request from M37.

- [ ] **M38.01** — Attempt an invalid result file, then upload the synthetic lab PDF through the assigned technician workspace. **Expected:** Invalid upload is rejected; valid result is attached to the intended request.
- [ ] **M38.02** — Publish/complete using the allowed workflow. **Expected:** Completion requires the correct result and intended audit history.
- [ ] **M38.03** — As patient, open the lab notification and /account/lab-tests, select the exact request and download. **Expected:** File and request reference match; PDF opens and is the synthetic report you uploaded.
- [ ] **M38.04** — Refresh, leave and return to the request; retry an offered upload/publish action once on a test fixture. **Expected:** Existing result is stable and repeated actions do not create unintended duplicate publication.
- [ ] **M38.05** — As Customer B, unrelated technician and unrelated partner, try copied result/detail links. **Expected:** Files and changes are denied; a revoked facility/account cannot publish.
- [ ] **M38.06** — Check in-app notification and actual external email receipt separately. **Expected:** Correct recipient and record link; mailbox delivery is only marked passed if actually received.

**Result:** ______  **References / evidence:** ______  **Actual result / issue:** ______


## 11. Staff catalog, inventory and content


### M39. Create/edit catalog products and exact variants

**Role:** Administrator; customer. **Covers:** CAT-01.

**Before starting:** Use a new synthetic product; do not edit live medicine details for a test.

- [ ] **M39.01** — Open /admin/brands and /admin/categories; create a clearly labelled test brand/category/subcategory. **Expected:** Records save once and are available in the product form.
- [ ] **M39.02** — Open /admin/products, create a product and two distinguishable variants with different strength/pack/price. Upload suitable test images. **Expected:** Parent and variant fields are distinct and exact SKUs remain unique.
- [ ] **M39.03** — Save and reopen each variant. Try duplicate SKU, invalid price and missing required fields in separate attempts. **Expected:** Valid values persist; invalid input does not partially replace good data.
- [ ] **M39.04** — Publish and open the storefront detail/search as customer. **Expected:** Brand/category, descriptions, images, variant options, prices and badges match admin data.
- [ ] **M39.05** — Edit only variant B image/price and refresh the storefront. **Expected:** Variant A is unchanged and B updates correctly.
- [ ] **M39.06** — Deactivate the test product after its test obligations finish. **Expected:** It leaves new customer purchasing while historical records remain readable.

**Result:** ______  **References / evidence:** ______  **Actual result / issue:** ______


### M40. Stock by variant/store, adjustments and low-stock indication

**Role:** Inventory staff; customer; administrator. **Covers:** INV-01 INV-02 INV-03 INV-07 INV-09.

**Before starting:** Use S1/S2 and variant A/B baselines from M02; coordinate a separate paid stock test.

- [ ] **M40.01** — Open /inventory/manage or /admin/inventory and record A/S1=50, A/S2=30 and B separate balances. **Expected:** Each row identifies the exact variant and store/location.
- [ ] **M40.02** — Adjust A/S1 through the authorized control with a reason, then refresh movement history. **Expected:** Quantity, actor, reason and timestamp are recorded; other rows are unchanged.
- [ ] **M40.03** — Restore the agreed A/S1 baseline with a separate documented adjustment. Complete an order for 2 packs allocated specifically to S1. **Expected:** At the configured commitment stage A/S1=48, A/S2=30 and B unchanged.
- [ ] **M40.04** — Check reserved versus available stock if supported, then repeat finalization through an offered stale confirmation. **Expected:** No second deduction or unexplained permanent reservation.
- [ ] **M40.05** — Use a prepared low-stock threshold fixture, cross its threshold and inspect staff/storefront indicator or notification. **Expected:** Configured low-stock signal appears for the correct row; do not assume an email unless actually received.
- [ ] **M40.06** — Try a negative balance/invalid quantity or mismatched row through visible staff controls. **Expected:** Validation prevents corrupt balances.
- [ ] **M40.07** — As customer, type the inventory URL and try any exposed edit action. **Expected:** Modification is denied.
- [ ] **M40.08** — Restore only temporary adjustment/threshold changes with reasons. **Expected:** Purchased stock movements and audit evidence are retained.

**Result:** ______  **References / evidence:** ______  **Actual result / issue:** ______


### M41. Two customers competing for the last unit

**Role:** Customer A; Customer B; inventory staff. **Covers:** INV-06.

**Before starting:** Set one isolated exact variant to one available unit, with backorders disabled.

- [ ] **M41.01** — In separate customer sessions, each add that variant and open checkout. **Expected:** Both see the same item; stock claims are not confused with parent availability.
- [ ] **M41.02** — Coordinate checkout/finalization as closely together as supported in the sandbox, approving only agreed test payments. **Expected:** At most one order commits the last unit; no negative stock.
- [ ] **M41.03** — Have staff inspect both orders, successful payments and inventory movements. **Expected:** Losing checkout has a useful outcome and any paid-but-unfulfillable order is flagged for reconciliation/refund, not hidden.
- [ ] **M41.04** — Refresh both customer views. **Expected:** No silent extra order or unhandled spinner; final balances and obligations are clear.
- [ ] **M41.05** — If real simultaneous execution cannot be achieved manually, record the observed outcome and request the technical locking/concurrency test. **Expected:** A sequential browser run is not reported as proof of concurrency.

**Result:** ______  **References / evidence:** ______  **Actual result / issue:** ______


### M42. External POS synchronization and fulfillment

**Role:** Inventory staff; integration tester. **Covers:** INV-08 ORD-14.

**Before starting:** Real POS testing is currently held at the user request; this guide does not remove that hold.

- [ ] **M42.01** — Confirm a dedicated test POS and explicit authorization to resume exist before starting. **Expected:** Otherwise mark Blocked; do not send synthetic orders to a real fulfillment service.
- [ ] **M42.02** — With authorized setup, map a known test SKU to exact variant/store and sync a known balance. **Expected:** Correct mapped inventory changes; other variants/stores do not.
- [ ] **M42.03** — Repeat the same update and submit an unknown mapping. **Expected:** Replays do not duplicate movements and unknown mappings are reported for review.
- [ ] **M42.04** — Use controlled test POS downtime/failure then restore service and retry. **Expected:** Failure is visible, retry is tracked and state recovers without duplicate records.
- [ ] **M42.05** — Push one authorized test order, retry the same push and compare external order reference. **Expected:** One external order, correct items/quantities and delivery data; store the external evidence.
- [ ] **M42.06** — If only mock/test-suite results are available, record them separately. **Expected:** They do not check off this real integration step.

**Result:** ______  **References / evidence:** ______  **Actual result / issue:** ______


### M43. Banners, FAQs, offers and settings on the storefront

**Role:** Administrator; visitor. **Covers:** CAT-06 SUP-04.

**Before starting:** Record original values and use one harmless test item/setting.

- [ ] **M43.01** — Open admin banner/FAQ/deal/content controls that are offered. Create a dated synthetic item and preview it on the public site. **Expected:** Correct text/image/link, dates and intended placement; missing editor is recorded.
- [ ] **M43.02** — Edit and unpublish the synthetic content, refreshing the public page each time. **Expected:** Saved visibility and changes persist; dates do not leak future/expired promotions.
- [ ] **M43.03** — Open /admin/settings, change a harmless public support/display setting and save. **Expected:** Refreshed public page shows only that intended public value.
- [ ] **M43.04** — Try an invalid price or unsafe/invalid policy URL through the form. **Expected:** Save is rejected clearly without replacing the valid setting.
- [ ] **M43.05** — As customer/visitor, check public settings content and try typing the admin settings URL. **Expected:** Private configuration/secrets are absent and writes are denied.
- [ ] **M43.06** — Restore original settings and remove/deactivate only your disposable content. **Expected:** Public information returns to its recorded baseline.

**Result:** ______  **References / evidence:** ______  **Actual result / issue:** ______


## 12. Payouts and finance


### M44. Calculate and create a source-linked payout

**Role:** Administrator maker; clinician. **Covers:** PAY-01.

**Before starting:** Use a completed paid synthetic consultation with a recorded earning; current payouts are administrative records.

- [ ] **M44.01** — Open /admin/invoices?view=payouts or the Payouts menu, inspect reference rules and record the applicable rate/commission. **Expected:** Rules are labelled as reference configuration, not automatic money transfers.
- [ ] **M44.02** — Select a real active professional recipient and the completed consultation source. **Expected:** Recipient role/account and source reference match; a display name alone cannot create an unlinked recipient.
- [ ] **M44.03** — Enter gross, commission, withholding and other deductions. Independently calculate net = gross − commission − withholding − deductions. **Expected:** Preview and saved amounts match; examples: 500−50=450 and 500−50−20−10=420.
- [ ] **M44.04** — Try negative deductions, deductions exceeding gross, wrong recipient role and a different clinician consultation. **Expected:** Validation blocks invalid amounts/source relationships.
- [ ] **M44.05** — Save the valid synthetic draft with a unique source/idempotency reference and explicit no-transfer note. **Expected:** One draft record with correct professional and earning link.
- [ ] **M44.06** — Try creating the same source again. **Expected:** Existing payout or useful conflict, never a second obligation.

**Result:** ______  **References / evidence:** ______  **Actual result / issue:** ______


### M45. Maker-checker, recorded payment and reconciliation

**Role:** Two administrators; clinician. **Covers:** PAY-02 PAY-03 PAY-04.

**Before starting:** Use one synthetic administrative payout from M44; no actual provider transfer is triggered by this application.

- [ ] **M45.01** — As maker, submit the payout; try approving your own entry. **Expected:** Maker-checker policy prevents self-approval.
- [ ] **M45.02** — As independent checker, review amount/source/recipient and approve. **Expected:** Approval actor/time are saved.
- [ ] **M45.03** — As permitted admin, progress to Processing, then record a clearly labelled SYNTHETIC-NO-TRANSFER payment reference only for this QA ledger test. **Expected:** UI explicitly describes an administrative record, not proof of actual transfer.
- [ ] **M45.04** — Reconcile the record and refresh audit history. **Expected:** Paid/matched status, reference and actor agree with the chosen source and amount.
- [ ] **M45.05** — Repeat mark-paid/reconcile or reuse the same reference on another disposable payout. **Expected:** Duplicates are denied and no new transfer/earning is invented.
- [ ] **M45.06** — As clinician, open earnings/payout history and match source, net and status. **Expected:** Only that professional records appear, with the administrative meaning clear.
- [ ] **M45.07** — If actual provider transfer is a requirement for your release, mark that additional requirement Blocked/unimplemented until an independent provider transfer exists. **Expected:** A ledger status does not satisfy it.

**Result:** ______  **References / evidence:** ______  **Actual result / issue:** ______


### M46. Payout holds, failures, retries, reversals and access

**Role:** Administrator; unrelated professional; customer. **Covers:** PAY-05 PAY-06 PAY-07.

**Before starting:** Use separate synthetic ledger fixtures for terminal branches.

- [ ] **M46.01** — Hold a payout with a reason, release it and attempt processing without renewed approval. **Expected:** Hold history persists and release requires approval again.
- [ ] **M46.02** — Mark a processing fixture failed with reason, then use Retry. **Expected:** Amount stays stable and retry count/history update once.
- [ ] **M46.03** — Cancel a separate eligible payout and reverse a separate paid synthetic ledger fixture. **Expected:** Correct terminal state/history and stated reconciliation exception; no claim that funds moved back automatically.
- [ ] **M46.04** — Try invalid transitions, missing required reason and future payment time. **Expected:** Useful validation prevents inconsistent records.
- [ ] **M46.05** — As customer/unrelated professional, type the admin payout URL and try a copied payout link. **Expected:** Admin actions and other recipients data are denied.
- [ ] **M46.06** — Refresh professional earnings after each appropriate branch. **Expected:** Ledger status, pending/recorded-paid amounts and source remain consistent.

**Result:** ______  **References / evidence:** ______  **Actual result / issue:** ______


## 13. Notifications, support and compliance


### M47. Inbox, unread counts, search and record links

**Role:** Customer A; relevant staff. **Covers:** NOT-01 NOT-02 NOT-04.

**Before starting:** Use notifications generated by your prescription, consultation, order and lab journeys.

- [ ] **M47.01** — Open /account/notifications and record the unread count. **Expected:** Correct signed-in recipient notices appear.
- [ ] **M47.02** — Mark one unread notice read, refresh and compare the count; then Mark all read and refresh. **Expected:** Counts decrease accurately and read state persists.
- [ ] **M47.03** — Search for a recorded order/prescription/consultation/lab reference and use pagination. **Expected:** Results and totals are correct and paging does not silently stop after the first page.
- [ ] **M47.04** — Open one link for each service type plus support. **Expected:** Exact authorized record opens; prescription panels can be closed and do not repeatedly reopen.
- [ ] **M47.05** — As B, try A notification/detail/delivery links. **Expected:** A private notices and records cannot be read or changed.
- [ ] **M47.06** — Have staff check the intended business recipient after each trigger. **Expected:** Correct patient/guardian/professional receives the notice; no unrelated child/user is notified.

**Result:** ______  **References / evidence:** ______  **Actual result / issue:** ______


### M48. Preferences, delivery failures and retries

**Role:** Customer A; notification test operator. **Covers:** NOT-03 NOT-05.

**Before starting:** Use only your disposable test notifications and authorized test destinations.

- [ ] **M48.01** — Open notification preferences; change an optional channel and save. Reload and sign in again. **Expected:** Preference persists.
- [ ] **M48.02** — Trigger an optional test notice with that channel disabled. **Expected:** Optional delivery follows preference; business record/inbox outcome follows the stated policy.
- [ ] **M48.03** — Request a verification/reset or permitted required receipt separately. **Expected:** Required operational policy is clear; do not assume optional marketing preferences suppress necessary security messages.
- [ ] **M48.04** — With test operator help, create one controlled failed delivery, then use its Retry control once. **Expected:** Attempt history records failure then retry on the same notification/delivery.
- [ ] **M48.05** — Retry a successful delivery, disable a channel before retry, or reach the configured cap with dedicated fixtures. **Expected:** Invalid retries are denied; no duplicate order/booking occurs.
- [ ] **M48.06** — Inspect actual recipient mailbox/phone and delivery status separately; restore preferences. **Expected:** Backend accepted/sent status is distinguished from actual recipient receipt; changes to addresses/preferences are respected.

**Result:** ______  **References / evidence:** ______  **Actual result / issue:** ______


### M49. Customer ticket, public reply, private note and resolution

**Role:** Customer A; Customer B; support administrator. **Covers:** SUP-01 SUP-02.

**Before starting:** Use a new ticket about a synthetic record; keep genuine refund inquiries open until settled.

- [ ] **M49.01** — Open /account/support, create a ticket with channel, reference, subject and valid priority. Submit once and refresh. **Expected:** One reference appears and is linked to the correct customer/service.
- [ ] **M49.02** — As admin, open /admin/support, find that reference and assign an eligible staff member if offered. **Expected:** Assignment and status changes persist.
- [ ] **M49.03** — Add a public reply, then a distinct Internal note. **Expected:** Staff can distinguish visibility and audit authors/times.
- [ ] **M49.04** — As customer, refresh the ticket and read history. **Expected:** Public reply/status are visible; internal note is absent from detail/export.
- [ ] **M49.05** — As B, try A ticket link and note controls. **Expected:** Read/write access is denied.
- [ ] **M49.06** — Resolve a settled synthetic inquiry and ask A to reply after resolution. **Expected:** Configured follow-up/reopening behavior is clear and saved; no hidden loss of the customer reply.
- [ ] **M49.07** — Use search/filter/paging/export if offered. **Expected:** Only authorized tickets/notes appear, and export preserves note privacy.

**Result:** ______  **References / evidence:** ______  **Actual result / issue:** ______


### M50. Contact form and newsletter

**Role:** Visitor; signed-in customer; support administrator. **Covers:** SUP-03.

**Before starting:** Use your own test email and a synthetic non-sensitive contact message.

- [ ] **M50.01** — Open /contact signed out and inspect submission guidance. **Expected:** Sign-in guidance matches the authenticated ticket policy; no false success from a non-working form.
- [ ] **M50.02** — Sign in, submit a valid contact message and note the resulting ticket. **Expected:** Customer support history and admin queue show the saved inquiry.
- [ ] **M50.03** — Find the newsletter form and submit an invalid address. **Expected:** Clear validation and no successful signup claim.
- [ ] **M50.04** — Submit a valid test email once, then submit the same email again. **Expected:** Useful confirmation/duplicate message without duplicate subscription or repeated confirmation spam.
- [ ] **M50.05** — If a controlled email failure is available, have the operator exercise it with your test address. **Expected:** Subscription state is not lost or duplicated; failure/retry information is honest.
- [ ] **M50.06** — Check external confirmation receipt only if configured, then have staff deactivate disposable marketing fixtures if needed. **Expected:** Marketing consent is deliberate and your test does not leave unwanted subscriptions.

**Result:** ______  **References / evidence:** ______  **Actual result / issue:** ______


### M51. Compliance evidence and role-limited download

**Role:** Administrator; PPB inspector/read-only role; customer. **Covers:** SUP-05.

**Before starting:** Use a clearly marked synthetic evidence PDF, not a real credential.

- [ ] **M51.01** — As admin, open /account/compliance and create evidence with required metadata and the synthetic document. **Expected:** Saved evidence appears with correct status and owner.
- [ ] **M51.02** — Refresh, open and download the protected evidence. **Expected:** File is the uploaded synthetic PDF and associated metadata persists.
- [ ] **M51.03** — As read-only inspector, open and download the permitted evidence, then try editing/upload/deletion controls. **Expected:** Read permission works and write permission is denied.
- [ ] **M51.04** — As customer or signed-out visitor, open a copied evidence/download URL. **Expected:** Private evidence is denied.
- [ ] **M51.05** — Ask technical tester to verify raw media denial on the actual hosted server. **Expected:** Hosted protection is evidenced separately from a local authorized download.
- [ ] **M51.06** — Leave the disposable evidence in an agreed review/archive state and retain its reference. **Expected:** Test evidence cannot be mistaken for a real approved license.

**Result:** ______  **References / evidence:** ______  **Actual result / issue:** ______


## 14. Mobile, accessibility and recovery


### M52. Repeat the main journeys on a phone

**Role:** Customer; relevant staff. **Covers:** Cross-cutting.

**Before starting:** Use your actual phone browser or a narrow browser window; record device/browser.

- [ ] **M52.01** — Open homepage, menus, search/results and product detail at narrow width. **Expected:** No clipped text, missing navigation, overlapping buttons or horizontal scrolling needed for core actions.
- [ ] **M52.02** — Choose a variant, edit cart, select delivery, read totals and initiate one authorized payment if necessary. **Expected:** Controls remain usable, keyboard does not hide required fields, and final amount is visible.
- [ ] **M52.03** — Upload a synthetic prescription from the phone file picker and open its status/history. **Expected:** Accepted types/limits and progress/errors work on mobile.
- [ ] **M52.04** — Open doctor/pediatric chat, scroll history, send a test message and open an attachment. **Expected:** Composer and latest messages are accessible with the keyboard open.
- [ ] **M52.05** — Open child selection, consent, lab booking/result, notifications and support. **Expected:** All core customer functions can be completed without switching to desktop.
- [ ] **M52.06** — Rotate the device and return from another app/payment prompt. **Expected:** Draft, session and current status remain stable; no duplicate payment/booking.

**Result:** ______  **References / evidence:** ______  **Actual result / issue:** ______


### M53. Keyboard, errors, loading and refresh recovery

**Role:** Customer; one representative staff role. **Covers:** Cross-cutting.

**Before starting:** Use a fresh disposable draft for interruptions; do not interrupt an unknown payment and immediately retry it.

- [ ] **M53.01** — Navigate sign-in, cart, checkout and support with Tab/Shift+Tab/Enter/Space. **Expected:** Focus is visible, controls have readable labels and modal focus does not trap you unexpectedly.
- [ ] **M53.02** — Increase browser zoom to 200% and inspect required fields/status/errors. **Expected:** Core content remains readable and operable without relying only on colour.
- [ ] **M53.03** — Submit a form with one invalid field and correct it. **Expected:** Error associates with the field; useful valid input is retained and screen focus can reach the problem.
- [ ] **M53.04** — Throttle/disconnect network temporarily during a harmless read or saved draft, then reconnect and refresh. **Expected:** Loading ends, a useful recovery action exists and saved state returns.
- [ ] **M53.05** — Navigate back/forward, refresh an account detail and open a direct bookmark after login. **Expected:** Correct record/role persists without endless redirects.
- [ ] **M53.06** — Inspect long product names, large histories, empty carts, no search results and long PDF instructions. **Expected:** Text is not clipped, empty states are useful and pagination works.
- [ ] **M53.07** — If session expires mid-form, sign back in through the intended flow and check the draft. **Expected:** No accidental duplicate submission or disclosure to the wrong account.

**Result:** ______  **References / evidence:** ______  **Actual result / issue:** ______


## 15. Connected runs and final reconciliation


### M54. Run all six journeys with one reference chain each

**Role:** Tester; all relevant role partners. **Covers:** E2E-01 E2E-02 E2E-03 E2E-04 E2E-05 E2E-06.

**Before starting:** Use your own new references; historical passed references are examples only.

- [ ] **M54.01** — Journey 1: new registration/verification → correct variant/cart → payment → stock → synthetic fulfillment → receipt/report, using M06, M04 and M10–M16. **Expected:** One customer/order chain, one successful payment and expected exact stock.
- [ ] **M54.02** — Journey 2: upload → clarification/reply → pharmacist approval → prescription checkout → payment → dispensing/delivery, using M20–M24. **Expected:** Prescription/item/variant/order/payment references agree.
- [ ] **M54.03** — Journey 3: professional approval → paid doctor booking → chat → e-prescription → pharmacist → medicine payment/order → completion → earning → administrative payout/reconciliation. **Expected:** Two distinct payment obligations, one consultation/earning and correctly labelled payout record.
- [ ] **M54.04** — Journey 4: guardian/two children → child A → consent → paid pediatric booking → prescription → separate medicine checkout → completion/history/earning. **Expected:** Same child ID throughout and sibling history stays separate.
- [ ] **M54.05** — Journey 5: approved lab partner/facility → request → code/sample collection → processing → result → patient notice/download. **Expected:** One consistent pay-later request with correct quote, facility, technician and private result.
- [ ] **M54.06** — Journey 6: failed payment → safe successful retry → one order → cancellation/return → quarantine → actual external refund evidence → correct finance → settled support ticket. **Expected:** One successful charge; no duplicate stock/refund; if external refund is unavailable, the live journey remains partial.
- [ ] **M54.07** — For each journey, compare refreshed customer and staff views, receipt/reference and inventory/earning/report rows. **Expected:** A nice-looking customer screen alone does not establish cross-role completion.

**Result:** ______  **References / evidence:** ______  **Actual result / issue:** ______


### M55. Record defects, clean up and review

**Role:** Tester; administrator; reviewer. **Covers:** Completion criteria.

**Before starting:** Use the issue template and result fields included below.

- [ ] **M55.01** — For every failed/blocked step, write its case/step ID, exact action, expected and actual result, record reference and screenshot. **Expected:** Someone else can reproduce it without your credentials.
- [ ] **M55.02** — After a fix, repeat the failed step and its surrounding journey with a clean fixture where needed. **Expected:** Retest result/date/evidence are recorded separately from the original failure.
- [ ] **M55.03** — Ask staff to compare successful payment count, exact stock movements, child identity, consultation/earning count and return obligations for all your references. **Expected:** No unresolved duplicate charge, wrong patient, unauthorized access or unexplained inventory movement.
- [ ] **M55.04** — List Paybill, POS, external refund, external email/SMS and hosted-file protection outcomes individually. **Expected:** Unavailable integrations are Blocked, and card/COD/pay-later/administrative-ledger scope exclusions have explicit reasons.
- [ ] **M55.05** — Remove/deactivate only disposable fixtures that have no pending provider result/financial obligation. Restore settings, prices and reference rules. **Expected:** Real evidence/history remains; old pending payments are not hidden by deleting fixtures.
- [ ] **M55.06** — Export/save the completed checklist and issue log, and retain screenshots/PDFs in a run folder. **Expected:** Results can be reviewed even if browser local storage is cleared.
- [ ] **M55.07** — Have the reviewer record overall Pass/Conditional/Not ready and explicitly list accepted limitations. **Expected:** Tester and reviewer names/date are recorded; an unexecuted integration is not quietly marked passed.

**Result:** ______  **References / evidence:** ______  **Actual result / issue:** ______


### M56. Technical handoffs that a browser run cannot prove alone

**Role:** Tester coordinates; technical/integration tester performs. **Covers:** ACC-07 INV-06 ORD-10 ORD-11 RX-09 CON-05 CON-06 CON-07 LAB-05 LAB-09 PAY-04 NOT-05.

**Before starting:** You do not need to use developer tools or send API requests yourself for these checks.

- [ ] **M56.01** — Ask for a logout/refresh-token revocation test, including an old token after suspension. **Expected:** Technical evidence confirms server enforcement beyond browser redirection.
- [ ] **M56.02** — Ask for concurrent last-unit stock allocation, open-doctor claim, collection-code use, result publication and payout-reference uniqueness tests. **Expected:** Real parallel requests/locking are covered; a sequential manual test is not substituted.
- [ ] **M56.03** — Ask for forged, mismatched amount/reference/customer, replayed and late payment callback tests and repeated finalization. **Expected:** Untrusted payment data cannot create paid records, duplicate bookings or stock movements.
- [ ] **M56.04** — Ask for file content/size, raw media, expired signed-link and revoked-account access tests in development and the intended hosted configuration. **Expected:** Private prescription/chat/lab/compliance files remain protected on the target environment.
- [ ] **M56.05** — Ask for forced delivery/provider/POS downtime and retry-cap tests using controlled fixtures. **Expected:** Business actions remain consistent and retries do not duplicate orders, bookings or transfers.
- [ ] **M56.06** — Record test report/log, environment/build, tester and outcome in your run sheet. **Expected:** Mark technical-only evidence clearly; if the website step itself failed, it remains a website failure.

**Result:** ______  **References / evidence:** ______  **Actual result / issue:** ______


## Evidence register: keep the same references across roles

| Journey | Customer / child ID | Order / booking / lab request | Prescription | Payment receipt(s) / amount | Exact variant + store + before/after stock | Earning / payout / return / support | Evidence / result |
|---|---|---|---|---|---|---|---|
| New customer order | ______ | ______ | N/A | ______ | ______ | ______ | ______ |
| Uploaded prescription order | ______ | ______ | ______ | ______ | ______ | ______ | ______ |
| Doctor consultation + medicine | ______ | ______ | ______ | consultation: ______; medicine: ______ | ______ | ______ | ______ |
| Pediatric consultation + medicine | guardian: ______; child: ______ | ______ | ______ | consultation: ______; medicine: ______ | ______ | ______ | ______ |
| Lab pay-later | ______ | ______ | N/A | arranged payment: ______ | N/A | result file: ______ | ______ |
| Failed payment / retry / return | ______ | ______ | ______ | failed: ______; success: ______; refund: ______ | ______ | ______ | ______ |

## Copy this issue template for each problem

- Issue ID: MANUAL-____
- Case and step: M__.____
- Date/time and timezone: ____
- Website/build, browser/device and role: ____
- Synthetic record reference(s): ____
- Starting state: ____
- Exact steps to reproduce: ____
- Expected result: ____
- Actual result / displayed error: ____
- Screenshot or file name: ____
- Impact: Blocker / High / Medium / Low
- Payment actually taken? Receipt/amount? Stock/child/privacy affected? ____
- Workaround, if any (does not change original result): ____
- Assigned person / fix reference: ____
- Retest date/build/steps and Pass/Fail: ____
- Reviewer decision: ____

## Final run sign-off

- [ ] Every case has Pass, Fail, Blocked, Partial or explained N/A; no untested item is silently marked passed.
- [ ] Required customer journeys were performed through the website; staff handoffs and technical-only evidence are identified.
- [ ] Every failure has reproduction steps/evidence and every claimed fix has a retest.
- [ ] Payment receipts, totals, exact stock, child identity, earnings and record ownership reconcile for all tested references.
- [ ] Remaining provider/POS/refund/delivery/deployment issues are explicitly listed with owner and next action.
- [ ] No actual refund/transfer is claimed from an administrative status change alone.
- [ ] Test fixtures and settings were cleaned up/restored without deleting evidence or hiding pending financial obligations.
- [ ] Tester and reviewer recorded the final decision below and exported the run results.

| Final field | Your result |
|---|---|
| Overall decision | Pass / Conditional / Not ready |
| Cases passed / failed / blocked / partial / N/A | ______ / ______ / ______ / ______ / ______ |
| Outstanding issues and owners | ______ |
| Accepted limitations, explicitly agreed by reviewer | ______ |
| Tester / date | ______ |
| Reviewer / date | ______ |
| Evidence folder / exported checklist file | ______ |

## Original acceptance-check coverage

This index maps every one of the 110 original top-level scenario IDs to at least one manual case. It maps coverage, not a passed result. Some server/concurrency/provider checks require the technical handoff in M56; a missing website control remains a website gap.

| Original scenario | Manual cases |
|---|---|

| SET-01 | M01 |
| SET-02 | M01 |
| SET-03 | M01 |
| SET-04 | M02 |
| SET-05 | M02 |
| SET-06 | M02 |
| SET-07 | M02 |
| ACC-01 | M06 |
| ACC-02 | M06 |
| ACC-03 | M07 |
| ACC-04 | M07 |
| ACC-05 | M08 |
| ACC-06 | M08 |
| ACC-07 | M08, M56 |
| ACC-08 | M09 |
| ACC-09 | M09 |
| ACC-10 | M25 |
| ACC-11 | M09 |
| CAT-01 | M39 |
| CAT-02 | M03, M04 |
| CAT-03 | M04 |
| CAT-04 | M05 |
| CAT-05 | M05 |
| CAT-06 | M03, M43 |
| INV-01 | M40 |
| INV-02 | M40 |
| INV-03 | M40 |
| INV-04 | M17 |
| INV-05 | M15 |
| INV-06 | M41, M56 |
| INV-07 | M40 |
| INV-08 | M42 |
| INV-09 | M40 |
| ORD-01 | M10 |
| ORD-02 | M10 |
| ORD-03 | M11 |
| ORD-04 | M11 |
| ORD-05 | M12 |
| ORD-06 | M14 |
| ORD-07 | M14 |
| ORD-08 | M14 |
| ORD-09 | M13 |
| ORD-10 | M13, M56 |
| ORD-11 | M19, M56 |
| ORD-12 | M15 |
| ORD-13 | M16 |
| ORD-14 | M42 |
| ORD-15 | M17 |
| ORD-16 | M18 |
| ORD-17 | M16 |
| ORD-18 | M19 |
| RX-01 | M20 |
| RX-02 | M20 |
| RX-03 | M21, M23 |
| RX-04 | M21 |
| RX-05 | M22 |
| RX-06 | M23 |
| RX-07 | M23 |
| RX-08 | M23 |
| RX-09 | M24, M56 |
| CON-01 | M25 |
| CON-02 | M26 |
| CON-03 | M27 |
| CON-04 | M27 |
| CON-05 | M27, M56 |
| CON-06 | M28, M56 |
| CON-07 | M29, M56 |
| CON-08 | M30 |
| CON-09 | M30 |
| CON-10 | M31 |
| CON-11 | M29 |
| PED-01 | M32 |
| PED-02 | M33 |
| PED-03 | M33 |
| PED-04 | M33 |
| PED-05 | M34 |
| PED-06 | M32, M34 |
| PED-07 | M32 |
| LAB-01 | M25, M35 |
| LAB-02 | M35 |
| LAB-03 | M36 |
| LAB-04 | M37 |
| LAB-05 | M37, M56 |
| LAB-06 | M37 |
| LAB-07 | M38 |
| LAB-08 | M36 |
| LAB-09 | M38, M56 |
| PAY-01 | M44 |
| PAY-02 | M45 |
| PAY-03 | M45 |
| PAY-04 | M45, M56 |
| PAY-05 | M46 |
| PAY-06 | M46 |
| PAY-07 | M46 |
| NOT-01 | M47 |
| NOT-02 | M47 |
| NOT-03 | M48 |
| NOT-04 | M47 |
| NOT-05 | M48, M56 |
| SUP-01 | M49 |
| SUP-02 | M49 |
| SUP-03 | M50 |
| SUP-04 | M43 |
| SUP-05 | M51 |
| E2E-01 | M54 |
| E2E-02 | M23, M54 |
| E2E-03 | M30, M54 |
| E2E-04 | M34, M54 |
| E2E-05 | M38, M54 |
| E2E-06 | M18, M54 |
