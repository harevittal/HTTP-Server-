"""
Integration tests: Runs the HTTP Server and tests with raw TCP sockets and HTTP client.
"""

import unittest
import threading
import socket
import time
import urllib.request
import urllib.error
import json
import os
from http_server.server import HTTPServer
from http_server.response import json_response, text_response


class TestHTTPServerIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Pick random available port
        s = socket.socket()
        s.bind(("", 0))
        cls.port = s.getsockname()[1]
        s.close()

        cls.server = HTTPServer(host="127.0.0.1", port=cls.port)

        # Register test routes
        @cls.server.get("/api/hello")
        def hello_handler(req):
            return text_response("Hello, World!")

        @cls.server.post("/api/echo")
        def echo_handler(req):
            data = req.json()
            return json_response({"echo": data})

        @cls.server.get("/api/users/<uid>")
        def user_handler(req):
            uid = req.path_params.get("uid")
            return json_response({"user_id": uid, "status": "active"})

        # Mount static directory
        static_dir = os.path.join(os.path.dirname(__file__), "..", "public")
        cls.server.mount_static("/static", static_dir)

        # Start server in background thread
        cls.server_thread = threading.Thread(target=cls.server.run, daemon=True)
        cls.server_thread.start()
        time.sleep(0.3)  # Allow server to bind

    @classmethod
    def tearDownClass(cls):
        cls.server.stop()
        cls.server_thread.join(timeout=1.0)

    def test_get_endpoint(self):
        url = f"http://127.0.0.1:{self.port}/api/hello"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req) as response:
            self.assertEqual(response.status, 200)
            self.assertEqual(response.read().decode(), "Hello, World!")

    def test_post_json_endpoint(self):
        url = f"http://127.0.0.1:{self.port}/api/echo"
        payload = json.dumps({"test": "data"}).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req) as response:
            self.assertEqual(response.status, 200)
            data = json.loads(response.read().decode())
            self.assertEqual(data["echo"], {"test": "data"})

    def test_parameterized_route(self):
        url = f"http://127.0.0.1:{self.port}/api/users/999"
        with urllib.request.urlopen(url) as response:
            self.assertEqual(response.status, 200)
            data = json.loads(response.read().decode())
            self.assertEqual(data["user_id"], "999")

    def test_static_file_serving(self):
        url = f"http://127.0.0.1:{self.port}/static/index.html"
        with urllib.request.urlopen(url) as response:
            self.assertEqual(response.status, 200)
            self.assertIn(b"Async HTTP/1.1 Server", response.read())

    def test_404_not_found(self):
        url = f"http://127.0.0.1:{self.port}/non-existent-page"
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(url)
        self.assertEqual(ctx.exception.code, 404)

    def test_keep_alive_raw_socket(self):
        # Open raw socket and send 2 pipelined/sequential requests on same TCP connection
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect(("127.0.0.1", self.port))

        req1 = b"GET /api/hello HTTP/1.1\r\nHost: localhost\r\nConnection: keep-alive\r\n\r\n"
        sock.sendall(req1)
        resp1 = sock.recv(4096)
        self.assertIn(b"200 OK", resp1)
        self.assertIn(b"Hello, World!", resp1)

        req2 = b"GET /api/users/123 HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n"
        sock.sendall(req2)
        resp2 = sock.recv(4096)
        self.assertIn(b"200 OK", resp2)
        self.assertIn(b'"user_id": "123"', resp2)

        sock.close()


if __name__ == "__main__":
    unittest.main()
