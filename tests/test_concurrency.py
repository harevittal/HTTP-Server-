"""
Concurrency and Load Tests for HTTP Server.
"""

import unittest
import threading
import socket
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from http_server.server import HTTPServer
from http_server.response import json_response


class TestServerConcurrency(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        s = socket.socket()
        s.bind(("", 0))
        cls.port = s.getsockname()[1]
        s.close()

        cls.server = HTTPServer(host="127.0.0.1", port=cls.port, worker_threads=16)

        @cls.server.get("/ping")
        def ping_handler(req):
            return json_response({"message": "pong"})

        cls.server_thread = threading.Thread(target=cls.server.run, daemon=True)
        cls.server_thread.start()
        time.sleep(0.3)

    @classmethod
    def tearDownClass(cls):
        cls.server.stop()
        cls.server_thread.join(timeout=1.0)

    def test_concurrent_clients(self):
        num_requests = 100
        concurrency = 20
        url = f"http://127.0.0.1:{self.port}/ping"

        def send_request(idx):
            with urllib.request.urlopen(url, timeout=5) as response:
                return response.status

        with ThreadPoolExecutor(max_workers=concurrency) as executor:
            futures = [executor.submit(send_request, i) for i in range(num_requests)]
            results = [f.result() for f in futures]

        self.assertEqual(len(results), num_requests)
        self.assertTrue(all(status == 200 for status in results))


if __name__ == "__main__":
    unittest.main()
