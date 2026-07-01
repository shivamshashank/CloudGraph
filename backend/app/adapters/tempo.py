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
    """
    Ingests a distributed trace span and draws relationships between spans and services.
    """
    query = """
    MERGE (p:Pod {id: $pod_id})
    ON CREATE SET p.name = $pod_name

    // Create the Trace node
    MERGE (t:Trace {spanId: $span_id})
    SET t.traceId = $trace_id,
        t.parentSpanId = $parent_span_id,
        t.serviceName = $service_name,
        t.duration = $duration,
        t.timestamp = $timestamp,
        t.status = $status

    // Link Pod to Trace
    MERGE (p)-[:GENERATES]->(t)

    // Self-link calling spans if parent is already indexed
    WITH t
    WHERE t.parentSpanId IS NOT NULL AND t.parentSpanId <> ""
    MATCH (parent:Trace {spanId: t.parentSpanId})
    MERGE (parent)-[:CALLS]->(t)
    RETURN t.spanId as span_id
    """
    params = {
        "pod_id": pod_id,
        "pod_name": pod_name,
        "span_id": span_id,
        "trace_id": trace_id,
        "parent_span_id": parent_span_id,
        "service_name": service_name,
        "duration": float(duration),
        "timestamp": int(timestamp),
        "status": status,
    }
    return neo4j_client.execute_query(query, params)
