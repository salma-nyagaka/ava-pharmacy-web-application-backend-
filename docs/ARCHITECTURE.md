# AvaPharma Backend — Architecture Document

## Overview

The AvaPharma backend is a RESTful API built on Django REST Framework, designed to serve a pharmacy platform that includes:

- E-commerce (products, cart, checkout, orders)
- Prescription management with pharmacist review workflow
- Telemedicine (doctor/pediatrician consultations via chat)
- Laboratory services (test booking, sample tracking, results)
- Customer support ticketing
- Staff payouts

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         Frontend (React)                        │
│                    http://localhost:5173                         │
└─────────────────────┬───────────────────────────────────────────┘
                       │  REST API (JSON) + JWT Auth
                       ▼
┌─────────────────────────────────────────────────────────────────┐
│                   Django REST Framework API                      │
│                    http://localhost:8000                         │
│                                                                  │
│  ┌──────────┐ ┌──────────┐ ┌────────────┐ ┌───────────────┐   │
│  │ accounts │ │ products │ │   orders   │ │ prescriptions │   │
│  └──────────┘ └──────────┘ └────────────┘ └───────────────┘   │
│  ┌──────────────┐ ┌──────┐ ┌─────────┐ ┌──────────┐           │
│  │consultations │ │  lab │ │ support │ │ payouts  │           │
│  └──────────────┘ └──────┘ └─────────┘ └──────────┘           │
└─────────────────────┬───────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────────┐
│                      PostgreSQL Database                         │
└─────────────────────────────────────────────────────────────────┘
```

---

## App Responsibilities

### `apps.accounts`
- Custom `User` model extending `AbstractBaseUser`
- Roles: `customer`, `admin`, `pharmacist`, `doctor`, `pediatrician`, `lab_technician`, `inventory_staff`
- JWT authentication via `djangorestframework-simplejwt`
- `PharmacistProfile` — stores granular pharmacist permissions
- `Address` — user shipping addresses
- `UserNote` — admin notes on user records

### `apps.products`
- `Category` — hierarchical (parent/subcategory via self-FK)
- `Brand` — product brands
- `Product` — full catalog with stock status (`branch`, `warehouse`, `out`)
- `ProductImage` — gallery images
- `ProductReview` — user ratings (1–5 stars)
- `Wishlist` — per-user product wishlists

### `apps.orders`
- `Cart` / `CartItem` — server-side cart (one per authenticated user)
- `Order` — denormalized shipping info snapshot at checkout
- `OrderItem` — product name/SKU/price snapshot at time of order
- `OrderNote` — admin notes on orders
- Checkout logic: calculates shipping fee (free ≥ KSh 3,000)

### `apps.prescriptions`
- `Prescription` — patient upload with reference (RX-XXXXXX)
- `PrescriptionFile` — uploaded prescription images/PDFs
- `PrescriptionItem` — individual medications in an approved prescription
- `PrescriptionAuditLog` — immutable audit trail of all changes
- Full lifecycle: `pending → approved/clarification/rejected`
- Dispatch tracking: `not_started → queued → packed → dispatched → delivered`

### `apps.consultations`
- `DoctorProfile` — doctor/pediatrician professional profile with verification docs
- `DoctorDocument` — supporting documents (license, certificates)
- `Consultation` — patient–doctor session (chat-based)
- `ConsultationMessage` — individual chat messages
- `DoctorPrescription` — prescriptions issued by doctors during consultations
- `DoctorEarning` — earning records per consultation

### `apps.lab`
- `LabTest` — catalog of available tests (Blood, Cardiac, Infectious, Wellness, Metabolic)
- `LabRequest` — patient request linked to a test
- `LabAuditLog` — immutable audit trail
- `LabResult` — result file + flags + abnormality indicators

### `apps.support`
- `SupportTicket` — customer issue reports (Order, Prescription, Consultation, Other channels)
- `SupportNote` — threaded notes by staff and customers

### `apps.payouts`
- `Payout` — staff/partner payment records (Doctor, Pediatrician, Pharmacist, Lab Partner)
- Methods: `bank_transfer`, `mpesa`, `cheque`, `cash`
- Lifecycle: `pending → paid / failed`

---

## Authentication & Authorization

### JWT Flow
```
POST /api/auth/login/
→ { access_token (1 hour), refresh_token (7 days) }

All requests: Authorization: Bearer <access_token>

POST /api/auth/token/refresh/  → new access_token
POST /api/auth/logout/         → blacklists refresh_token
```

### Permission Classes (apps/accounts/permissions.py)

| Class | Allows |
|-------|--------|
| `IsAdminUser` | Only `role == admin` |
| `IsPharmacist` | Only `role == pharmacist` |
| `IsPharmacistOrAdmin` | Pharmacist or admin |
| `IsDoctor` | Doctor or pediatrician |
| `IsDoctorOrAdmin` | Doctor, pediatrician, or admin |
| `IsLabTechOrAdmin` | Lab technician or admin |

---

## Database Design Principles

1. **Denormalization at order/prescription time** — Order items snapshot product name, SKU, and price to preserve historical accuracy even if products change.
2. **Audit trails** — `PrescriptionAuditLog` and `LabAuditLog` are append-only, never updated.
3. **Soft references** — ForeignKeys to `User` use `on_delete=SET_NULL` to preserve records when users are deleted.
4. **Self-referential categories** — `Category.parent` allows two-level hierarchy without a dedicated tree library.
5. **Reference codes** — All business entities (orders, prescriptions, consultations, etc.) use human-readable references (e.g., `ORD-ABC12345`, `RX-ABCDEF`) generated at creation time using UUID hex.

---

## Key Business Rules

### Shipping
- Orders < KSh 3,000: shipping fee = KSh 300
- Orders ≥ KSh 3,000: free shipping
- Configurable via `settings.FREE_SHIPPING_THRESHOLD` and `settings.SHIPPING_FEE`

### Prescription Approval
- Only pharmacists or admins can update prescription status
- Every status change is audit-logged
- Approved prescriptions can have items linked to products for cart integration

### Doctor Verification
- Doctors self-register via `/api/doctors/register/`
- Start with `status = pending`
- Admin verifies and sets `status = active` + records `verified_at`
- Only active doctors appear in public listing

### Pediatric Consultations
- `is_pediatric = True` enables guardian fields
- Consent must be `granted` before dosage alerts can be cleared
- Child age and weight stored for dosage calculation

---

## API Pagination

Default page size: **20 items**

```
GET /api/products/?page=2&page_size=10
```

Response includes `count`, `next`, `previous`, and `results`.

---

## File Uploads

| Entity | Field | Upload Path |
|--------|-------|-------------|
| Product image | `image` | `products/` |
| Product gallery | `gallery[].image` | `products/gallery/` |
| Brand logo | `logo` | `brands/` |
| Prescription file | `files[]` | `prescriptions/<id>/` |
| Doctor document | `file` | `doctors/documents/` |
| Lab result | `file` | `lab/results/` |

In development, files are served from `MEDIA_ROOT` via Django.
In production, configure `django-storages` with S3 or similar.

---

## Settings Structure

| File | Purpose |
|------|---------|
| `settings/base.py` | All shared settings (apps, middleware, DRF config, JWT, DB) |
| `settings/development.py` | `DEBUG=True`, verbose SQL logging |
| `settings/production.py` | Security headers, HTTPS enforcement, warning-level logging |

Switch environment via:
```bash
DJANGO_SETTINGS_MODULE=avapharmacy.settings.production
```
