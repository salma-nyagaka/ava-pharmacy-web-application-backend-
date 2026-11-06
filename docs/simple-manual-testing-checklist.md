# AvaPharmacy — step-by-step testing checklist

Start from the admin side, as if the website is new and only the first admin account exists. We will work through one section at a time. Existing records do not need to be deleted.

Tick a box only after it works. After saving anything, refresh to check it stayed saved. If something fails, write the problem beside it and we will fix it before continuing with that journey.


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

- [ ] Log in as admin and open the dashboard.
- [ ] Refresh and confirm you are still logged in as the correct admin.
- [ ] Open the main admin menu pages; check that none shows an error.
- [ ] Check that empty lists show a useful message when there are no records.
- [ ] Set the pharmacy name, contact details, address and opening hours.
- [ ] Set delivery areas, delivery fees and pickup options through the available settings.
- [ ] Open the public website and confirm the saved information appears correctly.

### Missing values and errors

- [ ] Try logging in with both fields empty, then leave only email empty, then only password empty — the missing field should be identified.
- [ ] Try an invalid email such as `admin@`, then a wrong password — login should fail with a clear message.
- [ ] Try opening an admin page while logged out and while logged in as a customer — access should be denied.
- [ ] Clear each required settings field separately, including the support email/phone where required — saving should fail without erasing the previous valid settings.
- [ ] Enter an invalid support email and a phone containing letters or too few digits — the form should explain the problem.
- [ ] Try a negative or non-numeric delivery fee, an invalid policy link and an incomplete delivery option — reject invalid values with a useful message.
- [ ] Where opening/closing times or dates are validated, try an invalid combination — explain the restriction rather than silently changing it.
- [ ] Correct the failed fields and save again — the error should clear and the valid settings should persist.

## 2. Staff accounts

### Main flow

- [ ] Create or invite the pharmacist and inventory staff through the available admin controls.
- [ ] Have each person log in and confirm they reach the correct dashboard.
- [ ] Confirm each staff member can only use the functions allowed for their role.
- [ ] Suspend a disposable staff account and confirm it loses access; reactivate it and check again.

Doctors, pediatricians and lab partners will apply and be approved in their own sections below.

### Missing values and errors

- [ ] Submit the staff form empty, then leave each required name, email, role or other marked field empty separately — show the relevant error.
- [ ] Try an invalid email, an invalid phone and an email already belonging to another account — do not create a duplicate or corrupt the existing account.
- [ ] If an invitation/password setup is used, try missing confirmation and mismatched passwords — activation should not complete.
- [ ] Cancel account creation/editing before saving — no account or change should be created.
- [ ] Submit a valid staff form twice quickly — one account/invitation record should result, with any repeat handled clearly.
- [ ] Try a copied private staff/admin link as an unauthorized role — do not expose records or allow role promotion.
- [ ] Refresh an already open dashboard after that disposable account is suspended — protected actions should stop working.

## 3. Products and catalog

### Main flow

- [ ] Create a brand.
- [ ] Create a category and subcategory.
- [ ] Create a product with its name, description, image and price.
- [ ] Add two clearly different variants, such as different strengths or pack sizes.
- [ ] Confirm each variant has its own SKU, price, pack details and image where needed.
- [ ] Add a prescription-only item, an out-of-stock item and a low-stock item for later tests.
- [ ] Search for these products on the public website and try the category/brand filters.
- [ ] Open a product, switch variants and confirm the displayed price, pack and availability match your selection.

### Missing values and errors

