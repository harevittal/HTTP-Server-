"""
Client socket connection wrapper and state machine.
"""

import time
import socket
import errno
from enum import Enum, auto
from typing import Optional, Tuple, List
from .constants import DEFAULT_RECV_BUFFER_SIZE, KEEP_ALIVE_TIMEOUT, KEEP_ALIVE_MAX_REQUESTS
from .request import Request, parse_request, HTTPParsingError
from .response import Response


class ConnectionState(Enum):
    READING = auto()
    PROCESSING = auto()
    WRITING = auto()
    CLOSED = auto()


class HTTPConnection:
    """
    Manages socket I/O buffers, state transitions, and keep-alive lifecycle.
    """
    def __init__(self, sock: socket.socket, client_address: Tuple[str, int]):
        self.sock = sock
        self.client_address = client_address
        self.state = ConnectionState.READING
        
        self.read_buffer = bytearray()
        self.write_buffer = bytearray()
        
        self.created_at = time.time()
        self.last_activity = time.time()
        self.requests_served = 0
        self.keep_alive = True
        self.current_request: Optional[Request] = None
        self.should_close = False

    def update_activity(self):
        """Updates timestamp of last socket activity."""
        self.last_activity = time.time()

    def is_timed_out(self, now: Optional[float] = None) -> bool:
        """Checks if connection exceeded idle keep-alive timeout."""
        if now is None:
            now = time.time()
        return (now - self.last_activity) > KEEP_ALIVE_TIMEOUT

    def read_from_socket(self) -> bool:
        """
        Reads available bytes from non-blocking socket into read_buffer.
        Returns False if connection was closed by peer or on error, True otherwise.
        """
        self.update_activity()
        while True:
            try:
                chunk = self.sock.recv(DEFAULT_RECV_BUFFER_SIZE)
                if not chunk:
                    # Client disconnected / EOF
                    return False
                self.read_buffer.extend(chunk)
            except (BlockingIOError, InterruptedError):
                # Socket buffer drained for now
                break
            except socket.error as e:
                if e.errno in (errno.EAGAIN, errno.EWOULDBLOCK):
                    break
                return False
        return True

    def parse_next_request(self) -> Tuple[Optional[Request], Optional[Response]]:
        """
        Attempts to extract the next full HTTP request from the read buffer.
        Returns (Request, None) if parsed successfully,
        (None, None) if incomplete (need more data),
        (None, ErrorResponse) if a parsing error occurred.
        """
        if not self.read_buffer:
            return None, None

        try:
            req, bytes_consumed = parse_request(bytes(self.read_buffer), self.client_address)
            if req is not None:
                # Consume parsed bytes from buffer
                del self.read_buffer[:bytes_consumed]
                self.requests_served += 1
                self.keep_alive = req.is_keep_alive and (self.requests_served < KEEP_ALIVE_MAX_REQUESTS)
                self.current_request = req
                return req, None
            return None, None
        except HTTPParsingError as e:
            self.read_buffer.clear()
            self.keep_alive = False
            self.should_close = True
            err_resp = Response.error(e.status_code, str(e))
            return None, err_resp

    def queue_response(self, response: Response, is_head_request: bool = False):
        """Serializes and queues response into write_buffer."""
        data = response.to_bytes(include_body=not is_head_request, keep_alive=self.keep_alive)
        self.write_buffer.extend(data)
        self.state = ConnectionState.WRITING
        if not self.keep_alive:
            self.should_close = True

    def write_to_socket(self) -> bool:
        """
        Writes pending bytes from write_buffer to non-blocking socket.
        Returns True if write buffer is completely flushed, False if partial.
        """
        self.update_activity()
        while self.write_buffer:
            try:
                sent = self.sock.send(self.write_buffer)
                if sent == 0:
                    return False
                del self.write_buffer[:sent]
            except (BlockingIOError, InterruptedError):
                return False
            except socket.error as e:
                if e.errno in (errno.EAGAIN, errno.EWOULDBLOCK):
                    return False
                self.state = ConnectionState.CLOSED
                return False

        if not self.write_buffer:
            if self.should_close:
                self.state = ConnectionState.CLOSED
            else:
                self.state = ConnectionState.READING
            return True

        return False

    def close(self):
        """Closes socket and marks connection state as CLOSED."""
        self.state = ConnectionState.CLOSED
        try:
            self.sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        try:
            self.sock.close()
        except OSError:
            pass
