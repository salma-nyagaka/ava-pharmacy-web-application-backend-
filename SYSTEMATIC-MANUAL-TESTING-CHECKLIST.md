# AvaPharmacy — systematic manual system testing checklist

Start from the admin side, as if the website is new and only the first admin account exists. We will work through one section at a time. Existing records do not need to be deleted.

Tick a box only after it works. After saving anything, refresh to check it stayed saved. If something fails, write the problem beside it and we will fix it before continuing with that journey.


Prepared **5 November 2026**. This is a fresh manual run for you to perform through the website; no previous passes are carried forward.

Based on the [technical acceptance checklist](docs/end-to-end-test-checklist.md) and [simple manual checklist](docs/simple-manual-testing-checklist.md). Also track PPB-specific evidence in the [compliance remediation checklist](docs/compliance-audit/2026-11-05/ppb-remediation-checklist.md).

## Time estimate and plan to finish today

**Planning estimate for one tester: about 12–18 hours of active testing for the full checklist**, plus breaks, troubleshooting and retesting. Several checkboxes contain multiple input variations, so 281 checkboxes are more than 281 individual actions. These estimates assume the application is running, admin access is available, test files/accounts can be created, and payment/test services respond normally. They exclude code fixes, real delivery travel, provider support delays and waiting for an external refund.

**For today: budget 6 hours 10 minutes of focused testing, 45 minutes of breaks and 20 minutes of contingency (7 hours 15 minutes total).** This is a priority run across every section, with the main connected journeys and selected high-risk errors. Completing every validation variation today is unlikely for one tester. Leave unperformed checks empty and record them as **Not tested — deferred**, rather than passed or blocked.

### Section budgets

| Section | Full checks, minutes | Today's priority budget, minutes |
|---|---:|---:|
| 1. Admin login/settings | 30–45 | 15 |
| 2. Staff accounts | 30–45 | 15 |
| 3. Brand, categories, products and variants | 60–90 | 30 |
| 4. Stores and inventory | 40–60 | 20 |
| 5. Offers and public content | 25–40 | 10 |
| 6. Customer account | 45–60 | 20 |
| 7. Cart, checkout and payment | 60–90 | 30 |
| 8. Delivery, cancellation and returns | 60–90 | 25 |
| 9. Uploaded prescriptions | 45–60 | 25 |
| 10. Doctor consultation | 60–90 | 35 |
| 11. Paediatric clinic | 60–90 | 35 |
| 12. Lab services | 60–90 | 30 |
| 13. Earnings and payouts | 40–60 | 20 |
| 14. Notifications and support | 40–60 | 20 |
| 15. Privacy, mobile and final checks | 45–60 | 25 |
| Connected records and final sign-off | 20–30 | 15 |
| **Total active testing** | **720–1060 (12.0–17.7 hours)** | **370 (6 hours 10 minutes)** |

### Today's schedule — 5 November 2026, Africa/Nairobi

Assumed EOD: **18:00 EAT**. Planned start: **10:45 EAT**. If you start later, reduce the deferred validation coverage or record unfinished work; do not shorten payment verification or mark untested steps passed.

| Time (EAT) | Work | Target outcome |
|---|---|---|
| 10:45–12:15 | Sections 1–5 | Admin/staff ready; brand, categories, products, variants, stock and offer created and checked |
| 12:15–13:30 | Sections 6–8 | Customer account; paid exact-variant order; stock, tracking and eligible cancellation/return checked |
| 13:30–14:00 | Break | 30 minutes |
| 14:00–15:35 | Sections 9–11 | Uploaded prescription, doctor journey and paediatric child/consent journey checked through medicine checkout and completion |
| 15:35–15:50 | Break | 15 minutes |
| 15:50–17:25 | Sections 12–15 | Lab request/result, payout ledger, notifications/support, privacy and mobile checks |
| 17:25–17:40 | Connected records and sign-off | Match references and amounts; list failures, blocks and deferred checks |
| 17:40–18:00 | Contingency | Retest the most important resolved issues or finish evidence recording |

### What to prioritise within each budget

1. Perform each section's **Main flow** first, using the same test records across customer and staff handoffs. Read the error checks before submitting so you can combine overlapping checks without repeating payments.
2. For each creation form, prioritise empty required fields, one invalid value and a duplicate where relevant. Defer exhaustive per-field variations if the budget runs out.
3. Always verify exact variant/store stock, correct totals and provider-confirmed payment. Check failed payment recovery without issuing another request while an existing payment is unresolved.
4. In the doctor and paediatric clinic flows, retain consent, correct patient/child identity, private-access checks, prescription limits and one earning per completed consultation. Use separate consultation and medicine payment references.
5. In the lab flow, prioritise the complete home-collection-to-result journey; defer the separate walk-in branch if needed. Verify a wrong collection code is rejected and another patient cannot download the result.
6. Use a second unrelated customer to check private orders, prescriptions, children, consultations and lab files. Do not defer an observed privacy, wrong-patient, duplicate-payment or incorrect-stock failure to declare a pass.
7. Time-box investigation of a non-critical failure to **10 minutes**, record the step ID and evidence, then continue with independent tests. Record unavailable required services as blocked; record tests skipped for time as deferred. Keep actual refunds, provider callbacks, external messages and POS outcomes pending until evidenced. Real POS remains on hold as stated below.
8. At 17:25, stop starting new journeys and reconcile existing records. Reuse evidence gathered during the section runs for the connected journey table; a complete second execution is outside today's priority budget. The final outcome may be **Partial**, even if all selected main flows pass.