- [ ] Try saving an empty brand, category, subcategory, product and variant form separately — each required field should be identified.
- [ ] Enter spaces only in required names or SKU fields — whitespace should not count as a valid required value.
- [ ] Try an existing brand/category name or SKU again, including leading/trailing spaces or changed letter case — handle duplicates according to the uniqueness rule without ambiguous duplicate records.
- [ ] Leave optional fields empty, such as an optional brand/image/description — accept them if optional; show an honest placeholder where needed.
- [ ] Try saving a product/variant without the required category, parent or exact SKU — reject incomplete relationships rather than saving a broken item.
- [ ] Try a negative price, letters in a price field and more decimal places than allowed — reject invalid amounts. Check that zero follows the stated free-item policy.
- [ ] Try an unsupported image file, a damaged image and a file above the displayed limit — show an upload error and keep the previous image.
- [ ] Type a very long name/description and ordinary punctuation — enforce displayed limits without breaking the page or silently cutting essential information.
- [ ] Switch variants after an invalid edit and after a successful edit — values must remain attached to the correct variant.
- [ ] Deactivate a disposable product/variant and try an old cart/detail link — it must not be sold as an active item.
- [ ] Search for a product that does not exist, and combine filters with no matches — show a useful empty state and let you clear the filters.

## 4. Stores and inventory

### Main flow

- [ ] Create the test stores/locations using the available controls; record a missing setup screen if necessary.
- [ ] Add stock for each exact variant and store; write down the starting quantities.
- [ ] Adjust one stock quantity with a reason and check its movement history.
- [ ] Confirm changing one variant/store does not change the others.
- [ ] Check the low-stock indicator and confirm an unavailable item cannot be bought as in stock.

### Missing values and errors

- [ ] Try creating a store/location without its required name/details — do not create an incomplete store.
- [ ] Try saving stock without selecting the variant or required store/location — reject it instead of updating a different row.
- [ ] Try negative, non-numeric and fractional quantities where whole packs are required — prevent invalid balances.
- [ ] Try a negative or non-numeric low-stock threshold — show a useful validation message.
- [ ] Try an adjustment without the required reason — ask for the reason and do not silently change stock.
- [ ] Submit the same adjustment twice quickly and inspect movement history — no unintended duplicate change.
- [ ] Edit a stock row, cancel without saving and refresh — the original balance should remain.
- [ ] Try changing stock as a customer or a staff member without inventory permission — deny the change.
- [ ] With two customer sessions, try buying the last unit of one test variant — no negative stock; ask for technical concurrency testing if simultaneous clicks cannot be verified.

## 5. Offers and public content

### Main flow

- [ ] Add a banner and FAQ, then confirm they appear correctly on the public website.
- [ ] Create a test offer and coupon; confirm the displayed terms and dates are correct.
- [ ] Edit or hide the test content and check the public page updates.

### Missing values and errors

- [ ] Try saving a banner, FAQ, offer or coupon with the required title, question, answer or code missing — show the missing fields.
- [ ] Try an invalid destination link and an unsupported/oversized banner image — reject invalid input without losing saved content.
- [ ] Try an end date before the start date and missing required dates — explain the error.
- [ ] Try an existing coupon code again, a negative discount and a percentage above 100 — reject invalid/duplicate values.
- [ ] Try a coupon below its minimum spend, outside its dates or on an excluded item — do not reduce the total incorrectly.
- [ ] Test an expired, future and inactive offer — public visibility and eligibility should follow its saved settings.
- [ ] Cancel an unsaved edit and refresh; then unpublish a disposable item — cancelled changes should be discarded and unpublished content should disappear.

## 6. Customer account

### Main flow

- [ ] Register a new customer, verify their email and log in.
- [ ] Try an already registered email and an incorrect password; check the error messages.
- [ ] Edit the customer profile and confirm the changes stay saved.
- [ ] Add, edit and remove an address; choose a default address.
- [ ] Check saved M-Pesa details if offered; confirm invalid details are rejected.
- [ ] Add and remove a favourite, then check that it stays saved after refresh.
- [ ] Change the password; confirm the old one fails and the new one works.
- [ ] Request a password reset; confirm the new password works and the used reset link cannot be reused.
- [ ] Log out and confirm private account pages require login again.

### Missing values and errors

