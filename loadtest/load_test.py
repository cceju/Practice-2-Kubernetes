"""
Load test for the RPC service deployed on Kubernetes.

Fires N requests with C of them in flight at the same time, using the
unchanged Practice 1 client (client/rpc_client.py), and reports throughput,
latency percentiles and errors.

Examples (run from the project root, on your own computer):

    # Heavy load: 96 calls to slow_task(1), 24 at a time
    python loadtest/load_test.py <WORKER_PUBLIC_IP> 30007 \
        --requests 96 --concurrency 24 --procedure slow_task --seconds 1 \
        --label "3 replicas"

    # Light, fast calls: 500 calls to add(4, 7), 50 at a time
    python loadtest/load_test.py <WORKER_PUBLIC_IP> 30007 \
        --requests 500 --concurrency 50 --procedure add --label "3 replicas"

Every run is also appended to results/load_test_results.csv so the runs
with 1, 3 and 6 replicas can be compared afterwards.
"""

from __future__ import annotations

import argparse
import csv
import os
import statistics
import sys
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from client.rpc_client import RPCClient, RPCError  # noqa: E402

CSV_PATH = os.path.join(ROOT, "results", "load_test_results.csv")
CSV_FIELDS = [
    "timestamp", "label", "procedure", "requests", "concurrency",
    "ok", "errors", "duration_s", "throughput_rps",
    "latency_mean_s", "latency_p50_s", "latency_p95_s", "latency_max_s",
]


def one_call(client: RPCClient, procedure: str, args: tuple) -> tuple[bool, float, str]:
    """Runs one RPC call. Returns (success, latency in seconds, error type)."""
    start = time.perf_counter()
    try:
        client.call(procedure, *args)
        return True, time.perf_counter() - start, ""
    except RPCError as e:
        return False, time.perf_counter() - start, type(e).__name__


def percentile(sorted_values: list[float], p: float) -> float:
    """Nearest-rank percentile of an already sorted list."""
    if not sorted_values:
        return 0.0
    index = max(0, min(len(sorted_values) - 1, round(p / 100 * len(sorted_values)) - 1))
    return sorted_values[index]


def run(args: argparse.Namespace) -> dict:
    client = RPCClient(args.host, args.port, timeout=args.timeout)

    if args.procedure == "slow_task":
        call_args: tuple = (args.seconds,)
    elif args.procedure in ("add", "multiply", "power"):
        call_args = (4, 7)
    else:
        call_args = tuple(args.args)

    print(
        f"Target {args.host}:{args.port} | {args.procedure}{call_args} | "
        f"{args.requests} requests, {args.concurrency} concurrent | "
        f"timeout {args.timeout}s | label '{args.label}'"
    )

    latencies: list[float] = []
    errors: Counter[str] = Counter()

    start = time.perf_counter()
    with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        futures = [
            pool.submit(one_call, client, args.procedure, call_args)
            for _ in range(args.requests)
        ]
        for done, future in enumerate(as_completed(futures), start=1):
            ok, latency, error = future.result()
            if ok:
                latencies.append(latency)
            else:
                errors[error] += 1
            if done % max(1, args.requests // 10) == 0:
                print(f"  {done}/{args.requests} done")
    duration = time.perf_counter() - start

    latencies.sort()
    ok_count = len(latencies)
    return {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "label": args.label,
        "procedure": args.procedure,
        "requests": args.requests,
        "concurrency": args.concurrency,
        "ok": ok_count,
        "errors": sum(errors.values()),
        "error_types": dict(errors),
        "duration_s": round(duration, 3),
        "throughput_rps": round(ok_count / duration, 2) if duration else 0.0,
        "latency_mean_s": round(statistics.mean(latencies), 3) if latencies else 0.0,
        "latency_p50_s": round(percentile(latencies, 50), 3),
        "latency_p95_s": round(percentile(latencies, 95), 3),
        "latency_max_s": round(latencies[-1], 3) if latencies else 0.0,
    }


def save(result: dict) -> None:
    os.makedirs(os.path.dirname(CSV_PATH), exist_ok=True)
    new_file = not os.path.exists(CSV_PATH)
    with open(CSV_PATH, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS, extrasaction="ignore")
        if new_file:
            writer.writeheader()
        writer.writerow(result)


def main() -> None:
    parser = argparse.ArgumentParser(description="Load test for the RPC service")
    parser.add_argument("host", help="Public IP of any cluster node")
    parser.add_argument("port", type=int, nargs="?", default=30007, help="NodePort (default 30007)")
    parser.add_argument("--requests", "-n", type=int, default=96, help="Total calls")
    parser.add_argument("--concurrency", "-c", type=int, default=24, help="Calls in flight at once")
    parser.add_argument("--procedure", "-p", default="slow_task", help="Remote procedure to call")
    parser.add_argument("--seconds", type=float, default=1.0, help="Argument for slow_task")
    parser.add_argument("--args", nargs="*", default=[], help="Arguments for other procedures")
    parser.add_argument("--timeout", type=float, default=60.0, help="Client timeout per call (s)")
    parser.add_argument("--label", default="", help="Free text saved with the result, e.g. '3 replicas'")
    args = parser.parse_args()

    result = run(args)
    save(result)

    print("\n--- Result ---")
    print(f"OK / errors     : {result['ok']} / {result['errors']} {result['error_types'] or ''}")
    print(f"Total time      : {result['duration_s']} s")
    print(f"Throughput      : {result['throughput_rps']} req/s")
    print(
        f"Latency (s)     : mean {result['latency_mean_s']} | p50 {result['latency_p50_s']} | "
        f"p95 {result['latency_p95_s']} | max {result['latency_max_s']}"
    )
    print(f"Saved to        : {os.path.relpath(CSV_PATH, ROOT)}")


if __name__ == "__main__":
    main()
