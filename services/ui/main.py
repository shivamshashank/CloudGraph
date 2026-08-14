"""UI proxy and static file server."""

import os
import http.server
import socketserver
import urllib.request
import urllib.error

PORT = int(os.environ.get("PORT", 3000))
# The target API url (e.g. from environment or default local)
API_URL = os.environ.get("REACT_APP_API_URL", "http://localhost:8080").rstrip("/")

# Endpoints that fan out to the LLM and take minutes; everything else fails fast.
_LONG_RUNNING_TIMEOUT = int(os.environ.get("PROXY_LONG_TIMEOUT", "900"))
_LONG_RUNNING_PREFIXES = (
    "/api/v1/investigations/",
    "/api/v1/benchmark/run",
    "/api/v1/research/report",
)


def _is_long_running(path: str) -> bool:
    """True when the proxied path is an LLM-backed, long-running operation."""
    return path.startswith(_LONG_RUNNING_PREFIXES)


STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")


class ProxyAndStaticHandler(http.server.SimpleHTTPRequestHandler):
    """HTTP request handler for UI proxy and static content."""

    def __init__(self, *args, **kwargs):
        """Initialize SimpleHTTPRequestHandler to serve from STATIC_DIR."""
        super().__init__(*args, directory=STATIC_DIR, **kwargs)

    def do_get(self):
        """Handle GET requests."""
        if self.path.startswith("/api/") or self.path.startswith("/health"):
            self.proxy_request("GET")
        else:
            # Serve static files normally
            super().do_GET()

    def do_post(self):
        """Handle POST requests."""
        if self.path.startswith("/api/"):
            self.proxy_request("POST")
        else:
            self.send_error(404, "Not Found")

    def do_put(self):
        """Handle PUT requests."""
        if self.path.startswith("/api/"):
            self.proxy_request("PUT")
        else:
            self.send_error(404, "Not Found")

    def do_delete(self):
        """Handle DELETE requests."""
        if self.path.startswith("/api/"):
            self.proxy_request("DELETE")
        else:
            self.send_error(404, "Not Found")

    def proxy_request(self, method):
        """Proxy the HTTP request to the backend API."""
        # Reconstruct the target API url
        target_url = API_URL + self.path

        # Read content-length and body if POST/PUT
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length) if content_length > 0 else None

        # Reconstruct headers to send to target
        headers = {}
        for key, val in self.headers.items():
            if key.lower() not in ["host", "content-length"]:
                headers[key] = val

        # Create request
        req = urllib.request.Request(
            target_url, data=body, headers=headers, method=method
        )

        # 15s suits graph reads, but an investigation is minutes of LLM latency.
        # The short ceiling turned every diagnosis into a proxy 500.
        timeout = _LONG_RUNNING_TIMEOUT if _is_long_running(self.path) else 15

        try:
            with urllib.request.urlopen(req, timeout=timeout) as response:
                # Read response status, headers, and body
                self.send_response(response.status)
                for key, val in response.headers.items():
                    # Forward headers
                    self.send_header(key, val)
                self.end_headers()
                self.wfile.write(response.read())
        except urllib.error.HTTPError as e:
            # Handle HTTP errors from backend API
            self.send_response(e.code)
            for key, val in e.headers.items():
                self.send_header(key, val)
            self.end_headers()
            self.wfile.write(e.read())
        except (urllib.error.URLError, OSError) as e:
            # Handle other connection exceptions
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            err_msg = (
                f'{{"error": "Failed to connect to backend at {API_URL}: '
                f'{str(e)}"}}'
            )
            self.wfile.write(err_msg.encode("utf-8"))


# Map helpers onto the method names BaseHTTPRequestHandler expects.
ProxyAndStaticHandler.do_GET = ProxyAndStaticHandler.do_get
ProxyAndStaticHandler.do_POST = ProxyAndStaticHandler.do_post
ProxyAndStaticHandler.do_PUT = ProxyAndStaticHandler.do_put
ProxyAndStaticHandler.do_DELETE = ProxyAndStaticHandler.do_delete


if __name__ == "__main__":
    # Unique setup layout to prevent duplicate block matches with other mock servers
    os.makedirs(STATIC_DIR, exist_ok=True)
    # Threaded: single-threaded, one multi-minute investigation blocked health
    # polls and static assets and the UI looked hung.
    socketserver.ThreadingTCPServer.allow_reuse_address = True
    socketserver.ThreadingTCPServer.daemon_threads = True
    server_address = ("", PORT)

    with socketserver.ThreadingTCPServer(
        server_address, ProxyAndStaticHandler
    ) as dev_server:
        print(f"UI proxy serving static assets. Proxying API to {API_URL} on {PORT}...")
        dev_server.serve_forever()