- [ ] Submit registration empty; then leave each marked required field empty one at a time — identify the correct missing field.
- [ ] Try an invalid email, a phone containing letters, an incomplete phone and a future birth date where collected — reject invalid details.
- [ ] Try a weak password, missing password confirmation and mismatched passwords — explain the restriction without creating an account.
- [ ] Try registering an existing email with spaces or changed case — do not create an unintended second account.
- [ ] Try signing in before required email verification, and reuse a verification link — enforce the configured verification policy safely.
- [ ] Try editing your profile to an email/phone already assigned to someone else — reject a conflicting value where uniqueness is required.
- [ ] Try saving an address without required street, county or area; enter only spaces — prevent an incomplete saved address.
- [ ] On the password-change form, try an incorrect current password, blank new password and mismatched confirmation — do not change the password.
- [ ] Try a used or expired reset link — reject it and explain how to request a new one.
- [ ] Request a reset for an unknown test email — use a safe response that does not reveal private account details.
- [ ] Open a favourite/address/payment record from a second unrelated account — do not show or change the first customer data.
- [ ] Cancel a disposable account-deactivation confirmation, then confirm it separately — cancellation keeps access; confirmed deactivation removes it.

## 7. Cart, checkout and payment

Use agreed test items and a sandbox phone. For a KSh 1 test, the final displayed total must actually be KSh 1.

### Main flow

- [ ] Add the exact variant you selected and confirm the cart shows the correct pack and price.
- [ ] Add another item, change quantities, remove a line and check the totals.
- [ ] Apply and remove a valid coupon; try an expired or ineligible coupon.
- [ ] Choose a delivery address and switch between delivery and pickup; check the fees and final total.
- [ ] Refresh checkout and confirm the address, delivery option and total are still correct.
- [ ] Leave Save address unchecked and confirm a new checkout address is not saved automatically.
- [ ] Send one M-Pesa prompt, approve it yourself and record the receipt and order reference.
- [ ] Confirm the website shows payment confirmed before allowing final checkout completion.
- [ ] Open customer order history and confirm the items, amount, receipt and payment status are correct.
- [ ] On a separate test order, decline a prompt; confirm it stays unpaid, then retry after failure and pay successfully.
- [ ] Refresh/reopen the successful order and confirm there is only one successful payment and one stock deduction.
- [ ] Try buying above available stock; confirm checkout blocks it or follows the stated backorder rule.

### Missing values and errors

- [ ] Open checkout with an empty cart — do not create or pay an empty order.
- [ ] Try zero, negative, fractional and excessive cart quantities through the visible controls — enforce the allowed quantity rules.
- [ ] Leave each required checkout field blank separately: customer details, phone, street, county, area and any required delivery selection — identify the field before continuing.
- [ ] Use an invalid email and a phone containing letters/too few digits — do not send a payment request to invalid input.
- [ ] Enter an unknown coupon or apply the same coupon twice — show a useful error and avoid duplicate discounts.
- [ ] Change the product price or availability with staff help after adding it to the cart — checkout should show the updated valid total or block the purchase.
- [ ] Try completing checkout before payment is confirmed — the final action must remain blocked.
- [ ] Decline a prompt, let one time out, or report no prompt received — show an honest failure/pending state and preserve the order reference.
- [ ] If a payment is still pending, check its status before sending another prompt — do not create overlapping requests or count provider acceptance as success.
- [ ] Cancel a pending attempt using the supported action, then check both website and phone — local cancellation must not claim to refund or reverse provider-side money.
- [ ] After success, double-click an available final button or reopen the confirmation page — one order and one stock deduction should remain.
- [ ] If the network fails while paying, reconnect and check the existing order/receipt before retrying — do not charge again because the page was slow.
- [ ] For Paybill, test the correct reference/amount and staff-assisted wrong amount/unmatched reference in the approved sandbox — mismatches must not mark an order paid.
- [ ] Check that card and cash-on-delivery are not offered as usable new payment methods under current scope.

## 8. Processing, delivery, cancellation and returns

Use synthetic fulfillment for test orders; do not ship real medicine for these tests.

### Main flow

