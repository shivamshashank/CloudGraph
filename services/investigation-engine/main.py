"""Investigation Engine Service with AIOps agents analyzing cluster telemetry."""

# pylint: disable=missing-function-docstring,broad-exception-caught
# pylint: disable=duplicate-code

import json
import os
import http.server
import socketserver
from typing import List, Dict, Any

try:
    from neo4j import GraphDatabase

    NEO4J_AVAILABLE = True
except ImportError:
    NEO4J_AVAILABLE = False


class Neo4jClient:
    """Lightweight Neo4j client connection wrapper."""

    def __init__(self):
        host = os.getenv("NEO4J_HOST", "localhost")
        self.uri = os.getenv("NEO4J_URI", f"bolt://{host}:7687")
        auth = os.getenv("NEO4J_AUTH")
        if auth and "/" in auth:
            self.user, self.password = auth.split("/", 1)
        else:
            self.user = os.getenv("NEO4J_USER", "neo4j")
            self.password = os.getenv("NEO4J_PASSWORD", "cloudgraph_dev_password")
        self.driver = None

    def connect(self):
        if not NEO4J_AVAILABLE:
            raise RuntimeError("neo4j driver not installed")
        if not self.driver:
            self.driver = GraphDatabase.driver(
                self.uri, auth=(self.user, self.password)
            )
        return self.driver

    def close(self):
        if self.driver:
            self.driver.close()
            self.driver = None

    def execute_query(
        self, query: str, parameters: dict = None
    ) -> List[Dict[str, Any]]:
        self.connect()
        with self.driver.session() as session:
            result = session.run(query, parameters or {})
            return [record.data() for record in result]


# Global Neo4j client instance
neo4j_client = Neo4jClient()


# Specialist Agents Definition
def run_monitoring_agent(pod_name: str) -> Dict[str, Any]:
    """Monitoring Agent: Inspects metric trends and utilization anomalies."""
    finding = "Pod resource utilization metrics are within normal operational limits."
    confidence = 0.8
    metadata = {}

    try:
        if NEO4J_AVAILABLE:
            query = """
            MATCH (p:Pod {name: $pod_name})-[:GENERATES]->(m:Metric)
            RETURN m.name as name, m.value as value, m.timestamp as ts
            ORDER BY m.timestamp DESC LIMIT 10
            """
            records = neo4j_client.execute_query(query, {"pod_name": pod_name})
            if records:
                cpu_vals = [r["value"] for r in records if "cpu" in r["name"].lower()]
                mem_vals = [
                    r["value"]
                    for r in records
                    if "memory" in r["name"].lower() or "mem" in r["name"].lower()
                ]

                anomalies = []
                if cpu_vals:
                    avg_cpu = sum(cpu_vals) / len(cpu_vals)
                    if avg_cpu > 80.0:
                        anomalies.append(f"High CPU usage ({avg_cpu:.1f}%)")
                        confidence = 0.9
                    elif max(cpu_vals) > 95.0:
                        anomalies.append(f"CPU spike detected ({max(cpu_vals):.1f}%)")
                        confidence = 0.88

                if mem_vals:
                    avg_mem = sum(mem_vals) / len(mem_vals)
                    if avg_mem > 90.0:
                        anomalies.append(f"Memory saturation ({avg_mem:.1f}%)")
                        confidence = 0.92

                if anomalies:
                    finding = f"Metric anomalies observed: {', '.join(anomalies)}."
                metadata = {
                    "cpu_values": cpu_vals,
                    "memory_values": mem_vals,
                    "anomalies": anomalies,
                }
    except Exception as exc:
        finding = f"Monitoring metrics unreachable (offline fallback): {str(exc)}"
        confidence = 0.5

    return {
        "name": "monitoring",
        "finding": finding,
        "confidence": confidence,
        "metadata": metadata,
    }


