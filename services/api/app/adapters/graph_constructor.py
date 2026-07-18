"""Adapter for constructing graphs and linking entities in Neo4j."""

from app.database.neo4j_client import neo4j_client


def run_entity_linking():
    """
    Performs dynamic graph linking:
    1. Links Pods to Nodes based on nodeName attributes.
    2. Links Pods to Deployments and Services based on name prefix conventions.
    """
    # Link Pods to Nodes
    link_pods_to_nodes_query = """
    MATCH (p:Pod), (n:Node)
    WHERE p.nodeName = n.name
    MERGE (p)-[:RUNS_ON]->(n)
    RETURN count(p) as linked_count
    """

    # Link Pods to Services
    link_pods_to_services_query = """
    MATCH (p:Pod), (s:Service)
    WHERE p.name STARTS WITH s.name
    MERGE (p)-[:BELONGS_TO]->(s)
    RETURN count(p) as linked_count
    """

    # Link Deployments to Pods
    link_deployments_to_pods_query = """
    MATCH (d:Deployment), (p:Pod)
    WHERE p.name STARTS WITH d.name
    MERGE (d)-[:MANAGES]->(p)
    RETURN count(d) as linked_count
    """

    node_links = neo4j_client.execute_query(link_pods_to_nodes_query)
    service_links = neo4j_client.execute_query(link_pods_to_services_query)
    deploy_links = neo4j_client.execute_query(link_deployments_to_pods_query)

    return {
        "pods_to_nodes": node_links[0]["linked_count"] if node_links else 0,
        "pods_to_services": service_links[0]["linked_count"] if service_links else 0,
        "deployments_to_pods": deploy_links[0]["linked_count"] if deploy_links else 0,
    }


def build_service_dependency_map():
    """
    Builds a lightweight service dependency map from the currently discovered
    Kubernetes service, pod, and trace span call relationships.
    """
    query = """
    MATCH (s1:Service)<-[:BELONGS_TO]-(p1:Pod)-[:HAS_TRACE]->(t1:Trace)
    MATCH (t2:Trace)<-[:HAS_TRACE]-(p2:Pod)-[:BELONGS_TO]->(s2:Service)
    WHERE t2.parentSpanId = t1.spanId AND s1 <> s2
    MERGE (s1)-[r:CALLS]->(s2)
    RETURN count(r) as relationships_created
    """
    result = neo4j_client.execute_query(query)
    return result[0]["relationships_created"] if result else 0


def record_state_history(pod_id: str, new_status: str, timestamp: int):
    """
    Appends a state history change record to track the timeline of
    Kubernetes pod state transitions.
    """
    query = """
    MATCH (p:Pod {id: $pod_id})
    CREATE (h:StateChange {
        id: apoc.create.uuid(),
        timestamp: $timestamp,
        oldStatus: COALESCE(p.status, "Unknown"),
        newStatus: $new_status
    })
    CREATE (p)-[:HAS_STATE_HISTORY]->(h)
    SET p.status = $new_status
    RETURN h.id as history_id
    """
    params = {"pod_id": pod_id, "new_status": new_status, "timestamp": int(timestamp)}
    result = neo4j_client.execute_query(query, params)
    return result[0]["history_id"] if result else None
