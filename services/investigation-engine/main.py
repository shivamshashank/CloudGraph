"""Investigation Engine Service with AIOps agents analyzing cluster telemetry."""

import json
import os
import http.server
import socketserver
from typing import List, Dict, Any
import requests

try:
    from neo4j import GraphDatabase
    from neo4j.exceptions import Neo4jError, ServiceUnavailable

    NEO4J_AVAILABLE = True
except ImportError:
    NEO4J_AVAILABLE = False

    class Neo4jError(Exception):
        """Stub for neo4j.exceptions.Neo4jError when driver is unavailable."""

    class ServiceUnavailable(Exception):
        """Stub for neo4j.exceptions.ServiceUnavailable when driver is unavailable."""


def _log_llm_request(provider: str, url: str, payload: dict) -> None:
    """Log the outgoing LLM call — safe to dump the payload verbatim since
    the API key lives in the headers, not here."""
    print(
        f"[LLM REQUEST] provider={provider} url={url}\n{json.dumps(payload, indent=2)}"
    )


def _log_llm_response(provider: str, status_code: int, raw_text: str) -> None:
    """Log the raw response body before any parsing — logged even on a
    non-2xx status, since seeing the actual error body is exactly what's
    needed to debug a bad request."""
    print(f"[LLM RESPONSE] provider={provider} status={status_code}\n{raw_text}")


def call_llm(
    prompt: str,
    system_prompt: str = (
        "You are a helpful AIOps assistant. Output strictly valid JSON."
    ),
    provider: str = "",
    api_key: str = "",
    model: str = "",
) -> dict:
    """Make a direct HTTP request to the configured cloud LLM provider and
    return parsed JSON. OpenAI and Gemini both expose an OpenAI-compatible
    /chat/completions surface, so they share one request shape. Meta uses a
    different, Responses-API-style surface (/v1/responses) with its own
    request/response shape — handled separately below.
    """
    provider = (provider or os.getenv("LLM_PROVIDER", "openai")).lower().strip()
    api_key = (
        api_key
        or os.getenv("OPENAI_API_KEY")
        or os.getenv("GEMINI_API_KEY")
        or os.getenv("META_API_KEY")
    )
    if not api_key:
        raise ValueError(
            f"No API key configured for provider {provider!r} — connect one "
            "via the Settings page."
        )
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    timeout = 60

    chat_completions_config = {
        "openai": (
            "https://api.openai.com/v1/chat/completions",
            "gpt-4o-mini",
        ),
        "gemini": (
            "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
            "gemini-1.5-flash",
        ),
    }
    if provider in chat_completions_config:
        url, default_model = chat_completions_config[provider]
        model = model or os.getenv("LLM_MODEL", default_model)
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.1,
        }
        _log_llm_request(provider, url, payload)
        res = requests.post(url, headers=headers, json=payload, timeout=timeout)
        _log_llm_response(provider, res.status_code, res.text)
        res.raise_for_status()
        content = res.json()["choices"][0]["message"]["content"]
        return json.loads(content)

    if provider == "meta":
        # Shape taken from one real api.meta.ai/v1/responses example plus the
        # OpenAI Responses API it mirrors, not from Meta's docs.
        url = "https://api.meta.ai/v1/responses"
        model = model or os.getenv("LLM_MODEL", "muse-spark-1.2")
        payload = {
            "model": model,
            "instructions": system_prompt,
            "input": [
                {
                    "role": "user",
                    "content": [{"type": "input_text", "text": prompt}],
                }
            ],
            "temperature": 0.1,
            "stream": False,
        }
        _log_llm_request("meta", url, payload)
        res = requests.post(url, headers=headers, json=payload, timeout=timeout)
        _log_llm_response("meta", res.status_code, res.text)
        res.raise_for_status()
        data = res.json()
        message_item = next(
            (item for item in data.get("output", []) if item.get("type") == "message"),
            None,
        )
        if not message_item or not message_item.get("content"):
            raise ValueError(f"Unexpected response shape from Meta API: {data!r}")
        content = message_item["content"][0]["text"]
        return json.loads(content)

    raise ValueError(
        f"Unsupported LLM provider: {provider!r} — must be one of "
        f"{sorted(list(chat_completions_config) + ['meta'])}."
    )


