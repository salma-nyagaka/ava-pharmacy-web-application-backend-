# Sequential manual acceptance run

Started 4 November 2026. Tester: user, guided by Codex. Results start unverified; previous automated/API/browser passes do not carry into this run.

## Starting assumption

Treat this as a newly installed website with only the initial bootstrap administrator. No products, categories, brands, stores, stock, customers, professional applications, bookings, orders or financial transactions are assumed prepared. A real fresh installation still requires migrations and one bootstrap administrator before website admin login can work.

Existing local records have not been deleted or reset. If records are present, record the baseline and use new clearly labelled manual-run records. A logically fresh workflow is not proof of empty-database behavior; actual fresh-database testing requires a separate isolated database/environment.

## Working agreement

Proceed one small step at a time. The user operates the website and reports the visible result. Codex records confirmed results, investigates failures when requested/necessary, and provides the next step. Do not bulk-seed records or perform subsequent setup ahead of the user. A described expectation is not a passed test. New passwords/PINs remain with the user.

## Dependency order

| Phase | Work | State |
|---|---|---|
| A | Bootstrap admin login, dashboard and actual empty-state baseline | Current; not yet verified |
| B | Essential public/business/support settings and delivery configuration | Not started |
| C | Staff accounts/permissions needed for later handoffs | Not started |
| D | Catalog structure: stores/locations, brands, categories/subcategories | Not started |
| E | Products, exact variants, images/descriptions, prices and stock | Not started |
| F | Storefront content, offers/coupons and catalog checks | Not started |
| G | New customer registration, verification, profile, addresses and cart | Not started |
| H | Payment, order, inventory, fulfillment, cancellation/return and finance | Not started |
| I | Prescription upload, pharmacist decisions and medicine purchase | Not started |
| J | Professional onboarding/approval, doctor and pediatric journeys | Not started |
| K | Lab partner/facility/test/technician setup and patient result journey | Not started |
| L | Earnings/payout ledger, notifications, support/compliance, mobile and final reconciliation | Not started |

Create dependencies through the available website workflows. If a setup screen is absent, record a UI gap and agree the technical handoff; do not silently substitute direct database creation as a website pass. Approval workflows are tested when professionals apply; staff setup does not pre-approve applications.

## A01 - Sign in as the initial administrator

- [ ] Open the agreed test website, then `/login`.
- [ ] Enter the initial administrator email/password yourself and sign in once.
- [ ] Verify the displayed account belongs to the intended administrator.
- [ ] Open `/admin/dashboard` if login does not take you there automatically.
- [ ] Refresh the dashboard once.

Expected: administrator workspace remains accessible after refresh, with correct identity, usable navigation and no permission/connection error. In a genuinely empty environment, totals/recent lists should represent no business records; defaults and the bootstrap admin itself may exist. If data exists, record it without deleting it.

Result: Awaiting user's observed result.

Evidence / visible message: ______

Next after A01 passes: inspect dashboard and empty list states, then configure essential settings. Do not create catalog or transactions before that baseline is recorded.

## Issues and decisions

| Step | Expected | Observed | Result | Issue / retest |
|---|---|---|---|---|
| A01 | Admin login/dashboard persists after refresh | Awaiting user | Not tested | — |
