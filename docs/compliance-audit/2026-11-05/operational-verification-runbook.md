# Operational verification still required

5 November 2026. This is an owner handover, not completed certification. Do not fill missing fields with invented values or mark simulations as genuine evidence.

## 1. Superintendent and regulatory owner

- [ ] Verify current premises and online pharmacy authorization, registered superintendent and scope of professional services.
- [ ] Populate actual safety code, registration/licence numbers, superintendent identity/registration, postal address and pharmacist consultation hours in Settings. Verify PPB contact and verification links.
- [ ] Verify each professional's actual registration, Kenyan practice eligibility, expiry, competence and permitted responsibilities. Application role assignment is insufficient evidence of qualification.
- [ ] Review medicine/non-medicine classifications, controlled/high-risk medicines, PPB registration/retention, authorized suppliers and actual batch/expiry records.
- [ ] Review PIL sources, contraindications, adverse effects, directions and storage limits for every medicine. Do not substitute scraped copy for authoritative professional review.
- [ ] Approve OTC questions, triage thresholds, interactions/red flags, guardian checks, suitability/refusal/referral and actual counselling procedures.
- [ ] Supply an approved current Kenyan holiday calendar using `KENYA_PUBLIC_HOLIDAYS` (comma-separated ISO dates). Confirm original-prescription and newer electronic-prescription handling with PPB.
- [ ] Approve and exercise delivery, recipient verification, temperature monitoring, failed delivery, returns/non-resale, complaints and recall procedures.

## 2. Privacy and infrastructure owners

- [ ] Verify ODPC registration, legal controller identity, processing register/lawful bases, minimization, processors/SLAs, data-subject notices/response deadlines and retention/legal holds.
- [ ] Verify approved hosting/data location, at-rest/transit protection, certificate requirements and private media delivery on the actual host. Source-code settings do not prove the deployed controls.
- [ ] Use separate migration/owner and restricted runtime database credentials. The runtime must not own protected tables or have DDL/TRUNCATE/trigger-disabling powers. Verify private-file backup/retention and storage-admin access separately.
- [ ] Supply actual public HTTPS URLs, strong secret management, allowed origins, CAPTCHA configuration and renewal/monitoring arrangements. Never commit secrets or certificate private keys.
- [ ] Review the final privacy notice against actual arrangements and approve written retention/disposal and rights-request procedures.

## 3. Daily encrypted backups and restore drill

The `backup_pharmacy` command requires approved versions of `pg_dump`, `age` and `rclone`. Provision and validate them on the target host. Public encryption recipients belong on the backup host; private decryption keys require separate protected custody. Offsite credentials and storage location/retention must be approved.

```sh
venv/bin/python manage.py backup_pharmacy \
  --output-dir /approved/protected/encrypted-backups \
  --recipients-file /approved/config/backup-public-recipients.txt \
  --offsite approved-offsite:pharmacy-backups
```

The command includes PostgreSQL and media, uses a restricted temporary directory, encrypts the archive, copies it offsite and checks the encrypted copy. It fails when required tools/copy verification fail. It never reports a restore as tested. It does not automatically schedule itself, provision storage, verify hosting jurisdiction or establish fire protection.

- [ ] Schedule at least daily execution using the approved scheduler/service account and monitor every success/failure and missing run.
- [ ] Verify offsite access controls, geography, durability, fire separation, immutability and retention.
- [ ] Restore into a **separate isolated database and media root** on an approved host, never over the live system. Verify database integrity, private-file readability, record totals, application permissions and representative clinical/order history.
- [ ] Record timestamps, archive integrity, responsible operator, recovery times, findings and corrective actions. Upload genuine backup/restore evidence and obtain independent review.
- [ ] Test notification delivery retry separately. `dispatch_recall_notifications` retries only unqueued notifications for open recalls; it can send real customer notifications when run on real data. Do not use real patients for a QA drill.

## 4. Management QA and inspector evidence

- [ ] Schedule and complete each of the twelve 12.1(a–l) areas: personnel; communications; professional services; receiving prescriptions; dispensing; secure delivery; documentation; IT validation; security/confidentiality; website information; feedback; complaints.
- [ ] Add actual staffing/training, equipment calibration/maintenance, continuity/capacity and disruption evidence.
- [ ] Upload documents with genuine issue/expiry or review dates. A different administrator must verify them with an external/reference check. Editing evidence clears that verification.
- [ ] Complete a synthetic recall drill, delivery excursion drill, overdue-original drill and privacy-request exercise, then attach signed findings/corrective actions.
- [ ] Demonstrate read-only inspector access and protected document downloads. Provide PPB any required website/API details and inspector credentials through approved secure channels.

## 5. Release gates

Run these against the real candidate deployment with production settings and genuine evidence:

```sh
DJANGO_SETTINGS_MODULE=avapharmacy.settings.production venv/bin/python manage.py check --deploy --fail-level ERROR
DJANGO_SETTINGS_MODULE=avapharmacy.settings.production venv/bin/python manage.py check_pharmacy_readiness
```

Deployment scripts now require readiness before Apache reload. They were edited but **not executed** in this work. Use a controlled migration/maintenance plan; test rollback against a copy. Restrictive schema/data defaults intentionally hold unreviewed inventory. Do not bypass the gates to make a demonstration pass.

- [ ] Resolve all reported errors and assess warnings, including schema generic/type warnings before relying on generated clients.
- [ ] Verify the actual host, TLS, private files, backups and restored application.
- [ ] Obtain superintendent, privacy/infrastructure owner and required regulator sign-off. Keep operational items pending until demonstrated.