- [ ] As staff, find the paid order and confirm the customer, items, address and amount match.
- [ ] Move it through Processing → Shipped → Delivered.
- [ ] As customer, check tracking and notifications after each change.
- [ ] Confirm the correct variant/store stock was deducted once and other stock stayed unchanged.
- [ ] Check the customer receipt and admin invoice/report for the same order and amount.
- [ ] Submit a product review where allowed; confirm it appears on the correct product.
- [ ] Cancel a separate eligible order; check its status and any stock release happen only once.
- [ ] Request a return on a delivered test order and confirm a return reference is actually saved.
- [ ] As staff, review the return and record quarantine/non-resale handling; confirm returned medicine is not added to saleable stock.
- [ ] If an actual external refund is completed, record its real reference and compare customer and finance records.
- [ ] Open a support ticket for a return/refund problem and close it only after the actual issue is settled.

### Missing values and errors

- [ ] Try moving an unpaid order into fulfillment — it should be blocked.
- [ ] Try a status change that is not allowed, such as reopening a delivered/cancelled order — reject it with an explanation.
- [ ] As a customer, try to change staff-only order/payment status — deny the action.
- [ ] Try tracking with a blank reference, an unknown reference and incorrect verification details — do not expose another customer information.
- [ ] Try cancelling an already dispatched/delivered or otherwise ineligible order — explain the policy and direct the customer to support/returns.
- [ ] Submit a return with no order reference, no required reason, an unknown order or another customer order — do not create an invalid return.
- [ ] Where a refund amount can be entered, try negative, non-numeric and above-paid amounts — reject them.
- [ ] Submit a return twice and refresh the public form — verify saved references; a page refresh alone is not a successful submission.
- [ ] Try receiving/closing a returned medicine without quarantine and non-resale acknowledgement — block the transition.
- [ ] Try marking the return refunded before an external refund is recorded — block premature closure.
- [ ] Repeat a permitted refund-recording action and inspect stock/history — no duplicate refund event and no saleable restock of dispatched medicine.
- [ ] Try a blank/out-of-range review and an edit to another customer review — reject invalid or unauthorized changes.
- [ ] Download an order/finance report for an empty range and for a range including the order creation date — show the appropriate empty result or matching order without errors.

## 9. Uploaded prescriptions

Use a synthetic prescription file.

### Main flow

- [ ] As customer, upload a valid PDF/JPG/PNG and confirm it appears in prescription history.
- [ ] Try an unsupported file, a file over 5 MB and more than five files; check the errors.
- [ ] As pharmacist, open the same prescription and review its files and patient details.
- [ ] Request clarification; reply as the customer and confirm the pharmacist sees the reply.
- [ ] Reject a separate prescription with a reason; confirm the customer sees it and cannot buy from it.
- [ ] Approve the main prescription with exact medicine variants and allowed quantities.
- [ ] As customer, add the approved items, pay and complete the medicine order.
- [ ] Confirm extra quantities, another variant and unauthorized reuse of the prescription are blocked.
- [ ] Complete dispensing/delivery and check the prescription and order statuses agree.

### Missing values and errors

- [ ] Submit without a file and without any other marked required details — no incomplete prescription should be created.
- [ ] Try a text file or other unsupported type, a damaged PDF/image, a file over 5 MB and a sixth file — reject invalid uploads clearly. Current permitted types are PDF/JPG/PNG, up to five files.
- [ ] Add the same file twice and remove a selected file before upload — selection should behave clearly without unintended duplicates.
- [ ] Try reviewing without permission or opening another customer prescription/file — deny access.
- [ ] Request clarification or reject without a required message/reason — ask for a useful explanation before saving.
- [ ] Try approving with no medicine items, an inactive/wrong variant or a quantity of zero/negative — do not issue an invalid approval.
- [ ] Try a controlled medicine that is not permitted for online supply — block it consistently.
- [ ] Try checking out a pending/rejected prescription or a stale approval link — do not allow purchase.
- [ ] Try more than the approved quantity, a different pack/strength and reuse after the allowance is consumed — enforce the prescription limits.
- [ ] Try skipping dispensing stages or editing already ordered items — protect the saved approval/order association.
- [ ] After a failed upload/review, correct it and retry — create one correct record and retain relevant clarification/audit history.

