"""Basic tests provided.

Run from the project root:

    python -m unittest discover -s tests
"""

from __future__ import annotations

import os
import socket
import sys
import threading
import unittest

from common.protocol import send_json, recv_json

# server.py imports its siblings (rpc_server, procedures) as top-level modules
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "server"))

from client.rpc_client import RPCClient, RPCRemoteError  # noqa: E402
from rpc_server import ErrorCode, RPCServer  # noqa: E402
import server as server_main  # noqa: E402


def add(a, b):
    return a + b


class ProtocolTests(unittest.TestCase):
    def test_send_and_receive_json(self):
        left, right = socket.socketpair()

        try:
            expected = {
                "function": "add",
                "args": [4, 7],
            }

            send_json(left, expected)
            received = recv_json(right)

            self.assertEqual(received, expected)

        finally:
            left.close()
            right.close()


class StudentTests(unittest.TestCase):
    def setUp(self):
        self.rpc = RPCServer()
        self.rpc.register(add)

    def test_dispatch_add(self):
        response = self.rpc.dispatch({"function": "add", "args": [4, 7]})
        self.assertEqual(response, {"status": "ok", "result": 11})

        response = self.rpc.dispatch({"function": "does_not_exist", "args": []})
        self.assertEqual(response["error"], ErrorCode.PROCEDURE_NOT_FOUND)

    def test_rpc_add(self):
        # Real server on a free localhost port, serving the calls in a thread
        listener = socket.socket()
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        port = listener.getsockname()[1]

        def serve(n_calls):
            for _ in range(n_calls):
                connection, address = listener.accept()
                server_main.handle(self.rpc, connection, address)

        thread = threading.Thread(target=serve, args=(2,), daemon=True)
        thread.start()

        try:
            client = RPCClient("127.0.0.1", port, timeout=2)
            self.assertEqual(client.call("add", 4, 7), 11)

            with self.assertRaises(RPCRemoteError) as ctx:
                client.call("add", 1)
            self.assertEqual(ctx.exception.code, ErrorCode.INVALID_ARGUMENTS)

            thread.join(timeout=2)
        finally:
            listener.close()


if __name__ == "__main__":
    unittest.main()
