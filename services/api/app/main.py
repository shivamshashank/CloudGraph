"""Main FastAPI application entry point, containing HTTP routes and lifespans."""

from contextlib import asynccontextmanager
import asyncio
import logging
import os
import time
import traceback
from typing import Any
import uuid

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import requests


from app.adapters.graph_constructor import (
    build_service_dependency_map,
    record_state_history,
    run_entity_linking,
)
from app.adapters.k8s_discovery import discover_cluster_topology
from app.database.neo4j_client import neo4j_client, NEO4J_CONNECTION_ERRORS
from app.database.qdrant import qdrant_client
from app.research.gcp import GraphConfidencePropagator
from app.research.gpcs import GraphProvenanceClaimScorer
from app.research.llm_settings import load_stored_llm_settings
from app.services.graphrag_search import graphrag_search
from app.dependencies import semantic_store

from app.schemas import (
    PodStatusPayload,
    InvestigationTrigger,
    EvidenceTrigger,
    GraphRAGSearchPayload,
)
from app.routers.telemetry import router as telemetry_router
from app.routers.webhooks import router as webhooks_router
from app.routers.benchmark import router as benchmark_router
from app.routers.incidents import router as incidents_router
from app.routers.settings import router as settings_router
from app.routers.logs import router as logs_router
from app.routers.report import router as report_router
from app.helpers import (
    build_relevant_evidence,
    build_retrieval_context_for_investigation,
    build_investigation_analysis,
)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """FastAPI application lifespan context manager for startup and shutdown."""
    neo4j_client.connect()
    qdrant_client.ensure_collections()
    # Backfill Qdrant from Neo4j at startup (non-blocking)
    asyncio.create_task(asyncio.to_thread(semantic_store.backfill_from_neo4j))
    yield
    qdrant_client.close()
    neo4j_client.close()


logger = logging.getLogger(__name__)

app = FastAPI(title="CloudGraph Ingestion Engine", version="1.0.0", lifespan=lifespan)


@app.exception_handler(Exception)
def debug_exception_handler(request, exc):
    """Print traceback of unhandled exceptions for debugging."""
    traceback.print_exc()
    _ = request

    return JSONResponse(status_code=500, content={"detail": str(exc)})


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(telemetry_router)
app.include_router(webhooks_router)
app.include_router(benchmark_router)
app.include_router(incidents_router)
app.include_router(settings_router)
app.include_router(logs_router)
app.include_router(report_router)


@app.get("/health")
def health_check():
    """Verify service and database connection health."""
    try:
        neo4j_client.execute_query("RETURN 1")
        return {
            "status": "healthy",
            "neo4j": "connected",
        }
    except NEO4J_CONNECTION_ERRORS as e:
        return {
            "status": "unhealthy",
            "error": str(e),
        }


@app.get("/ready")
def ready_check():
    """Verify server readiness for processing requests."""
    return {"status": "ready"}


@app.get("/api")
@app.get("/api/")
def api_root():
    """Welcome handler for the API root."""
    return {
        "message": (
            "Welcome to the CloudGraph Ingestion API. Use the telemetry "
            "endpoints under /api/v1/."
        ),
        "status": "running",
    }


