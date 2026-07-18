"""Helper functions for formatting and constructing analysis payloads."""

from typing import Any, List
from fastapi import HTTPException

from app.database.neo4j_client import neo4j_client
from app.schemas import GraphRAGSearchPayload


def build_relevant_evidence(
    pod_name: str, namespace: str = "cloudgraph-system"
) -> dict[str, Any]:
    """Query and construct related graph telemetry and log records for a pod."""
    query = """
    MATCH (p:Pod {name: $pod_name})
    OPTIONAL MATCH (p)-[:BELONGS_TO]->(s:Service)
    OPTIONAL MATCH (p)-[:RUNS_ON]->(n:Node)
    OPTIONAL MATCH (p)<-[:MANAGES]-(d:Deployment)
    OPTIONAL MATCH (p)-[:GENERATES]->(l:Log)
    WHERE l.level IN ['ERROR', 'WARN', 'INFO']
    RETURN p.name as pod_name,
           s.name as service_name, s.confidence as service_conf,
           d.name as deployment_name, d.confidence as deployment_conf,
           n.name as node_name, n.confidence as node_conf,
           collect(DISTINCT l.message)[0..3] as log_messages
    LIMIT 1
    """
    row = neo4j_client.execute_query(query, {"pod_name": pod_name})
    row = row[0] if row else {}

    evidence = []
    if row.get("service_name"):
        evidence.append(
            {
                "type": "service",
                "label": row["service_name"],
                "detail": (
                    "The pod belongs to this service and is part of the "
                    "active dependency chain."
                ),
                "confidence": row.get("service_conf") or 0.80,
            }
        )
    if row.get("deployment_name"):
        evidence.append(
            {
                "type": "deployment",
                "label": row["deployment_name"],
                "detail": (
                    "The deployment owning this pod is part of the workload "
                    "history being analyzed."
                ),
                "confidence": row.get("deployment_conf") or 0.75,
            }
        )
    if row.get("node_name"):
        evidence.append(
            {
                "type": "node",
                "label": row["node_name"],
                "detail": (
                    "This pod is scheduled onto the node shown by the "
                    "current topology graph."
                ),
                "confidence": row.get("node_conf") or 0.60,
            }
        )
    if row.get("log_messages"):
        evidence.append(
            {
                "type": "logs",
                "label": "Recent log signals",
                "detail": (
                    "Recent pod log lines were used as supporting "
                    "evidence for the diagnosis."
                ),
                "messages": row["log_messages"],
                "confidence": 0.85,
            }
        )

    if not evidence:
        evidence.append(
            {
                "type": "fallback",
                "label": "No graph evidence found",
                "detail": (
                    "The graph did not return additional context for this pod yet."
                ),
            }
        )

    return {
        "status": "success",
        "pod_name": pod_name,
        "namespace": namespace,
        "evidence": evidence,
    }


def build_retrieval_context_for_investigation(
    pod_name: str,
    search_func: Any,
    namespace: str = "cloudgraph-system",
) -> dict[str, Any]:
    """Search context for the automated incident investigation using GraphRAG."""
    try:
        search_payload = GraphRAGSearchPayload(
            query=pod_name,
            namespace=namespace,
            depth=2,
            method="hybrid",
        )
        search_res = search_func(search_payload)
        results = search_res.get("results", [])
        if results:
            top_result = results[0]
            return {
                "status": "success",
                "source": "graphrag",
                "query": pod_name,
                "summary": (
                    f"Retrieved {len(results)} ranked evidence items "
                    f"around '{pod_name}'."
                ),
                "top_result": {
                    "name": top_result.get("name"),
                    "score": top_result.get("score"),
                    "sources": top_result.get("sources"),
                },
            }
    except (RuntimeError, ConnectionError, OSError, HTTPException):
        pass

    return {
        "status": "fallback",
        "source": "rule-based",
        "query": pod_name,
        "summary": "Retrieval unavailable; rule-based evidence used instead.",
        "top_result": None,
    }


