"""
HTTP Server Constants and Status Code definitions.
Standard RFC 7231 / RFC 7230 definitions.
"""

from typing import Dict

# HTTP Status Codes
HTTP_STATUS_CODES: Dict[int, str] = {
    100: "Continue",
    101: "Switching Protocols",
    200: "OK",
    201: "Created",
    202: "Accepted",
    204: "No Content",
    301: "Moved Permanently",
    302: "Found",
    304: "Not Modified",
    307: "Temporary Redirect",
    308: "Permanent Redirect",
    400: "Bad Request",
    401: "Unauthorized",
    403: "Forbidden",
    404: "Not Found",
    405: "Method Not Allowed",
    408: "Request Timeout",
    411: "Length Required",
    413: "Payload Too Large",
    414: "URI Too Long",
    415: "Unsupported Media Type",
    500: "Internal Server Error",
    501: "Not Implemented",
    502: "Bad Gateway",
    503: "Service Unavailable",
    505: "HTTP Version Not Supported",
}

# Defaults & Limits
DEFAULT_RECV_BUFFER_SIZE = 8192      # 8 KB per read chunk
MAX_HEADER_SIZE = 65536               # 64 KB max header limit
MAX_BODY_SIZE = 50 * 1024 * 1024       # 50 MB max body limit
KEEP_ALIVE_TIMEOUT = 5.0              # 5 seconds idle keep-alive timeout
KEEP_ALIVE_MAX_REQUESTS = 100         # Max requests per persistent connection
REQUEST_READ_TIMEOUT = 10.0           # 10s maximum time to complete a single request read
SERVER_NAME = "AsyncPythonHTTPServer/1.0"
CRLF = b"\r\n"
DOUBLE_CRLF = b"\r\n\r\n"
