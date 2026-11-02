from html.parser import HTMLParser

from django.core import mail
from django.test import SimpleTestCase, override_settings

from apps.accounts.qa_emailing import QA_EMAIL_TYPES, render_qa_email, send_qa_email


class EmailLinks(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []

    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            self.links.append(dict(attrs).get('href'))


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
                   DEFAULT_FROM_EMAIL='qa@example.test', ADMIN_EMAIL='support@example.test')
class QAEmailTemplateTests(SimpleTestCase):
    def payload(self, kind):
        return {
            'kind': kind,
            'account_email': 'qa@example.test',
            'test_password': 'ExampleTestPass123!',
            'action_url': 'http://localhost:3000/reset-password?uid=example&token=example-token',
            'current_password': 'OldTestPass123!' if kind == 'change_password' else '',
            'registration_details': (('Name', 'Browser QA'), ('City', 'Nairobi')) if kind == 'signup' else (),
        }

    def test_each_variant_preserves_action_links_and_plain_text(self):
        for kind, definition in QA_EMAIL_TYPES.items():
            with self.subTest(kind=kind):
                payload = self.payload(kind)
                rendered = render_qa_email(**payload)
                parser = EmailLinks()
                parser.feed(rendered['html'])
                self.assertEqual(parser.links.count(payload['action_url']), 2)
                self.assertIn(payload['action_url'], rendered['text'])
                self.assertNotIn('&amp;token=', rendered['text'])
                self.assertIn(definition['action_label'], rendered['html'])
                self.assertIn('FOR LOCAL QA TESTING', rendered['html'])
                self.assertIn('cid:ava-logo', rendered['html'])

    def test_html_escapes_credentials_and_details_but_text_preserves_them(self):
        payload = self.payload('signup')
        payload['test_password'] = '<script>not-html</script>&"'
        payload['registration_details'] = (('Name', '<img src=x onerror=alert(1)>'),)
        rendered = render_qa_email(**payload)
        self.assertNotIn('<script>', rendered['html'])
        self.assertNotIn('<img src=x', rendered['html'])
        self.assertIn('&lt;script&gt;', rendered['html'])
        self.assertIn(payload['test_password'], rendered['text'])

    def test_delivery_contains_text_html_and_inline_logo(self):
        for kind in QA_EMAIL_TYPES:
            with self.subTest(kind=kind):
                self.assertEqual(send_qa_email(recipient='recipient@example.test', **self.payload(kind)), 1)
                message = mail.outbox[-1]
                self.assertEqual(message.to, ['recipient@example.test'])
                self.assertIn('ExampleTestPass123!', message.body)
                self.assertEqual(message.alternatives[0][1], 'text/html')
                parts = list(message.message().walk())
                self.assertTrue(any(part.get_content_type() == 'image/jpeg' and part['Content-ID'] == '<ava-logo>' for part in parts))

    def test_rejects_unknown_variant_and_unsafe_action_url(self):
        for changes in [{'kind': 'unknown'}, {'action_url': 'javascript:alert(1)'}, {'action_url': '/relative'}]:
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                render_qa_email(**{**self.payload('signup'), **changes})
