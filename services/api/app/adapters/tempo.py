"""Adapter for ingesting traces into Neo4j from Tempo."""

from app.database.neo4j_client import neo4j_client


def ingest_tempo_trace(*args, **kwargs):
    """Persist a trace span into Neo4j and link it to the pod that emitted it."""

    def _get_arg(index, name, default=None):
        if len(args) > index:
            return args[index]
        return kwargs.get(name, default)

    pod_id = _get_arg(0, "pod_id")
    pod_name = _get_arg(1, "pod_name")
    span_id = _get_arg(2, "span_id")
    trace_id = _get_arg(3, "trace_id")
    parent_span_id = _get_arg(4, "parent_span_id")
    service_name = _get_arg(5, "service_name")
    duration = _get_arg(6, "duration", 0.0)
    timestamp = _get_arg(7, "timestamp", 0)
    status = _get_arg(8, "status")

    query = """
    MERGE (p:Pod {id: $pod_id})
    MERGE (s:Service {name: $service_name})
    SET s.name = $service_name
    MERGE (t:Trace {id: $trace_id})
    SET t.spanId = $span_id,
        t.parentSpanId = $parent_span_id,
        t.serviceName = $service_name,
        t.durationMs = $duration,
        t.timestamp = $timestamp,
        t.status = $status,
        t.podName = $pod_name
    MERGE (p)-[:HAS_TRACE]->(t)
    MERGE (p)-[:BELONGS_TO]->(s)

    MERGE (ts:TraceSpan {id: $span_id})
    SET ts.traceId = $trace_id,
        ts.parentSpanId = $parent_span_id,
        ts.serviceName = $service_name,
        ts.durationMs = $duration,
        ts.timestamp = $timestamp,
        ts.status = $status,
        ts.podName = $pod_name
    MERGE (p)-[:HAS_SPAN]->(ts)

    WITH ts
    WHERE ts.parentSpanId IS NOT NULL AND ts.parentSpanId <> ""
    MERGE (parent:TraceSpan {id: ts.parentSpanId})
    MERGE (parent)-[:CALLS]->(ts)

    RETURN t.id as trace_id
    """
    params = {
        "pod_id": pod_id,
        "trace_id": trace_id,
        "span_id": span_id,
        "parent_span_id": parent_span_id,
        "service_name": service_name,
        "duration": float(duration) if duration is not None else 0.0,
        "timestamp": int(timestamp) if timestamp else 0,
        "status": status,
        "pod_name": pod_name,
    }
    try:
        return neo4j_client.execute_query(query, params)
    except (RuntimeError, ConnectionError, OSError):
        return []