_QUALITATIVE_CONFIDENCE = {
    "very high": 0.95,
    "high": 0.85,
    "medium": 0.6,
    "moderate": 0.6,
    "low": 0.35,
    "very low": 0.15,
}


def _coerce_confidence(value: Any, default: float = 0.5) -> float:
    """Coerce an LLM-provided confidence value to a 0.0-1.0 float.

    Prompts ask for a numeric 0.0-1.0 score, but real LLMs sometimes
    ignore that and return a qualitative label (e.g. "High") instead —
    never crash on this (a bare `float(x)` did, in production, the first
    time this ran against a real model), coerce or fall back to a safe
    default.
    """
    if isinstance(value, (int, float)):
        return max(0.0, min(1.0, float(value)))
    if isinstance(value, str):
        text = value.strip().lower()
        try:
            return max(0.0, min(1.0, float(text)))
        except ValueError:
            pass
        if text in _QUALITATIVE_CONFIDENCE:
            return _QUALITATIVE_CONFIDENCE[text]
    return default


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
            self.password = os.getenv("NEO4J_PASSWORD", "")
        self.driver = None

    def connect(self):
        """Establish connection to Neo4j database."""
        if not NEO4J_AVAILABLE:
            raise RuntimeError("neo4j driver not installed")
        if not self.driver:
            self.driver = GraphDatabase.driver(
                self.uri, auth=(self.user, self.password)
            )
        return self.driver

    def close(self):
        """Close the Neo4j database connection driver."""
        if self.driver:
            self.driver.close()
            self.driver = None

    def execute_query(
        self, query: str, parameters: dict = None
    ) -> List[Dict[str, Any]]:
        """Execute a Cypher query on the Neo4j database."""
        self.connect()
        with self.driver.session() as session:
            result = session.run(query, parameters or {})
            return [record.data() for record in result]


# Global Neo4j client instance
neo4j_client = Neo4jClient()


# Specialist Agents Definition
def _call_llm_agent(
    prompt: str,
    system_prompt: str,
    llm_provider: str | None,
    llm_api_key: str | None,
    llm_model: str | None,
) -> dict | None:
    """Helper to execute LLM calls for agents, catching exceptions."""
    try:
        provider = (llm_provider or os.getenv("LLM_PROVIDER", "openai")).strip().lower()
        api_key = (llm_api_key or "").strip()

        # api_key may be empty: call_llm() falls back to the env-var key and
        # raises its own error if none exists.
        if provider:
            return call_llm(
                prompt=prompt,
                system_prompt=system_prompt,
                provider=provider,
                api_key=api_key,
                model=llm_model,
            )
    except (
        ValueError,
        KeyError,
        requests.RequestException,
        json.JSONDecodeError,
    ) as exc:
        print(f"LLM Agent call failed: {str(exc)}")
    return None


def _analyze_metrics_rules(metadata: dict) -> tuple[str, float]:
    """Helper to run rule-based metrics analysis."""
    cpu_vals = metadata.get("cpu_values", [])
    mem_vals = metadata.get("memory_values", [])
    anomalies = []
    confidence = 0.8
    finding = "Pod resource utilization metrics are within normal operational limits."

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
    metadata["anomalies"] = anomalies
    return finding, confidence


def _analyze_logs_rules(error_text: str, logs_count: int) -> tuple[str, float, dict]:
    """Helper to run rule-based log classification."""
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
        finding = "Network connection failures or downstream timeout errors detected."
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

    return (
        finding,
        confidence,
        {
            "category": category,
            "scanned_logs_count": logs_count,
        },
    )


def _analyze_deployments_rules(
    deployment_info: dict, _metadata: dict
) -> tuple[str, float]:
    """Helper to run rule-based deployment analysis."""
    finding = (
        f"Correlated with deployment rollout '{deployment_info['name']}' "
        f"(status: {deployment_info['status']})."
    )
    confidence = 0.6
    if deployment_info.get("sha"):
        finding += (
            f" Active git commit revision: {deployment_info['sha'][:8]} "
            f"('{deployment_info['commit_msg']}')."
        )
        confidence = 0.85
    return finding, confidence


