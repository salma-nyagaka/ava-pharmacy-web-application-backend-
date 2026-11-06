# AvaPharmacy end-to-end test checklist

For the PPB software-control implementation and the genuine operational evidence still pending, use the [5 November compliance remediation checklist](compliance-audit/2026-11-05/ppb-remediation-checklist.md). Functional test passes do not establish regulatory sign-off.

Use this as a manual test plan across the website, backend, staff dashboards, and configured external services. These are acceptance checks to perform, not claims that the current implementation passes them.

For a fresh browser run with numbered actions and expected results, use the [manual end-user testing guide](manual-end-user-testing-guide.md) or its [interactive version](../output/manual-testing/index.html). Previous acceptance results below do not prefill your manual run.

Latest update: **1 November 2026** — reconciled against the latest module reports. [Consultations](test-runs/2026-10-29/consultations-completion.md): **18/18 passed at the recorded test layers**, including genuine doctor receipt UK1I20IYUB. [Prescriptions](test-runs/2026-10-29/prescriptions-completion.md): **9/9 local application checks passed**, including simulated checkout payment. [Inventory follow-up](test-runs/2026-10-28/inv02.md): **14/15 passed**, including exact-store stock deduction and cancellation with a simulated payment. [Orders / STK](test-runs/2026-10-29/ord05-retry.md): **ORD-05 provider-confirmed sandbox pass**; [ORD-06 Paybill](test-runs/2026-10-29/paybill-delivery-investigation.md) and real POS remain blocked. [Pediatric follow-up](test-runs/2026-10-30/pediatric-journey.md): all 7 pediatric checks pass at the recorded layers; receipt UJUI207MTB confirms KSh 1 intent 51, and CONS-8AF578 is completed with one KSh 0.90 earning. The four account credential-entry steps retain their user-verified browser results from 27 October.

Checked scenarios reflect the evidence layer stated in their module report. Simulated payment, automated/API verification, provider confirmation, and production deployment are separate outcomes.

## How to record a run

- Leave a box empty until the scenario passes. Record failures and blocked scenarios in the results table below.
- For each scenario, check the visible result, the saved record after refreshing, and related stock/payment/notification changes where applicable.
- Record order, prescription, consultation, lab request, and payment references so the same journey can be followed across dashboards.
- If a feature has no frontend screen, test its API and record that the UI step is blocked or unavailable. An API-only pass does not establish a full website pass.
- Use test accounts, synthetic patient information, and payment sandbox/test services. Record integrations that are unavailable as blocked, rather than passed.

| Run detail | Value |
|---|---|
| Date / tester | Latest documented run: 1 November 2026 / Codex; user-verified account steps retained separately |
| Frontend URL / version | `http://localhost:3000` / current local workspace; build evidence in module reports |
| Backend URL / commit | `http://127.0.0.1:8000` / `c47b265` plus workspace changes; not a deployed release |
| Database / environment | Local PostgreSQL and isolated Django test databases; synthetic QA records |
| M-Pesa / POS test setup (card excluded) | Safaricom sandbox; order, prescription, doctor and pediatric STK payments confirmed; ORD-06 pending; real POS held at user request |
| Email / notification setup | Local/test delivery and recorded notification evidence; external inbox delivery not independently verified |

| Scenario ID | Result: Pass / Fail / Blocked / N/A | Record reference / evidence | Issue / retest result |
|---|---|---|---|
| SET-01–07; ACC-01–11 | Pass at documented layers | [Setup](test-runs/2026-10-28/setup-completion.md); account section and retained user confirmations | Professional approval/activation also retested for both clinician roles |
| CAT-01–06; INV-01–07, INV-09 | Pass; INV-02 payment simulated | [Inventory completion](test-runs/2026-10-28/inv02.md) | Exact stock/cancellation verified; real POS remains separate |
| ORD-05 | Pass — provider-confirmed sandbox payment | [Order 2003 / ORD-7FF17F50](test-runs/2026-10-29/ord05-retry.md) | Receipt and KSh 1 total matched; exact stock deducted once |
| ORD-06; INV-08; ORD-14 | Blocked — real integrations | [Paybill investigation](test-runs/2026-10-29/paybill-delivery-investigation.md); inventory/orders reports | Paybill callback not confirmed; real POS held at user request |
| RX-01–09; E2E-02 | Pass — local application plus genuine STK rerun | [RX-7E5CC4 → ORD-599F53F7](test-runs/2026-10-31/connected-journeys.md) | Receipt UK1I20IJMO, stock 4 → 3; Paybill ORD-06 separate |
| CON-01–03, CON-05–11; PED-01, PED-03–07 | Pass at recorded layers; completed payments simulated | [Consultation report](test-runs/2026-10-29/consultations-completion.md) | 40 consultation tests, onboarding/activation, live links, exact stock and one earning per consultation verified |
| CON-04 | Resolved — genuine doctor sandbox payment | [Evidence](test-runs/2026-10-31/connected-journeys.md) | UK1I20IYUB → CONS-83F95C |
| PED-02 | Pass — genuine provider-confirmed sandbox payment | [Pediatric completion](test-runs/2026-10-30/pediatric-journey.md) | Receipt UJUI207MTB / KSh 1 intent 51; CONS-8AF578 completed with one KSh 0.90 earning |

