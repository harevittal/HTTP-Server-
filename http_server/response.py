"""
HTTP/1.1 Response model and serialization logic.
"""

import json
from email.utils import formatdate
from typing import Dict, Optional, Union, Any
from .constants import HTTP_STATUS_CODES, SERVER_NAME, CRLF


class Response:
    """Represents an HTTP response."""
    def __init__(
        self,
        status_code: int = 200,
        headers: Optional[Dict[str, str]] = None,
        body: Union[bytes, str] = b"",
        content_type: Optional[str] = None,
    ):
        self.status_code = status_code
        self.headers: Dict[str, str] = {}
        if headers:
            for k, v in headers.items():
                self.headers[k.lower()] = v

        if isinstance(body, str):
            self.body: bytes = body.encode("utf-8")
            if content_type is None and "content-type" not in self.headers:
                self.headers["content-type"] = "text/plain; charset=utf-8"
        else:
            self.body = body

        if content_type:
            self.headers["content-type"] = content_type

    def set_header(self, name: str, value: str) -> "Response":
        """Sets a header (case-insensitive key)."""
        self.headers[name.lower()] = str(value)
        return self

    def get_header(self, name: str, default: Optional[str] = None) -> Optional[str]:
        """Gets a header value."""
        return self.headers.get(name.lower(), default)

    def to_bytes(self, include_body: bool = True, keep_alive: bool = True) -> bytes:
        """
        Serializes the response object into raw HTTP/1.1 wire bytes.
        """
        reason = HTTP_STATUS_CODES.get(self.status_code, "Unknown Status")
        status_line = f"HTTP/1.1 {self.status_code} {reason}\r\n".encode("latin-1")

        # Set mandatory standard headers
        if "server" not in self.headers:
            self.headers["server"] = SERVER_NAME
        if "date" not in self.headers:
            self.headers["date"] = formatdate(timeval=None, localtime=False, usegmt=True)
        if "content-length" not in self.headers:
            self.headers["content-length"] = str(len(self.body))
        if "connection" not in self.headers:
            self.headers["connection"] = "keep-alive" if keep_alive else "close"

        header_lines = bytearray(status_line)
        for name, value in self.headers.items():
            header_name = "-".join(part.capitalize() for part in name.split("-"))
            header_lines.extend(f"{header_name}: {value}\r\n".encode("latin-1"))

        header_lines.extend(CRLF)
        if include_body and self.body:
            header_lines.extend(self.body)

        return bytes(header_lines)

    @classmethod
    def json(cls, data: Any, status_code: int = 200, headers: Optional[Dict[str, str]] = None) -> "Response":
        """Convenience constructor for JSON response."""
        json_bytes = json.dumps(data, indent=2).encode("utf-8")
        resp = cls(status_code=status_code, headers=headers, body=json_bytes, content_type="application/json")
        return resp

    @classmethod
    def text(cls, text_content: str, status_code: int = 200, headers: Optional[Dict[str, str]] = None) -> "Response":
        """Convenience constructor for plain text response."""
        return cls(status_code=status_code, headers=headers, body=text_content, content_type="text/plain; charset=utf-8")

    @classmethod
    def html(cls, html_content: str, status_code: int = 200, headers: Optional[Dict[str, str]] = None) -> "Response":
        """Convenience constructor for HTML response."""
        return cls(status_code=status_code, headers=headers, body=html_content, content_type="text/html; charset=utf-8")

    @classmethod
    def redirect(cls, location: str, status_code: int = 302) -> "Response":
        """Convenience constructor for redirects."""
        resp = cls(status_code=status_code, body=f"Redirecting to {location}...")
        resp.set_header("location", location)
        return resp

    @classmethod
    def error(cls, status_code: int, message: Optional[str] = None) -> "Response":
        """Generates a standard HTTP error response."""
        reason = HTTP_STATUS_CODES.get(status_code, "Error")
        desc = message or reason
        body = f"{status_code} {reason}\n\n{desc}"
        return cls(status_code=status_code, body=body, content_type="text/plain; charset=utf-8")


# Helper shortcuts
def json_response(data: Any, status_code: int = 200) -> Response:
    return Response.json(data, status_code=status_code)


def text_response(text: str, status_code: int = 200) -> Response:
    return Response.text(text, status_code=status_code)


def html_response(html: str, status_code: int = 200) -> Response:
    return Response.html(html, status_code=status_code)
