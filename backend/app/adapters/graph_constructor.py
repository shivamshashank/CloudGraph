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
        "deployments_to_pods": deploy_links[0]["linked_count"] if deploy_links else 0
    }

def build_service_dependency_map():
    """
    Traverses the Trace span tree to automatically generate Service-to-Service CALLS edges.
    Calculates moving averages for call metrics (count, avg_duration).
    """
    query = """
    MATCH (parentTrace:Trace)-[:CALLS]->(childTrace:Trace)
    MATCH (parentService:Service {name: parentTrace.serviceName})
    MATCH (childService:Service {name: childTrace.serviceName})
    WHERE parentService <> childService
    MERGE (parentService)-[r:CALLS]->(childService)
    ON CREATE SET
        r.count = 1,
        r.avg_duration = childTrace.duration
    ON MATCH SET
        r.count = r.count + 1,
        r.avg_duration = (r.avg_duration * (r.count - 1) + childTrace.duration) / r.count
    RETURN count(r) as relationships_created
    """
    result = neo4j_client.execute_query(query)
    return result[0]["relationships_created"] if result else 0

def record_state_history(pod_id: str, new_status: str, timestamp: int):
    """
    Appends a state history change record to track the timeline of Kubernetes pod state transitions.
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
    params = {
        "pod_id": pod_id,
        "new_status": new_status,
        "timestamp": int(timestamp)
    }
    result = neo4j_client.execute_query(query, params)
    return result[0]["history_id"] if result else None
