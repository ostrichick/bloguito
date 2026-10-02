import http.client
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

from analytics_http_receiver import INGEST_PATH, handler
from analytics_receiver import MAX_INPUT


class HttpReceiverTests(unittest.TestCase):
    def setUp(self):
        self.token = 'test-token-' + 'x' * 48
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), handler(self.token, Path(self.directory.name)))
        thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)

    def request(self, *, method='POST', path=INGEST_PATH, token=None, body=b'{}', headers=None):
        connection = http.client.HTTPConnection(*self.server.server_address, timeout=3)
        request_headers = {'Authorization': 'Bearer ' + (token or self.token), 'Content-Type': 'application/json'}
        request_headers.update(headers or {})
        connection.request(method, path, body, request_headers)
        response = connection.getresponse()
        status, data = response.status, response.read()
        connection.close()
        return status, data

    def test_auth_and_request_bounds_reject_without_receiving(self):
        with patch('analytics_http_receiver.receive') as ingest:
            self.assertEqual(self.request(token='wrong')[0], 401)
            self.assertEqual(self.request(method='GET')[0], 405)
            self.assertEqual(self.request(path='/arbitrary')[0], 404)
            self.assertEqual(self.request(headers={'Content-Length': str(MAX_INPUT + 1)})[0], 413)
            self.assertEqual(self.request(headers={'Content-Type': 'text/plain'})[0], 400)
            ingest.assert_not_called()

    def test_invalid_snapshot_is_not_persisted(self):
        self.assertEqual(self.request()[0], 400)
        self.assertEqual(list(Path(self.directory.name).iterdir()), [])

    def test_authenticated_request_uses_existing_receiver_without_returning_report(self):
        with patch('analytics_http_receiver.receive', return_value='2026-10-01') as ingest:
            status, body = self.request(body=b'{"private":"snapshot"}')
        self.assertEqual(status, 200)
        self.assertEqual(body, b'analytics_ingest_ok end=2026-10-01')
        ingest.assert_called_once_with(b'{"private":"snapshot"}', output_dir=Path(self.directory.name))

    def test_missing_token_fails_before_server_start(self):
        with self.assertRaisesRegex(ValueError, 'token_missing'):
            handler('')
