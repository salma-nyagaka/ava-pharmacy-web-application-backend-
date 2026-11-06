# Fixed consultation split — 6 November 2026

For new doctor and pediatrician consultations:

- Patient pays KSh 1,500.
- Clinician receives KSh 1,000 per fully paid consultation.
- AVA Pharmacy receives KSh 500.
- No percentage commission is deducted from new consultations.

The profile fee is fixed to KES 1,500. New consultation records snapshot the agreed total and clinician share. A payment below the agreed total does not generate the clinician earning. New payment intents carry a server-generated pricing-version marker. Historical consultations and payments initiated before the change retain legacy earnings treatment. Existing recorded earnings and payment amounts are not rewritten.

Registration, onboarding, clinician administration and activation emails show the fixed split. Percentage editing controls are removed; the legacy commission field remains stored for historical agreement calculations.

Migrations: consultations.0021 and 0022. Backend pricing and workflow regression checks passed, alongside frontend production build and Django checks.

# User cleanup

Requested keepers: IDs 89 and 90. Deleted IDs: 28, 91, 92. ID 93 could not be hard-deleted because its clinical audit references are protected by the database's append-only guard. Its login was disabled, password made unusable, and refresh tokens revoked. Only IDs 89 and 90 remain active. No audit protection was disabled. Full recovery copies and cleanup details are stored with restricted permissions under the git-ignored .local-backups directory.
