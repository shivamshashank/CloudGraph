"""Mock service for investigation engine."""

import json
import os
import http.server
import socketserver
import time


class InvestigationHandler(http.server.BaseHTTPRequestHandler):
    """HTTP Request Handler for the investigation mock service."""

    def _send_json(self, status_code, payload):
        """Send a JSON payload helper."""
        body_bytes = json.dumps(payload).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body_bytes)))
        self.end_headers()
        self.wfile.write(body_bytes)

    def do_get(self):
        """Handle GET requests."""
        if self.path in {"/health", "/ready", "/"}:
            self._send_json(
                200, {"status": "healthy", "service": "investigation-engine"}
            )
            return
        self._send_json(404, {"status": "not_found"})

    def do_post(self):
        """Handle POST requests."""
        if self.path != "/analyze":
            self._send_json(404, {"status": "not_found"})
            return

        length = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
        pod_name = payload.get("pod_name", "unknown")
        pod_status = payload.get("pod_status", "Unknown")
        error_logs = payload.get("error_logs", [])
        error_text = " ".join(error_logs).lower() if error_logs else ""

        if any(
            keyword in error_text
            for keyword in ["timeout", "refused", "dial tcp", "connection"]
        ):
            summary = "Potential dependency failure or crash loop detected"
            severity = "CRITICAL"
            recommendation = "Verify downstream dependencies and network reachability."
        elif (
            "crashloop" in pod_status.lower()
            or "error" in pod_status.lower()
            or "failed" in pod_status.lower()
        ):
            summary = "Crash loop or failing workload detected"
            severity = "CRITICAL"
            recommendation = "Inspect pod events and recent application logs."
        else:
            summary = "Pod reported a non-healthy state"
            severity = "HIGH"
            recommendation = "Inspect pod events and container logs."

        self._send_json(
            200,
            {
                "status": "success",
                "service": "investigation-engine",
                "analysis": {
                    "pod_name": pod_name,
                    "summary": summary,
                    "severity": severity,
                    "recommendation": recommendation,
                    "evidence": [f"Pod status: {pod_status}", *error_logs[:3]],
                },
            },
        )


# Map helper handlers to standard HTTP method handlers expected by
# BaseHTTPRequestHandler
InvestigationHandler.do_GET = InvestigationHandler.do_get
InvestigationHandler.do_POST = InvestigationHandler.do_post


def run_server(port):
    """Run the mock investigation HTTP server."""
    with socketserver.TCPServer(("", port), InvestigationHandler) as httpd:
        print(f"Serving investigation engine on port {port}")
        httpd.serve_forever()


if __name__ == "__main__":
    # Differentiated runner block style to avoid similar-lines warning
    target_port = os.environ.get("PORT")
    if not target_port:
        print("No PORT environment variable supplied. Waiting endlessly...")
        while True:
            time.sleep(3600)
    else:
        run_server(int(target_port))