## 0. Prepare once

Latest run: [28 October — setup completion](test-runs/2026-10-28/setup-completion.md). All 7 setup checks verified for local testing. Role logins/restrictions, shared fixtures, fee baselines and local worker/scheduler readiness are recorded; later module workflow sign-off remains separate.

- [x] SET-01: Start the frontend, backend, database, and any required background workers; confirm the website can reach the API.
- [x] SET-02: Prepare two unrelated customers, an admin, inventory staff, a pharmacist with review permission, a doctor, a pediatrician, a lab partner, and a lab technician.
- [x] SET-03: Prepare pending and suspended professional accounts to test approval and access restrictions.
- [x] SET-04: Create two stores and one product with multiple variants, including different strengths or pack sizes. Record starting stock separately for every variant and store.
- [x] SET-05: Prepare a normal item, prescription-only item, out-of-stock item, low-stock item, and a backorder item if backorders are enabled.
- [x] SET-06: Prepare synthetic prescription files, an invalid upload, a lab result, a valid/expired coupon, and delivery options.
- [x] SET-07: Record the configured prices, shipping fees, consultation fees, promotions, and payout rules to use as expected totals.

## 1. Accounts 10:30-11:30

Journey: register → verify email → log in → manage account → log out.

- [x] ACC-01: Register a customer; verify the email flow and log in successfully.
- [x] ACC-02: Reject duplicate registration, invalid account details, and incorrect login credentials with useful messages.
- [x] ACC-03: Edit the profile, refresh the page, and confirm changes persist.
- [x] ACC-04: Add, edit, and remove delivery addresses and saved payment-method entries; confirm no other customer's entries appear.
- [x] ACC-05: Change password; verify the old password fails and the new one works.
- [x] ACC-06: Request a password reset; use the link successfully, then confirm reused or expired links fail.
- [x] ACC-07: Refresh an access token; log out and confirm the logged-out refresh token cannot issue another access token.
- [x] ACC-08: Confirm customers cannot access staff functions or promote themselves to a staff role.
- [x] ACC-09: Suspend and reactivate an account; confirm access follows its current status, including with an existing session.
- [x] ACC-10: Submit a professional application, review it as admin, provision/activate the account, and log in to the correct dashboard. Check expired/reused activation links.
- [x] ACC-11: Exercise account deletion with a disposable test customer and verify the intended access and retention behavior. The implemented feature is soft deactivation with retained service records, now stated explicitly in the UI.

## 2. Products and inventory 11:30-12:30

Latest runs: [27 October — products and inventory](test-runs/2026-10-27/products-and-inventory.md), followed by [28 October — INV-02 completion](test-runs/2026-10-28/inv02.md). **14/15 application checks passed.** INV-02 completed in the browser with a controlled simulated payment notification and verified exact stock/cancellation behavior. Payment evidence is tracked separately: ORD-05 subsequently passed with a genuine sandbox confirmation; ORD-06 remains blocked. INV-08 real POS remains blocked at the user's request.

Journey: create product → create exact sellable variants → stock stores → browse → sell the correct variant.

