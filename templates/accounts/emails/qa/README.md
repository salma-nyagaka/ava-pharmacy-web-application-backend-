# Branded account QA emails

Four reusable variants: `change_password`, `reset_password`, `activate_doctor`, and `signup`.

They share the website's primary pink `#E81750`, burgundy `#991b1f`, navy `#031b4e`, light surfaces and the existing AVA Pharmacy logo. Layout uses email-safe tables, inline styling, a responsive width, a single primary action and a copyable fallback link. The logo is embedded as a CID attachment rather than loaded from a localhost image URL.

These are **QA instruction emails**, matching the four requested examples. They can include a generated test-password suggestion; do not use them to email production passwords. No real credentials or tokens are stored in these templates or previews. Existing production transactional email templates are unchanged.

## Preview without sending

```sh
venv/bin/python manage.py preview_qa_emails
```

Open `output/email-previews/index.html` through a local static server. Preview data uses example credentials and nonfunctional sample tokens. The `.txt` files show the corresponding plain-text versions.

## Send a variant

Use `apps.accounts.qa_emailing.send_qa_email` with explicit `recipient`, `kind`, `account_email`, `test_password` and `action_url`. Optional fields are `current_password`, `registration_details` (label/value pairs), and an existing Django email `connection`.

The sender builds multipart text/HTML email with an inline logo. Pass a freshly generated action URL from the appropriate account workflow; the sender does not generate tokens, apply passwords or change accounts. HTTP(S) action URLs are required and HTML values are autoescaped.

## Verification

```sh
venv/bin/python manage.py test avapharmacy.apps.accounts.tests.test_qa_emailing --noinput
```

Tests cover all four variants, correct action/fallback links, plain-text URL escaping, HTML escaping, safe URL schemes, recipient routing and the multipart inline-logo structure.
