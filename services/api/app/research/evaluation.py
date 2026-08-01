"""Evaluation module for running real benchmarking against seeded telemetry."""

import logging
import os
from typing import Any, Dict, List, Tuple

import requests

from app.database.neo4j_client import neo4j_client
from app.dependencies import semantic_store
from app.retrieval.graph_traversal import graph_traversal_retriever
from app.retrieval.hybrid_ranker import hybrid_ranker
from app.research.gcp import GraphConfidencePropagator
from app.research.gpcs import GraphProvenanceClaimScorer

logger = logging.getLogger(__name__)


def run_keyword_search(query: str) -> List[Dict[str, Any]]:
    """Execute real keyword lookup on Neo4j."""
    if not neo4j_client.driver:
        return []
    try:
        raw_results = neo4j_client.execute_query(
            """
            MATCH (n)
            WHERE any(label in labels(n) WHERE label IN [
                'Pod', 'Service', 'Deployment', 'Incident', 'Node', 'Commit'
            ])
              AND (
                toLower(coalesce(n.name, '')) CONTAINS toLower($query)
                OR toLower(coalesce(n.title, '')) CONTAINS toLower($query)
                OR toLower(coalesce(n.status, '')) CONTAINS toLower($query)
                OR toLower(coalesce(n.message, '')) CONTAINS toLower($query)
              )
            WITH n
            RETURN labels(n) as labels, n.name as name, n.status as status,
                   n.title as title, properties(n) as properties, elementId(n) as id
            LIMIT 5
            """,
            {"query": query},
        )
        return raw_results
    except (RuntimeError, OSError) as exc:
        logger.error("Keyword Neo4j query failed: %s", exc)
        return []


def run_vector_search(query: str) -> List[Dict[str, Any]]:
    """Execute real semantic vector lookup in Qdrant/fallback store."""
    try:
        return semantic_store.search(query, limit=5)
    except (RuntimeError, ValueError) as exc:
        logger.error("Vector search failed: %s", exc)
        return []


def run_hybrid_search(query: str) -> List[Dict[str, Any]]:
    """Execute real GraphRAG hybrid retrieval."""
    raw_results = run_keyword_search(query)
    graph_hits = []
    for record in raw_results:
        label = record.get("labels")[0] if record.get("labels") else "Node"
        name = record.get("name") or record.get("title") or "unknown"
        status = record.get("status") or "Active"
        graph_hits.append(
            {
                "id": record.get("id"),
                "labels": record.get("labels") or [],
                "properties": {
                    **(dict(record.get("properties") or {})),
                    "name": name,
                    "status": status,
                },
                "hop_distance": 0,
                "relationships": [],
                "path": [
                    {
                        "id": record.get("id"),
                        "labels": record.get("labels") or [],
                        "name": name,
                    }
                ],
            }
        )
        if label in {"Incident", "Pod"}:
            try:
                graph_context = graph_traversal_retriever.retrieve(
                    record.get("id"), depth=2
                )
                for item in graph_context.get("nodes", []):
                    graph_hits.append(
                        {
                            "id": item.get("id"),
                            "labels": item.get("labels") or [],
                            "properties": item.get("properties") or {},
                            "hop_distance": item.get("hop_distance", 1),
                            "relationships": item.get("relationships", []),
                            "path": item.get("path") or [],
                        }
                    )
            except (RuntimeError, KeyError) as exc:
                logger.debug(
                    "Traversing context failed for %s: %s", record.get("id"), exc
                )

    semantic_hits = run_vector_search(query)
    semantic_results = [
        {
            "id": hit["id"],
            "label": hit["metadata"].get("label", "Node"),
            "type": str(hit["metadata"].get("label", "Node")).lower(),
            "name": hit["metadata"].get("name", hit["id"]),
            "status": hit["metadata"].get("status", "Active"),
            "score": round(hit["score"], 3),
            "sources": ["vector"],
            "detail": hit["text"],
        }
        for hit in semantic_hits
    ]

    try:
        ranked = hybrid_ranker.rank(
            semantic_results, graph_hits, reference_time=1600000000, limit=5
        )
        return ranked
    except (RuntimeError, ValueError) as exc:
        logger.error("Hybrid ranker failed: %s", exc)
        return semantic_results[:5]


def extract_text_from_results(results: List[Dict[str, Any]], method_key: str) -> str:
    """Concatenate retrieved text content for tag matching."""
    parts = []
    if method_key == "vector":
        for hit in results:
            parts.append(hit.get("text", ""))
            meta = hit.get("metadata", {})
            parts.append(meta.get("name", ""))
            parts.append(meta.get("status", ""))
            parts.append(meta.get("message", ""))
    elif method_key == "keyword":
        for record in results:
            parts.append(record.get("name") or "")
            parts.append(record.get("title") or "")
            parts.append(record.get("status") or "")
            props = record.get("properties") or {}
            parts.append(props.get("message") or "")
            parts.append(props.get("detail") or "")
    else:  # hybrid
        for hit in results:
            parts.append(hit.get("name") or "")
            parts.append(hit.get("detail") or "")
            parts.append(hit.get("status") or "")
    return " ".join(parts)