## Your run sheet

| Detail | Your entry |
|---|---|
| Tester / date | |
| Website URL / version | |
| Browser / phone | |
| Test environment / payment setup | |
| Admin / pharmacist / inventory account labels | |
| Customer A / unrelated Customer B | |
| Doctor / paediatrician / lab partner / technician | |
| Evidence location | |

Follow Sections 1–15 in order: admin setup → staff → brand/category/product/variants → stock → public content → customer → checkout → delivery/returns → uploaded prescriptions → doctor → paediatric clinic → laboratory → payouts → notifications/support → final checks.

Use separate browser profiles for different roles. Create records with a shared prefix such as `MANUAL-20261105`; retain the same records throughout each journey. Existing records do not need resetting. Start with a running test environment and the initial administrator account.

Each step has an ID such as `S03-01`. Tick only verified passes. Record **Fail**, **Blocked**, or **N/A with a reason** in the problems table. Leave untested steps empty. If a failure blocks a journey, continue only with independent checks. Use disposable records for rejection, cancellation and deletion tests.

### How to test missing values and errors

For every form, first test a valid submission. Then use a separate disposable record for errors:

1. Submit the form completely empty.
2. Fill it in, then clear **one required field at a time** and submit again.
3. Try spaces only, an invalid value, a duplicate value and a value outside the allowed limit where relevant.
4. Leave **optional fields** empty separately — optional values should not be required without explanation.
5. Check the error tells you what to correct, keeps your other valid entries and does not show false success.
6. Correct the input, submit once and refresh to confirm one valid record was saved.

A disabled button that clearly explains the missing input is also a valid way to prevent submission. If a control or test path is unavailable, write **Blocked — reason** instead of ticking it. Use visible website controls; do not bypass validation with developer tools. Only tick an error test when the error is handled correctly. If invalid data is accepted, leave it unticked and record a failure.

Use test accounts/files only. Do not share passwords or payment PINs. Avoid repeated login/payment attempts once a rate limit or unresolved payment is shown; record it and let us investigate.

## 1. Admin login and settings

### Main flow

- [x] **S01-01** — Log in as admin and open the dashboard.
- [x] **S01-02** — Refresh and confirm you are still logged in as the correct admin.
- [x] **S01-03** — Open the main admin menu pages; check that none shows an error.
- are there only 20 categories in our database?  seperate the kpi active an inacitve categories and subcategories. why dont we have subcategories?
- are there only 20 helath concerns in our database  - http://localhost:3000/admin/health-concerns seperate the kpi active an inacitve, actually place the numbers in cm-toolbar
- are there only 20 brands in our database  - http://localhost:3000/admin/brands seperate the kpi active an inacitve, actually place the numbers in cm-toolbar, remove with logo kpi
- this page is taking so looong to load http://localhost:3000/admin/products, can we use celeery cache or somethignt to fasten the caching staretgy and when a new prodcut is created it should be picked. Failed to load resource: the server responded with a status of 404 (Not Found)
- also use celery cache for http://localhost:3000/admin/inventory, when a new inventory is created or deleted, also update the cache. why am i seeing Matching Variants 23411 but 2342 on the table .. the kpis should show for all the data and not only data on that page
- http://localhost:3000/admin/deals is not loading anything
- http://localhost:3000/admin/users?role=pharmacist only show kpis matching phrmacists
- http://localhost:3000/admin/doctors?type=Doctor, http://localhost:3000/admin/users?role=pharmacist, http://localhost:3000/admin/doctors?type=Pediatrician, http://localhost:3000/admin/prescriptions, make these pages have a consistence design please
- http://localhost:3000/admin/users?role=customer the kpis should only display info tied to customers
- http://localhost:3000/admin/dashboard and http://localhost:3000/admin/reports should be combined to one thing
- improve on the css and alignemnt in  http://localhost:3000/admin/compliance and http://localhost:3000/admin/settings


- [x] **S01-04** — Check that empty lists show a useful message when there are no records.
- [x] **S01-05** — Set the pharmacy name, contact details, address and opening hours.
- [x] **S01-06** — Set delivery areas, delivery fees and pickup options through the available settings.
- [x] **S01-07** — Open the public website and confirm the saved information appears correctly.

### Missing values and errors

- [x] **S01-08** — Try logging in with both fields empty, then leave only email empty, then only password empty — the missing field should be identified.
- [x] **S01-09** — Try an invalid email such as `admin@`, then a wrong password — login should fail with a clear message.
- [x] **S01-10** — Try opening an admin page while logged out and while logged in as a customer — access should be denied.
- [x] **S01-11** — Clear each required settings field separately, including the support email/phone where required — saving should fail without erasing the previous valid settings.
- [x] **S01-12** — Enter an invalid support email and a phone containing letters or too few digits — the form should explain the problem.
- [x] **S01-13** — Try a negative or non-numeric delivery fee, an invalid policy link and an incomplete delivery option — reject invalid values with a useful message.
- [x] **S01-14** — Where opening/closing times or dates are validated, try an invalid combination — explain the restriction rather than silently changing it.
- [x] **S01-15** — Correct the failed fields and save again — the error should clear and the valid settings should persist.

## 2. Staff accounts

### Main flow

- [x] **S02-01** — Create or invite the pharmacist and inventory staff through the available admin controls.
- [x] **S02-02** — Have each person log in and confirm they reach the correct dashboard.
- [x] **S02-03** — Confirm each staff member can only use the functions allowed for their role.
- [x] **S02-04** — Suspend a disposable staff account and confirm it loses access; reactivate it and check again.