def run_log_agent(pod_name: str, error_logs: List[str]) -> Dict[str, Any]:
    """Log Agent: Performs classification and error pattern recognition."""
    finding = "No critical error signatures detected in application logs."
    confidence = 0.6
    metadata = {}

    # Query from database if list is empty
    logs_to_scan = list(error_logs)
    if not logs_to_scan and NEO4J_AVAILABLE:
        try:
            query = """
            MATCH (p:Pod {name: $pod_name})-[:GENERATES]->(l:Log)
            WHERE l.level = 'ERROR'
            RETURN l.message as msg, l.timestamp as ts
            ORDER BY l.timestamp DESC LIMIT 5
            """
            records = neo4j_client.execute_query(query, {"pod_name": pod_name})
            logs_to_scan = [r["msg"] for r in records]
        except Exception:
            pass

    if logs_to_scan:
        error_text = " ".join(logs_to_scan).lower()
        finding = "Analyzed log streams. Standard runtime errors observed."
        confidence = 0.7
        category = "general"

        if (
            "oom" in error_text
            or "out of memory" in error_text
            or "oomkilled" in error_text
        ):
            finding = "Out-Of-Memory (OOM) signature detected in error logs."
            confidence = 0.96
            category = "oom"
        elif any(
            kw in error_text
            for kw in [
                "connection refused",
                "dial tcp",
                "timeout",
                "network unreachable",
            ]
        ):
            finding = (
                "Network connection failures or downstream timeout errors detected."
            )
            confidence = 0.92
            category = "network"
        elif any(
            kw in error_text
            for kw in [
                "password",
                "unauthorized",
                "access denied",
                "auth",
                "credential",
                "wrong-password",
            ]
        ):
            finding = "Authentication/Credential failure signature detected in logs."
            confidence = 0.94
            category = "auth"
        elif "crashloop" in error_text or "panic" in error_text:
            finding = "Application runtime crash loop or panic trace detected."
            confidence = 0.88
            category = "crash"

        metadata = {"category": category, "scanned_logs_count": len(logs_to_scan)}

    return {
        "name": "logs",
        "finding": finding,
        "confidence": confidence,
        "metadata": metadata,
    }


def run_deployment_agent(pod_name: str) -> Dict[str, Any]:
    """Deployment Agent: Correlates rollout states, replicasets, and git commits."""
    finding = "No recent rollout changes or code deployment regressions registered."
    confidence = 0.6
    metadata = {}

    try:
        if NEO4J_AVAILABLE:
            query = """
            MATCH (p:Pod {name: $pod_name})<-[:MANAGES]-(d:Deployment)
            OPTIONAL MATCH (d)-[:UPDATED_BY|TRIGGERED_BY]->(c:Commit)
            RETURN d.name as name, d.status as status, c.sha as sha,
                   c.message as commit_msg
            LIMIT 1
            """
            records = neo4j_client.execute_query(query, {"pod_name": pod_name})
            if records:
                row = records[0]
                finding = (
                    f"Correlated with deployment rollout '{row['name']}' "
                    f"(status: {row['status']})."
                )
                recent_change = True
                if row.get("sha"):
                    finding += (
                        f" Active git commit revision: {row['sha'][:8]} "
                        f"('{row['commit_msg']}')."
                    )
                    confidence = 0.85
                metadata = {
                    "deployment_name": row["name"],
                    "status": row["status"],
                    "commit_sha": row.get("sha"),
                    "recent_change": recent_change,
                }
    except Exception:
        pass

    return {
        "name": "deployments",
        "finding": finding,
        "confidence": confidence,
        "metadata": metadata,
    }


def run_topology_agent(pod_name: str) -> Dict[str, Any]:
    """Topology Agent: Analyzes cascade paths and scheduled host neighbors."""
    finding = "Pod dependency tree and networking paths are fully operational."
    confidence = 0.7
    metadata = {}

    try:
        if NEO4J_AVAILABLE:
            # Query Service dependencies
            query = """
            MATCH (p:Pod {name: $pod_name})-[:BELONGS_TO]->(s:Service)
            MATCH (s)-[:CALLS]->(other:Service)
            RETURN other.name as service
            """
            dep_records = neo4j_client.execute_query(query, {"pod_name": pod_name})
            dependencies = [d["service"] for d in dep_records]

            # Query scheduling neighbors
            node_query = """
            MATCH (p:Pod {name: $pod_name})-[:RUNS_ON]->(n:Node)
            MATCH (n)<-[:RUNS_ON]-(other:Pod)
            WHERE NOT other.status IN ['Running', 'Succeeded']
            RETURN n.name as node, collect(other.name) as bad_pods
            """
            node_records = neo4j_client.execute_query(
                node_query, {"pod_name": pod_name}
            )

            finding = "Active dependency hierarchy mapped."
            if dependencies:
                finding += f" Relies on external services: {', '.join(dependencies)}."

            noisy_neighbors = []
            if node_records:
                node_name = node_records[0]["node"]
                noisy_neighbors = node_records[0]["bad_pods"]
                if noisy_neighbors:
                    finding += (
                        f" Warning: Scheduled on host '{node_name}' "
                        f"alongside {len(noisy_neighbors)} failing pods."
                    )
                    confidence = 0.86

            metadata = {
                "dependencies": dependencies,
                "noisy_neighbors": noisy_neighbors,
            }
    except Exception:
        pass

    return {
        "name": "topology",
        "finding": finding,
        "confidence": confidence,
        "metadata": metadata,
    }


