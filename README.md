# AvaPharma Backend API

![Backend coverage](docs/badges/backend-coverage.svg)

A full-featured pharmacy backend built with Django REST Framework and PostgreSQL. Powers the AvaPharma platform including e-commerce, prescription management, telemedicine consultations, lab services, and customer support.

## Tech Stack

- **Framework**: Django 4.2 + Django REST Framework 3.15
- **Database**: PostgreSQL
- **Auth**: JWT via `djangorestframework-simplejwt`
- **API Docs**: OpenAPI 3.0 via `drf-spectacular` (Swagger UI + ReDoc)
- **Storage**: Local (development) / Configurable (production)
- **Server**: Gunicorn + WhiteNoise for static files

---

## Quick Start

### Prerequisites

- Python 3.11+
- PostgreSQL 14+
- pip / virtualenv

### 1. Clone and set up virtual environment

```bash
git clone <repo-url>
cd avapharmacy-backend
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment

```bash
cp .env.example .env
```

Edit `.env` with your database credentials:

```env
DEBUG=True
SECRET_KEY=your-secret-key
FIELD_ENCRYPTION_KEY=your-fernet-key
DATABASE_NAME=avapharmacy
DATABASE_USER=postgres
DATABASE_PASSWORD=yourpassword
DATABASE_HOST=localhost
DATABASE_PORT=5432
CORS_ALLOWED_ORIGINS=http://localhost:5173,http://localhost:3000
```

For payment and POS integration variables, use the full block in `.env.example` and see `docs/ops-payments-pos.md`.

### 4. Create the database

```bash
psql -U postgres -c "CREATE DATABASE avapharmacy;"
```

### 5. Run migrations

```bash
python manage.py migrate
```

### 6. Create a superuser

```bash
python manage.py createsuperuser
```

### 7. Run the development server

```bash
python manage.py runserver
```

API is now available at `http://localhost:8000/api/`

To run the full local stack, keep the backend running in one terminal and start the frontend in another:

```bash
cd /Users/salmanyagaka/Downloads/ava-pharmacy-web-application-frontend
npm install
npm run dev
```

Frontend is available at `http://localhost:3000`.

---

## Tests And Coverage

```bash
# Run the currently passing backend coverage target used by the badge
python manage.py test \
  avapharmacy.apps.accounts.tests.test_account_self_service \
  avapharmacy.apps.prescriptions.tests.test_workflow \
  avapharmacy.apps.support.tests.test_newsletter_subscription

# Run tests with coverage
coverage run manage.py test \
  avapharmacy.apps.accounts.tests.test_account_self_service \
  avapharmacy.apps.prescriptions.tests.test_workflow \
  avapharmacy.apps.support.tests.test_newsletter_subscription
coverage report
coverage json

# Refresh the README coverage badge
python scripts/coverage_badge.py coverage.json docs/badges/backend-coverage.svg "backend coverage"
```

---

## API Documentation

Interactive API docs are available at:

| Interface | URL |
|-----------|-----|
| Swagger UI | http://localhost:8000/api/docs/ |
| ReDoc | http://localhost:8000/api/redoc/ |
| OpenAPI Schema | http://localhost:8000/api/schema/ |
| Django Admin | http://localhost:8000/admin/ |

---

## Project Structure

```
avapharmacy-backend/
├── manage.py
├── requirements.txt
├── .env.example
├── avapharmacy/                  # Project config
│   ├── settings/
│   │   ├── base.py               # Shared settings
│   │   ├── development.py        # Dev overrides
│   │   └── production.py         # Prod overrides
│   ├── urls.py                   # Root URL config
│   ├── wsgi.py
│   └── asgi.py
└── apps/                         # Django apps
    ├── accounts/                 # Users, auth, addresses
    ├── products/                 # Catalog, brands, categories
    ├── orders/                   # Cart, checkout, orders
    ├── prescriptions/            # Prescription workflow
    ├── consultations/            # Telemedicine, doctor profiles
    ├── lab/                      # Lab tests and results
    ├── support/                  # Support tickets
    └── payouts/                  # Staff payouts
```

---

## User Roles

| Role | Description |
|------|-------------|
| `customer` | Default shopper — can browse, buy, upload prescriptions, book consultations |
| `admin` | Full platform access — manage users, orders, inventory, reports |
| `pharmacist` | Reviews prescriptions, manages dispatch |
| `doctor` | Conducts consultations, issues prescriptions |
| `pediatrician` | Pediatric consultations with guardian consent |
| `lab_technician` | Processes lab requests, uploads results |
| `inventory_staff` | Manages product inventory |

---

## Authentication

All protected endpoints require a `Bearer` JWT token in the `Authorization` header:

```
Authorization: Bearer <access_token>
```

### Token Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/auth/register/` | Register new user |
| POST | `/api/auth/login/` | Login — returns access + refresh tokens |
| POST | `/api/auth/logout/` | Logout — blacklists refresh token |
| POST | `/api/auth/token/refresh/` | Refresh access token |
| GET/PUT | `/api/auth/me/` | Current user profile |

---

## Core API Endpoints

