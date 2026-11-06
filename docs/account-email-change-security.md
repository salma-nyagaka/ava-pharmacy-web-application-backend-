# Verified account email changes

Account profile edits no longer replace the login email immediately. A changed email requires `current_password` (the acting administrator's password for an admin edit), then approval from the old address only. Other profile fields can still save normally.

The confirmation page requires an explicit approval click, not an automatic GET action. Tokens contain 32 cryptographically random bytes; only SHA-256 hashes are stored. The old-address link can approve once. Requests expire after 30 minutes; a newer request invalidates previous requests. A change in the saved password or original email invalidates outstanding approvals. Completion locks the user and request, rechecks email uniqueness and invalidates refresh tokens. Existing access tokens retain their normal expiry.

Endpoint: POST `/api/auth/confirm-email-change/` with `token`. Self profile edits use the existing endpoints and return `email_change` with `pending_email`, `sent_to`, and `failed_to`. Email-change requests are limited to five per hour per authenticated actor.

Password changes retain current-password verification and password validation. Their response includes `confirmation_email.sent_to` and `.failed_to`. Notifications contain no password or password hash. Delivery failures are logged without claiming a successful send; SMTP acceptance does not prove inbox receipt.

The frontend preserves action button labels and shows delivery/approval instructions separately. Failed delivery can be retried by submitting the email-change request again (within its rate limit). Existing email remains active while waiting. Administrator edits use the same approval workflow.

Migration: accounts.0019_emailchangerequest. Security checks use isolated test mail and test database records; no real user credentials or email addresses are changed by tests.
