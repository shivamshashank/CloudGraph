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


class PodStatusPayload(BaseModel):
    pod_id: str
    status: str
    timestamp: int


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


class InvestigationTrigger(BaseModel):
    namespace: str = "cloudgraph-system"


class GraphSearchPayload(BaseModel):
    query: str
    namespace: str = "cloudgraph-system"


class GraphRetrievePayload(BaseModel):
    query: str
    namespace: str = "cloudgraph-system"


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

                title = f"Incident detected on pod {pod_name}"
                severity = "HIGH"
                cause = "Unknown container error"
                recommendation = (
                    "Check container status and events via kubectl describe."
                )

                log_text = " ".join(error_msgs).lower()
                if (
                    "timeout" in log_text
                    or "refused" in log_text
                    or "dial tcp" in log_text
                ):
                    title = f"Network Timeout / Dependency failure on {pod_name}"
                    cause = "Failed to connect to downstream dependency (possible DB connection failure or network block)."
                    recommendation = "Verify connectivity to database and run network checks. Verify endpoints of services."
                    severity = "CRITICAL"
                elif "crashloop" in pod_status.lower() or "error" in pod_status.lower():
                    title = f"CrashLoopBackOff on {pod_name}"
                    cause = "Application crashed repeatedly. Recent logs show runtime exceptions."
                    recommendation = "Review application runtime environment variables and dependencies."
                    severity = "CRITICAL"
                elif (
                    "imagepull" in pod_status.lower()
                    or "errimagepull" in pod_status.lower()
                    or "image" in log_text
                ):
                    title = f"Image Pull failure on {pod_name}"
                    cause = "Kubernetes failed to download the container image. The image tag might be incorrect or registry authentication failed."
                    recommendation = "Check the deployment specification image field and verify registry authentication secrets."
                    severity = "HIGH"
                elif "oomkilled" in pod_status.lower() or "oom" in log_text:
                    title = f"Out Of Memory (OOMKilled) on {pod_name}"
                    cause = "Application exceeded container memory limits and was terminated by Linux kernel OOM Killer."
                    recommendation = "Increase the memory limit in the deployment manifest or profile application memory leaks."
                    severity = "CRITICAL"

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


@app.post("/api/v1/graphrag/search")
def graphrag_search(payload: GraphSearchPayload):
    try:
        query = payload.query.strip()
        if not query:
            raise HTTPException(status_code=400, detail="Query cannot be empty")

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
            evidence_chain = [
                {
                    "type": "entity",
                    "label": node_labels[0] if node_labels else "Node",
                    "name": record.get("name") or record.get("title") or "unknown",
                }
            ]

            related_query = """
            MATCH (n)-[r]-(m)
            WHERE elementId(n) = $node_id
            RETURN type(r) as rel, coalesce(m.name, m.title, m.status, m.id) as related_name, labels(m) as related_labels
            LIMIT 3
            """
            related = neo4j_client.execute_query(
                related_query, {"node_id": record.get("id")}
            )
            for edge in related:
                evidence_chain.append(
                    {
                        "type": "relation",
                        "label": edge.get("rel") or "RELATED_TO",
                        "name": edge.get("related_name") or "unknown",
                    }
                )

            results.append(
                {
                    "id": record.get("id"),
                    "label": node_labels[0] if node_labels else "Node",
                    "name": record.get("name") or record.get("title") or "unknown",
                    "status": record.get("status") or "Active",
                    "evidence_chain": evidence_chain,
                }
            )

        if semantic_context:
            results = [
                {
                    "id": hit["id"],
                    "label": hit["metadata"].get("label", "Node"),
                    "name": hit["metadata"].get("name", hit["id"]),
                    "status": hit["metadata"].get("status", "Active"),
                    "evidence_chain": [
                        {"type": "semantic", "label": "Embedding", "name": hit["text"]}
                    ],
                    "score": round(hit["score"], 3),
                }
                for hit in semantic_hits
            ] + results

        return {"status": "success", "query": query, "results": results}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/graphrag/retrieve")
def graphrag_retrieve(payload: GraphRetrievePayload):
    try:
        query = payload.query.strip()
        if not query:
            raise HTTPException(status_code=400, detail="Query cannot be empty")

        retrieve_query = """
        MATCH (n)
        WHERE any(label in labels(n) WHERE label IN ['Pod','Service','Deployment','Incident','Node','Commit'])
          AND (
            toLower(coalesce(n.title, '')) CONTAINS toLower($query)
            OR toLower(coalesce(n.name, '')) CONTAINS toLower($query)
            OR toLower(coalesce(n.status, '')) CONTAINS toLower($query)
          )
        WITH n
        RETURN labels(n) as labels, n.name as name, n.status as status, n.title as title, elementId(n) as id
        LIMIT 5
        """
        raw_results = neo4j_client.execute_query(retrieve_query, {"query": query})

        semantic_hits = semantic_store.search(query, limit=5)
        results = []
        for record in raw_results:
            node_labels = record.get("labels") or []
            related_query = """
            MATCH (n)-[r]-(m)
            WHERE elementId(n) = $node_id
            RETURN type(r) as rel, coalesce(m.name, m.title, m.status, m.id) as related_name, labels(m) as related_labels
            LIMIT 3
            """
            related = neo4j_client.execute_query(
                related_query, {"node_id": record.get("id")}
            )
            results.append(
                {
                    "id": record.get("id"),
                    "label": node_labels[0] if node_labels else "Node",
                    "name": record.get("name") or record.get("title") or "unknown",
                    "status": record.get("status") or "Active",
                    "related": related,
                }
            )

        if semantic_hits:
            results = [
                {
                    "id": hit["id"],
                    "label": hit["metadata"].get("label", "Node"),
                    "name": hit["metadata"].get("name", hit["id"]),
                    "status": hit["metadata"].get("status", "Active"),
                    "related": [],
                    "semantic_score": round(hit["score"], 3),
                }
                for hit in semantic_hits
            ] + results

        summary = (
            f"Retrieved {len(results)} semantically ranked context entries for '{query}'."
            if results
            else f"No graph context found for '{query}'."
        )
        return {"status": "success", "summary": summary, "results": results}
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
