"""Adapter for ingesting chaos experiment trigger events into Neo4j."""

from app.database.neo4j_client import neo4j_client


# pylint: disable=too-many-arguments
def ingest_chaos_experiment(
    experiment_id: str,
    name: str,
    target_pod_name: str,
    action: str,
    status: str,
    timestamp: int,
) -> list:
    """Persist chaos experiment events and link them to target Pods."""
    query = """
    MERGE (ce:ChaosExperiment {id: $experiment_id})
    SET ce.name = $name,
        ce.action = $action,
        ce.status = $status,
        ce.timestamp = $timestamp

    WITH ce
    OPTIONAL MATCH (p:Pod {name: $target_pod_name})
    FOREACH (o IN CASE WHEN p IS NOT NULL THEN [p] ELSE [] END |
        MERGE (ce)-[:TARGETS]->(o)
    )

    RETURN ce.id as experiment_id
    """
    params = {
        "experiment_id": experiment_id,
        "name": name,
        "target_pod_name": target_pod_name,
        "action": action,
        "status": status,
        "timestamp": int(timestamp),
    }
    try:
        return neo4j_client.execute_query(query, params)
    except (RuntimeError, ConnectionError, OSError):
        return []
