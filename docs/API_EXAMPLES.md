# AvaPharma API — Usage Examples

All examples use `curl`. Replace `<token>` with your JWT access token.

---

## Authentication

### Register
```bash
curl -X POST http://localhost:8000/api/auth/register/ \
  -H "Content-Type: application/json" \
  -d '{
    "email": "john@example.com",
    "first_name": "John",
    "last_name": "Doe",
    "phone": "0712345678",
    "password": "SecurePass123!",
    "password_confirm": "SecurePass123!",
    "role": "customer"
  }'
```

### Login
```bash
curl -X POST http://localhost:8000/api/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"email": "john@example.com", "password": "SecurePass123!"}'
```

Response:
```json
{
  "user": { "id": 1, "email": "john@example.com", "role": "customer", ... },
  "tokens": { "access": "eyJ...", "refresh": "eyJ..." }
}
```

---

## Products

### Browse products with filters
```bash
curl "http://localhost:8000/api/products/?category=health-wellness&min_price=100&max_price=2000&search=vitamin"
```

### Get product detail
```bash
curl "http://localhost:8000/api/products/centrum-multivitamin-60-tablets/"
```

---

## Cart & Checkout

### Add item to cart
```bash
curl -X POST http://localhost:8000/api/cart/items/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"product_id": 5, "quantity": 2}'
```

### Checkout
```bash
curl -X POST http://localhost:8000/api/checkout/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "first_name": "John",
    "last_name": "Doe",
    "email": "john@example.com",
    "phone": "0712345678",
    "street": "123 Kenyatta Avenue",
    "city": "Nairobi",
    "county": "Nairobi",
    "payment_method": "mpesa_stk"
  }'
```

---

## Prescriptions

### Upload prescription
```bash
curl -X POST http://localhost:8000/api/prescriptions/upload/ \
  -H "Authorization: Bearer <token>" \
  -F "patient_name=John Doe" \
  -F "doctor_name=Dr. Smith" \
  -F "notes=Urgent refill" \
  -F "files=@/path/to/prescription.pdf"
```

### Pharmacist approves prescription
```bash
curl -X PATCH http://localhost:8000/api/prescriptions/1/update/ \
  -H "Authorization: Bearer <pharmacist_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "status": "approved",
    "pharmacist_notes": "All medications verified",
    "items": [
      {"name": "Amoxicillin 500mg", "dose": "500mg", "frequency": "3x daily", "quantity": 21}
    ]
  }'
```

---

## Lab Services

### Book a lab test
```bash
curl -X POST http://localhost:8000/api/lab/requests/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "test": 1,
    "patient_name": "John Doe",
    "patient_phone": "0712345678",
    "priority": "routine",
    "channel": "walk_in"
  }'
```

### Upload lab result (lab technician)
```bash
curl -X POST http://localhost:8000/api/lab/requests/1/results/ \
  -H "Authorization: Bearer <lab_tech_token>" \
  -F "summary=All values within normal range" \
  -F "is_abnormal=false" \
  -F "file=@/path/to/result.pdf"
```

---

## Admin: Update Order Status

```bash
curl -X PATCH http://localhost:8000/api/admin/orders/1/ \
  -H "Authorization: Bearer <admin_token>" \
  -H "Content-Type: application/json" \
  -d '{"status": "shipped", "payment_status": "paid"}'
```

---

## Admin: Create Payout

```bash
curl -X POST http://localhost:8000/api/admin/payouts/ \
  -H "Authorization: Bearer <admin_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "recipient_name": "Dr. Sarah Johnson",
    "role": "doctor",
    "period": "January 2026",
    "amount": 25000,
    "method": "mpesa"
  }'
```