Doctors, pediatricians and lab partners will apply and be approved in their own sections below.

### Missing values and errors

- [x] **S02-05** — Submit the staff form empty, then leave each required name, email, role or other marked field empty separately — show the relevant error.
- [x] **S02-06** — Try an invalid email, an invalid phone and an email already belonging to another account — do not create a duplicate or corrupt the existing account.
- [x] **S02-07** — If an invitation/password setup is used, try missing confirmation and mismatched passwords — activation should not complete.
- [x] **S02-08** — Cancel account creation/editing before saving — no account or change should be created.
- [x] **S02-09** — Submit a valid staff form twice quickly — one account/invitation record should result, with any repeat handled clearly.
- [x] **S02-10** — Try a copied private staff/admin link as an unauthorized role — do not expose records or allow role promotion.
- [x] **S02-11** — Refresh an already open dashboard after that disposable account is suspended — protected actions should stop working.

## 3. Products and catalog

### Main flow

- [x] **S03-01** — As admin, create `MANUAL-20261105 Brand`; save and refresh. It should appear once in the brand list and product brand selector.
- [x] **S03-02** — Edit the test brand details, save and reopen it; confirm the changes persist.
- [x] **S03-03** — Create a category and subcategory; refresh and confirm the subcategory belongs to the correct parent.
- [x] **S03-04** — Create a product linked to your test brand/category/subcategory, with its name, description, image and pricing fields; save and reopen it to confirm every relationship and value.
- [x] **S03-05** — Add two clearly different variants, such as different strengths or pack sizes.
- [x] **S03-06** — Confirm each variant has its own SKU, price, pack details and image where needed.
- [x] **S03-07** — Add a prescription-only item, an out-of-stock item and a low-stock item for later tests.
- [x] **S03-08** — Search for these products on the public website and try the category/brand filters.
- [x] **S03-09** — Open a product, switch variants and confirm the displayed price, pack and availability match your selection.

### Missing values and errors

- [x] **S03-10** — Try saving an empty brand, category, subcategory, product and variant form separately — each required field should be identified.
- [x] **S03-11** — Enter spaces only in required names or SKU fields — whitespace should not count as a valid required value.
- [x] **S03-12** — Try an existing brand/category name or SKU again, including leading/trailing spaces or changed letter case — handle duplicates according to the uniqueness rule without ambiguous duplicate records.
- [x] **S03-13** — Leave optional fields empty, such as an optional brand/image/description — accept them if optional; show an honest placeholder where needed.
- [x] **S03-14** — Try saving a product/variant without the required category, parent or exact SKU — reject incomplete relationships rather than saving a broken item.
- [x] **S03-15** — Try a negative price, letters in a price field and more decimal places than allowed — reject invalid amounts. Check that zero follows the stated free-item policy.
- [x] **S03-16** — Try an unsupported image file, a damaged image and a file above the displayed limit — show an upload error and keep the previous image.
- [x] **S03-17** — Type a very long name/description and ordinary punctuation — enforce displayed limits without breaking the page or silently cutting essential information.
- [x] **S03-18** — Switch variants after an invalid edit and after a successful edit — values must remain attached to the correct variant.
- [x] **S03-19** — Deactivate a disposable product/variant and try an old cart/detail link — it must not be sold as an active item.
- [x] **S03-20** — Search for a product that does not exist, and combine filters with no matches — show a useful empty state and let you clear the filters.

## 4. Stores and inventory

### Main flow

- [x] **S04-01** — Create the test stores/locations using the available controls; record a missing setup screen if necessary.
- [x] **S04-02** — Add stock for each exact variant and store: variant A = 50 packs in store 1 and 30 in store 2; variant B = 10 and 20 respectively. If you choose other quantities, record them before purchasing.
- [x] **S04-03** — Adjust one stock quantity with a reason and check its movement history.
- [x] **S04-04** — Confirm changing one variant/store does not change the others.
- [ ] **S04-05** — Check the low-stock indicator and confirm an unavailable item cannot be bought as in stock.

### Missing values and errors

- [x] **S04-06** — Try creating a store/location without its required name/details — do not create an incomplete store.
- [x] **S04-07** — Try saving stock without selecting the variant or required store/location — reject it instead of updating a different row.
- [x] **S04-08** — Try negative, non-numeric and fractional quantities where whole packs are required — prevent invalid balances.
- [x] **S04-09** — Try a negative or non-numeric low-stock threshold — show a useful validation message.
- [x] **S04-10** — Try an adjustment without the required reason — ask for the reason and do not silently change stock.
- [ ] **S04-11** — Submit the same adjustment twice quickly and inspect movement history — no unintended duplicate change.
- [ ] **S04-12** — Edit a stock row, cancel without saving and refresh — the original balance should remain.
- [ ] **S04-13** — Try changing stock as a customer or a staff member without inventory permission — deny the change.
- [ ] **S04-14** — With two customer sessions, try buying the last unit of one test variant — no negative stock; ask for technical concurrency testing if simultaneous clicks cannot be verified.

## 5. Offers and public content

### Main flow

- [x] **S05-01** — Add a banner and FAQ, then confirm they appear correctly on the public website.
- [x] **S05-02** — Create a test offer and coupon; confirm the displayed terms and dates are correct.
- [x] **S05-03** — Edit or hide the test content and check the public page updates.

### Missing values and errors

