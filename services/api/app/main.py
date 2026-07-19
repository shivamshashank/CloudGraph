"""Main FastAPI application entry point, containing HTTP routes and lifespans."""

# pylint: disable=too-many-lines

from contextlib import asynccontextmanager
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
from app.database.redis_client import redis_client
from app.research.gcp import GraphConfidencePropagator
from app.research.gpcs import GraphProvenanceClaimScorer
from app.retrieval.graph_traversal import graph_traversal_retriever
from app.retrieval.hybrid_ranker import hybrid_ranker
from app.dependencies import semantic_store

from app.schemas import (
    PodStatusPayload,
    InvestigationTrigger,
    EvidenceTrigger,
    GraphRAGSearchPayload,
    IncidentCreate,
    IncidentUpdate,
    CommentCreate,
    SettingsPayload,
    LogEntryPayload,
)
from app.routers.telemetry import router as telemetry_router
from app.routers.webhooks import router as webhooks_router
from app.routers.benchmark import router as benchmark_router
from app.helpers import (
    build_relevant_evidence,
    build_retrieval_context_for_investigation,
    build_investigation_analysis,
    format_hybrid_result,
)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """FastAPI application lifespan context manager for startup and shutdown."""
    neo4j_client.connect()
    qdrant_client.ensure_collections()
    redis_client.connect()
    yield
    qdrant_client.close()
    neo4j_client.close()


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