- [x] CAT-01: Create a brand, category/subcategory, product, images, and at least two variants; confirm the storefront displays them correctly.
- [x] CAT-02: Search and filter the catalog; verify results, product details, prices, and availability match the selected variant.
- [x] CAT-03: Switch strength or pack size; confirm the cart receives that exact variant and its price.
- [x] CAT-04: Add/remove wishlist items and move an item to the cart; refresh and confirm persistence.
- [x] CAT-05: Submit and view a product review; verify validation and ownership rules.
- [x] CAT-06: Publish/edit banners, promotions, FAQs, and content blocks; verify their storefront appearance and configured visibility dates.
- [x] INV-01: Set variant A to 50 packs in store 1 and 30 packs in store 2. Set variant B to different quantities. Confirm each stock record is separate.
- [x] INV-02: Complete an order for 2 packs of variant A from store 1. At the configured stock-deduction stage, verify store 1 becomes 48, store 2 remains 30, and variant B is unchanged. Check reserved versus available stock too. **Passed with a simulated payment notification; no real provider payment is claimed.**
- [x] INV-03: Adjust stock as authorized staff; verify movement history records the quantity, reason, and actor.
- [x] INV-04: Reserve/release stock and exercise cancellation; verify available stock is restored correctly and repeating the action does not restore it twice.
- [x] INV-05: Attempt to buy above available stock; reject it or apply the configured backorder rule without negative stock.
- [x] INV-06: Have two customers attempt to buy the last unit at the same time; confirm it cannot be sold twice unless explicitly allowed as a backorder.
- [x] INV-07: Cross the low-stock threshold and verify the configured indicator/alert.
- [ ] INV-08: Sync POS inventory; verify SKU/POS mapping updates the correct variant and store. Repeat the update and test unknown mappings and POS downtime. **Blocked — real POS held at the user’s request; mapping/retry/downtime simulations pass.**
- [x] INV-09: Confirm customers cannot modify inventory and invalid quantities or mismatched store/variant records are rejected.

## 3. Orders and payments

Latest run: [29 October — STK retry and fixes](test-runs/2026-10-29/ord05-retry.md); [M-Pesa-only policy](test-runs/2026-10-29/mpesa-only.md). **14 passed scenarios, 2 N/A scenarios, and 2 incomplete integration scenarios (ORD-06, ORD-14).** Only M-Pesa STK Push and Paybill are supported. Card/COD are explicitly excluded; rejection checks pass. Flutterwave setup is no longer pending work.

Journey: cart → checkout → payment → processing → dispatch → delivery.

- [x] ORD-01: Add multiple variants, change quantities, remove items, and clear the cart; verify quantities and totals after refresh.
- [x] ORD-02: If guest cart merge is used, log in with an existing cart and confirm the merge does not lose or duplicate quantities.
- [x] ORD-03: Apply/remove a valid coupon; reject expired/ineligible coupons and verify promotion stacking follows configuration.
- [x] ORD-04: Select delivery details and method; independently calculate item totals, discounts, shipping, and final amount.
- [x] ORD-05: Complete M-Pesa STK checkout; match the provider confirmation, payment record, order total, stock allocation, and customer receipt. **Passed in sandbox: KSh 1, order 2003 (ORD-7FF17F50), intent 45, provider receipt UJTI203HXA. [Evidence](test-runs/2026-10-29/ord05-retry.md).**
  - [x] Genuine Safaricom success callback (ResultCode 0), matching request IDs, phone and KSh 1 amount.
  - [x] Order total and payment intent both KSh 1; order and payment marked paid.
  - [x] Finalized in customer browser; variant 23505 allocated from branch inventory row 64279, stock 2 → 1. Repeated finalization does not deduct again. This fixture uses branch location without a store listing.
  - [x] Customer confirmation/receipt displays PAID, KSh 1 and the correct item/order; email send timestamp recorded. External inbox delivery was not independently verified.
  - [x] Earlier failure (1037) preserves unpaid-order protection; restored checkout failure display and address consent fixed. 16 regression tests and frontend build passed.
  - [x] QA product and QA shipping option deactivated; paid sandbox order/payment and stock movement retained as evidence. Earlier KSh 350 attempt locally cancelled.
- [ ] ORD-06: Complete Paybill checkout; verify the correct reference matches the correct order. Test unmatched references and incorrect amounts without falsely marking an order paid. **Pending / blocked: [Latest delivery investigation](test-runs/2026-10-29/paybill-delivery-investigation.md). C2B shortcode 600980 and the callback tunnel are verified. Registration has succeeded, but the latest retry again returns HTTP 500 / 500.003.1001; earlier accepted simulations produced no confirmation callback. Orders 2005/2006 remain unpaid; stock is unchanged.**
  - [x] Verify the pharmacy app's C2B sandbox shortcode and correct the configuration.
  - [x] Restore the restricted callback gateway/tunnel and obtain provider registration success.
  - [x] Submit correct-amount, incorrect-amount and unmatched-reference sandbox simulations; record provider acceptance.
  - [ ] Receive and verify the actual provider confirmation, receipt, reference and amount; finalize and check stock/idempotency.
  - [ ] Verify provider-delivered wrong-amount and unmatched-reference callbacks; application rejection regressions already pass.
