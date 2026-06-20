# Customer-Doctor Consultation Flow and Pediatrician Extension

This document explains the current customer-to-doctor consultation flow and how to reuse it for pediatrician consultations. The main pediatrician difference is that the logged-in customer acts as the guardian, while the real patient is a child profile owned by that guardian. One guardian must be able to register more than one child.

## Current Customer-Doctor Flow

Core backend files:

- `avapharmacy/apps/consultations/models.py`
- `avapharmacy/apps/consultations/serializers.py`
- `avapharmacy/apps/consultations/views.py`
- `avapharmacy/apps/consultations/urls.py`
- `avapharmacy/apps/accounts/permissions.py`

### 1. Doctor profile setup

Doctors are stored in `ClinicianProfile` with `provider_type='doctor'`. Pediatricians already use the same model with `provider_type='pediatrician'`.

Admin or public onboarding creates a pending profile, then admin verification activates it. A clinician can receive consultations only when:

- `ClinicianProfile.status == active`
- linked user exists and is active, when applicable
- linked user status is `active`

Important endpoints:

| Action | Endpoint |
| --- | --- |
| List active doctors | `GET /api/doctors/` |
| View one doctor | `GET /api/doctors/<id>/` |
| Public doctor onboarding | `POST /api/doctors/register/` |
| Admin doctor review | `GET/PATCH /api/admin/doctors/<id>/` |
| Provision doctor account | `POST /api/admin/doctors/<id>/provision-account/` |

### 2. Customer starts a consultation

The customer must be authenticated. The customer selects a doctor, enters symptoms, and starts the payment process before the chat is created.

Current consultation input fields include:

- `doctor`
- `patient_name`
- `patient_email`
- `patient_phone`
- `patient_age`
- `issue`
- `requested_specialty`
- `priority`
- `scheduled_at`

If the customer does not select a specific doctor, the serializer can auto-route to an open doctor queue by specialty. In that case the consultation is created with `clinician = null` and is claimed by an eligible doctor later.

### 3. Payment gate

Doctor consultations are payment-gated. `POST /api/consultations/` returns `402 Payment Required` unless a successful payment intent is supplied.

Payment flow:

1. Customer posts consultation details to `POST /api/consultations/payments/intents/`.
2. Backend validates the selected active clinician.
3. Backend creates `ConsultationPaymentIntent` with the consultation payload stored in `consultation_payload`.
4. Customer pays through M-Pesa STK or Paybill.
5. Backend marks the intent `succeeded` after callback or status sync.
6. Customer finalizes with `POST /api/consultations/payments/finalize/`, or status sync finalizes automatically.
7. Backend creates the actual `Consultation` record and links it to the payment intent.

Important endpoints:

| Action | Endpoint |
| --- | --- |
| Create consultation payment intent | `POST /api/consultations/payments/intents/` |
| Sync payment intent | `POST /api/consultations/payments/intents/<id>/sync/` |
| Finalize after payment | `POST /api/consultations/payments/finalize/` |
| M-Pesa callback | `POST /api/consultations/payments/mpesa/callback/` |

### 4. Consultation creation and notification

The final `Consultation` stores:

- `clinician`: assigned doctor profile, or null for open doctor queue
- `patient`: logged-in customer user
- patient contact snapshot fields
- `issue`, `status`, `priority`, `channel`, and timestamps

After creation, the backend notifies the assigned doctor or eligible doctors in the open queue.

Consultation statuses:

- `waiting`
- `in_progress`
- `completed`
- `cancelled`

### 5. Doctor dashboard and queue

Doctor dashboard summary:

- `GET /api/doctor/dashboard/`

Doctor queue:

- `GET /api/doctor/consultations/`

For normal doctors, the queue contains:

- consultations assigned to that doctor
- unassigned non-pediatric consultations that match the doctor's specialty
- unassigned non-pediatric fallback consultations when no specialist match exists

Open queue records show limited patient information until a doctor claims or opens the consultation.

### 6. Chat and attachments

Messages are attached to a consultation. A participant can be:

- the patient/customer
- the assigned doctor
- an eligible doctor for an unassigned open consultation
- an admin

Important endpoints:

| Action | Endpoint |
| --- | --- |
| Consultation detail | `GET/PATCH /api/consultations/<id>/` |
| List or send messages | `GET/POST /api/consultations/<id>/messages/` |
| Download protected attachment | `GET /api/consultations/messages/<message_id>/attachment/` |

Sending a message:

1. Backend validates the requester is allowed to access the consultation.
2. If an eligible doctor sends on an unassigned consultation, the backend assigns that doctor and moves status to `in_progress`.
3. Backend saves `ConsultationMessage`.
4. Backend updates `last_message_at`.
5. Backend creates a notification for the other participant.
6. Backend broadcasts a websocket event to `consultation_<id>`.