- [x] **S05-04** — Try saving a banner, FAQ, offer or coupon with the required title, question, answer or code missing — show the missing fields.
- [x] **S05-05** — Try an invalid destination link and an unsupported/oversized banner image — reject invalid input without losing saved content.
- [x] **S05-06** — Try an end date before the start date and missing required dates — explain the error.
- [x] **S05-07** — Try an existing coupon code again, a negative discount and a percentage above 100 — reject invalid/duplicate values.
- [x] **S05-08** — Try a coupon below its minimum spend, outside its dates or on an excluded item — do not reduce the total incorrectly.
- [x] **S05-09** — Test an expired, future and inactive offer — public visibility and eligibility should follow its saved settings.
- [x] **S05-10** — Cancel an unsaved edit and refresh; then unpublish a disposable item — cancelled changes should be discarded and unpublished content should disappear.

## 6. Customer account

### Main flow

- [x] **S06-01** — Register a new customer, verify their email and log in.
- [x] **S06-02** — Try an already registered email and an incorrect password; check the error messages.
- [x] **S06-03** — Edit the customer profile and confirm the changes stay saved.
- [x] **S06-04** — Add, edit and remove an address; choose a default address.
- [x] **S06-05** — Check saved M-Pesa details if offered; confirm invalid details are rejected.
- [ ] **S06-06** — Add and remove a favourite, then check that it stays saved after refresh.
- [ ] **S06-07** — Change the password; confirm the old one fails and the new one works.
- [ ] **S06-08** — Request a password reset; confirm the new password works and the used reset link cannot be reused.
- [ ] **S06-09** — Log out and confirm private account pages require login again.

### Missing values and errors

- [x] **S06-10** — Submit registration empty; then leave each marked required field empty one at a time — identify the correct missing field.
- [x] **S06-11** — Try an invalid email, a phone containing letters, an incomplete phone and a future birth date where collected — reject invalid details.
- [x] **S06-12** — Try a weak password, missing password confirmation and mismatched passwords — explain the restriction without creating an account.
- [x] **S06-13** — Try registering an existing email with spaces or changed case — do not create an unintended second account.
- [x] **S06-14** — Try signing in before required email verification, and reuse a verification link — enforce the configured verification policy safely.
- [x] **S06-15** — Try editing your profile to an email/phone already assigned to someone else — reject a conflicting value where uniqueness is required.
- [x] **S06-16** — Try saving an address without required street, county or area; enter only spaces — prevent an incomplete saved address.
- [x] **S06-17** — On the password-change form, try an incorrect current password, blank new password and mismatched confirmation — do not change the password.
- [x] **S06-18** — Try a used or expired reset link — reject it and explain how to request a new one.
- [x] **S06-19** — Request a reset for an unknown test email — use a safe response that does not reveal private account details.
- [ ] **S06-20** — Open a favourite/address/payment record from a second unrelated account — do not show or change the first customer data.
- [ ] **S06-21** — Cancel a disposable account-deactivation confirmation, then confirm it separately — cancellation keeps access; confirmed deactivation removes it.

## 7. Cart, checkout and payment

Use agreed test items and a sandbox phone. For a KSh 1 test, the final displayed total must actually be KSh 1.

### Main flow

- [x] **S07-01** — Add the exact variant you selected and confirm the cart shows the correct pack and price.
- [x] **S07-02** — Add another item, change quantities, remove a line and check the totals.
- [] **S07-03** — Apply and remove a valid coupon; try an expired or ineligible coupon.
- [x] **S07-04** — Choose a delivery address and switch between delivery and pickup; check the fees and final total.
- [x] **S07-05** — Refresh checkout and confirm the address, delivery option and total are still correct.
- [x] **S07-06** — Leave Save address unchecked and confirm a new checkout address is not saved automatically.
- [x] **S07-07** — Send one M-Pesa prompt, approve it yourself and record the receipt and order reference.
- [x] **S07-08** — Confirm the website shows payment confirmed before allowing final checkout completion.
- [x] **S07-09** — Open customer order history and confirm the items, amount, receipt and payment status are correct.
- [x] **S07-10** — On a separate test order, decline a prompt; confirm it stays unpaid, then retry after failure and pay successfully.
- [x] **S07-11** — Refresh/reopen the successful order and confirm there is only one successful payment and one stock deduction.
- [x] **S07-12** — Try buying above available stock; confirm checkout blocks it or follows the stated backorder rule.

### Missing values and errors

- [ ] **S07-13** — Open checkout with an empty cart — do not create or pay an empty order.
- [ ] **S07-14** — Try zero, negative, fractional and excessive cart quantities through the visible controls — enforce the allowed quantity rules.
- [ ] **S07-15** — Leave each required checkout field blank separately: customer details, phone, street, county, area and any required delivery selection — identify the field before continuing.
- [ ] **S07-16** — Use an invalid email and a phone containing letters/too few digits — do not send a payment request to invalid input.
- [ ] **S07-17** — Enter an unknown coupon or apply the same coupon twice — show a useful error and avoid duplicate discounts.
- [ ] **S07-18** — Change the product price or availability with staff help after adding it to the cart — checkout should show the updated valid total or block the purchase.
- [ ] **S07-19** — Try completing checkout before payment is confirmed — the final action must remain blocked.
- [ ] **S07-20** — Decline a prompt, let one time out, or report no prompt received — show an honest failure/pending state and preserve the order reference.
- [ ] **S07-21** — If a payment is still pending, check its status before sending another prompt — do not create overlapping requests or count provider acceptance as success.
- [ ] **S07-22** — Cancel a pending attempt using the supported action, then check both website and phone — local cancellation must not claim to refund or reverse provider-side money.
- [ ] **S07-23** — After success, double-click an available final button or reopen the confirmation page — one order and one stock deduction should remain.
- [ ] **S07-24** — If the network fails while paying, reconnect and check the existing order/receipt before retrying — do not charge again because the page was slow.
- [ ] **S07-25** — For Paybill, test the correct reference/amount and staff-assisted wrong amount/unmatched reference in the approved sandbox — mismatches must not mark an order paid.
- [ ] **S07-26** — Check that card and cash-on-delivery are not offered as usable new payment methods under current scope.