- [x] ORD-07: **N/A — card payments excluded by the user.** New card checkout/intents and saved-card entry are rejected; historical records remain readable. Earlier card test evidence is historical only.
- [x] ORD-08: **N/A — cash on delivery excluded by the user.** COD checkout and finalization are rejected; new orders default to M-Pesa.
- [x] ORD-09: Cancel or fail payment; verify the customer can understand the result and retry without duplicate orders or charges.
- [x] ORD-10: Double-click checkout, refresh the payment return page, and repeat provider callbacks; confirm a single payment is applied and stock is not deducted twice.
- [x] ORD-11: Reject forged/unverified payment confirmations and payment references belonging to another customer or order.
- [x] ORD-12: Change price/availability after adding to cart; confirm checkout revalidates and clearly reports changes.
- [x] ORD-13: As staff, process → ship → deliver the order; confirm customer tracking, timestamps, notes, and notifications reflect each stage.
- [ ] ORD-14: Verify order push to the external fulfillment/POS service; simulate failure, retry, and confirm no duplicate external order. **Blocked for the real POS service at the user’s request; mocked failure/retry tests passed.**
- [x] ORD-15: Cancel an eligible order; verify stock release and payment/refund handling. Reject cancellation where policy disallows it.
- [x] ORD-16: Request a return, review it as admin, and exercise the configured refund path. Verify payment records, order status, and stock follow the chosen disposition; repeated actions do not duplicate a refund or restock.
- [x] ORD-17: Verify invoices, payment reconciliation, finance totals, and downloaded reports against the completed test orders.
- [x] ORD-18: Confirm another customer cannot view/change the order, payment, invoice, or return. Check public tracking reveals only intended information.

## 4. Prescriptions

Latest run: [29 October — prescription completion](test-runs/2026-10-29/prescriptions-completion.md). **All 9 local application scenarios passed; 112 prescription/order/consultation regression tests passed.** Public-file access and pharmacist permission bypasses are fixed. RX-06 and E2E-02 completed using an explicitly labeled **simulated payment**, with exact stock 4 → 3 and customer Paid / Delivered. No new provider-confirmed Paybill payment or production deployment is claimed; ORD-06 remains blocked.

**Integration dependency — pending ORD-06: Real Paybill confirmation has not arrived.** Registration is intermittent (latest retry HTTP 500); earlier accepted simulations delivered no callback. [Investigation and support draft](test-runs/2026-10-29/paybill-delivery-investigation.md). The simulated prescription payment does not satisfy this check.

Journey: upload → pharmacist assignment/review → approval → approved items → checkout.

- [x] RX-01: Upload a valid prescription; confirm it appears for its owner and in the pharmacist review queue.
- [x] RX-02: Reject unsupported/oversized files and incomplete required details with useful messages.
- [x] RX-03: Assign and review as a pharmacist with permission; verify patient details and map medicine items to exact catalog variants and quantities.
- [x] RX-04: Request clarification; reply as the customer, resubmit, and confirm the pharmacist sees the full exchange.
- [x] RX-05: Reject a prescription and confirm the reason is visible; reject checkout using pending/rejected prescriptions.
- [x] RX-06: Approve a prescription; add approved items to cart and complete an order. Confirm the approval applies to those variants and allowed quantities. **Genuine STK rerun passed: RX-7E5CC4 → ORD-599F53F7, KSh 1 receipt UK1I20IJMO, stock 4→3 and synthetic delivery. [Evidence](test-runs/2026-10-31/connected-journeys.md).**
- [x] RX-07: Attempt to substitute another variant, increase beyond the authorized quantity, or reuse a prescription beyond its permitted dispensing limits; enforce the configured rules.
- [x] RX-08: Progress dispensing through the supported queued/packed/dispatched/delivered steps; verify history and customer updates.
- [x] RX-09: Confirm unrelated customers and pharmacists without review permission cannot access/review protected prescriptions; check the audit trail identifies each change.

## 5. Consultations: doctor and pediatrician

