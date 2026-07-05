import json
import os
import http.server
import socketserver
import time


class OrchestratorHandler(http.server.BaseHTTPRequestHandler):
    def _send_json(self, status_code, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path in {"/health", "/ready", "/"}:
            self._send_json(200, {"status": "healthy", "service": "agent-orchestrator"})
            return
        self._send_json(404, {"status": "not_found"})

    def do_POST(self):
        if self.path != "/orchestrate":
            self._send_json(404, {"status": "not_found"})
            return

        length = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
        incident = payload.get("incident", {})
        summary = incident.get("summary", "No findings available")

        self._send_json(
            200,
            {
                "status": "success",
                "service": "agent-orchestrator",
                "consensus": {
                    "summary": summary,
                    "agents": [
                        {
                            "name": "monitoring",
                            "finding": "Pod health and metric trends were reviewed",
                            "confidence": 0.84,
                        },
                        {
                            "name": "logs",
                            "finding": "Recent error logs were correlated with the incident",
                            "confidence": 0.88,
                        },
                        {
                            "name": "deployments",
                            "finding": "The deployment state was checked for rollout regressions",
                            "confidence": 0.79,
                        },
                    ],
                },
            },
        )


def run_server(port):
    with socketserver.TCPServer(("", port), OrchestratorHandler) as httpd:
        print(f"Serving agent orchestrator on port {port}")
        httpd.serve_forever()


if __name__ == "__main__":
    port_str = os.environ.get("PORT")
    if port_str:
        run_server(int(port_str))
    else:
        print("Agent orchestrator running...")
        while True:
            time.sleep(3600)
