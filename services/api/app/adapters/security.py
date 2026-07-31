"""Adapter for ingesting runtime security events into Neo4j."""

from app.database.neo4j_client import neo4j_client


def ingest_security_event(payload: dict) -> list:
    """Persist Falco security events and link them to Pod, Node, and SA."""
    query = """
    MERGE (p:Pod {id: $pod_id})
    SET p.name = $pod_name

    MERGE (sa:ServiceAccount {name: $service_account})

    MERGE (se:SecurityEvent {id: $event_id})
    SET se.rule = $rule,
        se.priority = $priority,
        se.output = $output,
        se.timestamp = $timestamp,
        se.serviceAccount = $service_account

    MERGE (p)-[:HAS_SECURITY_EVENT]->(se)
    MERGE (sa)-[:HAS_SECURITY_EVENT]->(se)

    WITH p, se
    OPTIONAL MATCH (p)-[:RUNS_ON]->(n:Node)
    FOREACH (o IN CASE WHEN n IS NOT NULL THEN [n] ELSE [] END |
        MERGE (o)-[:HAS_SECURITY_EVENT]->(se)
    )

    RETURN se.id as event_id
    """
    params = {
        "event_id": payload["event_id"],
        "pod_id": payload["pod_id"],
        "pod_name": payload["pod_name"],
        "rule": payload["rule"],
        "priority": payload["priority"],
        "output": payload["output"],
        "timestamp": int(payload["timestamp"]),
        "service_account": payload.get("service_account", "default"),
    }
    try:
        return neo4j_client.execute_query(query, params)
    except (RuntimeError, ConnectionError, OSError):
        return []