## 10. Doctor consultation

### Main flow

- [ ] Submit a synthetic doctor application with the required documents and details.
- [ ] As admin, review, approve and activate the doctor account.
- [ ] As doctor, log in and check the profile, availability and consultation fee.
- [ ] As customer, select the doctor, enter a synthetic complaint, pay and finalize one booking.
- [ ] Confirm the same consultation appears for the customer and doctor, with the correct fee and payment.
- [ ] Exchange messages and a synthetic attachment; refresh and confirm the conversation stays saved.
- [ ] As doctor, draft and send an exact-item prescription; open its PDF and check all details are readable.
- [ ] Follow it through pharmacist approval and a separate medicine checkout/payment.
- [ ] Complete the consultation and confirm one correct earning appears for the doctor.

### Missing values and errors

- [ ] Submit the professional application empty or missing a required identity, license, contact, document, availability or declaration field — show exactly what is missing.
- [ ] Try invalid/duplicate email or phone, invalid dates and unsupported/oversized required documents — reject invalid data; do not claim an unperformed external license check.
- [ ] Leave required consent/terms/declaration unchecked — do not silently grant agreement.
- [ ] Try logging in or accepting bookings before approval/activation, then as a suspended clinician — enforce eligibility.
- [ ] Try a used/expired activation link and mismatched activation passwords — fail safely with recovery guidance.
- [ ] Try booking with a missing complaint or other required patient/clinician selection — show the appropriate error.
- [ ] Try an inactive clinician or one without a valid positive consultation fee — do not charge an unexplained fee or finalize an invalid booking.
- [ ] Try finalizing with an unpaid/failed payment and reusing a paid reference for another booking — deny both.
- [ ] Send a blank chat message, an unsupported attachment and one over 10 MB — reject invalid messages/files without losing the conversation.
- [ ] Try opening the consultation/files as an unrelated customer or clinician — deny access.
- [ ] Try sending an empty prescription or one missing required exact items, quantities or instructions — show relevant validation.
- [ ] Repeat booking finalization and consultation completion — one consultation and one earning should remain.
- [ ] If the open-doctor queue is offered, have two eligible doctors try to claim the same consultation — only one assignment should persist.

## 11. Pediatric consultation

### Main flow

- [ ] Apply, approve and activate a pediatrician, then check their profile and fee.
- [ ] As guardian, create two child profiles with different details.
- [ ] Select one child and confirm the correct child appears before booking.
- [ ] Enter the required details, give guardian consent, pay and finalize the booking.
- [ ] As pediatrician, confirm the selected child, guardian, consent and measurements are correct.
- [ ] Check that missing consent or invalid child details are handled properly.
- [ ] Exchange messages and follow the prescription through pharmacist approval and medicine payment.
- [ ] Complete the consultation and confirm one correct earning.
- [ ] Book/view another consultation for the same child; confirm their history stays separate from the sibling's.

### Missing values and errors

- [ ] Submit a child profile without each marked required field separately — no incomplete child should be silently saved.
- [ ] Try a future birth date, invalid age and zero/negative supplied measurements — reject invalid values; leave optional measurements blank separately and confirm none are invented.
- [ ] Create children with the same name but different details — keep them separate by child identity, not name alone.
- [ ] Try starting the booking without a selected child, required complaint or pediatrician where required — show useful validation.
- [ ] Leave guardian consent unchecked — enforce the required consent restriction; do not silently grant it after payment.
- [ ] If a pending-consent consultation can exist, try issuing its prescription — it must remain blocked until consent is granted.
- [ ] Try another guardian child/profile link and an unrelated pediatrician consultation link — deny access.
- [ ] After changing child selection, review the summary and clinician view — no sibling measurements, consent or history should be substituted.
- [ ] Try a failed payment, repeated finalization and repeated completion — do not create duplicate bookings or earnings.
- [ ] Repeat the doctor chat/file/prescription error checks for the pediatric flow — the same protections should hold.

