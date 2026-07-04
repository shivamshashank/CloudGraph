import os
import http.server
import socketserver
import urllib.request
import urllib.error

PORT = int(os.environ.get("PORT", 3000))
# The target API url (e.g. from environment or default local)
API_URL = os.environ.get("REACT_APP_API_URL", "http://localhost:8080").rstrip("/")

STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")


class ProxyAndStaticHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        # Initialize SimpleHTTPRequestHandler to serve from STATIC_DIR
        super().__init__(*args, directory=STATIC_DIR, **kwargs)

    def do_GET(self):
        if self.path.startswith("/api/") or self.path.startswith("/health"):
            self.proxy_request("GET")
        else:
            # Serve static files normally
            super().do_GET()

    def do_POST(self):
        if self.path.startswith("/api/"):
            self.proxy_request("POST")
        else:
            self.send_error(404, "Not Found")

    def do_PUT(self):
        if self.path.startswith("/api/"):
            self.proxy_request("PUT")
        else:
            self.send_error(404, "Not Found")

    def do_DELETE(self):
        if self.path.startswith("/api/"):
            self.proxy_request("DELETE")
        else:
            self.send_error(404, "Not Found")

    def proxy_request(self, method):
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

        try:
            with urllib.request.urlopen(req, timeout=15) as response:
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
        except Exception as e:
            # Handle other connection exceptions
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(
                f'{{"error": "Failed to connect to backend at {API_URL}: {str(e)}"}}'.encode(
                    "utf-8"
                )
            )


if __name__ == "__main__":
    # Ensure static directory exists
    os.makedirs(STATIC_DIR, exist_ok=True)

    # Start server
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("", PORT), ProxyAndStaticHandler) as httpd:
        print(
            f"Serving UI static files and proxying /api/ to {API_URL} on port {PORT}..."
        )
        httpd.serve_forever()
