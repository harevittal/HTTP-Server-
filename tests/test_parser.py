"""
Unit tests for HTTP Request Parsing.
"""

import unittest
from http_server.request import parse_request, decode_chunked_body, HTTPParsingError


class TestHTTPParser(unittest.TestCase):
    def test_simple_get_request(self):
        raw = b"GET /index.html HTTP/1.1\r\nHost: localhost:8080\r\nUser-Agent: TestClient\r\n\r\n"
        req, consumed = parse_request(raw)
        self.assertIsNotNone(req)
        self.assertEqual(req.method, "GET")
        self.assertEqual(req.path, "/index.html")
        self.assertEqual(req.http_version, "HTTP/1.1")
        self.assertEqual(req.get_header("host"), "localhost:8080")
        self.assertEqual(consumed, len(raw))

    def test_get_request_with_query_params(self):
        raw = b"GET /search?q=python%20async&page=2 HTTP/1.1\r\nHost: example.com\r\n\r\n"
        req, consumed = parse_request(raw)
        self.assertIsNotNone(req)
        self.assertEqual(req.path, "/search")
        self.assertEqual(req.query_params.get("q"), ["python async"])
        self.assertEqual(req.query_params.get("page"), ["2"])

    def test_post_request_with_json_body(self):
        body = b'{"name": "Alice", "age": 30}'
        raw = (
            b"POST /api/users HTTP/1.1\r\n"
            b"Host: localhost\r\n"
            b"Content-Type: application/json\r\n"
            b"Content-Length: " + str(len(body)).encode() + b"\r\n\r\n" + body
        )
        req, consumed = parse_request(raw)
        self.assertIsNotNone(req)
        self.assertEqual(req.method, "POST")
        self.assertEqual(req.json(), {"name": "Alice", "age": 30})
        self.assertEqual(consumed, len(raw))

    def test_incomplete_request_returns_none(self):
        raw = b"GET /index.html HTTP/1.1\r\nHost: localhost"  # No ending \r\n\r\n
        req, consumed = parse_request(raw)
        self.assertIsNone(req)
        self.assertEqual(consumed, 0)

    def test_chunked_transfer_decoding(self):
        chunks = b"4\r\nWiki\r\n6\r\npedia \r\nE\r\nin \r\n\r\nchunks.\r\n0\r\n\r\n"
        decoded, consumed = decode_chunked_body(chunks)
        self.assertEqual(decoded, b"Wikipedia in \r\n\r\nchunks.")
        self.assertEqual(consumed, len(chunks))

    def test_malformed_request_line(self):
        raw = b"INVALID_REQUEST\r\nHost: localhost\r\n\r\n"
        with self.assertRaises(HTTPParsingError):
            parse_request(raw)


if __name__ == "__main__":
    unittest.main()