## 12. Lab services

### Main flow

- [ ] Submit a synthetic lab-partner application; review, approve and activate it as admin.
- [ ] Add and approve a facility, then add its tests, prices and technician assignments.
- [ ] Confirm only approved facilities/tests are available to customers.
- [ ] As customer, book a walk-in test and check the request, facility, saved price and payment arrangement.
- [ ] Book a home-collection test and check the address, appointment details and assignment.
- [ ] As technician, try one incorrect collection code, then verify the correct one; confirm it cannot be reused.
- [ ] Move the request through sample collection and processing; upload the synthetic result and complete it.
- [ ] As customer, open the notification and download the correct result.
- [ ] Cancel a separate eligible request and check that its history and payment handling are clear.

### Missing values and errors

- [ ] Submit partner/facility forms with required details or documents missing — show the missing fields and keep the application unapproved.
- [ ] Try invalid/duplicate email or phone and missing required declarations — do not create conflicting or silently consented applications.
- [ ] Try creating a test/offer without a required name, permitted price or required facility details — reject invalid values.
- [ ] Try assigning a suspended technician or one from another partner/facility — deny the assignment.
- [ ] Try booking without a required facility/test/patient field or home address/appointment detail — identify each missing value.
- [ ] Try a pending/suspended facility or a test not offered by the selected facility — do not accept the booking.
- [ ] Where appointment rules are enforced, try an invalid or unavailable time — show the relevant restriction.
- [ ] Try blank, wrong, expired, already used and other-request collection codes — reject them; stop if the attempt limit is reached.
- [ ] Try skipping collection/processing steps or completing without a required result — block invalid transitions.
- [ ] Try no result file, an unsupported/damaged file and a file above the displayed limit — preserve the request and explain the failure.
- [ ] Try result upload/download as an unrelated patient, partner or technician — deny access.
- [ ] Try cancelling after collection or outside the permitted payment/status policy — reject with guidance.
- [ ] Change the test catalog price after booking and reopen the request — keep its saved quote rather than rewriting history.
- [ ] Repeat booking/result publication through offered controls — do not duplicate requests or result notifications.

## 13. Earnings and payouts

The current payout feature records administrative payments; it does not send money.

### Main flow

- [ ] Compare the completed consultation's paid fee, commission and clinician earning.
- [ ] Create one payout linked to that clinician and source; check the net amount.
- [ ] Submit it and have a different admin approve it; confirm the creator cannot approve their own payout.
- [ ] Use a clearly labelled synthetic reference for the ledger test, then record and reconcile the payout.
- [ ] Confirm the clinician sees the correct amount/status and duplicate sources or payment references are blocked.
- [ ] Test hold, failure/retry and cancellation on separate disposable payout records; check the history and amounts.

### Missing values and errors

- [ ] Submit a payout without the required recipient, source reference, gross amount or method — show the missing fields.
- [ ] Try a zero/negative gross amount, negative deductions, non-numeric amounts and deductions exceeding gross — reject invalid calculations.
- [ ] Select the wrong professional role, an inactive recipient or another clinician consultation — reject an unrelated payout source.
- [ ] Try a consultation that is unpaid, unfinished or has no earning — it should not qualify for a consultation-source payout.
- [ ] Try creating the same source payout twice and reusing an existing payment reference, including spaces/case variations — avoid duplicate obligations/references.
- [ ] Try approving your own payout, processing before approval and paying a cancelled/held payout — enforce the allowed workflow.
- [ ] Try marking paid without the required payment reference, using an invalid/future payment time and retrying a completed action — reject invalid records.
- [ ] Release a held payout and try processing without renewed approval — require approval again.
- [ ] Try payout admin actions and another professional financial records as a customer/unrelated professional — deny access.
- [ ] Check the screen and notification wording after recording payment — it must not imply that this ledger test sent actual money.