## 8. Processing, delivery, cancellation and returns

Use synthetic fulfillment for test orders; do not ship real medicine for these tests.

### Main flow

- [x] **S08-01** — As staff, find the paid order and confirm the customer, items, address and amount match.
- [x] **S08-02** — Move it through Processing → Shipped → Delivered.
- [x] **S08-03** — As customer, check tracking and notifications after each change.
- [ ] **S08-04** — Buy two packs of variant A from store 1: at the configured deduction stage, confirm 50 → 48 once, store 2 remains 30 and variant B remains 10/20. Adapt the arithmetic to your recorded baseline. Check reserved and available stock separately.
- [x] **S08-05** — Check the customer receipt and admin invoice/report for the same order and amount.
- [ ] **S08-06** — Submit a product review where allowed; confirm it appears on the correct product.
- [ ] **S08-07** — Cancel a separate eligible order; check its status and any stock release happen only once.
- [ ] **S08-08** — Request a return on a delivered test order and confirm a return reference is actually saved.
- [ ] **S08-09** — As staff, review the return and record quarantine/non-resale handling; confirm returned medicine is not added to saleable stock.
- [ ] **S08-10** — If an actual external refund is completed, record its real reference and compare customer and finance records.
- [ ] **S08-11** — Open a support ticket for a return/refund problem and close it only after the actual issue is settled.

### Missing values and errors

- [ ] **S08-12** — Try moving an unpaid order into fulfillment — it should be blocked.
- [ ] **S08-13** — Try a status change that is not allowed, such as reopening a delivered/cancelled order — reject it with an explanation.
- [ ] **S08-14** — As a customer, try to change staff-only order/payment status — deny the action.
- [ ] **S08-15** — Try tracking with a blank reference, an unknown reference and incorrect verification details — do not expose another customer information.
- [ ] **S08-16** — Try cancelling an already dispatched/delivered or otherwise ineligible order — explain the policy and direct the customer to support/returns.
- [ ] **S08-17** — Submit a return with no order reference, no required reason, an unknown order or another customer order — do not create an invalid return.
- [ ] **S08-18** — Where a refund amount can be entered, try negative, non-numeric and above-paid amounts — reject them.
- [ ] **S08-19** — Submit a return twice and refresh the public form — verify saved references; a page refresh alone is not a successful submission.
- [ ] **S08-20** — Try receiving/closing a returned medicine without quarantine and non-resale acknowledgement — block the transition.
- [ ] **S08-21** — Try marking the return refunded before an external refund is recorded — block premature closure.
- [ ] **S08-22** — Repeat a permitted refund-recording action and inspect stock/history — no duplicate refund event and no saleable restock of dispatched medicine.
- [ ] **S08-23** — Try a blank/out-of-range review and an edit to another customer review — reject invalid or unauthorized changes.
- [ ] **S08-24** — Download an order/finance report for an empty range and for a range including the order creation date — show the appropriate empty result or matching order without errors.

## 9. Uploaded prescriptions

Use a synthetic prescription file.

### Main flow

- [x] **S09-01** — As customer, upload a valid PDF/JPG/PNG and confirm it appears in prescription history.
- [x] **S09-02** — Try an unsupported file, a file over 5 MB and more than five files; check the errors.
- [x] **S09-03** — As pharmacist, open the same prescription and review its files and patient details.
- [x] **S09-04** — Request clarification; reply as the customer and confirm the pharmacist sees the reply.
- [x] **S09-05** — Reject a separate prescription with a reason; confirm the customer sees it and cannot buy from it.
- [x] **S09-06** — Approve the main prescription with exact medicine variants and allowed quantities.
- [x] **S09-07** — As customer, add the approved items, pay and complete the medicine order.
- [x] **S09-08** — Confirm extra quantities, another variant and unauthorized reuse of the prescription are blocked.
- [x] **S09-09** — Complete dispensing/delivery and check the prescription and order statuses agree.

### Missing values and errors

- [ ] **S09-10** — Submit without a file and without any other marked required details — no incomplete prescription should be created.
- [ ] **S09-11** — Try a text file or other unsupported type, a damaged PDF/image, a file over 5 MB and a sixth file — reject invalid uploads clearly. Current permitted types are PDF/JPG/PNG, up to five files.
- [ ] **S09-12** — Add the same file twice and remove a selected file before upload — selection should behave clearly without unintended duplicates.
- [ ] **S09-13** — Try reviewing without permission or opening another customer prescription/file — deny access.
- [ ] **S09-14** — Request clarification or reject without a required message/reason — ask for a useful explanation before saving.
- [ ] **S09-15** — Try approving with no medicine items, an inactive/wrong variant or a quantity of zero/negative — do not issue an invalid approval.
- [ ] **S09-16** — Try a controlled medicine that is not permitted for online supply — block it consistently.
- [ ] **S09-17** — Try checking out a pending/rejected prescription or a stale approval link — do not allow purchase.
- [ ] **S09-18** — Try more than the approved quantity, a different pack/strength and reuse after the allowance is consumed — enforce the prescription limits.
- [ ] **S09-19** — Try skipping dispensing stages or editing already ordered items — protect the saved approval/order association.
- [ ] **S09-20** — After a failed upload/review, correct it and retry — create one correct record and retain relevant clarification/audit history.