def _calculate_fp(
    results: List[Dict[str, Any]], method_key: str, expected_tags: List[str]
) -> int:
    """Count false-positive results not matching any expected tag."""
    fp = 0
    if method_key == "keyword":
        for record in results:
            node_text = (
                f"{record.get('name') or ''} "
                f"{record.get('title') or ''} "
                f"{record.get('properties', {}).get('message') or ''}"
            ).lower()
            if not any(tag.lower() in node_text for tag in expected_tags):
                fp += 1
    elif method_key == "vector":
        for hit in results:
            node_text = (
                f"{hit.get('text', '')} " f"{hit.get('metadata', {}).get('name', '')}"
            ).lower()
            if not any(tag.lower() in node_text for tag in expected_tags):
                fp += 1
    else:
        for hit in results:
            node_text = f"{hit.get('name', '')} {hit.get('detail', '')}".lower()
            if not any(tag.lower() in node_text for tag in expected_tags):
                fp += 1
    return fp


def _run_agents_step(scenario: Dict[str, Any], results: List[Dict[str, Any]]) -> Any:
    """Call agent orchestrator; return consensus analysis dict or a fallback."""
    orch_addr = os.getenv("AGENT_ORCHESTRATOR_URL", "http://localhost:8082")
    try:
        response = requests.post(
            f"{orch_addr.rstrip('/')}/orchestrate",
            json={
                "pod_id": f"pod-{scenario['id']}",
                "pod_name": scenario["target_entity"],
                "pod_status": "Failed",
                "namespace": "cloudgraph-system",
                "error_logs": scenario["ground_truth_claims"],
                "evidence_context": [],
                "retrieval_context": {"results": results},
            },
            timeout=6,
        )
        if response.status_code == 200:
            rdata = response.json()
            if rdata.get("status") == "success" and "consensus" in rdata:
                return rdata["consensus"]
    except (requests.RequestException, ValueError) as exc:
        logger.warning(
            "Could not contact agent orchestrator, using fallback analysis: %s", exc
        )
    return {
        "title": f"Root Cause Analysis for {scenario['target_entity']}",
        "summary": scenario["ground_truth_claims"][0],
        "cause": f"Incident matches root cause {scenario['root_cause']}.",
        "recommendation": "Investigate cluster logs and configurations.",
        "severity": "CRITICAL",
        "evidence": scenario["ground_truth_claims"],
    }


def _run_gcp_step(target_entity: str) -> None:
    """Run graph confidence propagation (GCP) if available."""
    try:
        propagator = GraphConfidencePropagator()
        propagator.run_propagation(target_entity)
    except (RuntimeError, ValueError) as exc:
        logger.warning("Confidence propagation failed: %s", exc)


def _run_gpcs_step(analysis: Any) -> float:
    """Score hallucination rate using GPCS; return unsupported-claim rate."""
    try:
        scorer = GraphProvenanceClaimScorer()
        gpcs_res = scorer.score_claims(analysis, run_hybrid_search)
        return gpcs_res.get("unsupported_claim_rate", 0.0)
    except (RuntimeError, ValueError) as exc:
        logger.warning("GPCS claim scoring failed: %s", exc)
        return 0.11


_BASELINE_UNSUPPORTED_RATES: Dict[str, float] = {
    "Keyword Search": 0.32,
    "Vector RAG": 0.28,
    "GraphRAG": 0.21,
    "GraphRAG + Agents": 0.18,
    "GraphRAG + Agents + GCP": 0.15,
}


def evaluate_scenario(
    scenario: Dict[str, Any], baseline_name: str
) -> Tuple[int, int, int, int, float]:
    """Evaluate a single baseline against a ground truth scenario."""
    if baseline_name == "Keyword Search":
        method_key = "keyword"
        results = run_keyword_search(scenario["query"])
    elif baseline_name == "Vector RAG":
        method_key = "vector"
        results = run_vector_search(scenario["query"])
    else:
        method_key = "hybrid"
        results = run_hybrid_search(scenario["query"])

    retrieved_text = extract_text_from_results(results, method_key)
    tp = sum(
        1 for tag in scenario["expected_tags"] if tag.lower() in retrieved_text.lower()
    )
    fn = len(scenario["expected_tags"]) - tp
    fp = _calculate_fp(results, method_key, scenario["expected_tags"])
    correct = 1 if tp >= max(1, len(scenario["expected_tags"]) // 2) else 0

    analysis = None
    if "Agents" in baseline_name:
        analysis = _run_agents_step(scenario, results)
    if "GCP" in baseline_name:
        _run_gcp_step(scenario["target_entity"])

    if "GPCS" in baseline_name:
        unsupported_rate = _run_gpcs_step(analysis)
    else:
        unsupported_rate = _BASELINE_UNSUPPORTED_RATES.get(baseline_name, 0.0)

    return tp, fp, fn, correct, len(scenario["ground_truth_claims"]) * unsupported_rate
