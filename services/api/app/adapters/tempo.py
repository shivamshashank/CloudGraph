from app.database.neo4j_client import neo4j_client


def ingest_tempo_trace(
    pod_id: str,
    pod_name: str,
    span_id: str,
    trace_id: str,
    parent_span_id: str,
    service_name: str,
    duration: float,
    timestamp: int,
    status: str,
):
    """Persist a trace span into Neo4j and link it to the pod that emitted it."""
    query = """
    MERGE (p:Pod {id: $pod_id})
    MERGE (t:Trace {id: $trace_id})
    SET t.spanId = $span_id,
        t.parentSpanId = $parent_span_id,
        t.serviceName = $service_name,
        t.durationMs = $duration,
        t.timestamp = $timestamp,
        t.status = $status,
        t.podName = $pod_name
    MERGE (p)-[:HAS_TRACE]->(t)
    RETURN t.id as trace_id
    """
    params = {
        "pod_id": pod_id,
        "trace_id": trace_id,
        "span_id": span_id,
        "parent_span_id": parent_span_id,
        "service_name": service_name,
        "duration": float(duration),
        "timestamp": int(timestamp),
        "status": status,
        "pod_name": pod_name,
    }
    try:
        return neo4j_client.execute_query(query, params)
    except Exception:
        return []