## 10. Doctor consultation

### Main flow

- [x] **S10-01** — Submit a synthetic doctor application with the required documents and details.
- [x] **S10-02** — As admin, review, approve and activate the doctor account.
- [x] **S10-03** — As doctor, log in and check the profile, availability and consultation fee.
- [x] **S10-04** — As customer, select the doctor, enter a synthetic complaint, pay and finalize one booking.
- [x] **S10-05** — Confirm the same consultation appears for the customer and doctor, with the correct fee and payment.
- [x] **S10-06** — Exchange messages and a synthetic attachment; refresh and confirm the conversation stays saved.
- [x] **S10-07** — As doctor, draft and send an exact-item prescription; open its PDF and check all details are readable.
- [x] **S10-08** — Follow it through pharmacist approval and a separate medicine checkout/payment.
- [x] **S10-09** — Complete the consultation and confirm one correct earning appears for the doctor.

### Missing values and errors

- [ ] **S10-10** — Submit the professional application empty or missing a required identity, license, contact, document, availability or declaration field — show exactly what is missing.
- [ ] **S10-11** — Try invalid/duplicate email or phone, invalid dates and unsupported/oversized required documents — reject invalid data; do not claim an unperformed external license check.
- [ ] **S10-12** — Leave required consent/terms/declaration unchecked — do not silently grant agreement.
- [ ] **S10-13** — Try logging in or accepting bookings before approval/activation, then as a suspended clinician — enforce eligibility.
- [ ] **S10-14** — Try a used/expired activation link and mismatched activation passwords — fail safely with recovery guidance.
- [ ] **S10-15** — Try booking with a missing complaint or other required patient/clinician selection — show the appropriate error.
- [ ] **S10-16** — Try an inactive clinician or one without a valid positive consultation fee — do not charge an unexplained fee or finalize an invalid booking.
- [ ] **S10-17** — Try finalizing with an unpaid/failed payment and reusing a paid reference for another booking — deny both.
- [ ] **S10-18** — Send a blank chat message, an unsupported attachment and one over 10 MB — reject invalid messages/files without losing the conversation.
- [ ] **S10-19** — Try opening the consultation/files as an unrelated customer or clinician — deny access.
- [ ] **S10-20** — Try sending an empty prescription or one missing required exact items, quantities or instructions — show relevant validation.
- [ ] **S10-21** — Repeat booking finalization and consultation completion — one consultation and one earning should remain.
- [ ] **S10-22** — If the open-doctor queue is offered, have two eligible doctors try to claim the same consultation — only one assignment should persist.

## 11. Paediatric clinic: guardian, child and paediatrician

### Main flow

- [ ] **S11-01** — Apply, approve and activate a pediatrician, then check their profile and fee.
- [ ] **S11-02** — As guardian, create two child profiles with different details.
- [ ] **S11-03** — Select one child and confirm the correct child appears before booking.
- [ ] **S11-04** — Enter the required details, give guardian consent, pay and finalize the booking.
- [ ] **S11-05** — As pediatrician, confirm the selected child, guardian, consent and measurements are correct.
- [ ] **S11-06** — Check that missing consent or invalid child details are handled properly.
- [ ] **S11-07** — Exchange messages and follow the prescription through pharmacist approval and medicine payment.
- [ ] **S11-08** — Complete the consultation and confirm one correct earning.
- [ ] **S11-09** — Book/view another consultation for the same child; confirm their history stays separate from the sibling's.

### Missing values and errors

- [ ] **S11-10** — Submit a child profile without each marked required field separately — no incomplete child should be silently saved.
- [ ] **S11-11** — Try a future birth date, invalid age and zero/negative supplied measurements — reject invalid values; leave optional measurements blank separately and confirm none are invented.
- [ ] **S11-12** — Create children with the same name but different details — keep them separate by child identity, not name alone.
- [ ] **S11-13** — Try starting the booking without a selected child, required complaint or pediatrician where required — show useful validation.
- [ ] **S11-14** — Leave guardian consent unchecked — enforce the required consent restriction; do not silently grant it after payment.
- [ ] **S11-15** — If a pending-consent consultation can exist, try issuing its prescription — it must remain blocked until consent is granted.
- [ ] **S11-16** — Try another guardian child/profile link and an unrelated pediatrician consultation link — deny access.
- [ ] **S11-17** — After changing child selection, review the summary and clinician view — no sibling measurements, consent or history should be substituted.
- [ ] **S11-18** — Try a failed payment, repeated finalization and repeated completion — do not create duplicate bookings or earnings.
- [ ] **S11-19** — Repeat the doctor chat/file/prescription error checks for the pediatric flow — the same protections should hold.

## 12. Lab services

### Main flow

