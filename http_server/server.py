"""
High-Performance Asynchronous HTTP/1.1 Server implementation.
Uses raw TCP sockets, non-blocking selectors, and worker thread pool offloading.
"""

import sys
import os
import time
import socket
import select
import selectors
import signal
import logging
from typing import Dict, Optional, Callable, List, Any
from .constants import SERVER_NAME
from .request import Request
from .response import Response
from .router import Router
from .static_handler import StaticFileHandler
from .connection import HTTPConnection, ConnectionState
from .thread_pool import WorkerPool

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] (%(threadName)s) %(message)s"
)
logger = logging.getLogger("HTTPServer")


class HTTPServer:
    """
    Asynchronous Non-Blocking HTTP/1.1 Server.
    """
    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 8080,
        worker_threads: int = 16,
        backlog: int = 1024,
    ):
        self.host = host
        self.port = port
        self.backlog = backlog
        self.router = Router()
        self.static_handlers: List[StaticFileHandler] = []
        self.worker_pool = WorkerPool(max_workers=worker_threads)

        self._selector: Optional[selectors.BaseSelector] = None
        self._server_sock: Optional[socket.socket] = None
        self._connections: Dict[int, HTTPConnection] = {}
        self._running = False
        self._last_sweep_time = time.time()

    def mount_static(self, url_prefix: str, directory: str):
        """Mounts a static directory."""
        handler = StaticFileHandler(root_dir=directory, url_prefix=url_prefix)
        self.static_handlers.append(handler)

    # Router convenience decorators
    def get(self, path: str):
        return self.router.get(path)

    def post(self, path: str):
        return self.router.post(path)

    def put(self, path: str):
        return self.router.put(path)

    def delete(self, path: str):
        return self.router.delete(path)

    def route(self, path: str, methods: Optional[List[str]] = None):
        return self.router.route(path, methods)

    def use(self, middleware: Callable):
        self.router.use(middleware)

    def _setup_socket(self) -> socket.socket:
        """Initializes and configures the master non-blocking listening socket."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        if hasattr(socket, "SO_REUSEPORT") and sys.platform != "win32":
            try:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
            except OSError:
                pass

        sock.setblocking(False)
        sock.bind((self.host, self.port))
        sock.listen(self.backlog)
        return sock

    def _accept_connection(self):
        """Accepts an incoming TCP connection."""
        while True:
            try:
                client_sock, client_addr = self._server_sock.accept()
                client_sock.setblocking(False)
                # Disable Nagle's algorithm for low-latency HTTP
                client_sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

                fileno = client_sock.fileno()
                conn = HTTPConnection(client_sock, client_addr)
                self._connections[fileno] = conn

                self._selector.register(client_sock, selectors.EVENT_READ, data=conn)
                logger.debug(f"Accepted connection from {client_addr} (fd={fileno})")
            except (BlockingIOError, InterruptedError):
                break
            except socket.error:
                break

    def _close_connection(self, conn: HTTPConnection):
        """Closes connection and unregisters from selector."""
        fileno = conn.sock.fileno()
        try:
            self._selector.unregister(conn.sock)
        except Exception:
            pass

        if fileno in self._connections:
            del self._connections[fileno]

        conn.close()
        logger.debug(f"Closed connection fd={fileno}")

    def _handle_request_execution(self, req: Request) -> Response:
        """
        Executes request through static handlers, middlewares, and router handlers.
        """
        # 1. Check static handlers
        for static_handler in self.static_handlers:
            if static_handler.url_prefix == "" or req.path.startswith(static_handler.url_prefix):
                resp = static_handler.handle(req)
                if resp is not None:
                    return resp

        # 2. Check router
        handler, path_params, err_code = self.router.resolve(req.method, req.path)
        if err_code == 404:
            return Response.error(404, f"Resource '{req.path}' not found")
        elif err_code == 405:
            return Response.error(405, f"Method '{req.method}' not allowed for '{req.path}'")

        req.path_params = path_params

        # 3. Apply middlewares and handler
        def execute_pipeline(curr_req: Request) -> Response:
            idx = 0
            middlewares = self.router.middlewares

            def next_handler(r: Request) -> Response:
                nonlocal idx
                if idx < len(middlewares):
                    curr_mid = middlewares[idx]
                    idx += 1
                    return curr_mid(r, next_handler)
                else:
                    res = handler(r)
                    if isinstance(res, Response):
                        return res
                    elif isinstance(res, (dict, list)):
                        return Response.json(res)
                    elif isinstance(res, str):
                        return Response.text(res)
                    elif isinstance(res, bytes):
                        return Response(body=res)
                    elif res is None:
                        return Response(status_code=204)
                    else:
                        return Response.text(str(res))

            return next_handler(curr_req)

        try:
            return execute_pipeline(req)
        except Exception as e:
            logger.exception(f"Error handling request {req.method} {req.path}: {e}")
            return Response.error(500, f"Internal Server Error: {str(e)}")

    def _process_read(self, conn: HTTPConnection):
        """Processes incoming data on ready client socket."""
        ok = conn.read_from_socket()
        if not ok:
            self._close_connection(conn)
            return

        # Attempt to parse requests
        while True:
            req, err_resp = conn.parse_next_request()
            if err_resp is not None:
                conn.queue_response(err_resp)
                self._update_selector_events(conn)
                break

            if req is None:
                # Need more bytes or buffer is empty
                break

            # Handle request
            is_head = (req.method == "HEAD")
            resp = self._handle_request_execution(req)
            conn.queue_response(resp, is_head_request=is_head)
            self._update_selector_events(conn)

    def _process_write(self, conn: HTTPConnection):
        """Processes outgoing data on writable client socket."""
        flushed = conn.write_to_socket()
        if conn.state == ConnectionState.CLOSED:
            self._close_connection(conn)
        else:
            self._update_selector_events(conn)

    def _update_selector_events(self, conn: HTTPConnection):
        """Updates selector interest based on connection state and buffer."""
        try:
            if conn.state == ConnectionState.CLOSED:
                self._close_connection(conn)
                return

            events = selectors.EVENT_READ
            if conn.write_buffer:
                events |= selectors.EVENT_WRITE

            self._selector.modify(conn.sock, events, data=conn)
        except (KeyError, OSError):
            self._close_connection(conn)

    def _sweep_idle_connections(self):
        """Closes connections that have exceeded the keep-alive idle timeout."""
        now = time.time()
        if now - self._last_sweep_time < 1.0:
            return
        self._last_sweep_time = now

        timed_out = [
            conn for conn in list(self._connections.values())
            if conn.is_timed_out(now)
        ]
        for conn in timed_out:
            logger.debug(f"Closing timed out idle connection fd={conn.sock.fileno()}")
            self._close_connection(conn)

    def run(self):
        """Starts the server event loop."""
        self._selector = selectors.DefaultSelector()
        self._server_sock = self._setup_socket()
        self._selector.register(self._server_sock, selectors.EVENT_READ, data=None)
        self._running = True

        logger.info(f"🚀 HTTP Server running at http://{self.host}:{self.port} (PID: {os.getpid()})")

        # Setup graceful shutdown handlers
        def signal_handler(signum, frame):
            logger.info("Received termination signal. Shutting down gracefully...")
            self.stop()

        try:
            signal.signal(signal.SIGINT, signal_handler)
            signal.signal(signal.SIGTERM, signal_handler)
        except (ValueError, AttributeError):
            pass

        try:
            while self._running:
                # Poll selector with short timeout for timer sweeps
                events = self._selector.select(timeout=0.5)
                for key, mask in events:
                    if key.data is None:
                        # Event on master server socket -> accept connections
                        self._accept_connection()
                    else:
                        conn: HTTPConnection = key.data
                        if mask & selectors.EVENT_READ:
                            self._process_read(conn)
                        if mask & selectors.EVENT_WRITE:
                            self._process_write(conn)

                # Periodic sweep
                self._sweep_idle_connections()

        finally:
            self._cleanup()

    def stop(self):
        """Signals the event loop to stop."""
        self._running = False

    def _cleanup(self):
        """Cleans up sockets, selector, and thread pool."""
        logger.info("Cleaning up server resources...")
        for conn in list(self._connections.values()):
            try:
                conn.close()
            except Exception:
                pass
        self._connections.clear()

        if self._server_sock:
            try:
                self._selector.unregister(self._server_sock)
                self._server_sock.close()
            except Exception:
                pass

        if self._selector:
            try:
                self._selector.close()
            except Exception:
                pass

        self.worker_pool.shutdown(wait=False)
        logger.info("Server stopped successfully.")