**1 November 2026:** 18/18 checks passed at the recorded API, automated, and browser layers. [Original results](test-runs/2026-10-29/consultations-completion.md); [latest pediatric completion](test-runs/2026-10-30/pediatric-journey.md). Pediatric intent 51 is genuinely provider-confirmed: KSh 1, receipt UJUI207MTB, completed consultation CONS-8AF578, one KSh 0.90 earning. Earlier application journeys used labelled simulations. Doctor CON-04 subsequently passed with genuine receipt UK1I20IYUB on 1 November; ORD-06 remains a separate Paybill block. Earlier pediatric intent 50 is retained as unconfirmed and does not establish a pass.

Doctor journey: approved clinician → booking/payment → chat → prescription → pharmacist → medicine order → earnings.

- [x] CON-01: Submit clinician profile, documents, availability, and payout details; approve/provision as admin and activate the account.
- [x] CON-02: Confirm pending/suspended clinicians cannot receive new bookings and only eligible clinicians appear for selection.
- [x] CON-03: Select a doctor, enter symptoms, and confirm the displayed consultation fee matches the payment amount.
- [x] CON-04: Pay and finalize a booking; verify one consultation appears for the customer and clinician. Block unpaid bookings and payment reuse across bookings. **Genuine doctor payment confirmed: intent 52, KSh 1 receipt UK1I20IYUB → CONS-83F95C. Existing automated unpaid/reuse guards retained. [Evidence](test-runs/2026-10-31/connected-journeys.md).**
- [x] CON-05: Exercise failed/cancelled payment, status sync, repeated callbacks, and repeated finalization; verify recovery creates no duplicate consultation.
- [x] CON-06: Where specialty routing is offered, book without a named doctor and have an eligible doctor claim it; prevent two doctors from claiming the same consultation.
- [x] CON-07: Exchange messages and attachments in both directions; verify live updates, persistence after refresh, and protected attachment access.
- [x] CON-08: Create/edit a draft prescription, send it, and download its PDF. Verify exact medicine details and pharmacist notification.
- [x] CON-09: Follow that prescription through pharmacist approval and customer checkout; confirm all records link to the same consultation/prescription. **Local application pass; genuine doctor/pediatric STK reruns now link consultation → prescription → medicine order with exact stock and one earning. [Evidence](test-runs/2026-10-31/connected-journeys.md).**
- [x] CON-10: End the consultation; verify completed status and one earnings record. Repeat the action to check earnings are not duplicated.
- [x] CON-11: Confirm unrelated customers and unassigned/ineligible clinicians cannot read private consultations or attachments.

Pediatric journey: guardian → child profile → consent → paid pediatric consultation → prescription → completion.

- [x] PED-01: As one guardian, create two child profiles; edit them and confirm both persist separately.
- [x] PED-02: Select a child and pediatrician, enter symptoms and configured child measurements, provide consent, and pay. **Passed — genuine KSh 1 sandbox receipt UJUI207MTB / intent 51; correct child 6, guardian 75, granted consent and one booking CONS-8AF578 verified in customer and clinician views. [Evidence](test-runs/2026-10-30/pediatric-journey.md).**
- [x] PED-03: Confirm the pediatrician sees the selected child, correct guardian, consent, and recorded measurements; the sibling's information is not substituted. **Same-name children now remain separate by child ID; distinct measurements and history verified in the browser. [Follow-up](test-runs/2026-10-30/pediatric-journey.md).**
- [x] PED-04: Exercise missing consent and required child information; verify the configured restrictions and useful validation messages. **Affirmative consent is preserved in the payment payload; missing consent is not silently granted.**
- [x] PED-05: Repeat chat, attachments, prescription → pharmacist → checkout, completion, and earnings checks for a pediatric consultation. **Local application pass; genuine doctor/pediatric STK reruns now link consultation → prescription → medicine order with exact stock and one earning. [Evidence](test-runs/2026-10-31/connected-journeys.md).**
- [x] PED-06: Book another consultation for the same child; verify patient history groups records under that child and keeps siblings separate. **Same-name children now remain separate by child ID; distinct measurements and history verified in the browser. [Follow-up](test-runs/2026-10-30/pediatric-journey.md).**
- [x] PED-07: Confirm another guardian cannot use that child profile and another pediatrician cannot browse unrelated child histories.

## 6. Lab services

Journey: approve partner/facility → offer test → patient request → verify collection → process → result.

