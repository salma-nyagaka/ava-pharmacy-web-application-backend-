"""Local QA gateway: expose only payment callbacks through an HTTPS tunnel.

Bind on loopback; do not point ngrok at Django/Vite directly. Query strings,
headers and request bodies are deliberately omitted from logs.
"""
import argparse
import json
import re
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib import error, request
from urllib.parse import urlsplit

POST_ROUTES = {
    '/callbacks/consultation/stk/': '/api/consultations/payments/mpesa/callback/',
    '/callbacks/mobile/stk/': '/api/payments/mpesa/callback/',
    '/callbacks/mobile/validate/': '/api/payments/mpesa/paybill/validation/',
    '/callbacks/mobile/confirm/': '/api/payments/mpesa/paybill/confirmation/',
}
POST_PATHS = frozenset(POST_ROUTES)
GET_PATHS = frozenset()
FORWARD_HEADERS = ('Content-Type', 'X-Ava-Mpesa-Secret')
MAX_BODY = 1024 * 1024

def logged_path(path):
    return re.sub(r'(/callbacks/mobile/)[^/]{16,256}(/)', r'\1[redacted]\2', path)


class NoRedirect(request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class CallbackHandler(BaseHTTPRequestHandler):
    upstream = 'http://127.0.0.1:8000'
    opener = request.build_opener(NoRedirect)

    def log_message(self, *args):
        pass

    def reply(self, code, body=b'', headers=None):
        try:
            self.send_response(code)
            for key in ('Content-Type', 'Location'):
                if headers and headers.get(key):
                    self.send_header(key, headers[key])
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass
        finally:
            print(json.dumps({'at': datetime.now(timezone.utc).isoformat(), 'method': self.command,
                              'path': logged_path(urlsplit(self.path).path), 'status': code}), flush=True)

    def dispatch(self):
        path = urlsplit(self.path).path
        allowed = POST_PATHS if self.command == 'POST' else GET_PATHS if self.command == 'GET' else ()
        if path not in allowed:
            return self.reply(404)
        if self.headers.get('Transfer-Encoding'):
            return self.reply(400)
        try:
            length = int(self.headers.get('Content-Length', 0))
        except ValueError:
            return self.reply(400)
        if length < 0 or length > MAX_BODY:
            return self.reply(413)
        body = self.rfile.read(length) if self.command == 'POST' else None
        headers = {key: self.headers[key] for key in FORWARD_HEADERS if self.headers.get(key)}
        target = POST_ROUTES[path] if self.command == 'POST' else path
        query = urlsplit(self.path).query
        if query:
            target += '?' + query
        req = request.Request(self.upstream + target, data=body, headers=headers, method=self.command)
        try:
            with self.opener.open(req, timeout=45) as response:
                self.reply(response.status, response.read(MAX_BODY), response.headers)
        except error.HTTPError as exc:
            self.reply(exc.code, exc.read(MAX_BODY), exc.headers)
        except (error.URLError, TimeoutError):
            self.reply(502)

    do_POST = dispatch
    do_GET = dispatch
    do_PUT = dispatch
    do_PATCH = dispatch
    do_DELETE = dispatch
    do_OPTIONS = dispatch


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8033)
    args = parser.parse_args()
    ThreadingHTTPServer(('127.0.0.1', args.port), CallbackHandler).serve_forever()