@app.post("/api/v1/graph/link")
def post_graph_link():
    """Trigger the asynchronous linking of related pod and node topology elements."""
    try:
        linking_results = run_entity_linking()
        dependencies_created = build_service_dependency_map()
        return {
            "status": "success",
            "linking": linking_results,
            "relationships_created": dependencies_created,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/api/v1/telemetry/pods/status")
def post_pod_status(payload: PodStatusPayload):
    """Directly log container lifecycle status switches."""
    try:
        history_id = record_state_history(
            payload.pod_id, payload.status, payload.timestamp
        )
        return {"status": "success", "history_id": history_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/api/v1/graph/discover")
def trigger_k8s_discovery(namespace: str = "cloudgraph-system"):
    """Discover Kubernetes resource structures and map into graph entities."""
    try:
        result = discover_cluster_topology(namespace=namespace)
        if result.get("status") == "success":
            discovered = result.get("discovered", {})
            semantic_store.index_document(
                "cluster-discovery",
                (
                    f"cluster discovery namespace {namespace} nodes "
                    f"{discovered.get('nodes')} pods {discovered.get('pods')} "
                    f"services {discovered.get('services')}"
                ),
                {"label": "Cluster", "name": namespace, "status": "Discovered"},
            )
        return result
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/api/v1/graph/data")
def get_graph_data():
    """Extract full active graph dataset for topology rendering."""
    try:
        query = """
        MATCH (n)
        WHERE n:Pod OR n:Node OR n:Service OR n:Deployment OR n:Commit OR n:Incident
        OPTIONAL MATCH (n)-[r]->(m)
        WHERE m IS NOT NULL AND (
            m:Pod OR m:Node OR m:Service OR m:Deployment OR m:Commit OR m:Incident
        )
        RETURN elementId(n) as n_id, labels(n) as n_labels, n as n_properties,
               CASE WHEN m IS NOT NULL THEN elementId(m) ELSE null END as m_id,
               CASE WHEN m IS NOT NULL THEN labels(m) ELSE [] END as m_labels,
               m as m_properties,
               type(r) as r_type
        """
        records = neo4j_client.execute_query(query)
        nodes_map = {}
        edges = []

        for r in records:
            nid = r.get("n_id")
            if nid and nid not in nodes_map:
                props = r.get("n_properties") or {}
                labels = r.get("n_labels") or []
                label = labels[0] if labels else "Node"
                nodes_map[nid] = {
                    "id": nid,
                    "label": label,
                    "name": props.get("name")
                    or props.get("sha")
                    or props.get("id")
                    or nid,
                    "status": props.get("status") or "Active",
                    "properties": props,
                }

            mid = r.get("m_id")
            if mid and mid not in nodes_map:
                props = r.get("m_properties") or {}
                labels = r.get("m_labels") or []
                label = labels[0] if labels else "Node"
                nodes_map[mid] = {
                    "id": mid,
                    "label": label,
                    "name": props.get("name")
                    or props.get("sha")
                    or props.get("id")
                    or mid,
                    "status": props.get("status") or "Active",
                    "properties": props,
                }

            rtype = r.get("r_type")
            if rtype and nid and mid:
                edges.append({"source": nid, "target": mid, "type": rtype})

        return {"status": "success", "nodes": list(nodes_map.values()), "edges": edges}
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e)) from e


def _propagate_confidence(pod_name: str) -> dict[str, float]:
    """Run GCP for a pod, or report zero confidence if it cannot run.

    Zeros rather than a confident-looking default: when propagation can't
    run (no reachable graph, or no topology around the pod), the honest
    report is "no confidence was computed". This previously defaulted to
    0.80, which an operator would reasonably read as a real, high-
    confidence score.
    """
    try:
        return GraphConfidencePropagator().run_propagation(pod_name)
    except RuntimeError as exc:
        logger.warning("Confidence propagation unavailable: %s", exc)
        return {"root_cause": 0.0, "recommendation": 0.0}


