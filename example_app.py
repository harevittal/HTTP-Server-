"""
Example Application using Async Python HTTP Server.
"""

import os
import time
from http_server import HTTPServer, json_response, text_response, html_response, Response

def create_app() -> HTTPServer:
    server = HTTPServer(host="127.0.0.1", port=8080, worker_threads=16)

    # Mount static assets
    public_dir = os.path.join(os.path.dirname(__file__), "public")
    server.mount_static("/static", public_dir)

    # Logging Middleware
    @server.use
    def logging_middleware(req, next_handler):
        start = time.time()
        resp = next_handler(req)
        duration_ms = (time.time() - start) * 1000
        print(f"[{req.method}] {req.path} -> {resp.status_code} ({duration_ms:.2f}ms)")
        return resp

    # Home Route
    @server.get("/")
    def home(req):
        return Response.redirect("/static/index.html")

    # Health Check API
    @server.get("/api/health")
    def health(req):
        return json_response({
            "status": "healthy",
            "server": "Async Python HTTP/1.1 Server",
            "uptime_seconds": time.time()
        })

    # Time API
    @server.get("/api/time")
    def server_time(req):
        return json_response({
            "iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "timestamp": time.time()
        })

    # Echo API (POST JSON)
    @server.post("/api/echo")
    def echo(req):
        data = req.json()
        return json_response({
            "received": data,
            "headers": req.headers,
            "client": req.client_address
        })

    # Parameterized User Route
    @server.get("/api/users/<user_id>")
    def get_user(req):
        user_id = req.path_params.get("user_id")
        return json_response({
            "id": user_id,
            "name": f"User {user_id}",
            "role": "Engineer",
            "permissions": ["read", "write", "deploy"]
        })

    return server


if __name__ == "__main__":
    app = create_app()
    try:
        app.run()
    except KeyboardInterrupt:
        pass