- [x] LAB-01: Register a lab partner, submit documents/facility details, and review them as admin; provision the partner account. **Passed — Automated partner application, documents, verification, provisioning and activation; live API facility approval passed. [Evidence](test-runs/2026-10-30/lab-services.md).**
- [x] LAB-02: Add facility tests and technicians; verify approved services appear to customers and assignments stay within the correct partner/facility. **Passed — Live API facility offerings/staff and customer catalog passed; automated assignment boundaries passed. [Evidence](test-runs/2026-10-30/lab-services.md).**
- [x] LAB-03: Create a walk-in lab request; verify patient, selected test, price, facility, payment status, and request reference. **Passed — Live API walk-in LAB-217755 completed; saved KSh 150 quote and pending payment verified. [Evidence](test-runs/2026-10-30/lab-services.md).**
- [x] LAB-04: Create a home sample collection request; verify collection details and assignment. **Passed — Customer and technician browser home request LAB-395DA4 passed with API assignment. [Evidence](test-runs/2026-10-30/lab-services.md).**
- [x] LAB-05: Issue and verify a collection code; reject wrong, expired, reused, or other-request codes according to policy. **Passed — Browser code handoff passed; automated wrong/expired/reused/other-request, attempt-limit and concurrency checks passed. [Evidence](test-runs/2026-10-30/lab-services.md).**
- [x] LAB-06: Move the request through awaiting sample → sample collected → processing → result ready → completed; confirm the visible status and audit history. **Passed — Technician browser completed all statuses; actor audit and immediate audit refresh passed. [Evidence](test-runs/2026-10-30/lab-services.md).**
- [x] LAB-07: Upload a synthetic result as authorized lab staff; view/download it as the patient and verify the notification and correct request association. **Passed — Synthetic result upload, patient browser/API download hash and notification association passed; external email receipt not independently verified. [Evidence](test-runs/2026-10-30/lab-services.md).**
- [x] LAB-08: Test cancellation and invalid status changes; verify recorded payment handling follows configured policy. If online lab payment is offered, exercise its success/failure path separately. **Passed — Patient browser cancellation and automated transition/payment-policy checks passed. Online lab payment is not offered; pay-later status remains pending. [Evidence](test-runs/2026-10-30/lab-services.md).**
- [x] LAB-09: Reject invalid result uploads; confirm another patient, another partner, and an unrelated technician cannot access results or alter the request. **Passed — Automated upload limits/content, private downloads, role/object access and concurrent duplicate checks passed. [Evidence](test-runs/2026-10-30/lab-services.md).**

## 7. Payouts

Journey: earning/source record → payout calculation → approval → processing → recorded payment → reconciliation.

- [x] PAY-01: Configure payout rules and create a payout for a test professional/source; independently verify gross amount, commission, withholding, deductions, and net amount. **Passed — Browser reference rule and source-linked payout passed; independent net checks 500 − 50 = 450 and 500 − 50 − 20 − 10 = 420. [Evidence](test-runs/2026-10-30/payouts.md).**
- [x] PAY-02: Progress through the supported approval and processing actions; verify actor, timestamps, and audit entries. **Passed — Browser maker-checker rejection, independent admin API approval, processing and actor/timestamp audit passed. [Evidence](test-runs/2026-10-30/payouts.md).**
- [x] PAY-03: Record payment reference and reconcile the payout; match recipient, amount, source, and professional earnings view where applicable. **Passed — PAY-2442FD recorded paid/matched for CONS-EE8CBC; recipient API and doctor browser earnings show KSh 450 paid and pending 0. [Evidence](test-runs/2026-10-30/payouts.md).**
- [x] PAY-04: Create the same source payout twice and repeat payment actions; confirm duplicates are prevented. **Passed — Source/idempotency, repeated actions, normalized/cross-field payment references and concurrent duplicate checks passed. [Evidence](test-runs/2026-10-30/payouts.md).**
- [x] PAY-05: Exercise hold, failure, retry, cancellation, and reversal where supported; confirm amounts and history remain consistent. **Passed — Live synthetic hold/reapproval/failure/retry/reversal/cancellation passed with stable amounts and retained audit history. [Evidence](test-runs/2026-10-30/payouts.md).**
- [x] PAY-06: Confirm customers/professionals cannot perform admin payout actions or access another person's protected financial information. **Passed — Automated/live role and recipient-scope checks passed; inactive admins and recipients denied. [Evidence](test-runs/2026-10-30/payouts.md).**
- [x] PAY-07: Verify whether execution is an actual provider transfer or an administrative record. If actual transfer is configured, confirm it independently in the test provider; a status change alone is not transfer evidence. **Passed — Administrative ledger confirmed. No actual transfer adapter executes; all test references are labelled synthetic, with no money sent. [Evidence](test-runs/2026-10-30/payouts.md).**