@app.get("/health")
def health_check():
    """Verify service and database connection health status."""
    try:
        neo4j_client.execute_query("RETURN 1")
        return {"status": "healthy", "neo4j": "connected"}
    except NEO4J_CONNECTION_ERRORS as e:
        return {"status": "unhealthy", "error": str(e)}


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
        redis_client.clear_cache()
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
        redis_client.clear_cache()
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
        redis_client.clear_cache()
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
            timeout=12,
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
                }
    except Exception:  # pylint: disable=broad-exception-caught
        pass

    if not analysis:
        analysis = build_investigation_analysis(
            pod_name=pod["name"],
            pod_status=pod["status"],
            error_msgs=error_msgs,
        )
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

    gcp_res = {"root_cause": 0.80, "recommendation": 0.75}
    claim_scoring = {"unsupported_claim_rate": 0.0, "claim_count": 0, "claims": []}
    try:
        gcp_res = GraphConfidencePropagator().run_propagation(pod["name"])
    except Exception:  # pylint: disable=broad-exception-caught
        pass

    try:
        claim_scoring = GraphProvenanceClaimScorer().score_claims(
            analysis, graphrag_search
        )
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
        investigations = []
        if anomalous_pods:
            for pod in anomalous_pods:
                investigations.append(
                    _investigate_pod(
                        pod,
                        payload.namespace,
                        llm_provider=payload.llm_provider,
                        llm_api_key=payload.llm_api_key,
                        llm_model=payload.llm_model,
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
        claim_scoring = GraphProvenanceClaimScorer().score_claims(
            analysis, graphrag_search
        )

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


def _process_graph_search_record(
    record: dict[str, Any],
    query: str,
    depth: int,
    start_time: int | None,
    end_time: int | None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Parse, link, and rank a raw Neo4j search result record."""
    label = record.get("labels")[0] if record.get("labels") else "Node"
    name = record.get("name") or record.get("title") or "unknown"
    status = record.get("status") or "Active"
    graph_hits = [
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
    ]

    evidence_chain = [{"type": "entity", "label": label, "name": name}]

    if label in {"Incident", "Pod"}:
        graph_context = graph_traversal_retriever.retrieve(
            record.get("id"),
            depth=depth,
            start_time=start_time,
            end_time=end_time,
            limit=20,
        )
        graph_hits.extend(graph_context)
        related = [
            {
                "rel": " -> ".join(item["relationships"]),
                "related_name": item["name"],
                "related_labels": item["labels"],
                "hop_distance": item["hop_distance"],
                "path": item["path"],
                "properties": item["properties"],
            }
            for item in graph_context
        ]
    else:
        related = neo4j_client.execute_query(
            """
            MATCH (n)-[r]-(m)
            WHERE elementId(n) = $node_id
            RETURN type(r) as rel,
                   coalesce(m.name, m.title, m.status, m.id) as related_name,
                   labels(m) as related_labels
            LIMIT 6
            """,
            {"node_id": record.get("id")},
        )

    context = []
    for edge in related:
        evidence_chain.append(
            {
                "type": "relation",
                "label": edge.get("rel") or "RELATED_TO",
                "name": edge.get("related_name") or "unknown",
                "hop_distance": edge.get("hop_distance", 1),
            }
        )
        context.append(
            {
                "name": edge.get("related_name") or "unknown",
                "type": str((edge.get("related_labels") or ["Node"])[0]).lower(),
                "relationship": edge.get("rel") or "RELATED_TO",
                "hop_distance": edge.get("hop_distance", 1),
                "path": edge.get("path", []),
            }
        )

    if not context:
        context.append(
            {
                "name": "No adjacent graph nodes",
                "type": "graph",
                "relationship": "none",
            }
        )

    score = 0.6
    if query.lower() in name.lower():
        score += 0.2
    if status and query.lower() in status.lower():
        score += 0.1
    if label.lower() in {"incident", "pod", "service"}:
        score += 0.05

    return {
        "id": record.get("id"),
        "label": label,
        "type": label.lower(),
        "name": name,
        "status": status,
        "evidence_chain": evidence_chain,
        "context": context[:3],
        "related": related,
        "score": round(min(0.99, score + min(0.15, len(context) * 0.03)), 2),
        "sources": ["graph"],
        "detail": (
            f"Matched the current graph context using the term "
            f"'{query}' and expanded nearby nodes for retrieval."
        ),
    }, graph_hits


def _build_search_payload(
    query: str,
    search_method: str,
    payload: GraphRAGSearchPayload,
    data: dict,
) -> dict:
    """Construct search result payload based on chosen method."""
    if search_method == "keyword":
        return {
            "status": "success",
            "query": query,
            "method": search_method,
            "retrieval": {
                "depth": payload.depth,
                "start_time": payload.start_time,
                "end_time": payload.end_time,
                "ranking_formula": "keyword-only",
            },
            "results": data["results"],
        }
    if search_method == "vector":
        return {
            "status": "success",
            "query": query,
            "method": search_method,
            "retrieval": {
                "depth": payload.depth,
                "start_time": payload.start_time,
                "end_time": payload.end_time,
                "ranking_formula": "vector-only",
            },
            "results": data["semantic_results"],
        }

    ref_time = payload.end_time or int(time.time())
    ranked = hybrid_ranker.rank(
        data["semantic_hits"],
        data["graph_hits"],
        reference_time=ref_time,
        limit=10,
    )
    hybrid_items = [format_hybrid_result(item) for item in ranked]
    if not hybrid_items:
        hybrid_items = data["semantic_results"] + hybrid_items
        hybrid_items.sort(key=lambda item: item.get("score", 0.0), reverse=True)

    return {
        "status": "success",
        "query": query,
        "method": search_method,
        "retrieval": {
            "depth": payload.depth,
            "start_time": payload.start_time,
            "end_time": payload.end_time,
            "ranking_formula": hybrid_ranker.FORMULA,
        },
        "results": hybrid_items,
    }


@app.post("/api/v1/graphrag/search")
def graphrag_search(payload: GraphRAGSearchPayload, method: str | None = None):
    """Search graphrag context by keyword, semantic vector, or hybrid ranking."""
    try:
        query = payload.query.strip()
        if not query:
            raise HTTPException(status_code=400, detail="Query cannot be empty")

        search_method = (method or payload.method or "hybrid").strip().lower()
        if search_method not in {"keyword", "vector", "hybrid"}:
            raise HTTPException(
                status_code=400,
                detail="method must be one of: keyword, vector, hybrid",
            )

        # Check cache
        cache_key = (
            f"graphrag:search:{query}:{search_method}:{payload.depth}:"
            f"{payload.start_time}:{payload.end_time}"
        )
        if redis_client.enabled:
            cached_res = redis_client.get(cache_key)
            if cached_res:
                return cached_res

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
            ORDER BY CASE WHEN n.status IN [
                'CrashLoopBackOff', 'ERROR', 'Critical'
            ] THEN 1 ELSE 2 END, n.name
            LIMIT 5
            """,
            {"query": query},
        )

        semantic_hits = []
        if search_method in {"vector", "hybrid"}:
            semantic_hits = semantic_store.search(query, limit=5)

        results = []
        graph_hits = []
        for record in raw_results:
            res_and_hts = _process_graph_search_record(
                record,
                query,
                payload.depth,
                payload.start_time,
                payload.end_time,
            )
            results.append(res_and_hts[0])
            graph_hits.extend(res_and_hts[1])

        semantic_results = [
            {
                "id": hit["id"],
                "label": hit["metadata"].get("label", "Node"),
                "type": str(hit["metadata"].get("label", "Node")).lower(),
                "name": hit["metadata"].get("name", hit["id"]),
                "status": hit["metadata"].get("status", "Active"),
                "evidence_chain": [
                    {
                        "type": "semantic",
                        "label": "Embedding",
                        "name": hit["text"],
                    }
                ],
                "context": [
                    {
                        "name": "Semantic text match",
                        "type": "semantic",
                        "relationship": "matched_text",
                    }
                ],
                "related": [],
                "score": round(hit["score"], 3),
                "sources": ["vector"],
                "detail": hit["text"],
            }
            for hit in semantic_hits
        ]

        res_payload = _build_search_payload(
            query,
            search_method,
            payload,
            {
                "results": results,
                "semantic_results": semantic_results,
                "semantic_hits": semantic_hits,
                "graph_hits": graph_hits,
            },
        )

        if redis_client.enabled:
            redis_client.set(cache_key, res_payload, ex=300)
        return res_payload
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


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
        redis_client.clear_cache()
        return {"status": "success", "message": "Graph cleared"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/api/v1/incidents")
def get_incidents():
    """Retrieve all incident records from Neo4j, sorted by timestamp descending."""
    try:
        query = """
        MATCH (i:Incident)
        OPTIONAL MATCH (p:Pod)-[:AFFECTED_BY]->(i)
        RETURN i.id as id,
               i.title as title,
               i.severity as severity,
               i.status as status,
               i.description as cause,
               i.recommendation as remediation,
               i.timestamp as timestamp,
               i.assigned as assigned,
               i.error_logs as error_logs,
               p.name as pod_name
        ORDER BY i.timestamp DESC
        """
        records = neo4j_client.execute_query(query)
        incidents = []
        for r in records:
            incidents.append(
                {
                    "id": r["id"],
                    "title": r["title"],
                    "severity": r["severity"],
                    "status": r["status"] or "Active",
                    "cause": r["cause"] or "",
                    "remediation": r["remediation"] or "",
                    "timestamp": (
                        int(r["timestamp"]) if r["timestamp"] else int(time.time())
                    ),
                    "assigned": r["assigned"] or "Unassigned",
                    "error_logs": r["error_logs"] or [],
                    "pod_name": r["pod_name"] or "",
                }
            )
        return {"status": "success", "incidents": incidents}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/api/v1/incidents")
def create_incident(payload: IncidentCreate):
    """Create a new manual incident record in Neo4j."""
    try:
        incident_id = f"incident-{int(time.time() * 1000)}-{uuid.uuid4().hex[:5]}"
        query = """
        CREATE (i:Incident {
            id: $id,
            title: $title,
            severity: $severity,
            status: $status,
            description: $cause,
            recommendation: $remediation,
            timestamp: $timestamp,
            assigned: $assigned,
            error_logs: $error_logs
        })
        RETURN i.id as id
        """
        neo4j_client.execute_query(
            query,
            {
                "id": incident_id,
                "title": payload.title,
                "severity": payload.severity,
                "status": payload.status,
                "cause": payload.cause,
                "remediation": payload.remediation,
                "timestamp": int(time.time()),
                "assigned": payload.assigned,
                "error_logs": payload.error_logs,
            },
        )
        return {"status": "success", "id": incident_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.patch("/api/v1/incidents/{incident_id}")
def update_incident(incident_id: str, payload: IncidentUpdate):
    """Update status and/or assignee of an incident, adding an audit comment."""
    try:
        check_query = """
        MATCH (i:Incident {id: $id})
        RETURN i.status as status, i.assigned as assigned
        """
        records = neo4j_client.execute_query(check_query, {"id": incident_id})
        if not records:
            raise HTTPException(status_code=404, detail="Incident not found")

        current = records[0]
        old_status = current.get("status") or "Active"
        old_assigned = current.get("assigned") or "Unassigned"

        updates = []
        params = {"id": incident_id}
        if payload.status is not None:
            updates.append("i.status = $status")
            params["status"] = payload.status
        if payload.assigned is not None:
            updates.append("i.assigned = $assigned")
            params["assigned"] = payload.assigned

        if updates:
            update_query = f"""
            MATCH (i:Incident {{id: $id}})
            SET {", ".join(updates)}
            RETURN i.id as id
            """
            neo4j_client.execute_query(update_query, params)

        if payload.status is not None and payload.status != old_status:
            comment_text = (
                f"Status updated from **{old_status}** to **{payload.status}**."
            )
            _add_system_comment(incident_id, comment_text)

        if payload.assigned is not None and payload.assigned != old_assigned:
            comment_text = (
                f"Ownership assigned from **{old_assigned}** to "
                f"**{payload.assigned}**."
            )
            _add_system_comment(incident_id, comment_text)

        return {"status": "success", "id": incident_id}
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/api/v1/incidents/{incident_id}/comments")
def get_incident_comments(incident_id: str):
    """Retrieve comments for a specific incident, ordered by timestamp ascending."""
    try:
        query = """
        MATCH (i:Incident {id: $id})
        OPTIONAL MATCH (i)-[:HAS_COMMENT]->(c:Comment)
        RETURN c.author as author, c.text as text, c.timestamp as timestamp
        ORDER BY c.timestamp ASC
        """
        records = neo4j_client.execute_query(query, {"id": incident_id})
        comments = []
        for r in records:
            if r.get("text"):
                comments.append(
                    {
                        "author": r["author"] or "Unknown",
                        "text": r["text"],
                        "timestamp": (
                            int(r["timestamp"])
                            if r["timestamp"]
                            else int(time.time() * 1000)
                        ),
                    }
                )
        return {"status": "success", "comments": comments}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/api/v1/incidents/{incident_id}/comments")
def add_incident_comment(incident_id: str, payload: CommentCreate):
    """Add a new comment or triage note to an incident."""
    try:
        check_query = "MATCH (i:Incident {id: $id}) RETURN i.id as id"
        if not neo4j_client.execute_query(check_query, {"id": incident_id}):
            raise HTTPException(status_code=404, detail="Incident not found")

        comment_query = """
        MATCH (i:Incident {id: $id})
        CREATE (i)-[:HAS_COMMENT]->(c:Comment {
            author: $author,
            text: $text,
            timestamp: $timestamp
        })
        RETURN c.timestamp as timestamp
        """
        neo4j_client.execute_query(
            comment_query,
            {
                "id": incident_id,
                "author": payload.author,
                "text": payload.text,
                "timestamp": int(time.time() * 1000),
            },
        )
        return {"status": "success"}
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


def _add_system_comment(incident_id: str, text: str):
    """Helper to insert a system-generated audit log comment."""
    comment_query = """
    MATCH (i:Incident {id: $id})
    CREATE (i)-[:HAS_COMMENT]->(c:Comment {
        author: "System (Triage Engine)",
        text: $text,
        timestamp: $timestamp
    })
    """
    neo4j_client.execute_query(
        comment_query,
        {
            "id": incident_id,
            "text": text,
            "timestamp": int(time.time() * 1000),
        },
    )


@app.get("/api/v1/settings")
def get_settings():
    """Retrieve LLM settings from Neo4j."""
    try:
        query = """
        MATCH (s:Settings {id: "llm_settings"})
        RETURN s.provider as provider, s.api_key as api_key, s.model as model
        LIMIT 1
        """
        records = neo4j_client.execute_query(query)
        if records:
            return {
                "status": "success",
                "settings": {
                    "provider": records[0]["provider"] or "",
                    "api_key": records[0]["api_key"] or "",
                    "model": records[0]["model"] or "",
                },
            }
        return {"status": "success", "settings": {}}
    except (RuntimeError, ValueError, KeyError, TypeError, AttributeError) as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/api/v1/settings")
def save_settings(payload: SettingsPayload):
    """Save LLM settings to Neo4j."""
    try:
        query = """
        MERGE (s:Settings {id: "llm_settings"})
        SET s.provider = $provider,
            s.api_key = $api_key,
            s.model = $model
        RETURN s.id as id
        """
        neo4j_client.execute_query(
            query,
            {
                "provider": payload.provider,
                "api_key": payload.api_key,
                "model": payload.model,
            },
        )
        return {"status": "success"}
    except (RuntimeError, ValueError, KeyError, TypeError, AttributeError) as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.delete("/api/v1/settings")
def clear_settings():
    """Clear LLM settings from Neo4j."""
    try:
        query = """
        MATCH (s:Settings {id: "llm_settings"})
        DETACH DELETE s
        """
        neo4j_client.execute_query(query)
        return {"status": "success"}
    except (RuntimeError, ValueError, KeyError, TypeError, AttributeError) as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/api/v1/logs")
def get_log_history():
    """Retrieve all stored live logs from Neo4j."""
    try:
        query = """
        MATCH (l:LiveLog)
        RETURN l.timestamp as timestamp,
               l.source as source,
               l.level as level,
               l.message as message,
               l.created_at as created_at
        ORDER BY l.created_at ASC
        """
        records = neo4j_client.execute_query(query)
        logs = [
            {
                "timestamp": r["timestamp"] or "",
                "source": r["source"] or "",
                "level": r["level"] or "",
                "message": r["message"] or "",
            }
            for r in records
        ]
        return {"status": "success", "logs": logs}
    except (RuntimeError, ValueError, KeyError, TypeError, AttributeError) as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/api/v1/logs")
def add_log_entry(payload: LogEntryPayload):
    """Save a live log entry to Neo4j."""
    try:
        query = """
        CREATE (l:LiveLog {
            timestamp: $timestamp,
            source: $source,
            level: $level,
            message: $message,
            created_at: timestamp()
        })
        WITH l
        MATCH (old:LiveLog)
        WITH count(old) as cnt, old
        ORDER BY old.created_at ASC
        LIMIT CASE WHEN cnt > 5000 THEN cnt - 5000 ELSE 0 END
        DETACH DELETE old
        """
        neo4j_client.execute_query(
            query,
            {
                "timestamp": payload.timestamp,
                "source": payload.source,
                "level": payload.level,
                "message": payload.message,
            },
        )
        return {"status": "success"}
    except (RuntimeError, ValueError, KeyError, TypeError, AttributeError) as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.delete("/api/v1/logs")
def clear_log_history():
    """Clear all live logs from Neo4j."""
    try:
        query = """
        MATCH (l:LiveLog)
        DETACH DELETE l
        """
        neo4j_client.execute_query(query)
        return {"status": "success"}
    except (RuntimeError, ValueError, KeyError, TypeError, AttributeError) as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
