"""Telemetry API endpoints."""

from fastapi import APIRouter, HTTPException
from app.schemas import (
    MetricPayload,
    LogPayload,
    TracePayload,
    SecurityEventPayload,
    ChaosExperimentPayload,
)
from app.adapters.graph_constructor import build_service_dependency_map
from app.adapters.prometheus import ingest_prometheus_metric
from app.adapters.loki import ingest_loki_log
from app.adapters.tempo import ingest_tempo_trace
from app.adapters.security import ingest_security_event
from app.adapters.chaos import ingest_chaos_experiment
from app.dependencies import semantic_store

router = APIRouter()


@router.post("/api/v1/telemetry/metrics")
def post_metric(payload: MetricPayload):
    """Ingest a Prometheus metric signal and register in semantic vector index."""
    try:
        result = ingest_prometheus_metric(
            payload.pod_id,
            payload.pod_name,
            payload.metric_name,
            payload.value,
            payload.timestamp,
            payload.labels,
        )
        metric_id = result[0]["metric_id"] if result else "metric-fallback"
        semantic_store.index_document(
            metric_id,
            (
                f"metric summary pod {payload.pod_name} metric {payload.metric_name} "
                f"value {payload.value} timestamp {payload.timestamp} "
                f"labels {payload.labels}"
            ),
            {
                "type": "metrics-summary",
                "label": "Metric",
                "name": payload.metric_name,
                "pod_name": payload.pod_name,
                "timestamp": payload.timestamp,
            },
        )
        return {"status": "success", "metric_id": metric_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/api/v1/telemetry/logs")
def post_log(payload: LogPayload):
    """Ingest a container log line and write into semantic search fallback."""
    try:
        result = ingest_loki_log(
            payload.pod_id,
            payload.pod_name,
            payload.message,
            payload.level,
            payload.timestamp,
            payload.container_name,
        )
        log_id = result[0]["log_id"] if result else "log-fallback"
        semantic_store.index_document(
            log_id,
            payload.message,
            {
                "type": "log",
                "label": "Log",
                "name": payload.pod_name,
                "pod_name": payload.pod_name,
                "level": payload.level.upper(),
                "container_name": payload.container_name,
                "timestamp": payload.timestamp,
            },
        )
        return {"status": "success", "log_id": log_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/api/v1/telemetry/traces")
def post_trace(payload: TracePayload):
    """Ingest a Tempo trace span and index it in the semantic search vector store."""
    try:
        result = ingest_tempo_trace(
            payload.pod_id,
            payload.pod_name,
            payload.span_id,
            payload.trace_id,
            payload.parent_span_id,
            payload.service_name,
            payload.duration,
            payload.timestamp,
            payload.status,
        )
        trace_id = result[0]["trace_id"] if result else "trace-fallback"
        semantic_store.index_document(
            trace_id,
            (
                f"Trace span {payload.span_id} from trace {payload.trace_id} "
                f"service {payload.service_name} duration {payload.duration}ms "
                f"status {payload.status}"
            ),
            {
                "type": "trace",
                "label": "Trace",
                "name": payload.service_name,
                "pod_name": payload.pod_name,
                "timestamp": payload.timestamp,
            },
        )
        relationships_created = 0
        try:
            relationships_created = build_service_dependency_map()
        except (RuntimeError, ValueError, KeyError, TypeError, AttributeError):
            relationships_created = 0

        return {
            "status": "success",
            "trace_id": trace_id,
            "relationships_created": relationships_created,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/api/v1/telemetry/security")
def post_security_event(payload: SecurityEventPayload):
    """Ingest Falco security event, save to Neo4j and index in Qdrant."""
    try:
        result = ingest_security_event(payload.model_dump())
        event_id = result[0]["event_id"] if result else "security-event-fallback"
        semantic_store.index_document(
            event_id,
            (
                f"Security Event rule {payload.rule} "
                f"priority {payload.priority} "
                f"output {payload.output}"
            ),
            {
                "type": "security-event",
                "label": "SecurityEvent",
                "name": payload.rule,
                "pod_name": payload.pod_name,
                "priority": payload.priority,
                "timestamp": payload.timestamp,
            },
        )
        return {"status": "success", "event_id": event_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/api/v1/telemetry/chaos")
def post_chaos_experiment(payload: ChaosExperimentPayload):
    """Ingest chaos experiment event, save to Neo4j and index in Qdrant."""
    try:
        result = ingest_chaos_experiment(payload.model_dump())
        experiment_id = (
            result[0]["experiment_id"] if result else "chaos-experiment-fallback"
        )
        semantic_store.index_document(
            experiment_id,
            (
                f"Chaos Experiment {payload.name} "
                f"action {payload.action} "
                f"status {payload.status} "
                f"target {payload.target_pod_name}"
            ),
            {
                "type": "chaos-experiment",
                "label": "ChaosExperiment",
                "name": payload.name,
                "pod_name": payload.target_pod_name,
                "action": payload.action,
                "status": payload.status,
                "timestamp": payload.timestamp,
            },
        )
        return {"status": "success", "experiment_id": experiment_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