### 7. Doctor prescription flow

Doctors create consultation prescriptions in `ClinicianPrescription`.

Important endpoints:

| Action | Endpoint |
| --- | --- |
| Search catalog variants | `GET /api/doctor/catalog/variants/` |
| Create/list prescriptions | `GET/POST /api/doctor/prescriptions/` |
| Send prescription | `POST /api/doctor/prescriptions/<id>/send/` |
| Download PDF | `GET /api/doctor/prescriptions/<id>/pdf/` |

Prescription flow:

1. Doctor creates a draft prescription linked to a consultation.
2. Items must be catalog variants or explicit non-catalog fallback items.
3. If a draft already exists for the same consultation and has not been paid for, posting again edits the same prescription.
4. Doctor sends the prescription.
5. Backend converts it into the pharmacy dispensing `Prescription`.
6. Backend creates dispensing items.
7. Pharmacists are notified to review the prescription before checkout.
8. Patient is notified that a new e-prescription is available.

### 8. End consultation and earnings

Doctor ends the consultation with:

- `POST /api/consultations/<id>/end/`

The backend:

- changes status to `completed`
- sets `ended_at`
- writes an audit log
- creates `ClinicianEarning` once for that consultation
- notifies the patient
- broadcasts a status-changed websocket event

## Existing Pediatrician Support

The backend already has partial pediatrician support:

- `ClinicianProfile.provider_type='pediatrician'`
- public pediatrician listing and detail endpoints
- pediatrician onboarding endpoint
- pediatrician dashboard endpoint
- pediatrician prescriptions and earnings endpoints
- pediatric-specific fields on `Consultation`

Current pediatrician fields stored directly on `Consultation`:

- `is_pediatric`
- `guardian_name`
- `child_name`
- `child_age`
- `weight_kg`
- `consent_status`
- `dosage_alert`

Important current pediatrician endpoints:

| Action | Endpoint |
| --- | --- |
| List pediatricians | `GET /api/pediatricians/` |
| View pediatrician | `GET /api/pediatricians/<id>/` |
| Public pediatrician onboarding | `POST /api/professionals/register/pediatrician/` |
| Pediatrician dashboard | `GET /api/pediatrician/dashboard/` |
| Pediatrician prescriptions | `GET/POST /api/pediatrician/prescriptions/` |
| Pediatrician earnings | `GET /api/pediatrician/earnings/` |
| Guardian consent | `POST /api/consultations/<id>/consent/` |

Current limitation: child and guardian data is copied into every consultation as plain fields. There is no reusable child patient record, so one guardian cannot manage multiple registered child profiles cleanly, and the pediatrician dashboard cannot show a proper child profile page.

## Target Pediatrician Flow

Use the same payment, chat, prescription, completion, audit, notification, and earnings flow as the doctor module. Add a child registration step before booking the pediatrician consultation.

### Customer/guardian side

1. Guardian logs in as a normal `customer`.
2. Guardian opens "My Children" or "Child Patients".
3. Guardian creates one or more child profiles.
4. Guardian selects a child when booking a pediatrician.
5. Guardian selects a pediatrician and enters symptoms.
6. Backend creates a consultation payment intent using the pediatrician consult fee.
7. After payment succeeds, backend creates the pediatric consultation.
8. Guardian grants consent if it was not already captured during booking.
9. Guardian chats with the pediatrician on behalf of the child.
10. Guardian receives prescription and checkout notifications.

### Pediatrician side

1. Pediatrician logs in with role `pediatrician`.
2. Dashboard loads pediatrician stats and assigned pediatric consultations.
3. Pediatrician opens a consultation.
4. Consultation detail shows:
   - guardian information
   - child information
   - symptoms
   - consent status
   - weight and dosage alert fields
   - previous pediatric consultations for the same child
5. Pediatrician chats, creates prescription, sends it for pharmacist review, and ends the consultation.
6. Pediatrician can open a dedicated child/guardian info page from the dashboard.

## Required Data Model Changes

Add a reusable child patient model. Keep `Consultation.patient` as the guardian user for permissions and notifications.

Recommended model:

```python
class ChildPatient(models.Model):
    guardian = models.ForeignKey(
        'accounts.User',
        on_delete=models.CASCADE,
        related_name='child_patients',
    )
    reference = models.CharField(max_length=20, unique=True, blank=True)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    age_years = models.PositiveIntegerField(null=True, blank=True)
    gender = models.CharField(max_length=20, blank=True)
    weight_kg = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    allergies = models.JSONField(default=list, blank=True)
    chronic_conditions = models.JSONField(default=list, blank=True)
    current_medications = models.JSONField(default=list, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
```

