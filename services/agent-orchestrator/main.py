"""Agent Orchestrator Service."""

import json
import os
import http.server
import socketserver
from typing import List, Dict, Any
import requests

INVESTIGATION_ENGINE_URL = os.getenv(
    "INVESTIGATION_ENGINE_URL", "http://localhost:8081"
).rstrip("/")


def call_llm(
    prompt: str,
    system_prompt: str = (
        "You are a helpful AIOps assistant. Output strictly valid JSON."
    ),
    provider: str = "",
    api_key: str = "",
    model: str = "",
) -> dict:
    """Make direct HTTP request to configured LLM provider and return parsed JSON."""
    provider = (provider or os.getenv("LLM_PROVIDER", "openai")).lower().strip()
    api_key = (
        api_key
        or os.getenv("OPENAI_API_KEY")
        or os.getenv("GEMINI_API_KEY")
        or os.getenv("ANTHROPIC_API_KEY")
    )

    if not api_key:
        raise ValueError("No API Key available for LLM service")

    if not model:
        if provider == "openai":
            model = os.getenv("LLM_MODEL", "gpt-4o-mini")
        elif provider == "gemini":
            model = os.getenv("LLM_MODEL", "gemini-1.5-flash")
        elif provider == "claude":
            model = os.getenv("LLM_MODEL", "claude-3-5-sonnet-latest")

    if provider == "openai":
        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.1,
        }
        res = requests.post(url, headers=headers, json=payload, timeout=20)
        res.raise_for_status()
        content = res.json()["choices"][0]["message"]["content"]
        return json.loads(content)

    if provider == "gemini":
        url = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.1,
        }
        res = requests.post(url, headers=headers, json=payload, timeout=20)
        res.raise_for_status()
        content = res.json()["choices"][0]["message"]["content"]
        return json.loads(content)

    if provider == "claude":
        url = "https://api.anthropic.com/v1/messages"
        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        payload = {
            "model": model,
            "max_tokens": 4000,
            "system": system_prompt,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.1,
        }
        res = requests.post(url, headers=headers, json=payload, timeout=20)
        res.raise_for_status()
        content = res.json()["content"][0]["text"]
        if "{" in content:
            start = content.index("{")
            end = content.rindex("}") + 1
            content = content[start:end]
        return json.loads(content)

    raise ValueError(f"Unsupported LLM provider: {provider}")


