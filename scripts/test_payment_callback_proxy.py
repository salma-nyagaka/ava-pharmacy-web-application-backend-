import threading
import json
import unittest
from http.server import ThreadingHTTPServer
from unittest.mock import patch, Mock
from urllib import request, error
from payment_callback_proxy import CallbackHandler, logged_path


class GatewayTests(unittest.TestCase):
    def setUp(self):
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), CallbackHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = 'http://127.0.0.1:' + str(self.server.server_port)

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def test_other_paths_and_methods_never_reach_backend(self):
        with patch.object(CallbackHandler.opener, 'open') as upstream:
            for path, method in [('/admin/', 'GET'), ('/api/auth/login/', 'POST'),
                                 ('/api/orders/', 'GET'), ('/callbacks/mobile/stk/', 'GET'),
                                 ('/api/payments/mpesa/callback/', 'DELETE'),
                                 ('/api/payments/mpesa/%2e%2e/callback/', 'POST')]:
                with self.subTest(path=path, method=method), self.assertRaises(error.HTTPError) as response:
                    request.urlopen(request.Request(self.url+path, method=method))
                self.assertEqual(response.exception.code, 404)
            upstream.assert_not_called()

    def test_callback_forwards_signature_and_body_but_not_login_headers(self):
        with patch.object(CallbackHandler.opener, 'open') as upstream:
            response = upstream.return_value.__enter__.return_value
            response.status, response.headers = 200, {'Content-Type': 'application/json'}
            response.read.return_value = b'{"accepted":true}'
            req = request.Request(self.url+'/callbacks/mobile/stk/', data=b'{}',
                                  headers={'X-Ava-Mpesa-Secret':'test-only', 'Authorization':'Bearer must-not-forward',
                                           'Cookie':'session=must-not-forward'})
            with request.urlopen(req) as received:
                self.assertEqual(received.status, 200)
            forwarded = upstream.call_args.args[0]
            self.assertEqual(forwarded.data, b'{}')
            self.assertEqual(forwarded.get_header('X-ava-mpesa-secret'), 'test-only')
            self.assertIsNone(forwarded.get_header('Authorization'))
            self.assertIsNone(forwarded.get_header('Cookie'))

    def test_mobile_alias_preserves_callback_authentication(self):
        with patch.object(CallbackHandler.opener, 'open') as upstream:
            response = upstream.return_value.__enter__.return_value
            response.status, response.headers = 200, {}
            response.read.return_value = b'{}'
            with request.urlopen(request.Request(self.url+'/callbacks/mobile/confirm/?token=test-only', data=b'{}')):
                pass
            self.assertEqual(upstream.call_args.args[0].full_url,
                             'http://127.0.0.1:8000/api/payments/mpesa/paybill/confirmation/?token=test-only')

    def test_consultation_alias_forwards_only_to_consultation_callback(self):
        with patch.object(CallbackHandler.opener, 'open') as upstream:
            response = upstream.return_value.__enter__.return_value
            response.status, response.headers = 200, {}
            response.read.return_value = b'{}'
            with request.urlopen(request.Request(self.url+'/callbacks/consultation/stk/?token=test-only', data=b'{}')):
                pass
            self.assertEqual(upstream.call_args.args[0].full_url,
                             'http://127.0.0.1:8000/api/consultations/payments/mpesa/callback/?token=test-only')

    def test_sensitive_path_segments_are_redacted_in_logs(self):
        token = 'a' * 32
        self.assertEqual(logged_path('/callbacks/mobile/' + token + '/confirm/'),
                         '/callbacks/mobile/[redacted]/confirm/')

    def test_disconnected_client_still_records_redacted_callback_result(self):
        handler = object.__new__(CallbackHandler)
        handler.command = 'POST'
        handler.path = '/callbacks/mobile/' + ('b' * 32) + '/confirm/?token=must-not-log'
        handler.send_response = Mock()
        handler.send_header = Mock()
        handler.end_headers = Mock()
        handler.wfile = Mock()
        handler.wfile.write.side_effect = BrokenPipeError()
        with patch('builtins.print') as logged:
            handler.reply(200, b'{}')
        event = json.loads(logged.call_args.args[0])
        self.assertEqual(event['status'], 200)
        self.assertEqual(event['path'], '/callbacks/mobile/[redacted]/confirm/')
        self.assertNotIn('must-not-log', logged.call_args.args[0])


if __name__ == '__main__':
    unittest.main()
