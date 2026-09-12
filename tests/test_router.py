"""
Unit tests for Router and Path Matching.
"""

import unittest
from http_server.router import Router
from http_server.response import Response, text_response


class TestRouter(unittest.TestCase):
    def setUp(self):
        self.router = Router()

    def test_exact_path_routing(self):
        @self.router.get("/health")
        def health_handler(req):
            return text_response("OK")

        handler, params, err = self.router.resolve("GET", "/health")
        self.assertIsNotNone(handler)
        self.assertEqual(params, {})
        self.assertIsNone(err)

    def test_parameterized_routing(self):
        @self.router.get("/users/<user_id>/posts/<post_id>")
        def get_post(req):
            return text_response(f"User {req.path_params['user_id']} Post {req.path_params['post_id']}")

        handler, params, err = self.router.resolve("GET", "/users/42/posts/101")
        self.assertIsNotNone(handler)
        self.assertEqual(params, {"user_id": "42", "post_id": "101"})
        self.assertIsNone(err)

    def test_method_not_allowed(self):
        @self.router.get("/only-get")
        def only_get(req):
            return text_response("GET only")

        handler, params, err = self.router.resolve("POST", "/only-get")
        self.assertIsNone(handler)
        self.assertEqual(err, 405)

    def test_not_found(self):
        handler, params, err = self.router.resolve("GET", "/does-not-exist")
        self.assertIsNone(handler)
        self.assertEqual(err, 404)


if __name__ == "__main__":
    unittest.main()