class ConsensusEngine:
    """Consensus Engine for aggregating multi-agent findings."""

    WEIGHTS = {
        "monitoring": 0.20,
        "logs": 0.30,
        "deployments": 0.20,
        "topology": 0.15,
        "security": 0.15,
    }

    @classmethod
    def get_weights(cls) -> Dict[str, float]:
        """Get the weights configuration."""
        return cls.WEIGHTS

    @classmethod
    def resolve_incident(
        cls,
        agents: List[Dict[str, Any]],
        pod_name: str,
        pod_status: str,
        llm_config: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        """Aggregate agent findings, determine root cause, compute consensus.

        Uses LLM if available.
        """
        llm_config = llm_config or {}

        # Try LLM first
        try:
            provider = (
                (llm_config.get("provider") or os.getenv("LLM_PROVIDER", ""))
                .strip()
                .lower()
            )
            api_key = (
                llm_config.get("api_key")
                or os.getenv("OPENAI_API_KEY")
                or os.getenv("GEMINI_API_KEY")
                or os.getenv("ANTHROPIC_API_KEY")
                or ""
            ).strip()

            if provider and api_key:
                agent_findings = "\n".join(
                    [
                        f"- {a['name'].upper()} Agent "
                        f"(Conf: {a['confidence']}): {a['finding']}"
                        for a in agents
                    ]
                )

                prompt = (
                    f"You are the Lead Consensus Orchestrator in an AIOps pipeline.\n"
                    f"You received telemetry from 5 agents for pod '{pod_name}' "
                    f"(Status: '{pod_status}'):\n\n"
                    f"{agent_findings}\n\n"
                    f"Correlate these findings to determine the root cause.\n"
                    f"Your response MUST be a JSON object with fields:\n"
                    f"- 'title': A short title "
                    f"(e.g. 'OOM Killed on billing-service').\n"
                    f"- 'summary': A high-level description of impact.\n"
                    f"- 'cause': A detailed explanation of the root cause.\n"
                    f"- 'recommendation': Actionable SRE remediation steps.\n"
                    f"- 'severity': 'CRITICAL', 'HIGH', 'MEDIUM', 'LOW', or 'NONE'.\n"
                    f"- 'confidence': score between 0.0 and 1.0.\n"
                    f"- 'evidence': list of decision path messages.\n"
                )

                system_prompt = (
                    "You are an expert AIOps consensus engine. "
                    "You output strictly JSON."
                )

                llm_res = call_llm(
                    prompt=prompt,
                    system_prompt=system_prompt,
                    provider=provider,
                    api_key=api_key,
                    model=llm_config.get("model"),
                )

                required = [
                    "title",
                    "summary",
                    "cause",
                    "recommendation",
                    "severity",
                    "confidence",
                    "evidence",
                ]
                if all(k in llm_res for k in required):
                    pct = int(float(llm_res["confidence"]) * 100)
                    return {
                        "title": str(llm_res["title"]),
                        "summary": str(llm_res["summary"]),
                        "cause": str(llm_res["cause"]),
                        "recommendation": str(llm_res["recommendation"]),
                        "severity": str(llm_res["severity"]).upper(),
                        "relevant_evidence": [
                            {"label": a["name"].upper(), "detail": a["finding"]}
                            for a in agents
                        ],
                        "evidence": [f"Consensus Engine confidence: {pct}%"]
                        + list(llm_res["evidence"]),
                        "agents": agents,
                    }
        except (
            ValueError,
            KeyError,
            requests.RequestException,
            json.JSONDecodeError,
        ) as e:
            print(
                "ConsensusEngine LLM resolution failed, "
                f"falling back to rule-based logic: {str(e)}"
            )

        return cls._resolve_fallback(agents, pod_name, pod_status)

    @classmethod
    def _resolve_fallback(
        cls, agents: List[Dict[str, Any]], pod_name: str, pod_status: str
    ) -> Dict[str, Any]:
        """Rule-based fallback for consensus resolution when LLM is unavailable."""
        # Map agent name -> details
        agent_map = {agent["name"]: agent for agent in agents}

        # Calculate weighted consensus confidence score
        confidence = sum(
            agent_map.get(name, {"confidence": 0.5})["confidence"] * weight
            for name, weight in cls.WEIGHTS.items()
        )
        confidence = round(min(0.99, max(0.1, confidence)), 2)

        category = agent_map.get("security", {}).get("metadata", {}).get(
            "category", ""
        ) or agent_map.get("logs", {}).get("metadata", {}).get("category", "general")

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
            if agent.get("confidence", 0) >= 0.7:
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
            engine_res = requests.post(
                f"{INVESTIGATION_ENGINE_URL}/analyze",
                json={
                    "pod_name": pod_name,
                    "pod_status": pod_status,
                    "error_logs": error_logs,
                    "evidence_context": payload.get("evidence_context", []),
                    "retrieval_context": payload.get("retrieval_context", {}),
                    "llm_provider": payload.get("llm_provider"),
                    "llm_api_key": payload.get("llm_api_key"),
                    "llm_model": payload.get("llm_model"),
                },
                timeout=12,
            )

            if engine_res.status_code == 200:
                engine_data = engine_res.json()
                agents = engine_data.get("agents", [])
                consensus_res = ConsensusEngine.resolve_incident(
                    agents,
                    pod_name,
                    pod_status,
                    llm_config={
                        "provider": payload.get("llm_provider"),
                        "api_key": payload.get("llm_api_key"),
                        "model": payload.get("llm_model"),
                    },
                )
                self._send_json(
                    200,
                    {
                        "status": "success",
                        "service": "agent-orchestrator",
                        "consensus": consensus_res,
                    },
                )
        except (requests.RequestException, json.JSONDecodeError, ValueError) as exc:
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
            has_payload = "payload" in locals()
            consensus_res = ConsensusEngine.resolve_incident(
                fallback_agents,
                pod_name,
                pod_status,
                llm_config={
                    "provider": payload.get("llm_provider") if has_payload else None,
                    "api_key": payload.get("llm_api_key") if has_payload else None,
                    "model": payload.get("llm_model") if has_payload else None,
                },
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
    """Run the HTTP server on the specified port."""
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