def _analyze_topology_rules(topology_info: dict, _metadata: dict) -> tuple[str, float]:
    """Helper to run rule-based topology neighbor analysis."""
    dependencies = topology_info.get("dependencies", [])
    noisy_neighbors = topology_info.get("noisy_neighbors", [])
    node_name = topology_info.get("node_name", "")

    finding = "Active dependency hierarchy mapped."
    confidence = 0.7
    if dependencies:
        finding += f" Relies on external services: {', '.join(dependencies)}."

    if noisy_neighbors:
        finding += (
            f" Warning: Scheduled on host '{node_name}' "
            f"alongside {len(noisy_neighbors)} failing pods."
        )
        confidence = 0.86
    return finding, confidence


def _analyze_security_rules(metadata: dict, threat_detected: bool) -> tuple[str, float]:
    """Helper to run rule-based security classification."""
    confidence = 0.8
    if threat_detected:
        if "log_sample" in metadata:
            finding = (
                f"Credential or unauthorized permission logs "
                f"detected: '{metadata['log_sample']}'."
            )
            confidence = 0.95
        else:
            finding = (
                "Potential credential exposure or authorization "
                "failure captured in logs."
            )
            confidence = 0.94
    else:
        finding = "No security breaches, secret reference warnings, or RBAC alerts."
    return finding, confidence


