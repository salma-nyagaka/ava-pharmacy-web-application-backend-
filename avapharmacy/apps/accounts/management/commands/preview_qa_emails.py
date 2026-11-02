"""Render safe sample email previews; this command never sends emails."""
import base64
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.accounts.qa_emailing import QA_EMAIL_TYPES, render_qa_email


class Command(BaseCommand):
    help = 'Render the four themed QA emails with placeholder credentials (no delivery).'

    def add_arguments(self, parser):
        parser.add_argument('--output-dir', default='output/email-previews')

    def handle(self, *args, **options):
        destination = Path(options['output_dir']).resolve()
        destination.mkdir(parents=True, exist_ok=True)
        logo = Path(settings.BASE_DIR) / 'templates/emails/assets/ava-logo.jpg'
        logo_uri = 'data:image/jpeg;base64,' + base64.b64encode(logo.read_bytes()).decode('ascii')
        paths = {
            'change_password': '/account/settings',
            'reset_password': '/reset-password?uid=preview-user&token=preview-token',
            'activate_doctor': '/auth/professional/activate?token=preview-token',
            'signup': '/register',
        }
        links = []
        for kind, definition in QA_EMAIL_TYPES.items():
            rendered = render_qa_email(
                kind=kind,
                account_email='doctor.qa@example.test' if kind == 'activate_doctor' else 'customer.qa@example.test',
                test_password='ExampleTestPass123!',
                action_url='http://localhost:3000' + paths[kind],
                current_password='CurrentTest123!' if kind == 'change_password' else '',
                registration_details=(('Name', 'Browser QA'), ('Phone', '+254700000000'), ('Delivery address', 'Sample QA address'), ('City / county', 'Nairobi')) if kind == 'signup' else (),
            )
            (destination / f'{kind}.html').write_text(rendered['html'].replace('cid:ava-logo', logo_uri), encoding='utf-8')
            (destination / f'{kind}.txt').write_text(rendered['text'], encoding='utf-8')
            links.append(f'<article><h2>{definition["subject"].removeprefix("AVA Pharmacy QA: ")}</h2><a href="{kind}.html">Open full preview</a><iframe title="{kind} email preview" src="{kind}.html"></iframe></article>')
        gallery = '''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>AVA Pharmacy email templates</title><style>body{margin:0;background:#f4f6fb;color:#031b4e;font-family:Arial,sans-serif;padding:30px}h1{font-size:32px;margin:0 0 10px}p{color:#647089}main{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:24px}article{min-width:0}h2{font-size:19px;margin-bottom:8px}a{color:#c91444;font-size:13px}iframe{display:block;border:1px solid #e7eaf2;border-radius:14px;width:100%;height:1200px;background:white;margin-top:14px}@media(max-width:800px){main{grid-template-columns:1fr}body{padding:18px}}</style></head><body><h1>AVA Pharmacy email templates</h1><p>Four account emails, one consistent theme. Preview data only; no live credentials or activation links.</p><main>''' + ''.join(links) + '</main></body></html>'
        (destination / 'index.html').write_text(gallery, encoding='utf-8')
        self.stdout.write(self.style.SUCCESS(f'Rendered four sample emails: {destination / "index.html"}'))
