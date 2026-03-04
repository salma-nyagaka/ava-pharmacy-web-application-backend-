# AvaPharma API — Usage Examples

All examples use `curl`. Replace `<token>` with your JWT access token.
The versioned ecommerce contract is available under `/api/v1/`.

---

## Authentication

### Register
```bash
curl -X POST http://localhost:8000/api/v1/auth/register/ \
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
curl -X POST http://localhost:8000/api/v1/auth/login/ \
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
curl "http://localhost:8000/api/v1/products/?category=health-wellness&min_price=100&max_price=2000&search=vitamin"
```

### Get CMS blocks for the homepage
```bash
curl "http://localhost:8000/api/v1/cms/?placement=home_hero"
```

### Get product detail
```bash
curl "http://localhost:8000/api/v1/products/centrum-multivitamin-60-tablets/"
```

### Create a product variant (admin)
```bash
curl -X POST http://localhost:8000/api/v1/admin/products/5/variants/ \
  -H "Authorization: Bearer <admin_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "sku": "HP-VIT-C-1000-30",
    "name": "30 Tablets",
    "attributes": {"pack_size": "30"},
    "price": 750,
    "stock_quantity": 40
  }'
```

---

## Cart & Checkout

### Add item to cart
```bash
curl -X POST http://localhost:8000/api/v1/cart/items/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"product_id": 5, "quantity": 2}'
```

### Apply coupon
```bash
curl -X POST http://localhost:8000/api/v1/cart/coupon/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"code": "WELCOME10"}'
```

### Create checkout draft
```bash
curl -X POST http://localhost:8000/api/v1/checkout/draft/ \
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
    "payment_method": "mpesa_stk",
    "delivery_method": "standard"
  }'
```

### Create payment intent for draft order
```bash
curl -X POST http://localhost:8000/api/v1/payments/intents/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "order_id": 12,
    "provider": "mpesa",
    "phone": "0712345678"
  }'
```

### Sync M-Pesa payment status
```bash
curl -X POST http://localhost:8000/api/v1/payments/intents/18/sync/ \
  -H "Authorization: Bearer <token>"
```

### M-Pesa callback endpoint
```bash
curl -X POST http://localhost:8000/api/v1/payments/mpesa/callback/ \
  -H "Content-Type: application/json" \
  -d '{"Body":{"stkCallback":{"MerchantRequestID":"12345","CheckoutRequestID":"ws_CO_12345","ResultCode":0,"ResultDesc":"Success","CallbackMetadata":{"Item":[{"Name":"MpesaReceiptNumber","Value":"QWE123XYZ"},{"Name":"Amount","Value":2500}]}}}}'
```

### Finalize order after payment confirmation
```bash
curl -X POST http://localhost:8000/api/v1/checkout/12/finalize/ \
  -H "Authorization: Bearer <token>"
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
curl -X PATCH http://localhost:8000/api/v1/prescriptions/1/update/ \
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
curl -X POST http://localhost:8000/api/v1/lab/requests/ \
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
curl -X POST http://localhost:8000/api/v1/lab/requests/1/results/ \
  -H "Authorization: Bearer <lab_tech_token>" \
  -F "summary=All values within normal range" \
  -F "is_abnormal=false" \
  -F "file=@/path/to/result.pdf"
```

---

## Admin: Update Order Status

```bash
curl -X PATCH http://localhost:8000/api/v1/admin/orders/1/ \
  -H "Authorization: Bearer <admin_token>" \
  -H "Content-Type: application/json" \
  -d '{"status": "shipped", "payment_status": "paid"}'
```

## Returns

### Create return request
```bash
curl -X POST http://localhost:8000/api/v1/returns/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "order_id": 12,
    "reason": "Received damaged item"
  }'
```

## Shipping

### List active shipping methods
```bash
curl "http://localhost:8000/api/v1/shipping-methods/"
```

### Create shipping method (admin)
```bash
curl -X POST http://localhost:8000/api/v1/admin/shipping-methods/ \
  -H "Authorization: Bearer <admin_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "code": "express",
    "name": "Express Delivery",
    "description": "Same day in Nairobi",
    "fee": 450,
    "free_shipping_threshold": 7000,
    "estimated_delivery_window": "Same day"
  }'
```

## Notifications

### Update notification preferences
```bash
curl -X PATCH http://localhost:8000/api/v1/notifications/preferences/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"sms_enabled": true, "order_updates_sms": true}'
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