- [ ] **S12-01** — Submit a synthetic lab-partner application; review, approve and activate it as admin.
- [ ] **S12-02** — Add and approve a facility, then add its tests, prices and technician assignments.
- [ ] **S12-03** — Confirm only approved facilities/tests are available to customers.
- [ ] **S12-04** — As customer, book a walk-in test and check the request, facility, saved price and payment arrangement.
- [ ] **S12-05** — Book a home-collection test and check the address, appointment details and assignment.
- [ ] **S12-06** — As technician, try one incorrect collection code, then verify the correct one; confirm it cannot be reused.
- [ ] **S12-07** — Move the request through sample collection and processing; upload the synthetic result and complete it.
- [ ] **S12-08** — As customer, open the notification and download the correct result.
- [ ] **S12-09** — Cancel a separate eligible request and check that its history and payment handling are clear.

### Missing values and errors

- [ ] **S12-10** — Submit partner/facility forms with required details or documents missing — show the missing fields and keep the application unapproved.
- [ ] **S12-11** — Try invalid/duplicate email or phone and missing required declarations — do not create conflicting or silently consented applications.
- [ ] **S12-12** — Try creating a test/offer without a required name, permitted price or required facility details — reject invalid values.
- [ ] **S12-13** — Try assigning a suspended technician or one from another partner/facility — deny the assignment.
- [ ] **S12-14** — Try booking without a required facility/test/patient field or home address/appointment detail — identify each missing value.
- [ ] **S12-15** — Try a pending/suspended facility or a test not offered by the selected facility — do not accept the booking.
- [ ] **S12-16** — Where appointment rules are enforced, try an invalid or unavailable time — show the relevant restriction.
- [ ] **S12-17** — Try blank, wrong, expired, already used and other-request collection codes — reject them; stop if the attempt limit is reached.
- [ ] **S12-18** — Try skipping collection/processing steps or completing without a required result — block invalid transitions.
- [ ] **S12-19** — Try no result file, an unsupported/damaged file and a file above the displayed limit — preserve the request and explain the failure.
- [ ] **S12-20** — Try result upload/download as an unrelated patient, partner or technician — deny access.
- [ ] **S12-21** — Try cancelling after collection or outside the permitted payment/status policy — reject with guidance.
- [ ] **S12-22** — Change the test catalog price after booking and reopen the request — keep its saved quote rather than rewriting history.
- [ ] **S12-23** — Repeat booking/result publication through offered controls — do not duplicate requests or result notifications.

## 13. Earnings and payouts

The current payout feature records administrative payments; it does not send money.

### Main flow

- [ ] **S13-01** — Compare the completed consultation's paid fee, commission and clinician earning.
- [ ] **S13-02** — Create one payout linked to that clinician and source; check the net amount.
- [ ] **S13-03** — Submit it and have a different admin approve it; confirm the creator cannot approve their own payout.
- [ ] **S13-04** — Use a clearly labelled synthetic reference for the ledger test, then record and reconcile the payout.
- [ ] **S13-05** — Confirm the clinician sees the correct amount/status and duplicate sources or payment references are blocked.
- [ ] **S13-06** — Test hold, failure/retry and cancellation on separate disposable payout records; check the history and amounts.

### Missing values and errors

- [ ] **S13-07** — Submit a payout without the required recipient, source reference, gross amount or method — show the missing fields.
- [ ] **S13-08** — Try a zero/negative gross amount, negative deductions, non-numeric amounts and deductions exceeding gross — reject invalid calculations.
- [ ] **S13-09** — Select the wrong professional role, an inactive recipient or another clinician consultation — reject an unrelated payout source.
- [ ] **S13-10** — Try a consultation that is unpaid, unfinished or has no earning — it should not qualify for a consultation-source payout.
- [ ] **S13-11** — Try creating the same source payout twice and reusing an existing payment reference, including spaces/case variations — avoid duplicate obligations/references.
- [ ] **S13-12** — Try approving your own payout, processing before approval and paying a cancelled/held payout — enforce the allowed workflow.
- [ ] **S13-13** — Try marking paid without the required payment reference, using an invalid/future payment time and retrying a completed action — reject invalid records.
- [ ] **S13-14** — Release a held payout and try processing without renewed approval — require approval again.
- [ ] **S13-15** — Try payout admin actions and another professional financial records as a customer/unrelated professional — deny access.
- [ ] **S13-16** — Check the screen and notification wording after recording payment — it must not imply that this ledger test sent actual money.

## 14. Notifications, support and settings

### Main flow

- [ ] **S14-01** — Check prescription, consultation, order and lab notifications reach the intended account and open the correct record.
- [ ] **S14-02** — Mark one notification read, then mark all read; refresh and check the unread count.
- [ ] **S14-03** — Change an optional notification preference and confirm it stays saved and affects delivery as expected.
- [ ] **S14-04** — Check a failed delivery/retry with staff help; confirm it does not duplicate the business action.
- [ ] **S14-05** — Create a support ticket; reply as staff, change its status and check the customer-visible history.
- [ ] **S14-06** — Add an internal staff note and confirm the customer cannot see it.
- [ ] **S14-07** — Submit the contact form and confirm it creates a saved inquiry; test newsletter signup with valid, invalid and duplicate emails.
- [ ] **S14-08** — Upload synthetic compliance evidence as admin; confirm permitted read-only staff can view but cannot edit it.

### Missing values and errors