### Products
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/categories/` | All categories with subcategories |
| GET | `/api/brands/` | All brands |
| GET | `/api/products/` | Product list (filterable, searchable) |
| GET | `/api/products/<slug>/` | Product detail |
| GET/POST | `/api/products/<id>/reviews/` | Product reviews |
| GET/POST | `/api/wishlist/` | User wishlist |

**Product Filters**: `category`, `brand`, `stock_source`, `requires_prescription`, `min_price`, `max_price`

### Cart & Orders
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/cart/` | View cart |
| POST | `/api/cart/items/` | Add item to cart |
| PATCH | `/api/cart/items/<id>/` | Update cart item quantity |
| DELETE | `/api/cart/items/<id>/delete/` | Remove cart item |
| DELETE | `/api/cart/clear/` | Clear cart |
| POST | `/api/checkout/` | Place order from cart |
| GET | `/api/orders/` | User order history |
| GET | `/api/orders/<id>/` | Order detail |
| POST | `/api/orders/<id>/cancel/` | Cancel an order |

### Prescriptions
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/prescriptions/` | User's prescriptions |
| POST | `/api/prescriptions/upload/` | Upload prescription (multipart) |
| GET | `/api/prescriptions/<id>/` | Prescription detail |
| PATCH | `/api/prescriptions/<id>/update/` | Update status (pharmacist/admin) |
| POST | `/api/prescriptions/<id>/audit/` | Add audit log entry |

### Consultations & Telemedicine
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/doctors/` | Browse active doctors |
| POST | `/api/doctors/register/` | Doctor onboarding |
| GET/POST | `/api/consultations/` | User's consultations |
| GET/PATCH | `/api/consultations/<id>/` | Consultation detail |
| GET/POST | `/api/consultations/<id>/messages/` | Chat messages |
| GET | `/api/doctor/consultations/` | Doctor's queue |
| GET/POST | `/api/doctor/prescriptions/` | Doctor-issued prescriptions |
| GET | `/api/doctor/earnings/` | Doctor earnings |

### Lab Services
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/lab/tests/` | Available lab tests |
| GET/POST | `/api/lab/requests/` | Lab requests |
| GET | `/api/lab/requests/<id>/` | Request detail |
| PATCH | `/api/lab/requests/<id>/update/` | Update request (lab tech/admin) |
| POST | `/api/lab/requests/<id>/results/` | Upload result |
| GET | `/api/lab/results/<id>/` | Fetch result |

### Support
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET/POST | `/api/support/tickets/` | Tickets (own or all for admin) |
| GET/PATCH | `/api/support/tickets/<id>/` | Ticket detail |
| POST | `/api/support/tickets/<id>/notes/` | Add note |

### Admin Endpoints
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET/POST | `/api/admin/users/` | User management |
| GET/PATCH/DELETE | `/api/admin/users/<id>/` | User detail |
| POST | `/api/admin/users/<id>/suspend/` | Suspend user |
| POST | `/api/admin/users/<id>/activate/` | Activate user |
| GET/POST | `/api/admin/orders/` | All orders |
| GET/PATCH | `/api/admin/orders/<id>/` | Update order status |
| GET/POST | `/api/admin/products/` | Product management |
| GET/POST | `/api/admin/prescriptions/` | All prescriptions |
| GET/POST | `/api/admin/doctors/` | Doctor management |
| GET/PATCH | `/api/admin/doctors/<id>/` | Verify/update doctor |
| GET/POST | `/api/admin/payouts/` | Payout management |
| GET | `/api/admin/reports/` | Platform overview stats |

---

## Checkout Flow

1. User adds products to cart via `POST /api/cart/items/`
2. User submits shipping + payment method via `POST /api/checkout/`
3. System creates an `Order` with a snapshot of cart items
4. Cart is cleared
5. Order status progresses: `pending → processing → shipped → delivered`

**Shipping fee**: KSh 300 (free for orders ≥ KSh 3,000)

**Payment methods**: `mpesa_stk`, `mpesa_paybill`, `card`, `cash_on_delivery`

---

## Prescription Workflow

1. Customer uploads files via `POST /api/prescriptions/upload/`
2. Pharmacist reviews via `PATCH /api/prescriptions/<id>/update/`
3. Status: `pending → approved / clarification / rejected`
4. Dispatch: `not_started → queued → packed → dispatched → delivered`
5. All changes are audit-logged automatically

---

## Running Tests

```bash
python manage.py test
```

---

## Production Deployment

```bash
# Set environment
export DJANGO_SETTINGS_MODULE=avapharmacy.settings.production

# Collect static files
python manage.py collectstatic --noinput

# Run with Gunicorn
gunicorn avapharmacy.wsgi:application --bind 0.0.0.0:8000 --workers 4
```

---

## Environment Variables Reference

| Variable | Default | Description |
|----------|---------|-------------|
| `DEBUG` | `True` | Debug mode |
| `SECRET_KEY` | — | Django secret key (required in prod) |
| `DATABASE_NAME` | `avapharmacy` | PostgreSQL database name |
| `DATABASE_USER` | `postgres` | Database user |
| `DATABASE_PASSWORD` | `postgres` | Database password |
| `DATABASE_HOST` | `localhost` | Database host |
| `DATABASE_PORT` | `5432` | Database port |
| `ALLOWED_HOSTS` | `localhost,127.0.0.1` | Allowed hosts (comma-separated) |
| `CORS_ALLOWED_ORIGINS` | `http://localhost:5173,...` | Allowed CORS origins |
| `MEDIA_URL` | `/media/` | Media file URL prefix |
| `STATIC_URL` | `/static/` | Static file URL prefix |
# ava-pharmacy-web-application-backend-
