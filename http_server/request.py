"""
HTTP/1.1 Request model and parsing logic.
"""

import json
from typing import Dict, List, Optional, Tuple, Any
from urllib.parse import parse_qs, unquote, urlparse
from .constants import MAX_HEADER_SIZE, MAX_BODY_SIZE, CRLF, DOUBLE_CRLF


class HTTPParsingError(Exception):
    """Raised when an incoming HTTP request is malformed."""
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


class Request:
    """Represents an HTTP request."""
    def __init__(
        self,
        method: str,
        target: str,
        path: str,
        query_string: str,
        query_params: Dict[str, List[str]],
        http_version: str,
        headers: Dict[str, str],
        body: bytes,
        client_address: Tuple[str, int] = ("", 0),
        path_params: Optional[Dict[str, str]] = None,
    ):
        self.method = method.upper()
        self.target = target
        self.path = path
        self.query_string = query_string
        self.query_params = query_params
        self.http_version = http_version
        self.headers = headers
        self.body = body
        self.client_address = client_address
        self.path_params = path_params or {}
        self._json_cache: Optional[Any] = None

    def get_header(self, name: str, default: Optional[str] = None) -> Optional[str]:
        """Case-insensitive header retrieval."""
        return self.headers.get(name.lower(), default)

    @property
    def is_keep_alive(self) -> bool:
        """Determines if the connection should be kept alive."""
        conn = self.get_header("connection", "").lower()
        if self.http_version == "HTTP/1.1":
            return conn != "close"
        elif self.http_version == "HTTP/1.0":
            return conn == "keep-alive"
        return False

    @property
    def content_length(self) -> int:
        """Returns the Content-Length header as an integer or 0."""
        val = self.get_header("content-length")
        if val is not None and val.isdigit():
            return int(val)
        return 0

    @property
    def content_type(self) -> str:
        """Returns the media type from the Content-Type header."""
        return self.get_header("content-type", "")

    def text(self, encoding: str = "utf-8") -> str:
        """Decodes body as text."""
        return self.body.decode(encoding, errors="replace")

    def json(self) -> Any:
        """Parses body as JSON."""
        if self._json_cache is not None:
            return self._json_cache
        if not self.body:
            return None
        self._json_cache = json.loads(self.text())
        return self._json_cache

    def form(self) -> Dict[str, List[str]]:
        """Parses x-www-form-urlencoded body."""
        return parse_qs(self.text())

    def __repr__(self) -> str:
        return f"<Request {self.method} {self.path} {self.http_version}>"


def parse_request_head(header_bytes: bytes) -> Tuple[str, str, str, str, Dict[str, List[str]], str, Dict[str, str]]:
    """
    Parses the request line and headers from the raw header byte slice.
    """
    if len(header_bytes) > MAX_HEADER_SIZE:
        raise HTTPParsingError("Request header exceeds maximum allowed size", status_code=431)

    try:
        header_text = header_bytes.decode("iso-8859-1")
    except UnicodeDecodeError:
        raise HTTPParsingError("Invalid character encoding in request headers", status_code=400)

    lines = header_text.split("\r\n")
    if not lines or not lines[0]:
        raise HTTPParsingError("Empty request line", status_code=400)

    # 1. Parse Request Line
    request_line_parts = lines[0].split(" ")
    if len(request_line_parts) != 3:
        raise HTTPParsingError(f"Malformed request line: '{lines[0]}'", status_code=400)

    method, raw_target, http_version = request_line_parts
    if not http_version.startswith("HTTP/"):
        raise HTTPParsingError(f"Unsupported protocol: '{http_version}'", status_code=505)

    # Parse target (path + query string)
    parsed_url = urlparse(raw_target)
    path = unquote(parsed_url.path)
    if not path.startswith("/"):
        path = "/" + path
    query_string = parsed_url.query
    query_params = parse_qs(query_string, keep_blank_values=True)

    # 2. Parse Headers
    headers: Dict[str, str] = {}
    for line in lines[1:]:
        if not line:
            continue
        if ":" not in line:
            raise HTTPParsingError(f"Malformed header line: '{line}'", status_code=400)
        name, value = line.split(":", 1)
        headers[name.strip().lower()] = value.strip()

    return method, raw_target, path, query_string, query_params, http_version, headers