## 8. Notifications

- [x] NOT-01: Trigger a prescription review, consultation message, order update, and lab result; verify the intended recipient receives each configured notification. **Passed — Local controlled-event inbox/recipient and configured delivery-policy checks passed for prescription, chat, order and lab. External email/SMS receipt not independently confirmed. [Evidence](test-runs/2026-10-30/notifications-support.md).**
- [x] NOT-02: Check unread count, mark one read, mark all read, and refresh; counts and saved state stay consistent. **Passed — Browser unread 73 → 72 → 0 persisted after refresh; notification and delivery paging passed. [Evidence](test-runs/2026-10-30/notifications-support.md).**
- [x] NOT-03: Change preferences; verify optional notification delivery follows them and required operational messages follow the configured policy. **Passed — Browser preferences persisted; opted-out email produced no delivery while inbox notice remained. Required receipt policy checked separately with mocks. [Evidence](test-runs/2026-10-30/notifications-support.md).**
- [x] NOT-04: Verify notification links open the correct record with access checks; another user cannot read or modify the notification. **Passed — Browser links opened the exact authorized records; prescription modal navigation fixed. Cross-user notification/delivery access denied. [Evidence](test-runs/2026-10-30/notifications-support.md).**
- [x] NOT-05: Check delivery records and simulate an email/delivery failure; confirm the business operation still has the intended result and retry behavior is recorded without duplicate business actions. **Passed — Delivery 169 failed then retried to backend-accepted sent, retaining one notification/delivery and two attempts; cap, concurrency and business-failure isolation tests passed. [Evidence](test-runs/2026-10-30/notifications-support.md).**

## 9. Support and site settings

- [x] SUP-01: Create a customer ticket, open it as staff, add an allowed reply/note, update status, and confirm the customer-visible history. **Passed — Browser customer/staff journey SUP-D85A43 and contact-form ticket SUP-C72906 passed; replies and resolution history persisted. [Evidence](test-runs/2026-10-30/notifications-support.md).**
- [x] SUP-02: Verify internal staff notes remain private and unrelated customers cannot read or alter the ticket. **Passed — Internal staff note excluded from customer browser/API; public reply retained and unrelated customer access denied. [Evidence](test-runs/2026-10-30/notifications-support.md).**
- [x] SUP-03: Subscribe a valid email to the newsletter; test duplicate and invalid submissions with useful responses. **Passed — Browser valid and duplicate signup, invalid-email API, failure preservation, throttling and concurrent duplicate tests passed. QA subscriber deactivated. [Evidence](test-runs/2026-10-30/notifications-support.md).**
- [x] SUP-04: Change a public site setting as admin; refresh the storefront and confirm the expected public information appears without exposing private configuration. **Passed — Admin API setting change appeared on refreshed storefront; original setting restored. Public allowlist and write/URL/price restrictions verified. [Evidence](test-runs/2026-10-30/notifications-support.md).**
- [x] SUP-05: Add/view compliance evidence with authorized roles; confirm read-only roles cannot modify records and customers cannot access restricted evidence. **Passed — Admin browser evidence upload/download passed; raw media/customer access denied. Inspector read-only behavior verified in automated tests; synthetic evidence retained as review_due. [Evidence](test-runs/2026-10-30/notifications-support.md).**

## 10. Complete connected journeys

Run these after the individual checks. Use the same references throughout each journey.

**1 November rerun:** E2E-01–04 have genuine KSh 1 sandbox payment evidence, synthetic fulfillment and matching stock/finance records. E2E-05 retains its local pay-later pass. E2E-06 application regression passed, but genuine external refund and support closure remain pending. [Current evidence](test-runs/2026-10-31/connected-journeys.md).