def build_investigation_analysis(
    pod_name: str, pod_status: str, error_msgs: List[str]
) -> dict[str, Any]:
    """Classify anomalous states and generate remediations based on
    statuses and log lines."""
    error_text = " ".join(error_msgs).lower() if error_msgs else ""

    if any(
        keyword in error_text
        for keyword in ["timeout", "refused", "dial tcp", "connection"]
    ):
        title = f"Potential dependency failure on {pod_name}"
        summary = "Potential dependency failure or crash loop detected"
        cause = "Observed connection or dependency errors in pod logs."
        recommendation = "Verify downstream dependencies and network reachability."
        severity = "CRITICAL"
    elif (
        "crashloop" in pod_status.lower()
        or "error" in pod_status.lower()
        or "failed" in pod_status.lower()
    ):
        title = f"CrashLoopBackOff on {pod_name}"
        summary = "Crash loop or failing workload detected"
        cause = "The workload is repeatedly restarting or failing."
        recommendation = "Inspect pod events and recent application logs."
        severity = "CRITICAL"
    elif any(keyword in error_text for keyword in ["imagepull", "errimagepull"]):
        title = f"Image pull failure on {pod_name}"
        summary = "Container image could not be pulled"
        cause = "Kubernetes failed to download the container image."
        recommendation = (
            "Check the deployment image reference and registry credentials."
        )
        severity = "HIGH"
    elif "oom" in error_text or "oomkilled" in pod_status.lower():
        title = f"Out of memory on {pod_name}"
        summary = "The container was terminated by the OOM killer"
        cause = "The application exceeded its memory limits."
        recommendation = "Increase memory limits or profile memory usage."
        severity = "CRITICAL"
    else:
        title = f"Pod anomaly on {pod_name}"
        summary = "Pod reported a non-healthy state"
        cause = (
            "The pod is unhealthy but the pattern is not specific "
            "enough for a single root cause."
        )
        recommendation = "Inspect pod events and container logs."
        severity = "HIGH"

    evidence = [f"Pod status: {pod_status or 'Unknown'}"]
    if error_msgs:
        evidence.append("Recent errors: " + " | ".join(error_msgs[:3]))
    else:
        evidence.append("No detailed log errors were captured")

    return {
        "title": title,
        "summary": summary,
        "cause": cause,
        "recommendation": recommendation,
        "severity": severity,
        "evidence": evidence,
    }


def format_hybrid_result(candidate: dict[str, Any]) -> dict[str, Any]:
    """Format combined Neo4j + Qdrant scoring values into standard
    JSON response fields."""
    metadata = candidate.get("metadata") or {}
    properties = candidate.get("properties") or {}
    label = (
        metadata.get("label")
        or ((candidate.get("labels") or [None])[0])
        or candidate.get("type", "Evidence").title()
    )
    relationships = candidate.get("relationships") or []
    path = candidate.get("path") or []
    context = []
    for index, node in enumerate(path[1:], start=1):
        node_labels = node.get("labels") or ["Node"]
        context.append(
            {
                "name": node.get("name") or node.get("id") or "unknown",
                "type": node_labels[0].lower(),
                "relationship": (
                    relationships[index - 1]
                    if index - 1 < len(relationships)
                    else "RELATED_TO"
                ),
                "hop_distance": index,
                "path": path,
            }
        )
    if not context:
        context.append(
            {
                "name": (
                    "Semantic evidence"
                    if "vector" in candidate["sources"]
                    else "Seed node"
                ),
                "type": "semantic" if "vector" in candidate["sources"] else "graph",
                "relationship": (
                    "matched_text" if "vector" in candidate["sources"] else "seed"
                ),
                "hop_distance": candidate.get("hop_distance"),
                "path": path,
            }
        )

    evidence_chain = [
        {
            "type": "ranking",
            "label": "Hybrid score",
            "name": candidate["score_breakdown"]["formula"],
            "score_breakdown": candidate["score_breakdown"],
        }
    ]
    evidence_chain.extend(
        {
            "type": "relation",
            "label": relationship,
            "name": (
                context[index]["name"] if index < len(context) else candidate["name"]
            ),
            "hop_distance": index + 1,
        }
        for index, relationship in enumerate(relationships)
    )

    return {
        "id": candidate["id"],
        "label": label,
        "type": candidate["type"],
        "name": candidate["name"],
        "status": metadata.get("status") or properties.get("status") or "Active",
        "text": candidate.get("text", ""),
        "sources": candidate["sources"],
        "hop_distance": candidate.get("hop_distance"),
        "relationships": relationships,
        "path": path,
        "evidence_chain": evidence_chain,
        "context": context,
        "related": [],
        "score": candidate["score"],
        "score_breakdown": candidate["score_breakdown"],
        "ranking_rationale": candidate["ranking_rationale"],
        "detail": " ".join(candidate["ranking_rationale"]),
    }
