# 🚀 Async HTTP/1.1 Web Server from Scratch

A high-performance, asynchronous HTTP/1.1 server built entirely from scratch in Python using **raw TCP sockets**, non-blocking I/O with **Python selectors** (`epoll`/`kqueue`), and thread pool offloading.

Built with **Zero External Dependencies** (uses standard library primitives only).

---

## 🌟 Highlights & Key Features

* **⚡ Non-Blocking I/O Multiplexing**: Built on top of `selectors.DefaultSelector` for concurrent multi-client handling without spawning a thread per connection.
* **🌐 RFC 7230 / 7231 HTTP/1.1 Parser**: Stream-safe parser for HTTP verbs (`GET`, `POST`, `PUT`, `DELETE`, `HEAD`), header parsing, chunked transfer decoding, and URL-encoded query/body parsing.
* **🔄 Connection Lifecycle Management**: Socket binding, non-blocking polling, keep-alive persistence (`Connection: keep-alive`), request pipelining, idle timeout sweeps, and graceful teardown (`SIGINT`/`SIGTERM`).
* **📁 Static File Engine**: Path traversal security sandboxing, automatic MIME type detection, byte range requests (`206 Partial Content`), and `ETag`/`If-Modified-Since` 304 caching.
* **🧵 Thread Pool Offload**: Seamlessly offloads heavy compute tasks and blocking disk operations to a configurable `ThreadPoolExecutor` worker pool.
* **🛣️ Flexible Routing & Middlewares**: Expressive decorators (`@app.get`, `@app.post`), parameterized routes (`/users/<user_id>`), and customizable middleware chain.

---

## 📐 Architecture Overview

```
                      ┌─────────────────────────┐
                      │    Listening Socket     │
                      └───────────┬─────────────┘
                                  │ (select / epoll)
                      ┌───────────▼─────────────┐
                      │    Single Event Loop    │
                      │ (selectors.Default)     │
                      └─────┬──────────────┬────┘
                            │              │
             ┌──────────────▼───┐     ┌────▼─────────────────┐
             │ Non-Blocking I/O │     │ ThreadPoolExecutor   │
             │ Socket Buffering │     │ (Disk I/O & Compute) │
             └──────────────┬───┘     └──────────────┬───────┘
                            │                        │
                            ▼                        ▼
                      ┌─────────────────────────┐
                      │   HTTP/1.1 Parser &     │
                      │   Router Dispatcher     │
                      └───────────┬─────────────┘
                                  │
                                  ▼
                      ┌─────────────────────────┐
                      │ Response Serialization  │
                      │ Keep-Alive Lifecycle    │
                      └─────────────────────────┘
```

---

## 📂 Project Structure

```text
http_server/
├── http_server/
│   ├── __init__.py           # Package exports
│   ├── constants.py          # HTTP status codes, headers, limits
│   ├── request.py            # Stream parser & Request object
│   ├── response.py           # Response builder & byte serializer
│   ├── connection.py         # Socket wrapper & keep-alive state machine
│   ├── router.py             # Route matching & parameter extraction
│   ├── static_handler.py     # Static files, byte ranges, MIME & caching
│   ├── thread_pool.py        # Worker thread pool for blocking tasks
│   └── server.py             # Event loop & connection lifecycle
├── public/                   # Static test assets
│   ├── index.html            # Web dashboard UI
│   ├── style.css             # UI styling
│   └── app.js                # Interactive API client
├── tests/
│   ├── test_parser.py        # Unit tests for HTTP parsing & chunking
│   ├── test_router.py        # Unit tests for routing & params
│   ├── test_integration.py   # Full client-server integration tests
│   └── test_concurrency.py   # High concurrency load tests
├── benchmark.py              # Performance benchmark utility
├── example_app.py            # Sample application with REST endpoints
└── README.md                 # Documentation
```

---

## 🚀 Quick Start

### 1. Run the Example Application
```bash
python example_app.py
```
Open your browser and navigate to `http://127.0.0.1:8080` to see the live dashboard!

### 2. Building an Application
```python
from http_server import HTTPServer, json_response, text_response

app = HTTPServer(host="127.0.0.1", port=8080)

@app.get("/api/greet/<name>")
def greet(request):
    name = request.path_params.get("name")
    return json_response({"message": f"Hello, {name}!"})

@app.post("/api/echo")
def echo(request):
    data = request.json()
    return json_response({"received": data})

if __name__ == "__main__":
    app.run()
```

---

## 🧪 Running Automated Tests

Run the full test suite using Python's built-in `unittest`:

```bash
python -m unittest discover -s tests -p "test_*.py" -v
```

---

## 📊 Performance Benchmarking

Run the built-in multi-threaded benchmarking utility:

```bash
python benchmark.py --host 127.0.0.1 --port 8080 --requests 2000 --concurrency 50
```

Sample Benchmark Output:
```text
============================================================
🔥 Starting Benchmark on http://127.0.0.1:8080/api/health
   Total Requests : 2000
   Concurrency    : 50
============================================================

📊 Benchmark Results:
  • Total Time Elapsed : 0.852 s
  • Successful Requests: 2000
  • Failed Requests    : 0
  • Throughput (RPS)   : 2,347.42 req/sec
  • Latency Average    : 20.91 ms
  • Latency P50 (Med)  : 19.34 ms
  • Latency P95        : 31.50 ms
  • Latency P99        : 44.12 ms
============================================================
```

---

## 🛡️ Security & Reliability Features
- **Path Traversal Protection**: Prevents malicious `../../etc/passwd` attacks by verifying canonical common paths.
- **Header & Body Limits**: Configured maximum header size (64KB) and payload size (50MB) to mitigate memory exhaustion and denial-of-service (DoS).
- **Graceful Shutdown**: Traps `SIGINT`/`SIGTERM` to safely drain active requests and close sockets.
- **Keep-Alive Sweeper**: Automatically terminates idle connections exceeding timeout thresholds.