def run_security_agent(pod_name: str, error_logs: List[str]) -> Dict[str, Any]:
    """Security Agent: Reviews IAM access privileges and credentials."""
    finding = "No security breaches, secret reference warnings, or RBAC alerts."
    confidence = 0.8
    metadata = {}

    logs_text = " ".join(error_logs).lower()
    threat_detected = False

    if any(
        kw in logs_text
        for kw in [
            "password",
            "unauthorized",
            "access denied",
            "auth",
            "credential",
            "wrong-password",
        ]
    ):
        finding = (
            "Potential credential exposure or authorization "
            "failure captured in logs."
        )
        confidence = 0.94
        threat_detected = True
        metadata = {"category": "credentials"}
    else:
        try:
            if NEO4J_AVAILABLE:
                query = """
                MATCH (p:Pod {name: $pod_name})-[:GENERATES]->(l:Log)
                WHERE l.message CONTAINS 'password'
                   OR l.message CONTAINS 'unauthorized'
                   OR l.message CONTAINS 'access denied'
                   OR l.message CONTAINS 'auth'
                RETURN l.message as msg
                LIMIT 1
                """
                records = neo4j_client.execute_query(query, {"pod_name": pod_name})
                if records:
                    finding = (
                        f"Credential or unauthorized permission logs "
                        f"detected: '{records[0]['msg']}'."
                    )
                    confidence = 0.95
                    threat_detected = True
                    metadata = {
                        "category": "credentials",
                        "log_sample": records[0]["msg"],
                    }
        except Exception:
            pass

    metadata["threat_detected"] = threat_detected
    return {
        "name": "security",
        "finding": finding,
        "confidence": confidence,
        "metadata": metadata,
    }


class InvestigationHandler(http.server.BaseHTTPRequestHandler):
    """HTTP Handler for executing microservice agent analysis."""

    def _send_json(self, status_code: int, payload: dict):
        body_bytes = json.dumps(payload).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body_bytes)))
        self.end_headers()
        self.wfile.write(body_bytes)

    def do_get(self):
        """Handle health-check endpoints."""
        if self.path in {"/health", "/ready", "/"}:
            neo4j_status = "unconnected"
            if NEO4J_AVAILABLE:
                try:
                    neo4j_client.connect()
                    neo4j_status = "connected"
                except Exception:
                    neo4j_status = "offline"
            self._send_json(
                200,
                {
                    "status": "healthy",
                    "service": "investigation-engine",
                    "neo4j": neo4j_status,
                    "agents": [
                        "monitoring",
                        "logs",
                        "deployments",
                        "topology",
                        "security",
                    ],
                },
            )
            return
        self._send_json(404, {"status": "not_found"})

    def do_post(self):
        """Handle analysis execution request."""
        if self.path != "/analyze":
            self._send_json(404, {"status": "not_found"})
            return

        length = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")

        pod_name = payload.get("pod_name", "unknown")
        pod_status = payload.get("pod_status", "Unknown")
        error_logs = payload.get("error_logs", [])

        # Execute all 5 specialized agents
        monitoring_res = run_monitoring_agent(pod_name)
        logs_res = run_log_agent(pod_name, error_logs)
        deployments_res = run_deployment_agent(pod_name)
        topology_res = run_topology_agent(pod_name)
        security_res = run_security_agent(pod_name, error_logs)

        # Build response
        self._send_json(
            200,
            {
                "status": "success",
                "service": "investigation-engine",
                "pod_name": pod_name,
                "pod_status": pod_status,
                "agents": [
                    monitoring_res,
                    logs_res,
                    deployments_res,
                    topology_res,
                    security_res,
                ],
            },
        )


# Map HTTP handlers
InvestigationHandler.do_GET = InvestigationHandler.do_get
InvestigationHandler.do_POST = InvestigationHandler.do_post


def run_server(port: int):
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("", port), InvestigationHandler) as httpd:
        print(f"Serving real investigation engine on port {port}")
        httpd.serve_forever()


if __name__ == "__main__":
    target_port = os.environ.get("PORT", "8081")
    run_server(int(target_port))
