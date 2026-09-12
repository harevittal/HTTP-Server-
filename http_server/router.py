"""
Router and URL dispatcher supporting exact match, parameterized routes, and HTTP methods.
"""

import re
from typing import Callable, Dict, List, Optional, Tuple, Any
from .request import Request
from .response import Response


RouteHandler = Callable[..., Any]
Middleware = Callable[[Request, Callable[[Request], Response]], Response]


class Route:
    """Represents a single registered HTTP route."""
    def __init__(self, path_pattern: str, methods: List[str], handler: RouteHandler):
        self.path_pattern = path_pattern
        self.methods = [m.upper() for m in methods]
        self.handler = handler
        self.param_names: List[str] = []
        self.regex = self._compile_pattern(path_pattern)

    def _compile_pattern(self, pattern: str) -> re.Pattern:
        """Converts `/users/<id>/profile` to regex `^/users/(?P<id>[^/]+)/profile$`."""
        # Find all <param_name> in pattern
        segments = pattern.strip("/").split("/")
        regex_parts = []

        if not pattern.strip("/"):
            return re.compile(r"^/$")

        for segment in segments:
            if segment.startswith("<") and segment.endswith(">"):
                param_name = segment[1:-1]
                self.param_names.append(param_name)
                regex_parts.append(rf"(?P<{param_name}>[^/]+)")
            else:
                regex_parts.append(re.escape(segment))

        regex_str = r"^/" + "/".join(regex_parts) + r"/?$"
        return re.compile(regex_str)

    def match(self, path: str) -> Optional[Dict[str, str]]:
        """Matches path and returns extracted parameters dictionary or None."""
        m = self.regex.match(path)
        if m:
            return m.groupdict()
        return None


class Router:
    """Manages routing table and endpoint dispatching."""
    def __init__(self):
        self.routes: List[Route] = []
        self.middlewares: List[Middleware] = []

    def use(self, middleware: Middleware) -> None:
        """Registers a global middleware."""
        self.middlewares.append(middleware)

    def add_route(self, path: str, methods: List[str], handler: RouteHandler) -> None:
        """Registers a route for specific HTTP methods."""
        route = Route(path, methods, handler)
        self.routes.append(route)

    def get(self, path: str):
        """Decorator for GET routes."""
        def decorator(fn: RouteHandler):
            self.add_route(path, ["GET", "HEAD"], fn)
            return fn
        return decorator

    def post(self, path: str):
        """Decorator for POST routes."""
        def decorator(fn: RouteHandler):
            self.add_route(path, ["POST"], fn)
            return fn
        return decorator

    def put(self, path: str):
        """Decorator for PUT routes."""
        def decorator(fn: RouteHandler):
            self.add_route(path, ["PUT"], fn)
            return fn
        return decorator

    def delete(self, path: str):
        """Decorator for DELETE routes."""
        def decorator(fn: RouteHandler):
            self.add_route(path, ["DELETE"], fn)
            return fn
        return decorator

    def route(self, path: str, methods: Optional[List[str]] = None):
        """Decorator for multi-method routes."""
        if methods is None:
            methods = ["GET"]
        def decorator(fn: RouteHandler):
            self.add_route(path, methods, fn)
            return fn
        return decorator

    def resolve(self, method: str, path: str) -> Tuple[Optional[RouteHandler], Dict[str, str], Optional[int]]:
        """
        Resolves a method and path.
        Returns: (handler, path_params, error_status_code)
        If found: (handler, params, None)
        If path matches but method not allowed: (None, {}, 405)
        If not found: (None, {}, 404)
        """
        matched_path_routes: List[Route] = []

        for r in self.routes:
            params = r.match(path)
            if params is not None:
                matched_path_routes.append(r)
                if method.upper() in r.methods:
                    return r.handler, params, None

        if matched_path_routes:
            return None, {}, 405  # Method Not Allowed

        return None, {}, 404  # Not Found
