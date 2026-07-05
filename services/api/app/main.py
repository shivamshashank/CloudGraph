from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List
import uuid
import time
from app.database.neo4j_client import neo4j_client
from app.adapters.prometheus import ingest_prometheus_metric
from app.adapters.loki import ingest_loki_log
from app.adapters.webhooks import ingest_git_commit, ingest_argocd_deployment
from app.adapters.graph_constructor import (
    run_entity_linking,
    build_service_dependency_map,
    record_state_history,
)
from app.services.semantic_store import SemanticVectorStore


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    neo4j_client.connect()
    yield
    # Shutdown
    neo4j_client.close()


app = FastAPI(title="CloudGraph Ingestion Engine", version="1.0.0", lifespan=lifespan)
semantic_store = SemanticVectorStore()

# Configure CORS Middleware for UI interaction
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health_check():
    try:
        # Check connection status
        neo4j_client.execute_query("RETURN 1")
        return {"status": "healthy", "neo4j": "connected"}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}


@app.get("/ready")
def ready_check():
    return {"status": "ready"}


# -----------------------------------------------------------------------------
# Models & Schemas
# -----------------------------------------------------------------------------


class MetricPayload(BaseModel):
    pod_id: str
    pod_name: str
    metric_name: str
    value: float
    timestamp: int
    labels: dict


class LogPayload(BaseModel):
    pod_id: str
    pod_name: str
    message: str
    level: str
    timestamp: int
    container_name: str


class GitCommitPayload(BaseModel):
    sha: str
    author: str
    message: str
    timestamp: int
    changed_files: List[str]


class ArgoCDDeploymentPayload(BaseModel):
    app_name: str
    namespace: str
    status: str
    revision: str
    timestamp: int


class PodStatusPayload(BaseModel):
    pod_id: str
    status: str
    timestamp: int


class InvestigationTrigger(BaseModel):
    namespace: str = "cloudgraph-system"


class EvidenceTrigger(BaseModel):
    pod_name: str
    namespace: str = "cloudgraph-system"


class GraphSearchPayload(BaseModel):
    query: str
    namespace: str = "cloudgraph-system"


class GraphRetrievePayload(BaseModel):
    query: str
    namespace: str = "cloudgraph-system"


class GraphRAGSearchPayload(BaseModel):
    query: str
    namespace: str = "cloudgraph-system"


# -----------------------------------------------------------------------------
# Endpoints
# -----------------------------------------------------------------------------


