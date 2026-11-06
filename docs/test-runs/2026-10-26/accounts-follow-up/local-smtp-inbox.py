import email
import html
import json
import re
import socketserver
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

destination = Path('/private/tmp/ava-accounts-smtp-mail.json')
messages = json.loads(destination.read_text()) if destination.exists() else []
lock = threading.Lock()

class SMTP(socketserver.StreamRequestHandler):
    def handle(self):
        self.connection.settimeout(30)
        recipients = []
        self.wfile.write(b'220 localhost Synthetic QA SMTP\r\n')
        while True:
            line = self.rfile.readline(10000)
            if not line:
                return
            command = line.decode(errors='replace').strip()
            verb = command.split(' ', 1)[0].upper()
            if verb == 'EHLO':
                self.wfile.write(b'250-localhost\r\n250 SIZE 10485760\r\n')
            elif verb in {'HELO', 'NOOP', 'MAIL'}:
                self.wfile.write(b'250 OK\r\n')
            elif verb == 'RCPT':
                recipients.append(email.utils.parseaddr(command.split(':', 1)[1])[1])
                self.wfile.write(b'250 OK\r\n')
            elif verb == 'RSET':
                recipients = []
                self.wfile.write(b'250 OK\r\n')
            elif verb == 'DATA':
                self.wfile.write(b'354 End with a dot\r\n')
                body = bytearray()
                while True:
                    part = self.rfile.readline(10485760)
                    if not part or part in {b'.\r\n', b'.\n'}:
                        break
                    body.extend(part[1:] if part.startswith(b'..') else part)
                    if len(body) > 10485760:
                        return
                parsed = email.message_from_bytes(bytes(body))
                text = '\n'.join(p.get_payload(decode=True).decode(p.get_content_charset() or 'utf-8') for p in parsed.walk() if p.get_content_type() == 'text/plain')
                with lock:
                    messages.insert(0, {'subject': str(parsed.get('Subject')), 'to': recipients[:], 'body': text})
                    destination.write_text(json.dumps(messages, indent=2))
                recipients = []
                self.wfile.write(b'250 Captured locally\r\n')
            elif verb == 'QUIT':
                self.wfile.write(b'221 Bye\r\n')
                return
            else:
                self.wfile.write(b'502 Unsupported\r\n')

class Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True

class Page(BaseHTTPRequestHandler):
    def do_GET(self):
        content = ['<html><head><title>Ava QA SMTP Inbox</title></head><body><h1>Ava QA SMTP Inbox</h1><p>Local SMTP delivery only. Synthetic test accounts.</p><a href="/">Refresh inbox</a>']
        with lock:
            snapshot = messages[:]
        for message in snapshot:
            text = html.escape(message['body'])
            text = re.sub(r'https?://(?:localhost|127\.0\.0\.1):\d+/[^\s]+', lambda m: '<a href="' + m.group(0) + '">' + m.group(0) + '</a>', text)
            content.append('<article><h2>' + html.escape(message['subject']) + '</h2><p>To: ' + html.escape(', '.join(message['to'])) + '</p><pre style="white-space:pre-wrap">' + text + '</pre></article><hr>')
        body = (''.join(content) + '</body></html>').encode()
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

smtp = Server(('127.0.0.1', 8025), SMTP)
threading.Thread(target=smtp.serve_forever, daemon=True).start()
ThreadingHTTPServer(('127.0.0.1', 8026), Page).serve_forever()
