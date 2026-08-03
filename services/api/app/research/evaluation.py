"""Evaluation module for running real benchmarking against seeded telemetry."""

import logging
import os
import time
from typing import Any, Dict, List, Optional, Tuple

import requests

from app.database.neo4j_client import neo4j_client
from app.dependencies import semantic_store
from app.retrieval.graph_traversal import graph_traversal_retriever
from app.retrieval.hybrid_ranker import hybrid_ranker
from app.research.gcp import GraphConfidencePropagator
from app.research.gpcs import GraphProvenanceClaimScorer
from app.research.llm_settings import load_stored_llm_settings

logger = logging.getLogger(__name__)

# First-pass constant, matching GPCS's own default trust threshold
# (see gpcs.py). Not yet calibrated on a held-out split — see
# IMPLEMENTATION_ROADMAP.md Phase 4.
GCP_CORRECTNESS_THRESHOLD = 0.50


class OrchestratorUnavailableError(RuntimeError):
    """Raised when the agent-orchestrator cannot be reached for a real,
    non-fabricated evaluation call. Callers must exclude this
    (scenario, baseline) pair from aggregate metrics rather than
    substitute synthetic data — never silently backfill with the
    scenario's own ground truth."""


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
              AND any(
                word IN split(toLower($query), ' ') WHERE
                size(word) > 2 AND (
                  toLower(coalesce(n.name, '')) CONTAINS word
                  OR toLower(coalesce(n.title, '')) CONTAINS word
                  OR toLower(coalesce(n.status, '')) CONTAINS word
                  OR toLower(coalesce(n.message, '')) CONTAINS word
                )
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
                # retrieve() returns a plain list[dict], not a
                # {"nodes": [...]} envelope — .get("nodes") on a list
                # would raise AttributeError (previously masked because
                # raw_results was always empty; see run_keyword_search).
                graph_context = graph_traversal_retriever.retrieve(
                    record.get("id"), depth=2
                )
                for item in graph_context:
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
    # HybridRanker.rank()'s vector_hits contract expects "text" (flat) and
    # "metadata" (nested dict) — semantic_hits (semantic_store.search()'s
    # raw output) already has exactly that shape. The previous code
    # reshaped this into a "detail"/flat-name/flat-status dict that the
    # ranker's field names don't match, silently dropping all vector
    # content before scoring (ranker read hit.get("text","") -> "" and
    # hit.get("metadata") -> {} for every candidate). Pass semantic_hits
    # straight through instead of re-inventing its shape.
    try:
        ranked = hybrid_ranker.rank(
            semantic_hits, graph_hits, reference_time=1600000000, limit=5
        )
        return ranked
    except (RuntimeError, ValueError) as exc:
        logger.error("Hybrid ranker failed: %s", exc)
        return semantic_hits[:5]


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
        # HybridRanker.rank() candidates carry "text" (preserved verbatim
        # from vector hits) and nested "properties"/"metadata" (from graph
        # hits) — there is no top-level "detail"/"status" key. Reading
        # "detail" here previously always returned "", silently discarding
        # every vector-sourced match's content.
        for hit in results:
            parts.append(hit.get("name") or "")
            parts.append(hit.get("text") or "")
            props = hit.get("properties") or {}
            parts.append(props.get("message") or "")
            parts.append(props.get("status") or "")
            meta = hit.get("metadata") or {}
            parts.append(meta.get("status") or "")
            parts.append(meta.get("message") or "")
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
            props = hit.get("properties") or {}
            node_text = (
                f"{hit.get('name', '')} {hit.get('text', '')} "
                f"{props.get('message', '')} {props.get('status', '')}"
            ).lower()
            if not any(tag.lower() in node_text for tag in expected_tags):
                fp += 1
    return fp


MAX_AGENT_STEP_ATTEMPTS = 3
AGENT_STEP_RETRY_BACKOFF_SECONDS = 4.0


def _run_agents_step(scenario: Dict[str, Any], results: List[Dict[str, Any]]) -> Any:
    """Call the real agent orchestrator, retrying transient failures up to
    MAX_AGENT_STEP_ATTEMPTS times; never fabricate a response.

    Raises OrchestratorUnavailableError only after all attempts fail
    (network error, non-200, malformed body) — never silently substitutes
    a canned analysis built from the scenario's own ground-truth claims.
    Retrying is honest (each attempt is still a real request); the
    orchestrator chains 6 sequential LLM calls once a key is configured
    (5 specialists + 1 consensus), so ordinary API flakiness on any single
    call would otherwise sour an entire scenario's result.
    """
    last_error: Optional[OrchestratorUnavailableError] = None
    for attempt in range(1, MAX_AGENT_STEP_ATTEMPTS + 1):
        try:
            return _request_agents_step(scenario, results)
        except OrchestratorUnavailableError as exc:
            last_error = exc
            logger.warning(
                "Agents step attempt %d/%d failed for scenario '%s': %s",
                attempt,
                MAX_AGENT_STEP_ATTEMPTS,
                scenario["id"],
                exc,
            )
            if attempt < MAX_AGENT_STEP_ATTEMPTS:
                time.sleep(AGENT_STEP_RETRY_BACKOFF_SECONDS * attempt)
    raise OrchestratorUnavailableError(
        f"all {MAX_AGENT_STEP_ATTEMPTS} attempts failed for scenario "
        f"'{scenario['id']}': {last_error}"
    ) from last_error


def _request_agents_step(
    scenario: Dict[str, Any], results: List[Dict[str, Any]]
) -> Any:
    """Single attempt to call the real agent orchestrator."""
    orch_addr = os.getenv("AGENT_ORCHESTRATOR_URL", "http://localhost:8082")
    llm_settings = load_stored_llm_settings()
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
                "llm_provider": llm_settings.get("provider"),
                "llm_api_key": llm_settings.get("api_key"),
                "llm_model": llm_settings.get("model"),
            },
            # Must accommodate a real LLM-backed orchestrator chain (5
            # sequential specialist calls + 1 consensus call) against a
            # local Ollama model — 6s only ever worked because the
            # rule-based fallback path is instant. Local CPU/GPU inference
            # speed varies a lot by model size and hardware, so this is
            # sized with real headroom.
            timeout=420,
        )
    except requests.RequestException as exc:
        raise OrchestratorUnavailableError(
            f"agent-orchestrator unreachable at {orch_addr}: {exc}"
        ) from exc

    if response.status_code != 200:
        raise OrchestratorUnavailableError(
            f"agent-orchestrator returned HTTP {response.status_code} "
            f"for scenario {scenario['id']}"
        )

    rdata = response.json()
    if rdata.get("status") != "success" or "consensus" not in rdata:
        raise OrchestratorUnavailableError(
            f"agent-orchestrator response missing consensus for "
            f"scenario {scenario['id']}: {rdata}"
        )
    return rdata["consensus"]


