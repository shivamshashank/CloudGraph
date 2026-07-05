import json
import os
import http.server
import socketserver
import time


class InvestigationHandler(http.server.BaseHTTPRequestHandler):
    def _send_json(self, status_code, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path in {"/health", "/ready", "/"}:
            self._send_json(
                200, {"status": "healthy", "service": "investigation-engine"}
            )
            return
        self._send_json(404, {"status": "not_found"})

    def do_POST(self):
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


def run_server(port):
    with socketserver.TCPServer(("", port), InvestigationHandler) as httpd:
        print(f"Serving investigation engine on port {port}")
        httpd.serve_forever()


if __name__ == "__main__":
    port_str = os.environ.get("PORT")
    if port_str:
        run_server(int(port_str))
    else:
        print("Investigation engine running...")
        while True:
            time.sleep(3600)