- [x] E2E-01: New customer → verification/login → exact medicine variant → cart → payment → inventory update → dispatch → delivery → receipt/report. **Passed locally with genuine KSh 1 sandbox receipt UK1I20HYZ4: customer 87 → exact variant 23514 → ORD-7B791366; one finalization event and stock 4→3; synthetic fulfillment delivered and finance export matched. Registration verification used a controlled QA mailbox. [Evidence](test-runs/2026-10-31/connected-journeys.md).**
- [x] E2E-02: Customer prescription upload → clarification/reply → pharmacist approval → medicine checkout → delivery. **Rerun passed with genuine KSh 1 sandbox receipt UK1I20IJMO: RX-7E5CC4 → ORD-599F53F7, clarification/reply and exact-variant approval, one stock deduction 4→3, synthetic delivery and prescription dispatch delivered, finance export matched. [Evidence](test-runs/2026-10-31/connected-journeys.md).**
- [x] E2E-03: Paid doctor consultation → chat → e-prescription → pharmacist approval → medicine order → completed consultation → earnings → payout/reconciliation. **Passed at recorded layers: genuine KSh 1 consultation receipt UK1I20IYUB → CONS-83F95C → clinician Rx 31 → dispensing Rx 50 → ORD-43CBF6BB, medicine receipt UK1I20J2W8. Synthetic delivery, one stock deduction 4→3 and one KSh 0.90 earning. Administrative payout PAY-25D0E1 paid/matched; no actual payout transfer executed. [Evidence](test-runs/2026-10-31/connected-journeys.md).**
- [x] E2E-04: Guardian with two children → choose one child → consent/payment → pediatric consultation → prescription → medicine order → correct child history and clinician earnings. **Passed locally with genuine sandbox payments: consultation UJUI207MTB → CONS-8AF578 / child 6 → clinician Rx 30 → dispensing Rx 48 → ORD-1DD38A84, medicine receipt UK1I20IVWS. Synthetic delivery and prescription dispatch delivered, stock 2→1 once, finance matched, one KSh 0.90 earning. [Evidence](test-runs/2026-10-31/connected-journeys.md). [Child identity checks](test-runs/2026-10-30/pediatric-journey.md).**
- [x] E2E-05: Approved lab partner/facility → patient request → collection verification → processing → result upload → patient notification/download. **Passed — Local synthetic pay-later journey passed: automated partner onboarding, live API facility approval, browser home booking/code/processing/result/completion and patient download; notification creation verified. [Evidence](test-runs/2026-10-30/lab-services.md).**
- [ ] E2E-06: Payment failure → safe retry → one paid order; cancellation/return/refund → correct stock and finance records → support resolution. **Application regression passed: 18 tests, including connected retry/refund/finance/support closure and unpaid cancellation. Live ORD-7B791366 has one genuine successful payment, stock 4→3 once, return 1 quarantined/non-resale; customer refund denied (403), premature refunded closure denied (400). Actual external refund remains unexecuted and support ticket 3 in progress, so full live completion remains pending. [Evidence](test-runs/2026-11-01/e2e06.md).**

## Completion criteria

Latest audit: **1 November 2026**. [Completion review, issue register and remaining gates](test-runs/2026-11-01/completion-review.md). [Scenario-by-scenario outcome ledger](test-runs/2026-11-01/completion-outcomes.md). These are local QA results, not a production release approval.

- [x] Every scenario has a recorded outcome; every N/A has a reason. **110 scenarios recorded: 104 passed at documented layers, 2 N/A (card/COD excluded), 3 integration-blocked, 1 partial (E2E-06).**
- [x] Failed cases have issue references and a retest result after a fix. **QA-FIX-01–09 map fixes to module reports, regression logs and browser/API retests.**
- [x] Blocked integrations and missing frontend screens are listed explicitly. **QA-OPEN-01–07 list provider/POS, refund, delivery/deployment and payment-reconciliation boundaries; no additional missing required local frontend screen is identified by the recorded module runs.**
- [ ] No unresolved duplicate charges, incorrect stock movements, wrong-patient records, or unauthorized access. **Four latest orders each have one successful payment and expected stock; child identity, consent and single earnings match. Security regressions pass. Final reconciliation remains pending for older pediatric intent 50 (requires_action, no linked booking or confirmed receipt); no duplicate charge is established.**
- [ ] Connected journeys pass with matching records across customer and staff views. **E2E-01–05 pass at recorded layers; E2E-06 awaits actual external refund and live support resolution.**
- [ ] Tester and reviewer record the final result and any accepted remaining issues. **Tester: Codex, 1 November 2026, conditional local QA result. Reviewer: pending; remaining issues have not been accepted on the user's behalf.**
