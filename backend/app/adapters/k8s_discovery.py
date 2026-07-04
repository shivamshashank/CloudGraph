import uuid
import time
import random
import logging
from kubernetes import client, config
from app.database.neo4j_client import neo4j_client

logger = logging.getLogger(__name__)


def get_k8s_client():
    """Loads Kubernetes config and returns clients for CoreV1 and AppsV1 APIs."""
    try:
        config.load_incluster_config()
        logger.info("Loaded in-cluster Kubernetes config")
    except Exception as e:
        logger.warning(f"Failed to load in-cluster config: {e}")
        try:
            config.load_kube_config()
            logger.info("Loaded local kubeconfig")
        except Exception as ex:
            logger.warning(f"Could not load Kubernetes configuration: {ex}")
            return None
    return client.CoreV1Api(), client.AppsV1Api()


def discover_cluster_topology(namespace="cloudgraph-system"):
    """
    Scrapes Kubernetes cluster metadata, maps resources to Neo4j,
    ingests pod logs, simulates pod metrics, and triggers entity linking.
    """
    apis = get_k8s_client()
    if not apis:
        return {"status": "skipped", "reason": "Kubernetes client not initialized"}

    v1, apps_v1 = apis

    nodes_discovered = []
    deployments_discovered = []
    services_discovered = []
    pods_discovered = []

    # 1. Discover Nodes
    try:
        node_list = v1.list_node()
        for node in node_list.items:
            node_name = node.metadata.name
            status = (
                "Ready"
                if any(
                    c.type == "Ready" and c.status == "True"
                    for c in node.status.conditions
                )
                else "NotReady"
            )

            query = """
            MERGE (n:Node {name: $name})
            SET n.status = $status,
                n.cpu = $cpu,
                n.memory = $memory
            RETURN n.name as name
            """
            neo4j_client.execute_query(
                query,
                {
                    "name": node_name,
                    "status": status,
                    "cpu": node.status.allocatable.get("cpu", "unknown")
                    if node.status.allocatable
                    else "unknown",
                    "memory": node.status.allocatable.get("memory", "unknown")
                    if node.status.allocatable
                    else "unknown",
                },
            )
            nodes_discovered.append(node_name)
    except Exception as e:
        logger.error(f"Error discovering nodes: {e}")

    # 2. Discover Deployments
    try:
        if namespace:
            deploy_list = apps_v1.list_namespaced_deployment(namespace)
        else:
            deploy_list = apps_v1.list_deployment_for_all_namespaces()

        for deploy in deploy_list.items:
            deploy_name = deploy.metadata.name
            ns = deploy.metadata.namespace
            status = (
                "Available"
                if any(
                    c.type == "Available" and c.status == "True"
                    for c in deploy.status.conditions
                )
                else "Progressing"
            )

            query = """
            MERGE (d:Deployment {name: $name})
            SET d.namespace = $namespace,
                d.status = $status,
                d.replicas = $replicas
            RETURN d.name as name
            """
            neo4j_client.execute_query(
                query,
                {
                    "name": deploy_name,
                    "namespace": ns,
                    "status": status,
                    "replicas": deploy.spec.replicas if deploy.spec else 1,
                },
            )
            deployments_discovered.append(deploy_name)
    except Exception as e:
        logger.error(f"Error discovering deployments: {e}")

    # 3. Discover Services
    try:
        if namespace:
            service_list = v1.list_namespaced_service(namespace)
        else:
            service_list = v1.list_service_for_all_namespaces()

        for svc in service_list.items:
            svc_name = svc.metadata.name
            ns = svc.metadata.namespace
            cluster_ip = svc.spec.cluster_ip if svc.spec else "unknown"
            svc_type = svc.spec.type if svc.spec else "ClusterIP"

            query = """
            MERGE (s:Service {name: $name})
            SET s.namespace = $namespace,
                s.type = $type,
                s.cluster_ip = $cluster_ip
            RETURN s.name as name
            """
            neo4j_client.execute_query(
                query,
                {
                    "name": svc_name,
                    "namespace": ns,
                    "type": svc_type,
                    "cluster_ip": cluster_ip,
                },
            )
            services_discovered.append(svc_name)
    except Exception as e:
        logger.error(f"Error discovering services: {e}")

    # 4. Discover Pods and Ingest logs / metrics
    try:
        if namespace:
            pod_list = v1.list_namespaced_pod(namespace)
        else:
            pod_list = v1.list_pod_for_all_namespaces()

        for pod in pod_list.items:
            pod_name = pod.metadata.name
            pod_uid = pod.metadata.uid
            ns = pod.metadata.namespace
            node_name = pod.spec.node_name if pod.spec else "unknown"
            status = pod.status.phase if pod.status else "Unknown"
            pod_ip = pod.status.pod_ip if pod.status else "unknown"

            query = """
            MERGE (p:Pod {id: $pod_uid})
            SET p.name = $name,
                p.namespace = $namespace,
                p.nodeName = $node_name,
                p.status = $status,
                p.ip = $ip
            RETURN p.name as name
            """
            neo4j_client.execute_query(
                query,
                {
                    "pod_uid": pod_uid,
                    "name": pod_name,
                    "namespace": ns,
                    "node_name": node_name,
                    "status": status,
                    "ip": pod_ip or "unknown",
                },
            )
            pods_discovered.append(pod_name)

            # Fetch container logs
            try:
                if pod.spec and pod.spec.containers and status == "Running":
                    container_name = pod.spec.containers[0].name
                    logs = v1.read_namespaced_pod_log(
                        name=pod_name,
                        namespace=ns,
                        container=container_name,
                        tail_lines=30,
                    )
                    for line in logs.splitlines():
                        line_str = line.strip()
                        if line_str:
                            level = "INFO"
                            lower_line = line_str.lower()
                            if (
                                "error" in lower_line
                                or "fail" in lower_line
                                or "exception" in lower_line
                            ):
                                level = "ERROR"
                            elif "warn" in lower_line:
                                level = "WARN"

                            log_query = """
                            MERGE (p:Pod {id: $pod_uid})
                            CREATE (l:Log {
                                id: $log_id,
                                message: $message,
                                level: $level,
                                timestamp: $timestamp,
                                containerName: $container_name
                            })
                            CREATE (p)-[:GENERATES]->(l)
                            """
                            neo4j_client.execute_query(
                                log_query,
                                {
                                    "pod_uid": pod_uid,
                                    "log_id": str(uuid.uuid4()),
                                    "message": line_str,
                                    "level": level,
                                    "timestamp": int(time.time()),
                                    "container_name": container_name,
                                },
                            )
            except Exception as log_ex:
                logger.debug(f"Could not read logs for pod {pod_name}: {log_ex}")

            # Simulate metrics for the pod
            try:
                if status == "Running":
                    # CPU metric
                    cpu_query = """
                    MERGE (p:Pod {id: $pod_uid})
                    CREATE (m:Metric {
                        id: $metric_id,
                        name: "pod_cpu_utilization_ratio",
                        value: $value,
                        timestamp: $timestamp,
                        labels: $labels
                    })
                    CREATE (p)-[:GENERATES]->(m)
                    """
                    neo4j_client.execute_query(
                        cpu_query,
                        {
                            "pod_uid": pod_uid,
                            "metric_id": str(uuid.uuid4()),
                            "value": float(random.uniform(5.0, 65.0)),
                            "timestamp": int(time.time()),
                            "labels": str({"unit": "%"}),
                        },
                    )

                    # Memory metric
                    mem_query = """
                    MERGE (p:Pod {id: $pod_uid})
                    CREATE (m:Metric {
                        id: $metric_id,
                        name: "pod_memory_utilization_ratio",
                        value: $value,
                        timestamp: $timestamp,
                        labels: $labels
                    })
                    CREATE (p)-[:GENERATES]->(m)
                    """
                    neo4j_client.execute_query(
                        mem_query,
                        {
                            "pod_uid": pod_uid,
                            "metric_id": str(uuid.uuid4()),
                            "value": float(random.uniform(25.0, 75.0)),
                            "timestamp": int(time.time()),
                            "labels": str({"unit": "%"}),
                        },
                    )
            except Exception as metric_ex:
                logger.debug(
                    f"Could not generate metrics for pod {pod_name}: {metric_ex}"
                )

    except Exception as e:
        logger.error(f"Error discovering pods: {e}")

    # 5. Run Entity Linking
    linking_results = {}
    try:
        from app.adapters.graph_constructor import (
            run_entity_linking,
            build_service_dependency_map,
        )

        linking_results = run_entity_linking()
        build_service_dependency_map()
    except Exception as e:
        logger.error(f"Error running entity linking: {e}")

    return {
        "status": "success",
        "discovered": {
            "nodes": len(nodes_discovered),
            "deployments": len(deployments_discovered),
            "services": len(services_discovered),
            "pods": len(pods_discovered),
        },
        "linking": linking_results,
    }
