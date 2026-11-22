"""
RPC client: turns a local call into a request sent to the remote server.

    rpc = RPCClient("<EC2_IP>", 5000)
    rpc.call("add", 4, 7)   # -> 11

Design decisions:
- One TCP connection per call. Simple and stateless (a failed call never
  leaves a half-used socket behind); the cost is one TCP handshake per call.
- Errors are raised as Python exceptions, so the caller handles a remote
  failure exactly like a local one. Each failure type has its own class.
- No automatic retries: a call that timed out may have run on the server
  anyway, and repeating a non-idempotent procedure is not safe.
"""

from __future__ import annotations

import itertools
import os
import socket
import sys
from typing import Any

# Allow `from common.protocol import ...` when running from client/
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from common.protocol import ProtocolError, recv_msg, send_msg  # noqa: E402

DEFAULT_TIMEOUT = 5.0


class RPCError(Exception):
    """Base class for every error raised by the RPC client."""


class RPCConnectionError(RPCError):
    """The server could not be reached or the connection broke."""


class RPCTimeoutError(RPCError):
    """The server did not reply within the timeout."""


class RPCProtocolError(RPCError):
    """The server replied with something that does not follow the protocol."""


class RPCRemoteError(RPCError):
    """The server processed the request and reported an error."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


class RPCClient:
    """Client side of the RPC layer."""

    def __init__(self, host: str, port: int, timeout: float = DEFAULT_TIMEOUT) -> None:
        """
        Args:
            host: Server IP or hostname (the EC2 public IP).
            port: Server TCP port.
            timeout: Seconds to wait for connecting and for each reply.
        """
        self.host = host
        self.port = port
        self.timeout = timeout
        self._ids = itertools.count(1)

    def call(self, function: str, *args: Any, timeout: float | None = None) -> Any:
        """
        Executes `function(*args)` on the server and returns its result.

        Args:
            function: Name of the remote procedure.
            *args: Positional arguments (must be JSON-serializable).
            timeout: Overrides the client timeout for this call only,
                e.g. for slow_task.

        Raises:
            RPCRemoteError: The server reported an error (unknown procedure,
                wrong arguments, exception during execution...).
            RPCTimeoutError, RPCConnectionError, RPCProtocolError.
            TypeError: Some argument cannot be serialized to JSON.
        """
        request = {"id": next(self._ids), "function": function, "args": list(args)}
        response = self._exchange(request, self.timeout if timeout is None else timeout)
        return self._unwrap(request, response)

    def __getattr__(self, name: str):
        """
        Syntactic sugar: rpc.add(4, 7) is the same as rpc.call("add", 4, 7).
        Makes the remote call look like a local one (RPC transparency).
        """
        if name.startswith("_"):
            raise AttributeError(name)
        return lambda *args, **kw: self.call(name, *args, **kw)

    def _exchange(self, request: dict, timeout: float) -> dict:
        """Opens a connection, sends the request and waits for one reply."""
        try:
            with socket.create_connection((self.host, self.port), timeout=timeout) as sock:
                send_msg(sock, request)
                response = recv_msg(sock)
        except socket.timeout as e:
            raise RPCTimeoutError(
                f"No reply from {self.host}:{self.port} within {timeout}s"
            ) from e
        except ProtocolError as e:
            raise RPCProtocolError(str(e)) from e
        except OSError as e:
            raise RPCConnectionError(
                f"Could not reach {self.host}:{self.port}: {e}"
            ) from e

        if response is None:
            raise RPCConnectionError("The server closed the connection without replying")
        return response

    @staticmethod
    def _unwrap(request: dict, response: dict) -> Any:
        """Validates the response and returns the result or raises the error."""
        # The server may not echo the id; only check it if it is there.
        if "id" in response and response["id"] != request["id"]:
            raise RPCProtocolError(
                f"Response id {response['id']} does not match request id {request['id']}"
            )

        status = response.get("status")
        if status == "ok":
            if "result" not in response:
                raise RPCProtocolError("'ok' response without 'result'")
            return response["result"]
        if status == "error":
            raise RPCRemoteError(
                response.get("error", "UNKNOWN_ERROR"),
                response.get("message", "no detail"),
            )
        raise RPCProtocolError(f"Unknown status: {status!r}")