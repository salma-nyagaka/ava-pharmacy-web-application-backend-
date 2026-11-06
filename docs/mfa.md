# Staff MFA

Authenticator-app MFA is mandatory for `admin`, `pharmacist`, `doctor`, and
`pediatrician` accounts, plus any `is_staff` or `is_superuser` account. Other
accounts retain the existing login flow. This backend supports standard TOTP
apps including Google Authenticator and Microsoft Authenticator.

## Frontend integration

All paths below use the `/api/` prefix; the existing API prefix aliases also work.
Responses use the existing `{ "success": true, "data": ... }` JSON envelope.
The examples describe fields inside `data`.

1. `POST /api/auth/login/` with `email` and `password`.
   Protected accounts receive **no JWTs** at this stage:
   ```json
   {
     "mfa_required": true,
     "mfa_setup_required": true,
     "challenge_token": "opaque-password-authenticated-challenge",
     "expires_at": "2026-11-06T20:00:00Z"
   }
   ```
   The challenge expires after five minutes. Starting another login invalidates
   the previous challenge. Password/email/role changes and account suspension
   also invalidate an outstanding challenge.
2. When `mfa_setup_required` is true, call `POST /api/auth/mfa/setup/` with
   `{"challenge_token": "..."}`. Display the returned `secret` for manual entry,
   and render `otpauth_uri` as a QR code **locally**. Never send that URI or secret
   to a remote QR-code service, logs, analytics, or URLs. Repeating setup within
   the same challenge returns the same secret.
3. Ask for the app's six-digit code. Call `POST /api/auth/mfa/confirm/` with
   `{"challenge_token": "...", "code": "123456"}`. This enables MFA and returns
   the existing `user` and `tokens` fields plus ten `recovery_codes`. Show these
   once and prompt the user to store them securely. Preserve leading zeroes in
   authenticator codes by sending strings.
4. On later logins, `mfa_setup_required` is false. Call
   `POST /api/auth/mfa/verify/` with `challenge_token` and `code`. The code may be
   a current authenticator code or one unused recovery code. Success returns
   `user` and `tokens`. Tokens then work with existing refresh/logout endpoints.

Public registration of a protected role returns the user and a message directing
them to log in. It does not start MFA or issue JWTs. Enrollment and MFA happen
only in the login flow. Once logged in, the verified session works without
additional MFA prompts during normal API use or token refresh. Professional
approval and activation remain separate existing account controls.

MFA challenge errors return HTTP 400; account MFA lockout returns HTTP 429. After
five incorrect codes across challenges and Django admin, the account is locked
for fifteen minutes. The MFA endpoints additionally limit requests by IP to
20/minute. Blank/malformed requests fail validation. A valid code may be used
only once, including the enrollment code. Ask users to wait for the next code if
an app code was just used. Server time must be synchronized; verification allows
one 30-second interval of clock drift in either direction.

MFA responses carry `Cache-Control: no-store`. Store challenge tokens only for
the short login flow. Do not persist authenticator secrets after setup.

The frontend source is not in this repository. Its login screen must implement
these challenge/setup/recovery screens before deploying this backend change.

## Deployment

Install `requirements.txt`, then run:

```sh
python manage.py migrate
```

The migration adds credential and challenge tables without changing existing
user records. Protected users enroll at their next password login. Existing
password-only staff access and refresh tokens are rejected immediately after
rollout; users must sign in again. Consultation WebSockets use the same MFA
checks and recheck credential revocation when processing activity.

Secrets (including pending enrollment secrets) use Fernet encryption. Recovery
codes and challenge tokens are stored as hashes. By default the encryption key
is derived from `SECRET_KEY` with a separate MFA domain. An optional dedicated
`MFA_ENCRYPTION_KEY` accepts a Fernet key generated with:

```sh
python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'
```

Choose the key before enrolling users, keep it stable across processes, and
include it in secure operational backups. Changing the effective encryption key
without re-encrypting credentials makes existing authenticator secrets unreadable.
There is no per-code external service or SMS provider.

The `/admin/` Django site requires prior enrollment through the application and
an authenticator/recovery code on its login form. Existing Django admin sessions
must log in again. There is no password-only admin bypass.

## Lost device and recovery

A recovery code can complete a password-authenticated login once. If a user needs
to replace their authenticator, a server operator must first verify their identity
independently, then run:

```sh
python manage.py reset_mfa --email user@example.com --reason 'Verified identity; support case 123'
```

This removes the factor and pending challenges, blacklists refresh tokens,
invalidates MFA access tokens/admin sessions, records an audit event, and forces
fresh enrollment at the next login. No web endpoint permits disabling mandatory
MFA. Password reset does not remove MFA. Avoid including secrets in reset reasons.

## Verification

`apps.accounts.tests.test_mfa` exercises protected roles, enrollment, encryption,
challenge expiry and invalidation, replay prevention, recovery codes, account
lockout, refresh/access enforcement, admin sessions, and operator resets. Account
journeys and consultation socket tests cover the changed login contract. Use a
separate PostgreSQL test database; existing inventory migrations cannot be fully
replayed on SQLite.