@app.post("/api/v1/telemetry/metrics")
def post_metric(payload: MetricPayload):
    try:
        result = ingest_prometheus_metric(
            payload.pod_id,
            payload.pod_name,
            payload.metric_name,
            payload.value,
            payload.timestamp,
            payload.labels,
        )
        return {"status": "success", "metric_id": result[0]["metric_id"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/telemetry/logs")
def post_log(payload: LogPayload):
    try:
        result = ingest_loki_log(
            payload.pod_id,
            payload.pod_name,
            payload.message,
            payload.level,
            payload.timestamp,
            payload.container_name,
        )
        return {"status": "success", "log_id": result[0]["log_id"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/webhook/git")
def post_git_webhook(payload: GitCommitPayload):
    try:
        result = ingest_git_commit(
            payload.sha,
            payload.author,
            payload.message,
            payload.timestamp,
            payload.changed_files,
        )
        return {"status": "success", "sha": result[0]["sha"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/webhook/argocd")
def post_argocd_webhook(payload: ArgoCDDeploymentPayload):
    try:
        result = ingest_argocd_deployment(
            payload.app_name,
            payload.namespace,
            payload.status,
            payload.revision,
            payload.timestamp,
        )
        return {
            "status": "success",
            "deployment": result[0]["deployment_name"] if result else None,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/graph/link")
def post_graph_link():
    try:
        linking_results = run_entity_linking()
        dependencies_created = build_service_dependency_map()
        return {
            "status": "success",
            "linking": linking_results,
            "relationships_created": dependencies_created,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/telemetry/pods/status")
def post_pod_status(payload: PodStatusPayload):
    try:
        history_id = record_state_history(
            payload.pod_id, payload.status, payload.timestamp
        )
        return {"status": "success", "history_id": history_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/graph/discover")
def trigger_k8s_discovery(namespace: str = "cloudgraph-system"):
    try:
        from app.adapters.k8s_discovery import discover_cluster_topology

        result = discover_cluster_topology(namespace=namespace)
        if result.get("status") == "success":
            discovered = result.get("discovered", {})
            semantic_store.index_document(
                "cluster-discovery",
                f"cluster discovery namespace {namespace} nodes {discovered.get('nodes')} pods {discovered.get('pods')} services {discovered.get('services')}",
                {"label": "Cluster", "name": namespace, "status": "Discovered"},
            )
        return result
    except Exception as e:
        import traceback

        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/graph/data")
def get_graph_data():
    try:
        query = """
        MATCH (n)
        WHERE n:Pod OR n:Node OR n:Service OR n:Deployment OR n:Commit OR n:Incident
        OPTIONAL MATCH (n)-[r]->(m)
        WHERE m IS NOT NULL AND (m:Pod OR m:Node OR m:Service OR m:Deployment OR m:Commit OR m:Incident)
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
        import traceback

        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


def _build_relevant_evidence(pod_name: str, namespace: str = "cloudgraph-system"):
    query = """
    MATCH (p:Pod {name: $pod_name})
    OPTIONAL MATCH (p)-[:BELONGS_TO]->(s:Service)
    OPTIONAL MATCH (p)-[:RUNS_ON]->(n:Node)
    OPTIONAL MATCH (p)<-[:MANAGES]-(d:Deployment)
    OPTIONAL MATCH (p)-[:GENERATES]->(l:Log)
    WHERE l.level IN ['ERROR', 'WARN', 'INFO']
    RETURN p.name as pod_name,
           s.name as service_name,
           d.name as deployment_name,
           n.name as node_name,
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
                "detail": "The pod belongs to this service and is part of the active dependency chain.",
            }
        )
    if row.get("deployment_name"):
        evidence.append(
            {
                "type": "deployment",
                "label": row["deployment_name"],
                "detail": "The deployment owning this pod is part of the workload history being analyzed.",
            }
        )
    if row.get("node_name"):
        evidence.append(
            {
                "type": "node",
                "label": row["node_name"],
                "detail": "This pod is scheduled onto the node shown by the current topology graph.",
            }
        )
    if row.get("log_messages"):
        evidence.append(
            {
                "type": "logs",
                "label": "Recent log signals",
                "detail": "Recent pod log lines were used as supporting evidence for the diagnosis.",
                "messages": row["log_messages"],
            }
        )

    if not evidence:
        evidence.append(
            {
                "type": "fallback",
                "label": "No graph evidence found",
                "detail": "The graph did not return additional context for this pod yet.",
            }
        )

    return {
        "status": "success",
        "pod_name": pod_name,
        "namespace": namespace,
        "evidence": evidence,
    }


def _build_investigation_analysis(
    pod_name: str, pod_status: str, error_msgs: List[str]
):
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
        cause = "The pod is unhealthy but the pattern is not specific enough for a single root cause."
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


@app.post("/api/v1/investigations/trigger")
def trigger_investigation(payload: InvestigationTrigger):
    try:
        from app.adapters.k8s_discovery import discover_cluster_topology

        discover_cluster_topology(namespace=payload.namespace)

        pod_query = """
        MATCH (p:Pod)
        WHERE NOT p.status IN ['Running', 'Succeeded']
        RETURN elementId(p) as id, p.name as name, p.status as status, p.nodeName as nodeName
        """
        anomalous_pods = neo4j_client.execute_query(pod_query)

        if not anomalous_pods:
            log_anomaly_query = """
            MATCH (p:Pod)-[:GENERATES]->(l:Log {level: 'ERROR'})
            RETURN DISTINCT elementId(p) as id, p.name as name, p.status as status, p.nodeName as nodeName
            LIMIT 5
            """
            anomalous_pods = neo4j_client.execute_query(log_anomaly_query)

        investigations = []

        if anomalous_pods:
            for pod in anomalous_pods:
                pod_id = pod["id"]
                pod_name = pod["name"]
                pod_status = pod["status"]

                error_query = """
                MATCH (p:Pod)-[:GENERATES]->(l:Log)
                WHERE elementId(p) = $pod_id AND l.level = 'ERROR'
                RETURN l.message as msg, l.timestamp as ts
                ORDER BY l.timestamp DESC LIMIT 3
                """
                errors = neo4j_client.execute_query(error_query, {"pod_id": pod_id})
                error_msgs = [e["msg"] for e in errors]

                analysis = _build_investigation_analysis(
                    pod_name=pod_name,
                    pod_status=pod_status,
                    error_msgs=error_msgs,
                )
                evidence_context = _build_relevant_evidence(
                    pod_name=pod_name, namespace=payload.namespace
                )
                title = analysis["title"]
                severity = analysis["severity"]
                cause = analysis["cause"]
                recommendation = analysis["recommendation"]

                incident_id = str(uuid.uuid4())
                create_incident_query = """
                CREATE (i:Incident {
                    id: $incident_id,
                    title: $title,
                    description: $cause,
                    status: "Open",
                    timestamp: $timestamp,
                    severity: $severity,
                    recommendation: $recommendation
                })
                WITH i
                MATCH (p:Pod) WHERE elementId(p) = $pod_id
                CREATE (p)-[:AFFECTED_BY]->(i)
                RETURN i.id as id
                """
                neo4j_client.execute_query(
                    create_incident_query,
                    {
                        "incident_id": incident_id,
                        "title": title,
                        "cause": cause,
                        "timestamp": int(time.time()),
                        "severity": severity,
                        "recommendation": recommendation,
                        "pod_id": pod_id,
                    },
                )

                # Vector store indexing
                semantic_store.index_document(
                    incident_id,
                    f"incident {title} {cause} {recommendation}",
                    {"label": "Incident", "name": title, "status": "Open"},
                )
                semantic_store.index_document(
                    pod_id,
                    f"pod {pod_name} status {pod_status} error logs {' '.join(error_msgs)}",
                    {"label": "Pod", "name": pod_name, "status": pod_status},
                )

                investigations.append(
                    {
                        "id": incident_id,
                        "title": title,
                        "pod_name": pod_name,
                        "status": "Investigated",
                        "severity": severity,
                        "cause": cause,
                        "remediation": recommendation,
                        "error_logs": error_msgs,
                        "summary": analysis["summary"],
                        "evidence": analysis["evidence"],
                        "relevant_evidence": evidence_context["evidence"],
                        "timestamp": int(time.time()),
                    }
                )
        else:
            investigations.append(
                {
                    "id": "healthy",
                    "title": "All cluster services healthy",
                    "status": "Healthy",
                    "severity": "NONE",
                    "cause": "No anomalies found in active pods or logs.",
                    "remediation": "No actions required.",
                    "error_logs": [],
                    "timestamp": int(time.time()),
                }
            )

        return {"status": "success", "results": investigations}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/investigations/evidence")
def get_relevant_evidence(payload: EvidenceTrigger):
    try:
        return _build_relevant_evidence(
            pod_name=payload.pod_name, namespace=payload.namespace
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/graphrag/search")
def graphrag_search(payload: GraphRAGSearchPayload):
    try:
        query = payload.query.strip()
        if not query:
            raise HTTPException(status_code=400, detail="Query cannot be empty")

        # 1. Neo4j search for matching nodes
        search_query = """
        MATCH (n)
        WHERE any(label in labels(n) WHERE label IN ['Pod','Service','Deployment','Incident','Node','Commit'])
          AND (
            toLower(coalesce(n.name, '')) CONTAINS toLower($query)
            OR toLower(coalesce(n.title, '')) CONTAINS toLower($query)
            OR toLower(coalesce(n.status, '')) CONTAINS toLower($query)
            OR toLower(coalesce(n.message, '')) CONTAINS toLower($query)
          )
        WITH n
        RETURN labels(n) as labels, n.name as name, n.status as status, n.title as title, elementId(n) as id
        ORDER BY CASE WHEN n.status IN ['CrashLoopBackOff', 'ERROR', 'Critical'] THEN 1 ELSE 2 END, n.name
        LIMIT 5
        """
        raw_results = neo4j_client.execute_query(search_query, {"query": query})

        # 2. Semantic store search
        semantic_hits = semantic_store.search(query, limit=5)
        semantic_context = []
        for hit in semantic_hits:
            semantic_context.append(
                {
                    "type": "semantic",
                    "label": hit["metadata"].get("label", "Node"),
                    "name": hit["metadata"].get("name", hit["id"]),
                    "score": round(hit["score"], 3),
                    "text": hit["text"],
                }
            )

        results = []
        for record in raw_results:
            node_labels = record.get("labels") or []
            label = node_labels[0] if node_labels else "Node"
            name = record.get("name") or record.get("title") or "unknown"
            status = record.get("status") or "Active"

            # Build evidence chain
            evidence_chain = [
                {
                    "type": "entity",
                    "label": label,
                    "name": name,
                }
            ]

            related_query = """
            MATCH (n)-[r]-(m)
            WHERE elementId(n) = $node_id
            RETURN type(r) as rel, coalesce(m.name, m.title, m.status, m.id) as related_name, labels(m) as related_labels
            LIMIT 6
            """
            related = neo4j_client.execute_query(
                related_query, {"node_id": record.get("id")}
            )

            context = []
            for edge in related:
                related_name = edge.get("related_name") or "unknown"
                related_label = (edge.get("related_labels") or ["Node"])[0]
                rel_type = edge.get("rel") or "RELATED_TO"

                # Append to evidence chain
                evidence_chain.append(
                    {
                        "type": "relation",
                        "label": rel_type,
                        "name": related_name,
                    }
                )
                # Append to context
                context.append(
                    {
                        "name": related_name,
                        "type": related_label.lower(),
                        "relationship": rel_type,
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

            # Calculate heuristic score
            score = 0.6
            if query.lower() in name.lower():
                score += 0.2
            if status and query.lower() in status.lower():
                score += 0.1
            if label.lower() in {"incident", "pod", "service"}:
                score += 0.05
            final_score = round(min(0.99, score + min(0.15, len(context) * 0.03)), 2)

            results.append(
                {
                    "id": record.get("id"),
                    "label": label,
                    "type": label.lower(),
                    "name": name,
                    "status": status,
                    "evidence_chain": evidence_chain,
                    "context": context[:3],
                    "related": related,
                    "score": final_score,
                    "detail": f"Matched the current graph context using the term '{query}' and expanded nearby nodes for retrieval.",
                }
            )

        # Merge semantic hits into results
        if semantic_context:
            semantic_results = []
            for hit in semantic_hits:
                lbl = hit["metadata"].get("label", "Node")
                nm = hit["metadata"].get("name", hit["id"])
                semantic_results.append(
                    {
                        "id": hit["id"],
                        "label": lbl,
                        "type": lbl.lower(),
                        "name": nm,
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
                        "detail": hit["text"],
                    }
                )
            results = semantic_results + results

        # Sort by score descending
        results.sort(key=lambda item: item.get("score", 0.0), reverse=True)

        return {"status": "success", "query": query, "results": results}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/graphrag/retrieve")
def graphrag_retrieve(payload: GraphRAGSearchPayload):
    try:
        query = payload.query.strip()
        if not query:
            raise HTTPException(status_code=400, detail="Query cannot be empty")

        # Reuse graphrag_search logic
        search_res = graphrag_search(payload)
        results = search_res["results"]

        summary = (
            f"Retrieved {len(results)} semantically ranked context entries for '{query}'."
            if results
            else f"No graph context found for '{query}'."
        )
        return {
            "status": "success",
            "query": query,
            "summary": summary,
            "results": results,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/demo/reset")
def reset_demo():
    try:
        neo4j_client.execute_query("MATCH (n) DETACH DELETE n")
        return {"status": "success", "message": "Graph cleared"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