def _run_gcp_step(target_entity: str) -> float:
    """Run graph confidence propagation (GCP) and return the real
    root-cause confidence score. Returns 0.0 (not a fabricated confident
    value) if propagation cannot run at all."""
    try:
        propagator = GraphConfidencePropagator()
        result = propagator.run_propagation(target_entity)
        return float(result.get("root_cause", 0.0))
    except (RuntimeError, ValueError, TypeError) as exc:
        logger.warning("Confidence propagation failed: %s", exc)
        return 0.0


def _run_gpcs_step(analysis: Any) -> Optional[float]:
    """Score hallucination rate using GPCS; return unsupported-claim rate,
    or None if scoring failed (never a fabricated placeholder rate)."""
    try:
        scorer = GraphProvenanceClaimScorer()
        gpcs_res = scorer.score_claims(analysis, run_hybrid_search)
        return gpcs_res.get("unsupported_claim_rate", 0.0)
    except (RuntimeError, ValueError) as exc:
        logger.warning("GPCS claim scoring failed: %s", exc)
        return None


def evaluate_scenario(
    scenario: Dict[str, Any], baseline_name: str
) -> Optional[Tuple[int, int, int, int, Optional[float]]]:
    """Evaluate a single baseline against a ground-truth scenario using only
    real pipeline calls.

    Returns None if a required live component (the agent-orchestrator) is
    unreachable — callers must exclude this result from aggregate metrics
    rather than substitute fabricated data.

    The fifth element of the returned tuple (unsupported claim count) is
    None for baselines that generate no text to score (pure retrieval),
    since hallucination rate is undefined for them, not merely unmeasured.
    """
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
        try:
            analysis = _run_agents_step(scenario, results)
        except OrchestratorUnavailableError as exc:
            logger.error(
                "Excluding scenario '%s' baseline '%s' from results: %s",
                scenario["id"],
                baseline_name,
                exc,
            )
            return None

    if "GCP" in baseline_name:
        gcp_confidence = _run_gcp_step(scenario["target_entity"])
        # GCP-tier baselines must also clear a confidence bar to count as
        # correct, not just pass the tag-overlap check — otherwise this
        # tier is indistinguishable from "Agents" alone.
        correct = 1 if (correct and gcp_confidence >= GCP_CORRECTNESS_THRESHOLD) else 0

    if analysis is not None:
        # Any baseline that produced real generated text gets a real,
        # measured hallucination rate via GPCS — the only claim-scoring
        # mechanism this system has. This may legitimately come out close
        # to (or identical to) later tiers' numbers, since GPCS here is a
        # measurement instrument, not yet a remediation step — report that
        # honestly rather than adjusting the harness.
        unsupported_rate = _run_gpcs_step(analysis)
    else:
        unsupported_rate = None

    unsupported_claims_count = (
        len(scenario["ground_truth_claims"]) * unsupported_rate
        if unsupported_rate is not None
        else None
    )

    return tp, fp, fn, correct, unsupported_claims_count
