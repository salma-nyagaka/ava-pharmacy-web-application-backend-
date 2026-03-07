# AVA Pharmacy Registration Implementation

This document reflects the current backend implementation as of March 5, 2026.

Base URL used below:

- `http://127.0.0.1:8000/avapharmacy/api/v1`

## 1. What Is Implemented

- Unified professional registration flow for:
  - doctor
  - pediatrician
  - lab_partner
  - lab_technician
- Dedicated registration endpoints per profession.
- Admin review endpoints to approve/request docs/reject (with rejection reason).
- Admin provisioning of approved applications into real login users.
- Admin pharmacist creation + activation email + resend activation.
- Separate tables for customers and pharmacists.
- Audit fields on registration/application tables (`created_at`, `updated_at`, `created_by`, `updated_by`).

## 2. Response Format (Current Behavior)

Responses are not yet globally wrapped in a single `detail/data/errors` envelope.

- Professional unified registration returns:
  - `detail`
  - `registration_type`
  - `registration_type_display`
  - `application`
  - `next_steps`
- Other endpoints return either serializer objects directly or standard DRF validation errors.

## 3. Public Registration Endpoints

No token required.

### 3.1 Unified professional registration

- `POST /professionals/register/`
- Content-Type: `application/json` or `multipart/form-data`

Allowed `type`:

- `doctor`
- `pediatrician` (alias `paediatrician`)
- `lab_partner`
- `lab_technician`

Doctor example payload:

```json
{
  "type": "doctor",
  "name": "Dr. James Kariuki",
  "email": "doctor.james@example.com",
  "phone": "0711002200",
  "license": "KMPDC-12345",
  "licenseBoard": "KMPDC",
  "licenseCountry": "Kenya",
  "licenseExpiry": "2027-12-31",
  "idNumber": "12345678",
  "specialty": "General Medicine",
  "facility": "Aga Khan Hospital",
  "experience": 6,
  "availability": "Mon-Fri 8:00-17:00",
  "fee": "1500.00",
  "county": "Nairobi",
  "address": "3rd Floor, Block A",
  "bio": "General physician with telemedicine experience.",
  "languages": ["English", "Swahili"],
  "consultModes": ["chat", "video"],
  "payoutMethod": "mpesa",
  "payoutAccount": "254711002200",
  "backgroundConsent": true,
  "complianceDeclaration": true,
  "agreedToTerms": true
}
```

### 3.2 Dedicated registration endpoints

- `POST /professionals/register/doctor/`
- `POST /professionals/register/pediatrician/`
- `POST /professionals/register/lab-partner/`
- `POST /professionals/register/lab-technician/`

### 3.3 Lab partner options for lab technician registration

- `GET /professionals/lab-partners/`

Returns verified lab partners for `labPartnerId` selection.

## 4. Admin Review and Approval Flow

Auth: Admin JWT (`Authorization: Bearer <access_token>`).

### 4.1 List and detail

- Doctors:
  - `GET /admin/doctors/`
  - `GET /admin/doctors/{id}/`
- Pediatricians:
  - `GET /admin/pediatricians/`
  - `GET /admin/pediatricians/{id}/`
- Lab partners:
  - `GET /admin/lab/partners/`
  - `GET /admin/lab/partners/{id}/`
- Lab technicians:
  - `GET /admin/lab/partners/{partner_id}/technicians/`
  - `GET /admin/lab/technicians/{id}/`

### 4.2 Action endpoints

- Doctor: `POST /admin/doctors/{id}/action/`
  - actions: `approve`, `request_docs`, `reject`
- Pediatrician: `POST /admin/pediatricians/{id}/action/`
  - actions: `approve`, `request_docs`, `reject`
- Lab partner: `POST /admin/lab/partners/{id}/action/`
  - actions: `verify`, `request_docs`, `reject`, `suspend`
- Lab technician: `POST /admin/lab/technicians/{id}/action/`
  - actions: `approve`, `request_docs`, `reject`

Rejection payload:

```json
{
  "action": "reject",
  "note": "License document is expired."
}
```

`note` is required for `reject` (and for `request_docs` on lab endpoints).

## 5. Provision Approved Applications to Real User Accounts

Auth: Admin JWT.

- Doctor: `POST /admin/doctors/{id}/provision-account/`
- Pediatrician: `POST /admin/pediatricians/{id}/provision-account/`
- Lab partner: `POST /admin/lab/partners/{id}/provision-account/`
- Lab technician: `POST /admin/lab/technicians/{id}/provision-account/`

Payload (optional):

```json
{
  "password": "StrongPass@123"
}
```

If `password` is omitted, a temporary password is generated and returned.

## 6. Pharmacist Creation and Activation (Admin-Driven)

### 6.1 Create pharmacist

- `POST /admin/users/`
- role must be `pharmacist`

Example:

```json
{
  "email": "pharmacist.one@avapharmacy.com",
  "first_name": "Jane",
  "last_name": "Mwangi",
  "phone": "0711006600",
  "role": "pharmacist",
  "address": "Nairobi",
  "pharmacist_permissions": [
    "prescription.review",
    "inventory.adjust",
    "orders.dispense"
  ]
}
```

Pharmacist user is created inactive until activation.

### 6.2 Resend activation

- `POST /admin/users/{id}/resend-activation/`

### 6.3 Set password from activation token

- `POST /auth/pharmacist/activate/`

```json
{
  "token": "activation-token-from-email-link",
  "new_password": "StrongPass@123",
  "new_password_confirm": "StrongPass@123"
}
```

Browser fallback page:

- `GET/POST /auth/pharmacist/activate/{token}/`

## 7. User Registration and Login Endpoints

- Customer/self-registration: `POST /auth/register/`
- Login: `POST /auth/login/`
- Refresh token: `POST /auth/token/refresh/`
- Logout: `POST /auth/logout/`

## 8. Database Tables (Registration Related)

### 8.1 Core users and profiles

- `accounts_user` (all auth users)
- `accounts_customer` (customer-only profile, 1:1 to user)
- `accounts_pharmacist` (pharmacist-only profile, 1:1 to user)

### 8.2 Professional applications

- `consultations_doctorprofile`
- `consultations_pediatricianprofile`
- `lab_labpartner`
- `lab_labtechnicianprofile`

These store onboarding applications before/while being linked to real user accounts.

## 9. Audit Fields Added

The following registration-related models now include audit ownership/timestamps:

- `accounts.Pharmacist`
- `accounts.Customer`
- `consultations.DoctorProfile`
- `consultations.PediatricianProfile`
- `lab.LabPartner`
- `lab.LabTechnicianProfile`

Fields:

- `created_at`
- `updated_at`
- `created_by` (nullable FK to `accounts_user`)
- `updated_by` (nullable FK to `accounts_user`)