def decode_chunked_body(raw_body: bytes) -> Tuple[bytes, int]:
    """
    Decodes a chunked transfer-encoded byte string.
    Returns (decoded_body, bytes_consumed).
    """
    decoded = bytearray()
    offset = 0
    total_len = len(raw_body)

    while offset < total_len:
        # Find next CRLF ending the chunk-size line
        crlf_pos = raw_body.find(CRLF, offset)
        if crlf_pos == -1:
            # Incomplete chunk header
            return bytes(decoded), -1

        size_line = raw_body[offset:crlf_pos].decode("ascii", errors="ignore").split(";")[0].strip()
        try:
            chunk_size = int(size_line, 16)
        except ValueError:
            raise HTTPParsingError("Invalid chunk size in chunked encoding", status_code=400)

        offset = crlf_pos + 2

        if chunk_size == 0:
            # End of chunks, find trailer end
            end_crlf = raw_body.find(CRLF, offset)
            if end_crlf == -1:
                return bytes(decoded), -1
            return bytes(decoded), end_crlf + 2

        if offset + chunk_size + 2 > total_len:
            # Incomplete chunk data
            return bytes(decoded), -1

        decoded.extend(raw_body[offset:offset + chunk_size])
        offset += chunk_size + 2  # Skip data + trailing CRLF

    return bytes(decoded), offset


def parse_request(raw_data: bytes, client_address: Tuple[str, int] = ("", 0)) -> Tuple[Optional[Request], int]:
    """
    Attempts to parse a complete HTTP Request from a byte buffer.
    Returns (Request, bytes_consumed) if complete, or (None, 0) if incomplete.
    """
    # 1. Find the delimiter between headers and body
    header_end = raw_data.find(DOUBLE_CRLF)
    if header_end == -1:
        if len(raw_data) > MAX_HEADER_SIZE:
            raise HTTPParsingError("Headers too large", status_code=431)
        return None, 0

    header_bytes = raw_data[:header_end]
    body_start = header_end + 4

    (method, target, path, query_string,
     query_params, http_version, headers) = parse_request_head(header_bytes)

    # 2. Body Handling
    transfer_encoding = headers.get("transfer-encoding", "").lower()
    content_length_str = headers.get("content-length")

    if "chunked" in transfer_encoding:
        chunked_slice = raw_data[body_start:]
        decoded_body, bytes_consumed = decode_chunked_body(chunked_slice)
        if bytes_consumed == -1:
            return None, 0  # Need more data
        
        req = Request(
            method=method,
            target=target,
            path=path,
            query_string=query_string,
            query_params=query_params,
            http_version=http_version,
            headers=headers,
            body=decoded_body,
            client_address=client_address,
        )
        return req, body_start + bytes_consumed

    elif content_length_str is not None:
        try:
            content_length = int(content_length_str)
        except ValueError:
            raise HTTPParsingError("Invalid Content-Length header", status_code=400)

        if content_length > MAX_BODY_SIZE:
            raise HTTPParsingError("Payload Too Large", status_code=413)

        total_needed = body_start + content_length
        if len(raw_data) < total_needed:
            return None, 0  # Incomplete body

        body = raw_data[body_start:total_needed]
        req = Request(
            method=method,
            target=target,
            path=path,
            query_string=query_string,
            query_params=query_params,
            http_version=http_version,
            headers=headers,
            body=body,
            client_address=client_address,
        )
        return req, total_needed

    else:
        # No body expected for GET/HEAD or 0 length
        body = b""
        req = Request(
            method=method,
            target=target,
            path=path,
            query_string=query_string,
            query_params=query_params,
            http_version=http_version,
            headers=headers,
            body=body,
            client_address=client_address,
        )
        return req, body_start
