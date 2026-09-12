"""
Static file handler with path traversal security, MIME resolution, and caching headers.
"""

import os
import mimetypes
import hashlib
from email.utils import formatdate, parsedate_to_datetime
from datetime import timezone
from typing import Optional, Tuple
from .request import Request
from .response import Response


class StaticFileHandler:
    """Safely serves static files from a specified directory."""
    def __init__(self, root_dir: str, url_prefix: str = "/static"):
        self.root_dir = os.path.abspath(root_dir)
        self.url_prefix = url_prefix.rstrip("/")

        # Initialize extra mime types
        mimetypes.init()
        mimetypes.add_type("application/javascript", ".js")
        mimetypes.add_type("text/css", ".css")
        mimetypes.add_type("image/svg+xml", ".svg")
        mimetypes.add_type("application/json", ".json")

    def _get_safe_path(self, req_path: str) -> Optional[str]:
        """Resolves path and guards against path traversal vulnerabilities."""
        relative = req_path
        if self.url_prefix and req_path.startswith(self.url_prefix):
            relative = req_path[len(self.url_prefix):]

        relative = relative.lstrip("/\\")
        if not relative:
            relative = "index.html"

        target_path = os.path.abspath(os.path.join(self.root_dir, relative))

        # Security check: target must be inside root_dir
        try:
            common = os.path.commonpath([self.root_dir, target_path])
            if common != self.root_dir:
                return None
        except ValueError:
            return None

        return target_path

    def handle(self, request: Request) -> Optional[Response]:
        """
        Attempts to serve static file for request. Returns Response or None if not found/invalid.
        """
        file_path = self._get_safe_path(request.path)
        if not file_path or not os.path.exists(file_path):
            return None

        if os.path.isdir(file_path):
            index_path = os.path.join(file_path, "index.html")
            if os.path.exists(index_path):
                file_path = index_path
            else:
                return None

        try:
            stat_info = os.stat(file_path)
        except OSError:
            return None

        last_modified = stat_info.st_mtime
        file_size = stat_info.st_size
        last_modified_str = formatdate(last_modified, usegmt=True)

        # Generate simple ETag
        etag = f'"{hashlib.md5(f"{last_modified}-{file_size}".encode()).hexdigest()}"'

        # Conditional GET (If-None-Match / If-Modified-Since)
        if_none_match = request.get_header("if-none-match")
        if if_none_match and if_none_match == etag:
            return Response(status_code=304)

        if_modified_since = request.get_header("if-modified-since")
        if if_modified_since:
            try:
                ims_dt = parsedate_to_datetime(if_modified_since)
                if ims_dt.timestamp() >= int(last_modified):
                    return Response(status_code=304)
            except Exception:
                pass

        # Determine MIME type
        mime_type, _ = mimetypes.guess_type(file_path)
        if not mime_type:
            mime_type = "application/octet-stream"

        # Check for Range header
        range_header = request.get_header("range")
        if range_header and range_header.startswith("bytes="):
            return self._handle_range_request(file_path, range_header, file_size, mime_type, last_modified_str, etag)

        # Read file
        try:
            with open(file_path, "rb") as f:
                content = f.read()
        except OSError:
            return Response.error(500, "Unable to read static file")

        resp = Response(status_code=200, body=content, content_type=mime_type)
        resp.set_header("last-modified", last_modified_str)
        resp.set_header("etag", etag)
        resp.set_header("accept-ranges", "bytes")
        return resp

    def _handle_range_request(
        self, file_path: str, range_header: str, file_size: int,
        mime_type: str, last_modified_str: str, etag: str
    ) -> Response:
        """Handles HTTP Byte Range Requests (206 Partial Content)."""
        try:
            byte_range = range_header.replace("bytes=", "").split("-")
            start = int(byte_range[0]) if byte_range[0] else 0
            end = int(byte_range[1]) if len(byte_range) > 1 and byte_range[1] else file_size - 1

            if start >= file_size or end >= file_size or start > end:
                resp = Response(status_code=416, body="Requested Range Not Satisfiable")
                resp.set_header("content-range", f"bytes */{file_size}")
                return resp

            length = end - start + 1
            with open(file_path, "rb") as f:
                f.seek(start)
                content = f.read(length)

            resp = Response(status_code=206, body=content, content_type=mime_type)
            resp.set_header("content-range", f"bytes {start}-{end}/{file_size}")
            resp.set_header("content-length", str(length))
            resp.set_header("last-modified", last_modified_str)
            resp.set_header("etag", etag)
            resp.set_header("accept-ranges", "bytes")
            return resp
        except Exception:
            return Response.error(400, "Invalid Range Header")