def _investigate_pod(
    pod: dict[str, Any],
    namespace: str,
    llm_provider: str | None = None,
    llm_api_key: str | None = None,
    llm_model: str | None = None,
) -> dict[str, Any]:
    """Execute investigation checks, logs querying, and context extraction for a pod."""
    error_msgs = [
        e["msg"]
        for e in neo4j_client.execute_query(
            """
            MATCH (p:Pod)-[:GENERATES]->(l:Log)
            WHERE elementId(p) = $pod_id AND l.level = 'ERROR'
            RETURN l.message as msg, l.timestamp as ts
            ORDER BY l.timestamp DESC LIMIT 3
            """,
            {"pod_id": pod["id"]},
        )
    ]

    analysis = None

    try:
        orch_addr = os.getenv("AGENT_ORCHESTRATOR_URL", "http://localhost:8082")
        evidence_context = build_relevant_evidence(
            pod_name=pod["name"], namespace=namespace
        )
        retrieval_context = build_retrieval_context_for_investigation(
            pod_name=pod["name"],
            search_func=graphrag_search,
            namespace=namespace,
        )
        response = requests.post(
            f"{orch_addr.rstrip('/')}/orchestrate",
            json={
                "pod_id": pod["id"],
                "pod_name": pod["name"],
                "pod_status": pod["status"],
                "namespace": namespace,
                "error_logs": error_msgs,
                "evidence_context": evidence_context["evidence"],
                "retrieval_context": retrieval_context,
                "llm_provider": llm_provider,
                "llm_api_key": llm_api_key,
                "llm_model": llm_model,
            },
            # Must accommodate a real LLM-backed orchestrator chain, same as
            # self_consistency.py's and evaluation.py's calls to this same
            # /orchestrate endpoint — see the timeout comment in
            # agent-orchestrator/main.py. This was previously 12s, which
            # meant the live "Run AI Diagnosis" flow almost certainly timed
            # out and silently used the rule-based fallback below on every
            # real request, never the LLM path — verified as a real bug,
            # not a hypothetical one.
            timeout=1200,
        )
        if response.status_code == 200:
            rdata = response.json()
            if rdata.get("status") == "success" and "consensus" in rdata:
                analysis = {
                    "title": rdata["consensus"]["title"],
                    "summary": rdata["consensus"]["summary"],
                    "cause": rdata["consensus"]["cause"],
                    "recommendation": rdata["consensus"]["recommendation"],
                    "severity": rdata["consensus"]["severity"],
                    "evidence": rdata["consensus"]["evidence"],
                    # Defaults to the fallback assumption, not "llm" — if the
                    # orchestrator ever omits this field, treat it as
                    # unverified rather than silently claiming success.
                    "generation_source": rdata["consensus"].get(
                        "generation_source", "rule_based_fallback"
                    ),
                }
    except (requests.RequestException, ValueError, KeyError):
        pass

    if not analysis:
        analysis = build_investigation_analysis(
            pod_name=pod["name"],
            pod_status=pod["status"],
            error_msgs=error_msgs,
        )
        # Orchestrator was unreachable entirely — this is a local,
        # non-LLM-backed fallback, same class of result as the
        # orchestrator's own internal rule_based_fallback, just from a
        # different code path.
        analysis["generation_source"] = "rule_based_fallback"
    evidence_context = build_relevant_evidence(
        pod_name=pod["name"], namespace=namespace
    )
    retrieval_context = build_retrieval_context_for_investigation(
        pod_name=pod["name"],
        search_func=graphrag_search,
        namespace=namespace,
    )
    if retrieval_context["status"] == "success":
        analysis["evidence"].append(
            f"Retrieval context: {retrieval_context['summary']}"
        )

    gcp_res = _propagate_confidence(pod["name"])
    claim_scoring = {"unsupported_claim_rate": 0.0, "claim_count": 0, "claims": []}

    try:
        claim_scoring = GraphProvenanceClaimScorer(
            llm_settings={
                "provider": llm_provider or "",
                "api_key": llm_api_key or "",
                "model": llm_model or "",
            }
        ).score_claims(analysis, graphrag_search)
    except (ValueError, KeyError, TypeError, RuntimeError, HTTPException):
        claim_scoring = {"unsupported_claim_rate": 0.0, "claim_count": 0, "claims": []}

    incident_id = str(uuid.uuid4())
    neo4j_client.execute_query(
        """
        CREATE (i:Incident {
            id: $incident_id,
            title: $title,
            description: $cause,
            status: "Active",
            timestamp: $timestamp,
            severity: $severity,
            recommendation: $recommendation,
            root_cause_confidence: $root_cause_conf,
            recommendation_confidence: $rec_conf,
            assigned: $assigned,
            error_logs: $error_logs
        })
        WITH i
        MATCH (p:Pod) WHERE elementId(p) = $pod_id
        CREATE (p)-[:AFFECTED_BY]->(i)
        RETURN i.id as id
        """,
        {
            "incident_id": incident_id,
            "title": analysis["title"],
            "cause": analysis["cause"],
            "timestamp": int(time.time()),
            "severity": analysis["severity"],
            "recommendation": analysis["recommendation"],
            "pod_id": pod["id"],
            "root_cause_conf": gcp_res["root_cause"],
            "rec_conf": gcp_res["recommendation"],
            "assigned": "Unassigned",
            "error_logs": error_msgs,
        },
    )

    semantic_store.index_document(
        incident_id,
        (
            f"incident {analysis['title']} {analysis['cause']} "
            f"{analysis['recommendation']}"
        ),
        {
            "type": "incident",
            "label": "Incident",
            "name": analysis["title"],
            "status": "Active",
            "root_cause_confidence": gcp_res["root_cause"],
            "recommendation_confidence": gcp_res["recommendation"],
        },
    )
    semantic_store.index_document(
        pod["id"],
        (
            f"pod {pod['name']} status {pod['status']} "
            f"error logs {' '.join(error_msgs)}"
        ),
        {"label": "Pod", "name": pod["name"], "status": pod["status"]},
    )

    return {
        "id": incident_id,
        "title": analysis["title"],
        "pod_name": pod["name"],
        "status": "Active",
        "severity": analysis["severity"],
        "cause": analysis["cause"],
        "remediation": analysis["recommendation"],
        "error_logs": error_msgs,
        "summary": analysis["summary"],
        "evidence": analysis["evidence"],
        "relevant_evidence": evidence_context["evidence"],
        "retrieval_context": retrieval_context,
        "claim_scoring": claim_scoring,
        "timestamp": int(time.time()),
        "root_cause_confidence": gcp_res["root_cause"],
        "recommendation_confidence": gcp_res["recommendation"],
        "generation_source": analysis.get("generation_source", "rule_based_fallback"),
    }


