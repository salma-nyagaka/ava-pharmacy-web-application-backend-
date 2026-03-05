# AVA Pharmacy Backend Registration Documentation

## 1. Current Scope Implemented

This document covers what is implemented so far for:

- Professional registration by profession.
- Admin provisioning of approved professional applications into real user accounts.
- Pharmacist registration by admin (separate pharmacist table).

Base API prefix used in examples:

- `http://127.0.0.1:8000/avapharmacy/api/v1`


## 2. Standard API Response Format

All non-callback JSON API responses are standardized to:

```json
{
  "detail": "Request successful.",
  "data": {},
  "errors": null
}
```

Validation/error responses:

```json
{
  "detail": "Request validation failed.",
  "data": null,
  "errors": {
    "code": "validation_error",
    "details": {
      "field_name": ["error message"]
    }
  }
}
```


## 3. Public Professional Registration

## 3.1 Unified Endpoint (Recommended)

- Method: `POST`
- URL: `/avapharmacy/api/v1/professionals/register/`
- Auth: No token required
- Content-Type: `application/json` or `multipart/form-data`

`type` controls profession:

- `doctor`
- `pediatrician` (also accepts `paediatrician`)
- `lab_partner`
- `lab_technician`

Core fields used across professions:

- `type`, `name`, `email`, `phone`
- `payoutMethod` (`mpesa` or `bank_transfer`)
- `payoutAccount`
- `backgroundConsent` (boolean)
- `complianceDeclaration` (boolean)
- `agreedToTerms` (boolean)

### Doctor payload example

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

### Pediatrician payload example

```json
{
  "type": "pediatrician",
  "name": "Dr. Amina Hassan",
  "email": "pedi.aminah@example.com",
  "phone": "0711003300",
  "license": "KMPDC-67890",
  "licenseBoard": "KMPDC",
  "licenseCountry": "Kenya",
  "licenseExpiry": "2028-05-30",
  "idNumber": "98765432",
  "specialty": "Pediatrics",
  "facility": "Nairobi Hospital",
  "experience": 8,
  "availability": "Mon-Sat 9:00-16:00",
  "fee": "1200.00",
  "county": "Nairobi",
  "address": "Children Wing",
  "bio": "Pediatric specialist focused on early-child care.",
  "languages": ["English", "Swahili"],
  "consultModes": ["chat", "video"],
  "payoutMethod": "mpesa",
  "payoutAccount": "254711003300",
  "backgroundConsent": true,
  "complianceDeclaration": true,
  "agreedToTerms": true
}
```

### Lab Partner payload example

```json
{
  "type": "lab_partner",
  "name": "Grace Njeri",
  "email": "operations@citylab.co.ke",
  "phone": "0711004400",
  "labName": "City Lab Diagnostics",
  "labLocation": "Nairobi CBD",
  "labAccreditation": "KENAS-ACC-2291",
  "license": "MOH-LAB-00991",
  "experience": 11,
  "county": "Nairobi",
  "address": "Tom Mboya Street",
  "bio": "ISO-certified diagnostics provider.",
  "payoutMethod": "bank_transfer",
  "payoutAccount": "01-2456789-00",
  "backgroundConsent": true,
  "complianceDeclaration": true,
  "agreedToTerms": true
}
```

### Lab Technician payload example

```json
{
  "type": "lab_technician",
  "name": "Kevin Omondi",
  "email": "kevin.omondi@example.com",
  "phone": "0711005500",
  "labPartnerId": 1,
  "license": "KMLTTB-22334",
  "licenseBoard": "KMLTTB",
  "licenseCountry": "Kenya",
  "licenseExpiry": "2027-11-20",
  "idNumber": "22334455",
  "specialty": "Clinical Chemistry",
  "experience": 4,
  "availability": "Mon-Fri 8:00-17:00",
  "county": "Nairobi",
  "address": "Westlands",
  "bio": "Experienced in hematology and chemistry.",
  "payoutMethod": "mpesa",
  "payoutAccount": "254711005500",
  "backgroundConsent": true,
  "complianceDeclaration": true,
  "agreedToTerms": true
}
```

## 3.2 Optional Dedicated Registration Endpoints

Also available:

- `POST /avapharmacy/api/v1/professionals/register/doctor/`
- `POST /avapharmacy/api/v1/professionals/register/pediatrician/`
- `POST /avapharmacy/api/v1/professionals/register/lab-partner/`
- `POST /avapharmacy/api/v1/professionals/register/lab-technician/`


## 4. Admin Provisioning of Approved Professional Applications

These endpoints create real `accounts_user` login records after application review.

- Auth: Admin JWT required (`Authorization: Bearer <access_token>`)
- Method: `POST`
- Payload: optional password

```json
{
  "password": "StrongPass@123"
}
```

If password is omitted, a temporary password is generated and returned.

### Endpoints

- Doctor: `/avapharmacy/api/v1/admin/doctors/{id}/provision-account/`
- Pediatrician: `/avapharmacy/api/v1/admin/pediatricians/{id}/provision-account/`
- Lab partner: `/avapharmacy/api/v1/admin/lab/partners/{id}/provision-account/`
- Lab technician: `/avapharmacy/api/v1/admin/lab/technicians/{id}/provision-account/`


## 5. Pharmacist Registration by Admin

Pharmacists are created by admin using users endpoint with role `pharmacist`.
When created, they are marked inactive until they set password from activation email.

- Method: `POST`
- URL: `/avapharmacy/api/v1/admin/users/`
- Auth: Admin JWT required

Payload example:

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

Response includes activation email metadata (`sent_to`, `expires_at`) when email is sent.

## 5.2 Pharmacist activation and resend flow

### Auto email on create

When admin creates pharmacist, backend sends activation email with a one-time link.

### Admin resend activation email

- Method: `POST`
- URL: `/avapharmacy/api/v1/admin/users/{id}/resend-activation/`
- Auth: Admin JWT required
- Body: empty JSON `{}` (or no body)

This issues a fresh link and invalidates previous active links.

### API endpoint to set password from token

- Method: `POST`
- URL: `/avapharmacy/api/v1/auth/pharmacist/activate/`
- Auth: none

```json
{
  "token": "activation-token-from-email-link",
  "new_password": "StrongPass@123",
  "new_password_confirm": "StrongPass@123"
}
```

### Browser fallback activation page

- Method: `GET` then `POST`
- URL: `/avapharmacy/api/v1/auth/pharmacist/activate/{token}/`

This is a themed server-rendered page for setting password directly from email link.
After activation, pharmacist can access frontend dashboard:

- `http://localhost:3000/pharmacist/dashboard`

## 5.1 Where pharmacist data is stored

- Core account: `accounts_user`
- Pharmacist-specific data: `accounts_pharmacist` (one-to-one with user)

This keeps pharmacists distinct from customers at database level.


## 6. Tables for Professional Applications

- Doctor applications: `consultations_doctorprofile`
- Pediatrician applications: `consultations_pediatricianprofile`
- Lab partner applications: `lab_labpartner`
- Lab technician applications: `lab_labtechnicianprofile`

When provisioned, login users are created in `accounts_user` with role-specific role values.
