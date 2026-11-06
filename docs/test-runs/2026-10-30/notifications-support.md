# Notifications, support and site settings — 30 October 2026

All ten NOT/SUP scenarios pass at the local browser/API/automated layers recorded below. Synthetic QA accounts and content only. External mailbox receipt and real SMS delivery were not independently confirmed. The four business notification events were deliberately triggered against existing synthetic records, without creating another order, consultation, prescription or lab result.

## Notifications

| Check | Result and evidence |
| --- | --- |
| NOT-01 | Controlled prescription review, consultation-message, order-status and lab-result helpers generated notifications for **customer 75**, using prescription **46 / RX-6856F1**, consultation **34 / CONS-EE8CBC**, order **2007 / ORD-33DED1F4**, and lab request **1 / LAB-395DA4**. All four appeared in that customer's browser inbox. Email for these controlled event triggers used a local-memory backend; consultation messages retain their configured inbox/live-alert behavior. Automated tests assert intended recipient and sensitive-email redaction. This does not establish external SMTP receipt. |
| NOT-02 | Browser unread count **73 → 72 → 0**, followed by full refresh retaining 0. Notification and delivery history pagination passed in the browser, including older records. Final QA unread count is 0. Automated tests check per-user counts and prevent cross-user read/delete/mark actions. |
| NOT-03 | Browser saved email opt-out; a new **SYNTHETIC QA30 preference check** remained in the inbox with **zero external delivery records**. Browser re-enabled email; original preferences were restored after testing. Automated checks cover master email/SMS/live-alert switches, marketing opt-in, order-email opt-out, and retries after channel disablement. Required transaction-receipt rendering follows its existing separate policy, verified with a mocked sender; no payment was initiated. |
| NOT-04 | Browser links opened and expanded the correct prescription 46, consultation 34 and lab request 1; order link opened **ORD-33DED1F4**, and support link selected ticket 1. The prescription detail panel's repeated reopening bug was found through this test and fixed; closing the panel and navigating away then passed. Another user receives 404 for the notification and delivery retry. Source record APIs retain their own access controls. |
| NOT-05 | Deliberately failed delivery **169** was retried from the customer browser: **failed attempt 1 → sent attempt 2**, retaining one notification and one delivery record. The configured SMTP backend accepted the retry; external mailbox receipt is unverified. Repeating a sent delivery returns 409. Automated tests cover three-attempt limits, concurrent retries sending once, zero messages accepted by a backend, changed destinations, and business status updates surviving notification failure. Historical failed deliveries remain visible; only the labelled QA retry fixture was resent in this run. |

## Support and site settings

| Check | Result and evidence |
| --- | --- |
| SUP-01 | Customer browser created **SUP-D85A43 / ticket 1**, added a reply; staff browser opened, assigned and resolved it, with public reply and status-change history. Customer browser saw the public reply and resolution. The previously inactive contact form now creates a real ticket: browser **SUP-C72906 / ticket 2** passed, then was resolved during cleanup. Automated tests cover reopening a resolved ticket after a new customer reply. |
| SUP-02 | Staff browser saved **PRIVATE SYNTHETIC QA30 STAFF NOTE** as internal and a separate public reply. Customer browser and live customer API exclude the private note while retaining public messages. Another customer cannot read/reply/update the ticket. Internal notes no longer notify customers or place their text in browser audit storage. |
| SUP-03 | New footer form subscribed **synthetic.qa30.newsletter@avapharmacy.test** and displayed a confirmation response. Duplicate browser submission returned **You are already subscribed**; one subscriber exists. Invalid email returns 400. Automated tests cover failure without subscription rollback, reactivation and retry after a failed reactivation confirmation, normalized addresses, isolated throttling, and simultaneous duplicate signups producing one confirmation. External email receipt is unverified; the synthetic subscriber was deactivated after testing. |
| SUP-04 | Admin API temporarily changed the public support address. Browser contact page and footer displayed **SYNTHETIC QA30 local storefront visibility check — Nairobi**. The original address was restored and reappeared. Public settings use the explicit public serializer fields. Automated checks reject unauthorized/inactive-admin writes, negative delivery amounts and unsafe/malformed policy URLs. No private provider/email credentials are included in public settings. |
| SUP-05 | Admin browser uploaded and downloaded evidence **1**, labelled **SYNTHETIC QA30 training evidence — not a licence or authorization**. Download bytes match the source synthetic PDF. Requests to the actual raw media path return 404; customer protected-download access returns 403. Automated tests verify inspector read/download access with write rejection, invalid content/dates and role boundaries. The QA document is retained as review_due. No legal/accreditation claim is made. |

## Implemented fixes and missing workflows

- Added a customer inbox with search, pagination, persisted read actions, delivery preferences and delivery history/retry controls. Added account navigation and legacy notification-link handling.
- Corrected lab, support and clinician notification destinations; added automatic authorized-record expansion. Fixed the prescription query-link modal loop.
- Optional channel switches now apply to live pushes and order processing emails as well as other notices. Inbox history remains available. Marketing requires opt-in; required verification/password/transaction receipts retain their separate operational policy.
- Delivery outcomes retain timestamped attempt history. Retries are owner-scoped, row-locked, capped at three attempts and limited to failed deliveries; changed destinations and disabled channels are rejected. Order-status email delivery now has delivery records too. A backend returning zero accepted emails is treated as failure.
- Added explicit support-note visibility, privacy filtering and staff public replies. Existing administrator notes are migrated to private because the previous admin interface labelled them internal. Added status-change history, valid staff assignment checks, customer follow-up reopening, working export, and success-only client audit entries.
- Replaced the inactive contact form with authenticated ticket creation and provided guest sign-in guidance. Added a visible newsletter form with server feedback, duplicate/concurrent confirmation protection, throttling and delivery-failure handling that preserves subscription state.
- Added protected compliance downloads and an admin/inspector evidence page. Raw compliance media is denied by Django and the Apache source configurations. Public settings validate prices and policy URLs.
- Applied **support.0006_supportnote_is_internal** and **notifications.0004_alter_notification_type** locally. Hosted Apache deployment was not performed or verified.

## Verification and artifacts

- **208 automated tests passed** across support, notifications, orders, consultations, lab and payouts. Expected error messages in the log come from deliberate fault-injection/provider-failure tests. [Regression output](notifications-support/regression-tests.log).
- Original support/site readiness baseline: **13 tests passed**. [Baseline](notifications-support/baseline-tests.log).
- TypeScript/Vite production build passed. [Build output](notifications-support/frontend-build.log).
- Migration check: no missing notification/support migrations. Patch whitespace checks passed.
- [Live API evidence and cleanup](notifications-support/live-api-evidence.json).
- [Final inbox](notifications-support/notifications-complete.png), [delivery retry](notifications-support/notification-retry.png), [customer public history](notifications-support/customer-ticket.png), [staff history](notifications-support/staff-ticket.png), [newsletter duplicate](notifications-support/newsletter-duplicate.png), [temporary public setting](notifications-support/public-setting-changed.png), [restricted evidence](notifications-support/compliance-evidence.png).

Original public settings and QA customer preferences are restored. Both synthetic tickets are resolved; the QA subscriber is inactive, the QA evidence is review_due, and notification history is retained with zero unread QA notices. No real SMS, payment prompt, payout transfer or production deployment was performed. Existing provider/POS blockers and incomplete connected journeys remain unchanged.