@app.post("/api/v1/investigations/trigger")
def trigger_investigation(payload: InvestigationTrigger):
    """Trigger faulty workloads topology analysis and log incidents."""
    try:
        discover_cluster_topology(namespace=payload.namespace)

        pod_query = """
        MATCH (p:Pod)
        WHERE NOT p.status IN ['Running', 'Succeeded']
        RETURN elementId(p) as id, p.name as name, p.status as status,
               p.nodeName as nodeName
        """
        anomalous_pods = neo4j_client.execute_query(pod_query)

        if not anomalous_pods:
            log_anomaly_query = """
            MATCH (p:Pod)-[:GENERATES]->(l:Log {level: 'ERROR'})
            RETURN DISTINCT elementId(p) as id, p.name as name,
                            p.status as status, p.nodeName as nodeName
            LIMIT 5
            """
            anomalous_pods = neo4j_client.execute_query(log_anomaly_query)
        # The UI posts only a namespace and expects the server to use whatever
        # provider was saved on the Settings page. Without this fallback the
        # per-request fields stay None and the downstream consensus call
        # defaults to the `openai` env value — so the five specialists ran on
        # the configured provider while consensus 401'd against OpenAI and
        # silently degraded to the rule-based path.
        stored = load_stored_llm_settings() or {}
        llm_provider = payload.llm_provider or stored.get("provider")
        llm_api_key = payload.llm_api_key or stored.get("api_key")
        llm_model = payload.llm_model or stored.get("model")

        investigations = []
        if anomalous_pods:
            for pod in anomalous_pods:
                investigations.append(
                    _investigate_pod(
                        pod,
                        payload.namespace,
                        llm_provider=llm_provider,
                        llm_api_key=llm_api_key,
                        llm_model=llm_model,
                    )
                )
        else:
            investigations.append(
                {
                    "id": "healthy",
                    "title": "All cluster services healthy",
                    "status": "Healthy",
                    "severity": "NONE",
                    "cause": "No anomalies found in active workloads.",
                    "remediation": "No actions required.",
                    "error_logs": [],
                    "timestamp": int(time.time()),
                }
            )

        return {"status": "success", "results": investigations}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/api/v1/investigations/evidence")
