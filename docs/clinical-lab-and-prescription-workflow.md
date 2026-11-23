# Clinical lab orders, prescriptions, and fulfilment

Lab requests are created only by the verified treating doctor or paediatrician from an in-progress or completed consultation. The API derives the patient account and identifying details from that consultation. A clinician selects a test and an approved partner offering that test and collection method. The partner receives a notification immediately and chooses its approved laboratory and active technician. Customers cannot create requests; they can pay, track progress, cancel eligible requests, and view results from their account.

Home collections retain the collection-fee, AVA rider/collection-verification, dispatch, laboratory receipt, and test-payment controls. For a patient visiting the laboratory, the partner records sample receipt directly without an AVA dispatch. New clinician orders require test payment before the assigned technician starts processing. Only a processing request can receive a published result. Reports are accessible through authenticated, object-scoped downloads to the patient, assigned partner, treating clinician, assigned technician, and overseeing admin.

Public product browsing omits prescription variants. Search results and the prescription product selector include eligible prescription variants. Prescription uploads require a selected prescription product and exact variant. Existing catalogue regulatory restrictions still apply.

Pharmacists enter medication route, patient instructions, patient-facing notes, and optional refill intervals in days or calendar months. Approval schedules the first reminder. Reminders prompt the patient to contact the pharmacy; they do not authorize dispensing, create an order, or bypass prescription validity. Expired prescriptions stop receiving refill reminders.

Pharmacists process, dispatch, and complete product orders. Administrators retain order visibility, staff notes, cancellations, refunds, and oversight. Store pickup is quoted without shipping fees in the backend and checkout. Settled payment totals are preserved.

## Scheduled notifications

`apps.notifications.tasks.send_clinical_and_stock_reminders` is registered in Celery Beat every five minutes. It sends due refill reminders and in-app low-stock alerts to active administrators. A low-stock alert is sent once per stock record until inventory is replenished above its threshold, after which a later drop triggers another alert. Polling catches bulk POS inventory updates.

Run the configured Celery worker and Beat processes with the application's normal environment:

```sh
celery -A avapharmacy worker --loglevel=info
celery -A avapharmacy beat --loglevel=info
```

For cron-based deployments, run this command every five minutes instead of the Beat schedule:

```sh
python3 manage.py send_workflow_reminders
```

The command and task share the same locking and duplicate-suppression logic. Tests use synthetic accounts and an isolated cache, and do not send real patient messages.
