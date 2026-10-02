"""Authenticated, write-only analytics ingestion behind the HTTPS proxy."""

import hmac
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from analytics_collector import CollectionError, DEFAULT_OUTPUT
from analytics_receiver import MAX_INPUT, receive

INGEST_PATH = '/_bloguito/analytics-ingest'


def handler(token, output_dir=DEFAULT_OUTPUT):
    if not isinstance(token, str) or len(token) < 40:
        raise ValueError('analytics_ingest_token_missing_or_short')

    class IngestHandler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            # Do not log headers, report content, client URLs or exceptions.
            pass

        def respond(self, status, message):
            body = message.encode('ascii')
            self.send_response(status)
            self.send_header('Content-Type', 'text/plain; charset=ascii')
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Connection', 'close')
            self.end_headers()
            self.wfile.write(body)
            self.close_connection = True

        def do_GET(self):
            self.respond(405, 'method_not_allowed')

        def do_POST(self):
            self.connection.settimeout(15)
            if self.path != INGEST_PATH:
                self.respond(404, 'not_found')
                return
            auth = self.headers.get('Authorization', '')
            if not hmac.compare_digest(auth.encode('utf-8'), ('Bearer ' + token).encode('utf-8')):
                self.respond(401, 'unauthorized')
                return
            lengths = self.headers.get_all('Content-Length', [])
            if (len(lengths) != 1 or not lengths[0].isdigit()
                    or self.headers.get('Transfer-Encoding')
                    or self.headers.get_content_type() != 'application/json'):
                self.respond(400, 'invalid_request')
                return
            length = int(lengths[0])
            if not 0 < length <= MAX_INPUT:
                self.respond(413, 'payload_too_large')
                return
            try:
                data = self.rfile.read(length)
                if len(data) != length:
                    raise CollectionError('incomplete_snapshot')
                end = receive(data, output_dir=output_dir)
            except (CollectionError, OSError, TypeError, KeyError, OverflowError):
                self.respond(400, 'invalid_or_unwritable_report')
                return
            self.respond(200, 'analytics_ingest_ok end=' + end)

    return IngestHandler


def main():
    token = os.environ.get('BLOGUITO_ANALYTICS_TOKEN', '')
    server = ThreadingHTTPServer(('127.0.0.1', 8766), handler(token))
    server.serve_forever()


if __name__ == '__main__':
    main()
