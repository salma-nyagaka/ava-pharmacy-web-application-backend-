# Prepare once — 28 October 2026

**All seven setup checks are complete for local testing.** This is preparation/readiness sign-off, not a claim that later module workflows or external integrations passed. The existing Products/inventory payment-confirmation and real-POS blocks remain unchanged.

| Check | Result | Evidence |
|---|---|---|
| SET-01 | Pass | Restarted frontend on port 3000; API on 8000, PostgreSQL query and Redis connection succeeded. Browser rendered current catalog results. Django checks pass and migrations are applied. Fixed Celery import shadowing and retry-command defaults; installed required Redis transport. Development now uses shared loopback Redis databases 14/15, queue `ava_local_dev`; worker and beat are running. Worker ping and actual scheduler-to-worker dispatch/execution passed. POS URLs remain unset, so the sync smoke task safely returned an empty result. |
| SET-02 | Pass | Prepared nine dedicated active accounts: two unrelated customers, admin, inventory, prescription-review pharmacist, doctor, pediatrician, verified lab partner and linked active technician. Every account passed real HTTP password login, identity verification and its role endpoint. This verifies setup access, not all dashboard interactions. |
| SET-03 | Pass | Dedicated pending doctor: inactive user, pending profile, login 401 and protected dashboard 401. Dedicated suspended doctor: suspended user/profile, login 403 and protected dashboard 403. Signed tokens did not bypass the restrictions. |
| SET-04 | Pass — rechecked existing fixtures | Two stores and six variants retain separate rows; fixture IDs/prices/quantities are recorded. The parent product remains inactive to avoid publishing test medicine. |
| SET-05 | Pass — rechecked existing fixtures | Normal, prescription-required, zero-stock, low-stock and backorder inventory fixtures exist. Prepared stock is not evidence of an order or dispensing workflow passing. |
| SET-06 | Pass | Shared synthetic prescription/result PDFs created, rendered and visually inspected; unsupported text upload prepared. Valid and expired coupons created and availability verified. Delivery-method API returns 200; configured methods and zones recorded. No clinical file upload or lab-result workflow is claimed. |
| SET-07 | Pass | Recorded prices, stock rules, delivery sources, clinician fees/commission, coupon limits, active promotions and payout-rule state. Checked example calculations below. No fee/payout policy was invented or changed. |

## Fixture and calculation baseline

- Dedicated users: `setup28.<role>@avapharmacy.test`. Exact IDs and linkage: [snapshot](setup/fixtures-and-rules.json). Generated passwords are only in `/private/tmp/ava-setup-20261028-credentials.json`, mode 0600; not in this report/repository.
- Existing catalog prefix: `E2E-QA-20261026-`, product 22365, test stores `e2e-qa-20261026-1/-2`. A=KSh 100, B=400, RX=200, ZERO/LOW/BACK=100. A stocks 50/30, B 15/10; full row details in snapshot.
- Upload fixtures: `output/pdf/qa-setup/synthetic-prescription.pdf`, `synthetic-lab-result.pdf`, `invalid-upload.txt`. PDFs visibly state SYNTHETIC QA ONLY and carry no real patient information or dispensing authority. Hashes/sizes are in snapshot.
- `SETUPQA28VALID`: 10%, minimum subtotal 100, cap 100, usage limit 5; available through 11 November 2026. `SETUPQA28EXPIRED`: expired 27 October, rejected by availability check. Both remain as explicit QA fixtures.
- Two A packs: subtotal 200; valid coupon discount 20; discounted subtotal 180.
- Explicit shipping-method ID 1 (`qa-standard`): fee 150, no free threshold, estimate 1–2 days; discounted test total 330.
- Default cart/site delivery: fee 300, free threshold 3,000; discounted test total 480, without coupon 500. Active zones: Nairobi/Kiambu/Mombasa. These are distinct configured sources: Orders testing must compare the selected method and actual checkout path rather than interchange their fees.
- Dedicated doctor and pediatrician: fee 500, commission 10%, commission amount 50, clinician net 450. Verified using the implemented earnings calculation.
- No active promotions and no `PayoutRule` records exist. This absence is recorded, not replaced with invented business policy. Later payout tests must set explicit test inputs. Verified model calculation with database write mocked: gross 500 − commission 50 − withholding 20 − deductions 10 = net 420. No payout was created or paid.

## Runtime fixes and verification

`manage.py`, WSGI/ASGI and package startup now append the apps namespace after installed packages, preventing the project's `celery.py` from shadowing the Celery library. Previously task functions silently fell back to plain functions. The retry task now invokes its management command through `call_command`, supplying parsed defaults instead of raising a missing-option error.

Development broker/result defaults use Redis DBs 14/15, with a distinct local queue; explicit environment overrides still take precedence. Production settings are not changed by the development defaults. A separate QA worker was stopped after the persistent local worker was verified.

- [Role login and restriction HTTP evidence](setup/http-role-checks.json)
- [Fixture/rules snapshot and expected totals](setup/fixtures-and-rules.json)
- [Worker ping, scheduler dispatch and result](setup/worker-check.json)
- [Worker log](setup/worker.log), [beat startup log](setup/beat.log)
- [Regression log](setup/regressions.log): **164 tests passed** across accounts, products and orders, including the new scheduled-task regression.
- Django system checks, migration readiness, dependency checks and scoped whitespace checks passed.

Worker/scheduler processes are local development services, not production deployment. The 15-minute sync and 5-minute retry intervals are configured and beat is started; the scheduler smoke explicitly dispatched a task rather than waiting 15 minutes. Real POS synchronization remains blocked as requested.

Local startup commands from backend root:

```sh
venv/bin/python manage.py runserver 127.0.0.1:8000
venv/bin/python -m celery -A avapharmacy worker --pool=solo -Q ava_local_dev --hostname=ava-local-dev@localhost
venv/bin/python -m celery -A avapharmacy beat --schedule=/private/tmp/ava-local-dev-celerybeat
```

Do not start duplicate workers or beat processes while these instances run. The frontend was restarted on port 3000 using its existing API configuration. Existing unrelated records/settings were preserved; newly prepared synthetic fixtures remain for the next module.
