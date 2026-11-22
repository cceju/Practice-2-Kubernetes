"""
Wire protocol shared by client and server.

Every message is a JSON object encoded in UTF-8 and preceded by a 4-byte
big-endian header with the body length. TCP is a byte stream, not a message
stream, so this framing is what lets the receiver know where a message ends.

    +----------------+---------------------------+
    | length (4 B)   | JSON body (length bytes)  |
    +----------------+---------------------------+

Request:  {"function": "add", "args": [4, 7]}
Response: {"status": "ok", "result": 11}
          {"status": "error", "error": "<CODE>", "message": "<detail>"}
"""

from __future__ import annotations  # keeps `X | None` hints valid on Python 3.9 (EC2)

import json
import socket
import struct

ENCODING = "utf-8"
HEADER = struct.Struct("!I")       # unsigned 32-bit int, network byte order
MAX_MESSAGE_SIZE = 10 * 1024 * 1024  # 10 MB: protects against absurd length headers


class ProtocolError(Exception):
    """The peer sent something that does not follow the protocol."""


def send_msg(sock: socket.socket, message: dict) -> None:
    """Serializes `message` and sends it with its length header."""
    body = json.dumps(message).encode(ENCODING)
    if len(body) > MAX_MESSAGE_SIZE:
        raise ProtocolError(f"Message too large: {len(body)} bytes")
    sock.sendall(HEADER.pack(len(body)) + body)


def recv_msg(sock: socket.socket) -> dict | None:
    """
    Receives one complete message.

    Returns:
        The decoded message, or None if the peer closed the connection
        cleanly before sending anything.

    Raises:
        ProtocolError: truncated message, oversized length or invalid JSON.
        socket.timeout / OSError: network problems (left to the caller).
    """
    header = _recv_exact(sock, HEADER.size)
    if header is None:
        return None

    (length,) = HEADER.unpack(header)
    if length > MAX_MESSAGE_SIZE:
        raise ProtocolError(f"Declared length too large: {length} bytes")

    body = _recv_exact(sock, length)
    if body is None:
        raise ProtocolError("Connection closed in the middle of a message")

    try:
        message = json.loads(body.decode(ENCODING))
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        raise ProtocolError(f"Invalid JSON body: {e}") from e

    if not isinstance(message, dict):
        raise ProtocolError("Message must be a JSON object")
    return message


def _recv_exact(sock: socket.socket, n: int) -> bytes | None:
    """
    Reads exactly `n` bytes, looping over recv().

    Returns None only if the connection closes before the first byte.
    Raises ProtocolError if it closes after some bytes were read.
    """
    buffer = bytearray()
    while len(buffer) < n:
        chunk = sock.recv(n - len(buffer))
        if not chunk:
            if not buffer:
                return None
            raise ProtocolError(f"Expected {n} bytes, received {len(buffer)}")
        buffer.extend(chunk)
    return bytes(buffer)

# Aliases used by the provided tests
send_json = send_msg
recv_json = recv_msg