def get_relevant_evidence(payload: EvidenceTrigger):
    """Query and return related graph telemetry and log records for a pod."""
    try:
        return build_relevant_evidence(
            pod_name=payload.pod_name, namespace=payload.namespace
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/api/v1/investigations/context-comparison")
def context_comparison(payload: GraphRAGSearchPayload):
    """Compare the raw context payload for multiple retrieval configurations."""
    try:
        query = payload.query.strip()
        if not query:
            raise HTTPException(status_code=400, detail="Query cannot be empty")

        comparisons = []
        for method in ["keyword", "vector", "hybrid"]:
            search_payload = GraphRAGSearchPayload(
                query=query,
                namespace=payload.namespace,
                depth=payload.depth,
                method=method,
            )
            search_res = graphrag_search(search_payload, method=method)
            comparisons.append(
                {
                    "config": method,
                    "label": f"{method.title()} Retrieval",
                    "detail": (
                        "GraphRAG search payload showing raw retrieval and ranking "
                        f"details for method '{method}'."
                    ),
                    "payload": {
                        "query": search_res["query"],
                        "method": search_res["method"],
                        "retrieval": search_res["retrieval"],
                        "results": search_res["results"],
                    },
                }
            )

        evidence_payload = build_relevant_evidence(
            pod_name=query, namespace=payload.namespace
        )
        retrieval_context = build_retrieval_context_for_investigation(
            pod_name=query,
            search_func=graphrag_search,
            namespace=payload.namespace,
        )
        analysis = build_investigation_analysis(query, "Unknown", [])
        llm_settings = load_stored_llm_settings()
        claim_scoring = GraphProvenanceClaimScorer(
            llm_settings=llm_settings
        ).score_claims(analysis, graphrag_search)

        comparisons.append(
            {
                "config": "agent-context",
                "label": "Agent / GCP Context",
                "detail": (
                    "Fallback investigation context payload used by the agent "
                    "orchestrator and confidence propagation pipeline."
                ),
                "payload": {
                    "query": query,
                    "search_payload": {
                        "query": query,
                        "namespace": payload.namespace,
                        "depth": payload.depth,
                        "method": "hybrid",
                    },
                    "prompts": {
                        "raw_prompt": (
                            f"Investigate the issue for '{query}' using the "
                            "active graph context, recent logs, and metric summaries."
                        ),
                        "llm_provider": payload.method,
                    },
                    "evidence": evidence_payload,
                    "retrieval_context": retrieval_context,
                    "claim_scoring": claim_scoring,
                },
                "unsupported": claim_scoring["unsupported_claim_rate"] > 0.4,
            }
        )

        return {
            "status": "success",
            "query": query,
            "unsupported_claim_rate": claim_scoring["unsupported_claim_rate"],
            "claim_count": claim_scoring["claim_count"],
            "claims": claim_scoring["claims"],
            "comparisons": comparisons,
        }
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/api/v1/graphrag/search")
def _graphrag_search_route(payload: GraphRAGSearchPayload, method: str | None = None):
    """Search graphrag context by keyword, semantic vector, or hybrid
    ranking. Thin route wrapper — the real logic lives in
    app.services.graphrag_search so app.research.report_runner/
    evaluation can call it directly without importing this module
    (which would cycle back through app.routers.report).
    """
    return graphrag_search(payload, method)


@app.post("/api/v1/graphrag/retrieve")
def graphrag_retrieve(payload: GraphRAGSearchPayload, method: str | None = None):
    """Retrieve and summarize matching contextual nodes and graph relationships."""
    try:
        query = payload.query.strip()
        if not query:
            raise HTTPException(status_code=400, detail="Query cannot be empty")

        search_res = graphrag_search(payload, method=method)
        results = search_res["results"]

        summary = (
            (
                f"Retrieved {len(results)} semantically ranked context "
                f"entries for '{query}'."
            )
            if results
            else f"No graph context found for '{query}'."
        )
        return {
            "status": "success",
            "query": query,
            "summary": summary,
            "retrieval": search_res["retrieval"],
            "results": results,
        }
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/api/v1/demo/reset")
def reset_demo():
    """Clear all nodes and relationships in the Neo4j database graph."""
    try:
        neo4j_client.execute_query("MATCH (n) DETACH DELETE n")
        return {"status": "success", "message": "Graph cleared"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
