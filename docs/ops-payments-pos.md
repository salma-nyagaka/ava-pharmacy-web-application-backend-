# Payments and POS Integration

## Required Environment Variables

Copy these from `.env.example` into the deployed `.env` and set real values:

- `MPESA_ENVIRONMENT`
- `MPESA_CONSUMER_KEY`
- `MPESA_CONSUMER_SECRET`
- `MPESA_SHORTCODE`
- `MPESA_PASSKEY`
- `MPESA_CALLBACK_URL`
- `FLUTTERWAVE_SECRET_KEY`
- `FLUTTERWAVE_SECRET_HASH`
- `FLUTTERWAVE_REDIRECT_URL`
- `POS_ORDER_PUSH_URL`
- `POS_ORDER_PUSH_TOKEN`
- `POS_ORDER_PUSH_MAX_ATTEMPTS`
- `POS_ORDER_PUSH_BACKOFF_SECONDS`
- `POS_ORDER_PUSH_MAX_BACKOFF_SECONDS`
- `POS_ORDER_PUSH_QUEUE_MAX_ATTEMPTS`
- `PAYMENT_WEBHOOK_SECRET`

## Live Payment Flows

### M-Pesa

- Checkout creates a draft order.
- Backend creates an M-Pesa payment intent.
- Backend initiates Daraja STK Push.
- Safaricom posts to `POST /api/payments/mpesa/callback/`.
- Backend marks the payment as paid.
- Frontend finalizes the order with `POST /api/checkout/<order_id>/finalize/`.

### Card Payments

- Checkout creates a draft order.
- Backend creates a payment intent with provider `card`.
- Backend requests a Flutterwave hosted checkout link.
- Frontend redirects the shopper to Flutterwave.
- Flutterwave redirects back to `FLUTTERWAVE_REDIRECT_URL`.
- Frontend verifies the transaction with `POST /api/payments/intents/<intent_id>/sync/`.
- Flutterwave can also call `POST /api/payments/webhook/`.
- Backend marks the payment as paid.
- Frontend finalizes the order with `POST /api/checkout/<order_id>/finalize/`.

## Webhook Endpoints

### Flutterwave Webhook

- Endpoint: `POST /api/payments/webhook/`
- Validation: request must include a valid `flutterwave-signature` or `verif-hash`
- Secret source: `FLUTTERWAVE_SECRET_HASH`

### M-Pesa Callback

- Endpoint: `POST /api/payments/mpesa/callback/`
- Source: Safaricom Daraja callback configuration
- Secret/header verification is not part of Daraja; protect with HTTPS and exact callback URL configuration

## POS Order Push

The backend pushes orders to the configured POS endpoint when an order is:

- created/finalized
- cancelled
- refunded
- admin-updated

Target endpoint:

- `POS_ORDER_PUSH_URL`

Authorization:

- `Authorization: Bearer <POS_ORDER_PUSH_TOKEN>` if token is configured

Content type:

- `application/json`

Payload shape:

```json
{
  "action": "created",
  "order": {
    "id": 123,
    "order_number": "ORD-ABC12345",
    "status": "paid",
    "payment_method": "mpesa_stk",
    "payment_status": "paid",
    "payment_reference": "QWE123RTY",
    "total": "1500.00",
    "subtotal": "1200.00",
    "discount_total": "0.00",
    "shipping_fee": "300.00",
    "shipping": {
      "first_name": "Jane",
      "last_name": "Doe",
      "email": "jane@example.com",
      "phone": "254712345678",
      "street": "Ngong Road",
      "city": "Nairobi",
      "county": "Nairobi"
    },
    "items": [
      {
        "id": 10,
        "product_id": 11,
        "product_sku": "DSAD-DFGI",
        "product_name": "dsad",
        "variant_id": null,
        "variant_sku": "",
        "variant_name": "",
        "quantity": 2,
        "unit_price": "600.00",
        "discount_total": "0.00",
        "prescription_id": null
      }
    ]
  }
}
```

Supported `action` values:

- `created`
- `updated`
- `cancelled`
- `refunded`

### Retry and Backoff

Outbound POS order pushes now retry automatically for transient failures:

- network failures
- `408 Request Timeout`
- `429 Too Many Requests`
- any `5xx` response

They do not retry for permanent client-side failures such as most `4xx` responses.

Tuning variables:

- `POS_ORDER_PUSH_MAX_ATTEMPTS` default `3`
- `POS_ORDER_PUSH_BACKOFF_SECONDS` default `1.0`
- `POS_ORDER_PUSH_MAX_BACKOFF_SECONDS` default `8.0`
- `POS_ORDER_PUSH_QUEUE_MAX_ATTEMPTS` default `10`

Backoff strategy:

- exponential backoff per retry attempt
- attempt 1: immediate
- attempt 2: `1.0s` by default
- attempt 3: `2.0s` by default
- capped by `POS_ORDER_PUSH_MAX_BACKOFF_SECONDS`

### Persistent Retry Queue

If inline retries still fail, the backend now stores the outbound push in the database for later replay.

Queue model:

- `OutboundOrderPush`

Important fields:

- `status`
- `attempt_count`
- `max_attempts`
- `next_attempt_at`
- `response_status_code`
- `response_body`
- `last_error`

Queue statuses:

- `pending`
- `retrying`
- `succeeded`
- `exhausted`

### Replay Command

Run queued retries manually or from cron:

```bash
python manage.py retry_order_pushes
```

Options:

```bash
python manage.py retry_order_pushes --limit 50
python manage.py retry_order_pushes --id 123
```

Recommended cron example:

```bash
*/5 * * * * cd /path/to/avapharmacy-backend && /path/to/venv/bin/python manage.py retry_order_pushes --limit 50
```

## Ops Checklist

- Daraja callback URL must point to the live backend.
- Flutterwave webhook must point to the live backend.
- Flutterwave secret hash in the dashboard must match `FLUTTERWAVE_SECRET_HASH`.
- POS endpoint must be reachable by the backend and accept JSON POST requests.
- HTTPS is required for all live callback and webhook URLs.

## Failure Handling

- Payment verification failures are recorded on the payment intent as `last_error`.
- POS push success/failure is logged as order events:
  - `order_push_succeeded`
  - `order_push_failed`
- Event metadata includes:
  - final status code
  - total attempt count
  - per-attempt outcomes
- Failed pushes are also visible in Django admin under `Outbound order pushes`
- Admins can inspect those events from the order record.
