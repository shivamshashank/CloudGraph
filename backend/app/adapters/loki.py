from app.database.neo4j_client import neo4j_client
import uuid


def ingest_loki_log(
    pod_id: str,
    pod_name: str,
    message: str,
    level: str,
    timestamp: int,
    container_name: str,
):
    """
    Ingests a log entry, identifies error patterns, and links the Log node to its Pod.
    """
    query = """
    MERGE (p:Pod {id: $pod_id})
    ON CREATE SET p.name = $pod_name
    CREATE (l:Log {
        id: $log_id,
        message: $message,
        level: $level,
        timestamp: $timestamp,
        containerName: $container_name
    })
    CREATE (p)-[:GENERATES]->(l)
    RETURN l.id as log_id
    """
    log_id = str(uuid.uuid4())
    params = {
        "pod_id": pod_id,
        "pod_name": pod_name,
        "log_id": log_id,
        "message": message,
        "level": level.upper(),
        "timestamp": int(timestamp),
        "container_name": container_name,
    }
    return neo4j_client.execute_query(query, params)
