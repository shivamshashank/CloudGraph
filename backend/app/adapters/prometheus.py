from app.database.neo4j_client import neo4j_client
import uuid

def ingest_prometheus_metric(pod_id: str, pod_name: str, metric_name: str, value: float, timestamp: int, labels: dict):
    """
    Ingests a timeseries metric point and links it to its generating Pod in Neo4j.
    """
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
        "value": float(value),
        "timestamp": int(timestamp),
        "labels": str(labels)
    }
    return neo4j_client.execute_query(query, params)
