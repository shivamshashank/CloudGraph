"""Adapter for ingesting logs into Neo4j from Loki."""

import uuid

from app.adapters._common import get_arg
from app.database.neo4j_client import neo4j_client


def ingest_loki_log(*args, **kwargs):
    """
    Ingests a log entry, identifies error patterns, and links the Log node to its Pod.
    """

    pod_id = get_arg(args, kwargs, 0, "pod_id")
    pod_name = get_arg(args, kwargs, 1, "pod_name")
    message = get_arg(args, kwargs, 2, "message")
    level = get_arg(args, kwargs, 3, "level")
    timestamp = get_arg(args, kwargs, 4, "timestamp")
    container_name = get_arg(args, kwargs, 5, "container_name", "unknown")

    query = """
    MERGE (pod:Pod {id: $pod_id})
    ON CREATE SET pod.name = $pod_name
    CREATE (log:Log {
        id: $log_uuid,
        message: $msg,
        level: $lvl,
        timestamp: $time_val,
        containerName: $container
    })
    CREATE (pod)-[:GENERATES]->(log)
    RETURN log.id as log_id
    """
    log_id = str(uuid.uuid4())
    params = {
        "pod_id": pod_id,
        "pod_name": pod_name,
        "log_uuid": log_id,
        "msg": message,
        "lvl": level.upper() if level else "INFO",
        "time_val": int(timestamp) if timestamp else 0,
        "container": container_name,
    }
    return neo4j_client.execute_query(query, params)
