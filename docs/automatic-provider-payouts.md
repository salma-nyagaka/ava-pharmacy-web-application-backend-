# Automatic provider payouts

Finishing a doctor or pediatrician consultation creates one payout from its existing earning and customer payment. Completing a lab request creates a payout for each assigned, linked recipient with a nonzero share. Rows appear under Admin → Payouts, linked to the consultation or lab request reference. Repeated completion requests do not create duplicates.

## Lab agreements

Use Admin → Payouts → Lab agreements to configure a partner's lab, technician and AVA percentages. All three must be nonnegative and total 100%. No commercial percentages are assumed by default.

Shares use the booked test price, not the current catalogue price. The agreement and calculated amounts are captured at completion (or first release if no agreement existed), and remain fixed even if the agreement or catalogue changes later. Provider shares round to cents; AVA receives the remaining amount so the allocation always totals the booked fee.

Missing agreements or booked prices create held records. Configure the agreement, confirm the customer payment, and use Release hold. Missing linked lab accounts or technicians for allocated shares also require resolution before payment approval. The assigned technician and lab partner receive separate rows; AVA's retained share appears in the allocation audit metadata.

## Admin workflow

Automatic records start Pending, or On hold when requirements are missing. An active finance admin approves the pending record, makes the payment using the bank or M-Pesa, and selects Record payment to enter its reference. The application records the payment; it does not initiate a transfer. Existing maker-checker controls remain for manually created adjustments. Automatic rows have a system creator, so an admin can approve them.

The customer payment and completed source are checked again at release, approval, processing and payment recording. Clinical completion and payout creation share a transaction, so a failed record creation cannot silently lose a payable item. Opening or refreshing Admin → Payouts synchronizes historical completed doctor and pediatrician consultations into the queue. Each completed consultation has one row per clinician; waiting, ongoing and cancelled consultations are excluded. Existing payouts and paid records are preserved. Missing historical earnings are recovered only from recorded fixed consultation shares; where those terms are absent the payout stays on hold for review.

## Deployment

Apply the additive migrations with `python manage.py migrate`, then deploy the backend and frontend. Configure real lab agreement percentages before completing new lab work. No existing paid payout amounts are recalculated.

API endpoints (finance admins only):

- `POST /admin/payouts/sync-consultations/` (called before loading the table)
- `GET/POST /admin/lab-revenue-agreements/`
- `GET/PATCH /admin/lab-revenue-agreements/{id}/`

The existing `/admin/payouts/` and payout action endpoints provide the table, approval and payment recording.
