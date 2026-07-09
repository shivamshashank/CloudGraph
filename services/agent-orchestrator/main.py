"""Agent Orchestrator Service."""

# pylint: disable=too-many-locals,too-few-public-methods
# pylint: disable=broad-exception-caught,import-outside-toplevel
# pylint: disable=missing-function-docstring,duplicate-code

import json
import os
import http.server
import socketserver
from typing import List, Dict, Any

INVESTIGATION_ENGINE_URL = os.getenv(
    "INVESTIGATION_ENGINE_URL", "http://localhost:8081"
).rstrip("/")


class ConsensusEngine:
    """Consensus Engine: Aggregates findings from specialized agents

    and computes unified MTTR metrics.
    """

    WEIGHTS = {
        "monitoring": 0.20,
        "logs": 0.30,
        "deployments": 0.20,
        "topology": 0.15,
        "security": 0.15,
    }

    @classmethod
    def resolve_incident(
        cls, agents: List[Dict[str, Any]], pod_name: str, pod_status: str
    ) -> Dict[str, Any]:
        """Aggregate agent findings, determine root cause, compute

        consensus confidence and recommendations.
        """
        # Map agent name -> details
        agent_map = {agent["name"]: agent for agent in agents}

        # Calculate weighted consensus confidence score
        confidence = 0.0
        for name, weight in cls.WEIGHTS.items():
            agent = agent_map.get(name, {"confidence": 0.5})
            confidence += agent["confidence"] * weight
        confidence = round(min(0.99, max(0.1, confidence)), 2)

        # Retrieve agent details for categorization
        log_meta = agent_map.get("logs", {}).get("metadata", {})
        log_category = log_meta.get("category", "general")
        sec_meta = agent_map.get("security", {}).get("metadata", {})
        sec_category = sec_meta.get("category", "")

        category = sec_category if sec_category else log_category

        # Classify root cause based on agent findings
        if category == "oom":
            title = f"Out of memory on {pod_name}"
            summary = "The container was terminated by the OOM killer"
            cause = (
                "The application exceeded its memory limits. "
                "Observed OOM signature in logs."
            )
            recommendation = "Increase memory limits or profile memory usage."
            severity = "CRITICAL"
        elif category == "auth":
            title = f"Database authentication failure on {pod_name}"
            summary = "Invalid database or downstream API credentials detected"
            cause = "Observed incorrect login/authentication credentials error logs."
            recommendation = (
                "Check secret configuration credentials and database settings."
            )
            severity = "CRITICAL"
        elif category == "network":
            title = f"Connection timeout or downstream dependency failure on {pod_name}"
            summary = "Failed network connectivity to external database/service"
            cause = "TCP dial or timeout errors observed in application logs."
            recommendation = (
                "Verify downstream service availability and network security policies."
            )
            severity = "CRITICAL"
        elif category == "crash" or "crash" in pod_status.lower():
            title = f"CrashLoopBackOff on {pod_name}"
            summary = "Workload repeatedly crashing or failing container runtime"
            cause = (
                "Container runtime panic or unhandled application exception detected."
            )
            recommendation = "Inspect pod events and recent application stderr logs."
            severity = "CRITICAL"
        else:
            title = f"Unhealthy workload anomaly on {pod_name}"
            summary = "Pod reported a non-healthy operational lifecycle state"
            cause = (
                "Unusual pattern detected in telemetry; pod is in state: " + pod_status
            )
            recommendation = "Inspect pod logs and scheduled host metrics."
            severity = "HIGH"

        # Build evidence trace list from all agents
        evidence = []
        evidence.append(f"Consensus Engine confidence: {int(confidence * 100)}%")

        for agent in agents:
            if agent["confidence"] >= 0.7:
                evidence.append(
                    f"Agent '{agent['name']}' signal: {agent['finding']} "
                    f"(Confidence: {agent['confidence']})"
                )

        return {
            "title": title,
            "summary": summary,
            "cause": cause,
            "recommendation": recommendation,
            "severity": severity,
            "relevant_evidence": [
                {"label": agent["name"].upper(), "detail": agent["finding"]}
                for agent in agents
            ],
            "evidence": evidence,
            "agents": agents,
        }


class OrchestratorHandler(http.server.BaseHTTPRequestHandler):
    """HTTP Request Handler for Orchestration services."""

    def _send_json(self, status_code: int, payload: Dict[str, Any]):
        body_bytes = json.dumps(payload).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body_bytes)))
        self.end_headers()
        self.wfile.write(body_bytes)

    def do_get(self):
        """Handle health-check requests."""
        if self.path in {"/health", "/ready", "/"}:
            self._send_json(200, {"status": "ok", "service": "agent-orchestrator"})
        else:
            self._send_json(404, {"status": "not_found"})

    def do_post(self):
        """Orchestrate diagnostic findings from investigation engine."""
        if self.path != "/orchestrate":
            self._send_json(404, {"status": "not_found"})
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")

            pod_name = payload.get("pod_name", "unknown")
            pod_status = payload.get("pod_status", "Unknown")
            error_logs = payload.get("error_logs", [])

            # Forward to investigation-engine
            import requests

            engine_res = requests.post(
                f"{INVESTIGATION_ENGINE_URL}/analyze",
                json={
                    "pod_name": pod_name,
                    "pod_status": pod_status,
                    "error_logs": error_logs,
                },
                timeout=5,
            )

            if engine_res.status_code == 200:
                engine_data = engine_res.json()
                agents = engine_data.get("agents", [])
                consensus_res = ConsensusEngine.resolve_incident(
                    agents, pod_name, pod_status
                )
                self._send_json(
                    200,
                    {
                        "status": "success",
                        "service": "agent-orchestrator",
                        "consensus": consensus_res,
                    },
                )
        except Exception as exc:
            # Fallback to local rule-based simulation inside orchestrator
            # if engine is down
            fallback_agents = [
                {
                    "name": "monitoring",
                    "finding": "Monitoring metrics unavailable.",
                    "confidence": 0.5,
                },
                {
                    "name": "logs",
                    "finding": (
                        f"Logs scanned directly. Category simulated "
                        f"from status '{pod_status}'."
                    ),
                    "confidence": 0.7,
                    "metadata": {
                        "category": (
                            "crash" if "crash" in pod_status.lower() else "general"
                        )
                    },
                },
                {
                    "name": "deployments",
                    "finding": "Git deployments commits log unreachable.",
                    "confidence": 0.5,
                },
                {
                    "name": "topology",
                    "finding": "Downstream routing nodes unassessed.",
                    "confidence": 0.5,
                },
                {
                    "name": "security",
                    "finding": "RBAC cluster authorization unassessed.",
                    "confidence": 0.5,
                },
            ]
            consensus_res = ConsensusEngine.resolve_incident(
                fallback_agents, pod_name, pod_status
            )
            self._send_json(
                200,
                {
                    "status": "success",
                    "service": "agent-orchestrator",
                    "note": f"Unreachable investigation-engine: {str(exc)}",
                    "consensus": consensus_res,
                },
            )


# Map HTTP handlers
OrchestratorHandler.do_GET = OrchestratorHandler.do_get
OrchestratorHandler.do_POST = OrchestratorHandler.do_post


def run_server(port: int):
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("", port), OrchestratorHandler) as httpd:
        print(
            f"Serving real agent orchestrator on port {port} "
            f"pointing to {INVESTIGATION_ENGINE_URL}"
        )
        httpd.serve_forever()


if __name__ == "__main__":
    target_port = os.environ.get("PORT", "8082")
    run_server(int(target_port))