Recommended `Consultation` additions:

```python
child_patient = models.ForeignKey(
    'consultations.ChildPatient',
    on_delete=models.SET_NULL,
    null=True,
    blank=True,
    related_name='consultations',
)
guardian_snapshot = models.JSONField(default=dict, blank=True)
child_snapshot = models.JSONField(default=dict, blank=True)
```

Why use snapshots:

- The child profile can change later.
- Old consultations and prescriptions should preserve the child's details at the time of care.
- Existing inline fields can remain during migration for backward compatibility.

## Required API Additions

Guardian child management:

| Action | Endpoint |
| --- | --- |
| List guardian's children | `GET /api/guardian/children/` |
| Create child profile | `POST /api/guardian/children/` |
| View child profile | `GET /api/guardian/children/<id>/` |
| Update child profile | `PATCH /api/guardian/children/<id>/` |
| Archive/delete child profile | `DELETE /api/guardian/children/<id>/` |

Pediatrician child/guardian pages:

| Action | Endpoint |
| --- | --- |
| Pediatrician consultations | `GET /api/pediatrician/consultations/` |
| Child/guardian list for assigned consultations | `GET /api/pediatrician/patients/` |
| Child/guardian detail | `GET /api/pediatrician/patients/<child_id>/` |

The child detail response should include:

- child profile
- guardian user summary
- active consultation with this pediatrician, if any
- previous consultations with this pediatrician
- prescription summaries
- consent status from the current consultation

## Pediatric Consultation Creation Rules

When `pediatrician` is supplied:

- force `is_pediatric = true`
- require `child_patient_id`
- validate `child_patient.guardian == request.user`
- set `patient = request.user`
- copy guardian details into `guardian_snapshot`
- copy child details into `child_snapshot`
- keep `guardian_name`, `child_name`, `child_age`, and `weight_kg` populated for compatibility
- set `consent_status = granted` if consent checkbox is submitted during booking, otherwise `pending`

The payment intent must store `child_patient_id` in `consultation_payload` so finalization creates the consultation for the same child after payment succeeds.

## Pediatrician Dashboard Requirements

Extend `GET /api/pediatrician/dashboard/` or add companion endpoints so the frontend can show:

- total pediatric consultations today
- waiting consultations
- in-progress consultations
- completed consultations this month
- consent pending count
- dosage alert count
- monthly earnings
- recent pediatric consultations
- recent child patients
- child/guardian detail link per consultation

The dashboard page should not rely only on `child_name` strings. It should use `child_patient.id` so the pediatrician can open a stable child profile.

## Permissions

Guardian:

- can create, view, update, and archive only their own child profiles
- can create pediatric consultations only for their own child profiles
- can view pediatric consultations where `Consultation.patient == guardian`

Pediatrician:

- can view only pediatric consultations assigned to their own `ClinicianProfile`
- can view child/guardian details only when that child has at least one consultation assigned to that pediatrician
- can prescribe only inside assigned consultations

Admin:

- can view all child profiles and pediatric consultations for support/audit

## Implementation Checklist

1. Add `ChildPatient` model and migration.
2. Add `child_patient`, `guardian_snapshot`, and `child_snapshot` to `Consultation`.
3. Add child serializers and guardian child CRUD views.
4. Update `ConsultationCreateSerializer` to require and validate `child_patient_id` for pediatrician bookings.
5. Update payment intent creation/finalization to preserve `child_patient_id`.
6. Update pediatrician dashboard serializers to return child and guardian summaries.
7. Add pediatrician patient list/detail endpoints.
8. Update prescription creation so pediatric prescriptions display the child name, while checkout and notifications still use the guardian user.
9. Add tests for:
   - guardian with multiple children
   - guardian cannot book for another guardian's child
   - pediatrician can see assigned child/guardian info
   - pediatrician cannot see unrelated child profiles
   - payment finalization preserves the selected child
   - prescription uses child name in pediatric context

## Recommended Frontend Pages

Guardian/customer:

- `My Children`: list all child profiles owned by the guardian.
- `Add/Edit Child`: collect child demographics, weight, allergies, conditions, medications, and notes.
- `Book Pediatrician`: select child first, then pediatrician, then symptoms and payment.

Pediatrician:

- `Pediatrician Dashboard`: stats, queue, recent consultations, consent alerts, dosage alerts.
- `Patients`: children seen by this pediatrician, grouped by guardian.
- `Patient Detail`: child details, guardian contact, consultation history, prescriptions, and current consent state.

## Key Decision

Do not create a separate pediatrician consultation system. Reuse the existing consultation, payment, chat, prescription, notification, audit, and earnings infrastructure. Add the missing child profile layer and pediatrician dashboard views on top of it.
