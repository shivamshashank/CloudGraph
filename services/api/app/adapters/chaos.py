"""Adapter for ingesting chaos experiment trigger events into Neo4j."""

from app.database.neo4j_client import neo4j_client


def ingest_chaos_experiment(payload: dict) -> list:
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
        "experiment_id": payload["experiment_id"],
        "name": payload["name"],
        "target_pod_name": payload["target_pod_name"],
        "action": payload["action"],
        "status": payload["status"],
        "timestamp": int(payload["timestamp"]),
    }
    try:
        return neo4j_client.execute_query(query, params)
    except (RuntimeError, ConnectionError, OSError):
        return []
