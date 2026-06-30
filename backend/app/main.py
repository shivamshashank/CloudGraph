from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from app.database.neo4j_client import neo4j_client
from app.adapters.prometheus import ingest_prometheus_metric
from app.adapters.loki import ingest_loki_log
from app.adapters.tempo import ingest_tempo_trace
from app.adapters.webhooks import ingest_git_commit, ingest_argocd_deployment
from app.adapters.graph_constructor import run_entity_linking, build_service_dependency_map, record_state_history

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    neo4j_client.connect()
    yield
    # Shutdown
    neo4j_client.close()

app = FastAPI(title="CloudGraph Ingestion Engine", version="1.0.0", lifespan=lifespan)

@app.get("/health")
def health_check():
    try:
        # Check connection status
        neo4j_client.execute_query("RETURN 1")
        return {"status": "healthy", "neo4j": "connected"}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}

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

class TracePayload(BaseModel):
    pod_id: str
    pod_name: str
    span_id: str
    trace_id: str
    parent_span_id: Optional[str] = ""
    service_name: str
    duration: float
    timestamp: int
    status: str

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
            payload.pod_id, payload.pod_name, payload.metric_name,
            payload.value, payload.timestamp, payload.labels
        )
        return {"status": "success", "metric_id": result[0]["metric_id"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/telemetry/logs")
def post_log(payload: LogPayload):
    try:
        result = ingest_loki_log(
            payload.pod_id, payload.pod_name, payload.message,
            payload.level, payload.timestamp, payload.container_name
        )
        return {"status": "success", "log_id": result[0]["log_id"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/telemetry/traces")
def post_trace(payload: TracePayload):
    try:
        result = ingest_tempo_trace(
            payload.pod_id, payload.pod_name, payload.span_id,
            payload.trace_id, payload.parent_span_id, payload.service_name,
            payload.duration, payload.timestamp, payload.status
        )
        return {"status": "success", "span_id": result[0]["span_id"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/webhook/git")
def post_git_webhook(payload: GitCommitPayload):
    try:
        result = ingest_git_commit(
            payload.sha, payload.author, payload.message,
            payload.timestamp, payload.changed_files
        )
        return {"status": "success", "sha": result[0]["sha"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/webhook/argocd")
def post_argocd_webhook(payload: ArgoCDDeploymentPayload):
    try:
        result = ingest_argocd_deployment(
            payload.app_name, payload.namespace, payload.status,
            payload.revision, payload.timestamp
        )
        return {"status": "success", "deployment": result[0]["deployment_name"] if result else None}
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
            "relationships_created": dependencies_created
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
