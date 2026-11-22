"""
Usage example of the RPC client.

    python client_example.py <EC2_IP> [port]
"""

import sys
import time

from rpc_client import RPCClient, RPCError, RPCRemoteError, RPCTimeoutError

host = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1"
port = int(sys.argv[2]) if len(sys.argv) > 2 else 5000

rpc = RPCClient(host, port)

# Normal calls
print("add(4, 7)        =", rpc.call("add", 4, 7))
print("multiply(3, 5)   =", rpc.call("multiply", 3, 5))
print("power(2, 10)     =", rpc.power(2, 10))  # same as rpc.call("power", 2, 10)

start = time.perf_counter()
print("slow_task(2)     =", rpc.call("slow_task", 2), f"({time.perf_counter() - start:.2f}s)")

# Error handling
for description, function, args, kwargs in [
    ("unknown procedure", "does_not_exist", (), {}),
    ("wrong arguments",   "add", (1,), {}),
    ("error inside call", "add", (1, "a"), {}),
    ("client timeout",    "slow_task", (3,), {"timeout": 1}),
]:
    try:
        rpc.call(function, *args, **kwargs)
    except RPCRemoteError as e:
        print(f"[{description}] remote error {e.code}: {e.message}")
    except RPCTimeoutError as e:
        print(f"[{description}] timeout: {e}")
    except RPCError as e:
        print(f"[{description}] {type(e).__name__}: {e}")