## 14. Notifications, support and settings

### Main flow

- [ ] Check prescription, consultation, order and lab notifications reach the intended account and open the correct record.
- [ ] Mark one notification read, then mark all read; refresh and check the unread count.
- [ ] Change an optional notification preference and confirm it stays saved and affects delivery as expected.
- [ ] Check a failed delivery/retry with staff help; confirm it does not duplicate the business action.
- [ ] Create a support ticket; reply as staff, change its status and check the customer-visible history.
- [ ] Add an internal staff note and confirm the customer cannot see it.
- [ ] Submit the contact form and confirm it creates a saved inquiry; test newsletter signup with valid, invalid and duplicate emails.
- [ ] Upload synthetic compliance evidence as admin; confirm permitted read-only staff can view but cannot edit it.

### Missing values and errors

- [ ] Open notifications/support with no records, then search for a reference that does not exist — show a useful empty state.
- [ ] Try reading, changing or retrying another user notification/delivery — deny access.
- [ ] Retry a successful delivery, a disabled-channel delivery and a failed one above its retry cap — block invalid retries without duplicating the business event.
- [ ] Submit a support ticket with an empty required subject/channel/other marked field or an invalid priority — explain the missing/invalid value.
- [ ] Post an empty reply and try assigning an ineligible staff member — reject invalid changes.
- [ ] Try opening another customer ticket and viewing an internal staff note as a customer — private data must stay hidden.
- [ ] Submit Contact without its required fields and newsletter signup with an empty or invalid email — show useful errors, not false success.
- [ ] Submit the same valid newsletter email twice and handle a staff-assisted delivery failure — retain one consistent subscription state.
- [ ] Upload compliance evidence with required metadata/file missing, invalid dates or a disallowed file — reject invalid input.
- [ ] Try editing compliance evidence as a read-only inspector and downloading it as a customer/visitor — enforce the allowed role scope.
- [ ] After a failed save or send, correct the input and retry — preserve prior valid data and create one intended ticket/message/record.

## 15. Privacy, mobile and final check

### Main flow

- [ ] Use a second unrelated customer account and confirm it cannot see or change the first customer's orders, prescriptions, consultations, children, lab results or support tickets.
- [ ] Confirm signed-out users and unrelated staff cannot download private files or use restricted dashboards.
- [ ] On a disposable customer account, test deactivation and confirm that account loses access.
- [ ] Repeat the main customer journeys on a phone; check menus, forms, uploads, chat and payment screens.
- [ ] Check that invalid forms show useful errors, buttons work and pages recover after refresh or a connection interruption.
- [ ] Compare each completed journey across customer and staff views using the same references.
- [ ] Record anything failed or blocked, retest fixes and restore temporary settings/test changes.

### Missing values and errors

- [ ] On a phone, submit the main forms with missing fields — errors and the corrective fields must remain visible with the keyboard open.
- [ ] Zoom in and use keyboard navigation — labels, focus and errors should remain readable and usable without relying only on colour.
- [ ] Disconnect/reconnect during a harmless save/read test — show a useful error or recovery state rather than an endless spinner or false saved message.
- [ ] Let a session expire or log out in another tab before submitting a disposable form — request login again without saving under another account.
- [ ] Use Back, Forward, refresh, direct links and an unknown URL — recover predictably without private-data leaks or duplicate actions.
- [ ] Try a long name, long description, long chat and an empty list — content should not clip, crash or hide the needed controls.
- [ ] For every rejected submission, check the list/history afterward — no partial record, charge, stock change or success notification should have been created.
- [ ] Correct each failed input and repeat the valid flow — errors should clear and the intended action should succeed once.

## Things to leave pending when unavailable

- Paybill: leave pending until a real provider confirmation reaches the correct order.
- POS: real POS testing remains on hold until we agree to resume it.
- Returns: the current public form may not save a request. A refresh without a saved reference is a failure to record.
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

**Start now with Section 1. We will confirm each result together before moving on.**