def run_monitoring_agent(
    pod_name: str,
    llm_config: dict[str, Any] | None = None,
    evidence_context: list[dict[str, Any]] | None = None,
    retrieval_context: dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """Monitoring Agent: Inspects metric trends and utilization anomalies."""
    finding = "Pod resource utilization metrics are within normal operational limits."
    confidence = 0.8
    metadata = {}
    metrics_log = []

    try:
        if NEO4J_AVAILABLE:
            records = neo4j_client.execute_query(
                """
                MATCH (p:Pod {name: $pod_name})-[:GENERATES]->(m:Metric)
                RETURN m.name as name, m.value as value, m.timestamp as ts
                ORDER BY m.timestamp DESC LIMIT 10
                """,
                {"pod_name": pod_name},
            )
            if records:
                metrics_log = records
                metadata = {
                    "cpu_values": [
                        r["value"] for r in records if "cpu" in r["name"].lower()
                    ],
                    "memory_values": [
                        r["value"]
                        for r in records
                        if "memory" in r["name"].lower() or "mem" in r["name"].lower()
                    ],
                }
    except (RuntimeError, Neo4jError, ServiceUnavailable) as exc:
        finding = f"Monitoring metrics unreachable (offline fallback): {str(exc)}"
        confidence = 0.5

    # Attempt LLM reasoning if database returned metrics
    if metrics_log:
        prompt = (
            f"You are a Specialist Monitoring Agent.\n"
            f"Analyze metrics for Pod '{pod_name}' to check "
            f"for anomalies.\n\n"
            f"Metrics:\n{json.dumps(metrics_log, indent=2)}\n\n"
        )
        if retrieval_context and retrieval_context.get("status") == "success":
            prompt += (
                "Retrieved graph evidence summary:\n"
                f"{json.dumps(retrieval_context, indent=2)}\n\n"
            )
        elif evidence_context:
            prompt += (
                f"Related evidence items:\n{json.dumps(evidence_context, indent=2)}\n\n"
            )
        prompt += "Output JSON with: 'finding', 'confidence', 'anomalies'."
        system_prompt = "You are a monitoring specialist AI. You output strictly JSON."

        config = llm_config or {}
        llm_res = _call_llm_agent(
            prompt,
            system_prompt,
            config.get("provider"),
            config.get("api_key"),
            config.get("model"),
        )

        if llm_res and "finding" in llm_res and "confidence" in llm_res:
            return {
                "name": "monitoring",
                "finding": str(llm_res["finding"]),
                "confidence": round(_coerce_confidence(llm_res.get("confidence")), 2),
                "metadata": {
                    **metadata,
                    "anomalies": llm_res.get("anomalies", []),
                },
            }

    if metrics_log:
        finding, confidence = _analyze_metrics_rules(metadata)

    return {
        "name": "monitoring",
        "finding": finding,
        "confidence": confidence,
        "metadata": metadata,
    }


def run_log_agent(
    pod_name: str,
    error_logs: List[str],
    llm_config: dict[str, Any] | None = None,
    evidence_context: list[dict[str, Any]] | None = None,
    retrieval_context: dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """Log Agent: Performs classification and error pattern recognition."""
    finding = "No critical error signatures detected in application logs."
    confidence = 0.6
    metadata = {}

    # Query from database if list is empty
    logs_to_scan = list(error_logs)
    if not logs_to_scan and NEO4J_AVAILABLE:
        try:
            records = neo4j_client.execute_query(
                """
                MATCH (p:Pod {name: $pod_name})-[:GENERATES]->(l:Log)
                WHERE l.level = 'ERROR'
                RETURN l.message as msg, l.timestamp as ts
                ORDER BY l.timestamp DESC LIMIT 5
                """,
                {"pod_name": pod_name},
            )
            logs_to_scan = [r["msg"] for r in records]
        except (RuntimeError, ValueError, KeyError, TypeError, AttributeError):
            pass

    if logs_to_scan:
        prompt = (
            f"You are a Specialist Log Agent.\n"
            f"Analyze logs for Pod '{pod_name}' to check "
            f"for failure patterns.\n\n"
            f"Logs:\n{chr(10).join(logs_to_scan)}\n\n"
        )
        if retrieval_context and retrieval_context.get("status") == "success":
            prompt += (
                "Retrieved graph evidence summary:\n"
                f"{json.dumps(retrieval_context, indent=2)}\n\n"
            )
        elif evidence_context:
            prompt += (
                f"Related evidence items:\n{json.dumps(evidence_context, indent=2)}\n\n"
            )
        prompt += "Output JSON with: 'finding', 'confidence', 'category'."
        system_prompt = (
            "You are a log analysis specialist AI. You output strictly JSON."
        )

        config = llm_config or {}
        llm_res = _call_llm_agent(
            prompt,
            system_prompt,
            config.get("provider"),
            config.get("api_key"),
            config.get("model"),
        )

        if llm_res and "finding" in llm_res and "confidence" in llm_res:
            return {
                "name": "logs",
                "finding": str(llm_res["finding"]),
                "confidence": round(_coerce_confidence(llm_res.get("confidence")), 2),
                "metadata": {
                    "category": llm_res.get("category", "general"),
                    "scanned_logs_count": len(logs_to_scan),
                },
            }

        error_text = " ".join(logs_to_scan).lower()
        finding, confidence, metadata = _analyze_logs_rules(
            error_text, len(logs_to_scan)
        )

    return {
        "name": "logs",
        "finding": finding,
        "confidence": confidence,
        "metadata": metadata,
    }


def run_deployment_agent(
    pod_name: str,
    llm_config: dict[str, Any] | None = None,
    evidence_context: list[dict[str, Any]] | None = None,
    retrieval_context: dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """Deployment Agent: Correlates rollout states, replicasets, and git commits."""
    finding = "No recent rollout changes or code deployment regressions registered."
    confidence = 0.6
    metadata = {}
    deployment_info = {}

    try:
        if NEO4J_AVAILABLE:
            records = neo4j_client.execute_query(
                """
                MATCH (p:Pod {name: $pod_name})<-[:MANAGES]-(d:Deployment)
                OPTIONAL MATCH (d)-[:UPDATED_BY|TRIGGERED_BY]->(c:Commit)
                RETURN d.name as name, d.status as status, c.sha as sha,
                       c.message as commit_msg
                LIMIT 1
                """,
                {"pod_name": pod_name},
            )
            if records:
                deployment_info = records[0]
                metadata = {
                    "deployment_name": deployment_info["name"],
                    "status": deployment_info["status"],
                    "commit_sha": deployment_info.get("sha"),
                    "recent_change": True,
                }
    except (RuntimeError, ValueError, KeyError, TypeError, AttributeError):
        pass

    if deployment_info:
        prompt = (
            f"You are a Specialist Deployment Agent.\n"
            f"Analyze deployment and Git status for Pod '{pod_name}' "
            f"to check for regressions.\n\n"
            f"Deployment info:\n{json.dumps(deployment_info, indent=2)}\n\n"
        )
        if retrieval_context and retrieval_context.get("status") == "success":
            prompt += (
                "Retrieved graph evidence summary:\n"
                f"{json.dumps(retrieval_context, indent=2)}\n\n"
            )
        elif evidence_context:
            prompt += (
                f"Related evidence items:\n{json.dumps(evidence_context, indent=2)}\n\n"
            )
        prompt += "Output JSON with: 'finding', 'confidence'."
        system_prompt = (
            "You are a deployment rollout analysis specialist AI. "
            "You output strictly JSON."
        )

        config = llm_config or {}
        llm_res = _call_llm_agent(
            prompt,
            system_prompt,
            config.get("provider"),
            config.get("api_key"),
            config.get("model"),
        )

        if llm_res and "finding" in llm_res and "confidence" in llm_res:
            return {
                "name": "deployments",
                "finding": str(llm_res["finding"]),
                "confidence": round(_coerce_confidence(llm_res.get("confidence")), 2),
                "metadata": metadata,
            }

        finding, confidence = _analyze_deployments_rules(deployment_info, metadata)

    return {
        "name": "deployments",
        "finding": finding,
        "confidence": confidence,
        "metadata": metadata,
    }


def run_topology_agent(
    pod_name: str,
    llm_config: dict[str, Any] | None = None,
    evidence_context: list[dict[str, Any]] | None = None,
    retrieval_context: dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """Topology Agent: Analyzes cascade paths and scheduled host neighbors."""
    finding = "Pod dependency tree and networking paths are fully operational."
    confidence = 0.7
    metadata = {}
    topology_info = {}

    try:
        if NEO4J_AVAILABLE:
            dep_records = neo4j_client.execute_query(
                """
                MATCH (p:Pod {name: $pod_name})-[:BELONGS_TO]->(s:Service)
                MATCH (s)-[:CALLS]->(other:Service)
                RETURN other.name as service
                """,
                {"pod_name": pod_name},
            )
            node_records = neo4j_client.execute_query(
                """
                MATCH (p:Pod {name: $pod_name})-[:RUNS_ON]->(n:Node)
                MATCH (n)<-[:RUNS_ON]-(other:Pod)
                WHERE NOT other.status IN ['Running', 'Succeeded']
                RETURN n.name as node, collect(other.name) as bad_pods
                """,
                {"pod_name": pod_name},
            )

            topology_info = {
                "dependencies": [d["service"] for d in dep_records],
                "node_name": node_records[0]["node"] if node_records else "",
                "noisy_neighbors": (
                    node_records[0]["bad_pods"] if node_records else []
                ),
            }
            metadata = {
                "dependencies": topology_info["dependencies"],
                "noisy_neighbors": topology_info["noisy_neighbors"],
            }
    except (RuntimeError, ValueError, KeyError, TypeError, AttributeError):
        pass

    if topology_info:
        prompt = (
            f"You are a Specialist Topology Agent.\n"
            f"Analyze topology for Pod '{pod_name}' to check "
            f"for noisy neighbors.\n\n"
            f"Topology:\n{json.dumps(topology_info, indent=2)}\n\n"
        )
        if retrieval_context and retrieval_context.get("status") == "success":
            prompt += (
                "Retrieved graph evidence summary:\n"
                f"{json.dumps(retrieval_context, indent=2)}\n\n"
            )
        elif evidence_context:
            prompt += (
                f"Related evidence items:\n{json.dumps(evidence_context, indent=2)}\n\n"
            )
        prompt += "Output JSON with: 'finding', 'confidence'."
        system_prompt = "You are a topology specialist AI. You output strictly JSON."

        config = llm_config or {}
        llm_res = _call_llm_agent(
            prompt,
            system_prompt,
            config.get("provider"),
            config.get("api_key"),
            config.get("model"),
        )

        if llm_res and "finding" in llm_res and "confidence" in llm_res:
            return {
                "name": "topology",
                "finding": str(llm_res["finding"]),
                "confidence": round(_coerce_confidence(llm_res.get("confidence")), 2),
                "metadata": metadata,
            }

        finding, confidence = _analyze_topology_rules(topology_info, metadata)

    return {
        "name": "topology",
        "finding": finding,
        "confidence": confidence,
        "metadata": metadata,
    }


def run_security_agent(
    pod_name: str,
    error_logs: List[str],
    llm_config: dict[str, Any] | None = None,
    evidence_context: list[dict[str, Any]] | None = None,
    retrieval_context: dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """Security Agent: Reviews IAM access privileges and credentials."""
    finding = "No security breaches, secret reference warnings, or RBAC alerts."
    confidence = 0.8
    metadata = {}
    threat_detected = False
    security_logs = []

    if any(
        kw in " ".join(error_logs).lower()
        for kw in [
            "password",
            "unauthorized",
            "access denied",
            "auth",
            "credential",
            "wrong-password",
        ]
    ):
        threat_detected = True
        security_logs = error_logs
        metadata = {"category": "credentials"}
    else:
        try:
            if NEO4J_AVAILABLE:
                records = neo4j_client.execute_query(
                    """
                    MATCH (p:Pod {name: $pod_name})-[:GENERATES]->(l:Log)
                    WHERE l.message CONTAINS 'password'
                       OR l.message CONTAINS 'unauthorized'
                       OR l.message CONTAINS 'access denied'
                       OR l.message CONTAINS 'auth'
                    RETURN l.message as msg
                    LIMIT 3
                    """,
                    {"pod_name": pod_name},
                )
                if records:
                    threat_detected = True
                    security_logs = [r["msg"] for r in records]
                    metadata = {
                        "category": "credentials",
                        "log_sample": records[0]["msg"],
                    }
        except (RuntimeError, ValueError, KeyError, TypeError, AttributeError):
            pass

    if threat_detected:
        prompt = (
            f"You are a Specialist Security Agent.\n"
            f"Analyze logs for Pod '{pod_name}' to check "
            f"for credential leaks.\n\n"
            f"Logs:\n{chr(10).join(security_logs)}\n\n"
        )
        if retrieval_context and retrieval_context.get("status") == "success":
            prompt += (
                "Retrieved graph evidence summary:\n"
                f"{json.dumps(retrieval_context, indent=2)}\n\n"
            )
        elif evidence_context:
            prompt += (
                f"Related evidence items:\n{json.dumps(evidence_context, indent=2)}\n\n"
            )
        prompt += "Output JSON with: 'finding', 'confidence', 'threat_detected'."

        config = llm_config or {}
        llm_res = _call_llm_agent(
            prompt,
            "You are a security analysis specialist AI. You output strictly JSON.",
            config.get("provider"),
            config.get("api_key"),
            config.get("model"),
        )

        if llm_res and "finding" in llm_res and "confidence" in llm_res:
            return {
                "name": "security",
                "finding": str(llm_res["finding"]),
                "confidence": round(_coerce_confidence(llm_res.get("confidence")), 2),
                "metadata": {
                    **metadata,
                    "threat_detected": bool(llm_res.get("threat_detected", True)),
                },
            }

        finding, confidence = _analyze_security_rules(metadata, threat_detected)

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
                except (RuntimeError, Neo4jError, ServiceUnavailable):
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
        evidence_context = payload.get("evidence_context", [])
        retrieval_context = payload.get("retrieval_context", {})
        llm_config = {
            "provider": payload.get("llm_provider"),
            "api_key": payload.get("llm_api_key"),
            "model": payload.get("llm_model"),
        }

        # All 5 specialists, sequentially. No inter-agent pacing: add backoff if
        # a real rate limit shows up rather than guessing at per-tier limits.
        monitoring_res = run_monitoring_agent(
            pod_name,
            llm_config=llm_config,
            evidence_context=evidence_context,
            retrieval_context=retrieval_context,
        )
        logs_res = run_log_agent(
            pod_name,
            error_logs,
            llm_config=llm_config,
            evidence_context=evidence_context,
            retrieval_context=retrieval_context,
        )
        deployments_res = run_deployment_agent(
            pod_name,
            llm_config=llm_config,
            evidence_context=evidence_context,
            retrieval_context=retrieval_context,
        )
        topology_res = run_topology_agent(
            pod_name,
            llm_config=llm_config,
            evidence_context=evidence_context,
            retrieval_context=retrieval_context,
        )
        security_res = run_security_agent(
            pod_name,
            error_logs,
            llm_config=llm_config,
            evidence_context=evidence_context,
            retrieval_context=retrieval_context,
        )

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
    """Run the HTTP server on the specified port.

    Threaded, not a plain TCPServer — a single-threaded server can't answer
    the /health liveness probe while a long-running /analyze request (5
    sequential specialist LLM calls) is in flight, which starves the probe
    and gets the container SIGKILLed by kubelet mid-request. The same bug,
    verified live, took down agent-orchestrator's identical server pattern.
    """
    socketserver.ThreadingTCPServer.allow_reuse_address = True
    socketserver.ThreadingTCPServer.daemon_threads = True
    with socketserver.ThreadingTCPServer(("", port), InvestigationHandler) as httpd:
        print(f"Serving real investigation engine on port {port}")
        httpd.serve_forever()


if __name__ == "__main__":
    target_port = os.environ.get("PORT", "8081")
    run_server(int(target_port))