- [ ] **S14-09** — Open notifications/support with no records, then search for a reference that does not exist — show a useful empty state.
- [ ] **S14-10** — Try reading, changing or retrying another user notification/delivery — deny access.
- [ ] **S14-11** — Retry a successful delivery, a disabled-channel delivery and a failed one above its retry cap — block invalid retries without duplicating the business event.
- [ ] **S14-12** — Submit a support ticket with an empty required subject/channel/other marked field or an invalid priority — explain the missing/invalid value.
- [ ] **S14-13** — Post an empty reply and try assigning an ineligible staff member — reject invalid changes.
- [ ] **S14-14** — Try opening another customer ticket and viewing an internal staff note as a customer — private data must stay hidden.
- [ ] **S14-15** — Submit Contact without its required fields and newsletter signup with an empty or invalid email — show useful errors, not false success.
- [ ] **S14-16** — Submit the same valid newsletter email twice and handle a staff-assisted delivery failure — retain one consistent subscription state.
- [ ] **S14-17** — Upload compliance evidence with required metadata/file missing, invalid dates or a disallowed file — reject invalid input.
- [ ] **S14-18** — Try editing compliance evidence as a read-only inspector and downloading it as a customer/visitor — enforce the allowed role scope.
- [ ] **S14-19** — After a failed save or send, correct the input and retry — preserve prior valid data and create one intended ticket/message/record.

## 15. Privacy, mobile and final check

### Main flow

- [ ] **S15-01** — Use a second unrelated customer account and confirm it cannot see or change the first customer's orders, prescriptions, consultations, children, lab results or support tickets.
- [ ] **S15-02** — Confirm signed-out users and unrelated staff cannot download private files or use restricted dashboards.
- [ ] **S15-03** — On a disposable customer account, test deactivation and confirm that account loses access.
- [ ] **S15-04** — Repeat the main customer journeys on a phone; check menus, forms, uploads, chat and payment screens.
- [ ] **S15-05** — Check that invalid forms show useful errors, buttons work and pages recover after refresh or a connection interruption.
- [ ] **S15-06** — Compare each completed journey across customer and staff views using the same references.
- [ ] **S15-07** — Record anything failed or blocked, retest fixes and restore temporary settings/test changes.

### Missing values and errors

- [ ] **S15-08** — On a phone, submit the main forms with missing fields — errors and the corrective fields must remain visible with the keyboard open.
- [ ] **S15-09** — Zoom in and use keyboard navigation — labels, focus and errors should remain readable and usable without relying only on colour.
- [ ] **S15-10** — Disconnect/reconnect during a harmless save/read test — show a useful error or recovery state rather than an endless spinner or false saved message.
- [ ] **S15-11** — Let a session expire or log out in another tab before submitting a disposable form — request login again without saving under another account.
- [ ] **S15-12** — Use Back, Forward, refresh, direct links and an unknown URL — recover predictably without private-data leaks or duplicate actions.
- [ ] **S15-13** — Try a long name, long description, long chat and an empty list — content should not clip, crash or hide the needed controls.
- [ ] **S15-14** — For every rejected submission, check the list/history afterward — no partial record, charge, stock change or success notification should have been created.
- [ ] **S15-15** — Correct each failed input and repeat the valid flow — errors should clear and the intended action should succeed once.

## Things to leave pending when unavailable

- Paybill: leave pending until a real provider confirmation reaches the correct order.
- POS: real POS testing remains on hold until we agree to resume it.
- Returns: verify the form saves a request with a reference. A refresh without a saved reference must not be counted as success.
- Refunds: a recorded refund status alone does not return money; keep the issue open without external refund proof.
- Lab payments: currently pay-later. Payouts: currently an administrative ledger. Card and cash on delivery: excluded.
- Email/SMS: check the actual test inbox/phone before marking external delivery passed.

## Problems found

Write the section and checkbox, the value you tried, the message you expected, what actually happened and any saved reference. Add a screenshot where useful. Keep the original failure and its later retest result.

| Section / item | Value tried / expected error / actual result | Reference or screenshot | Fixed and retested? |
|---|---|---|---|
| | | | |
| | | | |
| | | | |

## Connected journey record

Record the same references in customer and staff views. Consultation fees and medicine orders require separate payment checks.

| Journey | References to record | Result / evidence |
|---|---|---|
| Brand → product → variant → stock → customer → checkout → delivery | Brand, product, SKU, store, order, provider receipt, stock movement | |
| Uploaded prescription → clarification → pharmacist → medicine payment → dispensing | Prescription, order, provider receipt, dispatch | |
| Doctor approval → booking/payment → chat → prescription → pharmacist → medicine order → completion → payout | Doctor, consultation, consultation receipt, prescription, medicine order/receipt, earning, payout | |
| Guardian → selected child → consent → paediatric consultation → prescription → medicine delivery → child history | Guardian, child ID, consultation, both receipts, prescription, order, earning | |
| Lab partner → facility/test → booking → collection → processing → result download | Partner, facility, request, result | |
| Payment failure → safe retry → return/refund → support resolution | Order, payment attempts, receipt, return, external refund evidence, ticket | |

## Finish the run

- [ ] **S16-01** — Every step has a verified pass or a recorded Fail / Blocked / N/A outcome; no untested step is counted as passed.
- [ ] **S16-02** — Every connected journey has matching customer/staff references and evidence.
- [ ] **S16-03** — Failed checks retain their original issue and a separate retest result.
- [ ] **S16-04** — Unconfirmed payments, refunds, external messages and integrations remain explicitly pending.
- [ ] **S16-05** — Restore temporary public settings and deactivate disposable records where appropriate; retain payment and audit evidence.
- [ ] **S16-06** — Record your overall result and reviewer below.

| Sign-off | Entry |
|---|---|
| Overall: Pass / Fail / Blocked / Partial | |
| Open issues / limitations | |
| Tester / date | |
| Reviewer / date | |

Start with Section 1, then create the brand and catalog in Section 3 before testing customer purchases.
