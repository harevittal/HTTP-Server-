"""
High-concurrency HTTP Server Benchmark Utility.
Measures Requests/sec, Latency Distribution (P50, P95, P99), and Throughput.
"""

import sys
import time
import socket
import argparse
import statistics
from concurrent.futures import ThreadPoolExecutor


def make_raw_http_request(host: str, port: int, path: str) -> float:
    """Sends a raw HTTP/1.1 request over a TCP socket and returns latency in milliseconds."""
    start = time.perf_counter()
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(5.0)
    try:
        sock.connect((host, port))
        request = (
            f"GET {path} HTTP/1.1\r\n"
            f"Host: {host}:{port}\r\n"
            f"Connection: close\r\n\r\n"
        ).encode("latin-1")
        sock.sendall(request)

        # Read response
        response = bytearray()
        while True:
            chunk = sock.recv(4096)
            if not chunk:
                break
            response.extend(chunk)

        end = time.perf_counter()
        return (end - start) * 1000.0
    finally:
        sock.close()


def run_benchmark(host: str, port: int, path: str, total_requests: int, concurrency: int):
    print("=" * 60)
    print(f"🔥 Starting Benchmark on http://{host}:{port}{path}")
    print(f"   Total Requests : {total_requests}")
    print(f"   Concurrency    : {concurrency}")
    print("=" * 60)

    latencies = []
    errors = 0
    start_total = time.perf_counter()

    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = [
            executor.submit(make_raw_http_request, host, port, path)
            for _ in range(total_requests)
        ]
        for f in futures:
            try:
                lat = f.result()
                latencies.append(lat)
            except Exception as e:
                errors += 1

    total_time = time.perf_counter() - start_total
    rps = len(latencies) / total_time if total_time > 0 else 0

    latencies.sort()
    p50 = statistics.median(latencies) if latencies else 0
    p95 = latencies[int(len(latencies) * 0.95)] if latencies else 0
    p99 = latencies[int(len(latencies) * 0.99)] if latencies else 0
    avg = statistics.mean(latencies) if latencies else 0

    print("\n📊 Benchmark Results:")
    print(f"  • Total Time Elapsed : {total_time:.3f} s")
    print(f"  • Successful Requests: {len(latencies)}")
    print(f"  • Failed Requests    : {errors}")
    print(f"  • Throughput (RPS)   : {rps:,.2f} req/sec")
    print(f"  • Latency Average    : {avg:.2f} ms")
    print(f"  • Latency P50 (Med)  : {p50:.2f} ms")
    print(f"  • Latency P95        : {p95:.2f} ms")
    print(f"  • Latency P99        : {p99:.2f} ms")
    print("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Async HTTP Server Benchmark")
    parser.add_argument("--host", default="127.0.0.1", help="Target host")
    parser.add_argument("--port", type=int, default=8080, help="Target port")
    parser.add_argument("--path", default="/api/health", help="Target endpoint path")
    parser.add_argument("--requests", type=int, default=1000, help="Total number of requests")
    parser.add_argument("--concurrency", type=int, default=50, help="Concurrent workers")

    args = parser.parse_args()
    run_benchmark(args.host, args.port, args.path, args.requests, args.concurrency)
