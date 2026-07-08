"""Adapter for ingesting metrics into Neo4j from Prometheus."""

import uuid

from app.adapters._common import get_arg
from app.database.neo4j_client import neo4j_client


def ingest_prometheus_metric(*args, **kwargs):
    """
    Ingests a timeseries metric point and links it to its generating Pod in Neo4j.
    """

    pod_id = get_arg(args, kwargs, 0, "pod_id")
    pod_name = get_arg(args, kwargs, 1, "pod_name")
    metric_name = get_arg(args, kwargs, 2, "metric_name")
    value = get_arg(args, kwargs, 3, "value")
    timestamp = get_arg(args, kwargs, 4, "timestamp")
    labels = get_arg(args, kwargs, 5, "labels", {})

    query = """
    MERGE (p:Pod {id: $pod_id})
    ON CREATE SET p.name = $pod_name
    CREATE (m:Metric {
        id: $metric_id,
        name: $metric_name,
        value: $value,
        timestamp: $timestamp,
        labels: $labels
    })
    CREATE (p)-[:GENERATES]->(m)
    RETURN m.id as metric_id
    """
    # Generate unique metric point hash
    metric_id = str(uuid.uuid4())
    params = {
        "pod_id": pod_id,
        "pod_name": pod_name,
        "metric_id": metric_id,
        "metric_name": metric_name,
        "value": float(value) if value is not None else 0.0,
        "timestamp": int(timestamp) if timestamp else 0,
        "labels": str(labels),
    }
    return neo4j_client.execute_query(query, params)
