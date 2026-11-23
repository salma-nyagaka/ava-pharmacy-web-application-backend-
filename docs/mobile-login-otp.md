# Login OTP

Set `LOGIN_OTP_DELIVERY=sms` to send codes to each user's account phone through
BongaSMS. Use `email` to deliver codes through Django's email backend.

For email delivery, configure `EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend`, `EMAIL_HOST`,
`EMAIL_PORT`, `EMAIL_USE_TLS`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, and
`DEFAULT_FROM_EMAIL` on the backend. Console, file, and dummy mail backends are
rejected for OTP delivery. Restart the backend after changing environment settings.

Apply migrations with `python manage.py migrate`. Login returns `otp_required`,
`challenge_id`, `delivery_channel: "email"`, a masked `email_hint`, `expires_in: 300`,
and `resend_after: 60`. For SMS, the response uses `delivery_channel: "sms"`
and a masked `phone_hint`.
Submit the six-digit code and challenge ID to the existing
`/avapharmacy/api/v1/auth/login/verify-otp/` endpoint to receive JWTs.

Codes expire after five minutes, allow five attempts, and are single-use.
Repeat email/password login after 60 seconds to resend. Resending invalidates
the previous code. Changing the account email or password invalidates the challenge.
Accounts do not need a phone number for email OTP. SMS challenges issued before
this change are invalidated by the email binding.

`LOGIN_OTP_REQUIRED=False` preserves password-only login for staged rollout.
The previous Twilio adapter has been replaced with a prepared BongaSMS adapter.
Configure BONGASMS_SEND_URL (provider-confirmed HTTPS), BONGASMS_CLIENT_ID,
BONGASMS_API_KEY, BONGASMS_API_SECRET, and BONGASMS_SERVICE_ID.
Set BONGASMS_SEND_URL to the HTTPS endpoint supplied by your BongaSMS account.
The adapter sends form-encoded POST data with TLS certificate verification.
Provider reference: https://api.olivetreehub.com/sms/quicksms/sendsms
Production CAPTCHA requires the frontend public site key and matching backend secret.
