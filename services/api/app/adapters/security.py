"""Adapter for ingesting runtime security events into Neo4j."""

from app.database.neo4j_client import neo4j_client


# pylint: disable=too-many-arguments
def ingest_security_event(
    event_id: str,
    pod_id: str,
    pod_name: str,
    rule: str,
    priority: str,
    output: str,
    timestamp: int,
    service_account: str = "default",
) -> list:
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
        "event_id": event_id,
        "pod_id": pod_id,
        "pod_name": pod_name,
        "rule": rule,
        "priority": priority,
        "output": output,
        "timestamp": int(timestamp),
        "service_account": service_account,
    }
    try:
        return neo4j_client.execute_query(query, params)
    except (RuntimeError, ConnectionError, OSError):
        return []
