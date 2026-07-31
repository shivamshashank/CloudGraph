"""Helper module for seeding and cleaning benchmark scenario data.

Covers both Neo4j graph nodes and Qdrant dense-vector documents.
"""

import logging
import uuid
from typing import Any, Dict

from qdrant_client.models import PointIdsList

from app.database.neo4j_client import neo4j_client
from app.database.qdrant import qdrant_client
from app.dependencies import semantic_store

logger = logging.getLogger(__name__)


def seed_scenario_data(scenario: Dict[str, Any]) -> None:
    """Seed Neo4j graph nodes and Qdrant semantic vectors for a benchmark scenario."""
    scenario_id = scenario["id"]
    target_service = scenario["target_service"]
    target_entity = scenario["target_entity"]
    root_cause = scenario["root_cause"]
    claims = scenario["ground_truth_claims"]

    # 1. Seed Neo4j properties
    if neo4j_client.driver:
        try:
            # Create Pod, Service, Deployment, Node
            neo4j_client.execute_query(
                """
                MERGE (p:Pod {name: $pod_name})
                SET p.status = 'Failed',
                    p.nodeName = 'node-worker-01',
                    p.is_benchmark = true,
                    p.id = $pod_name
                MERGE (s:Service {name: $svc_name})
                SET s.is_benchmark = true
                MERGE (n:Node {name: 'node-worker-01'})
                SET n.status = 'Ready',
                    n.is_benchmark = true
                MERGE (d:Deployment {name: $deploy_name})
                SET d.status = 'Degraded',
                    d.is_benchmark = true

                MERGE (p)-[:BELONGS_TO {is_benchmark: true}]->(s)
                MERGE (p)-[:RUNS_ON {is_benchmark: true}]->(n)
                MERGE (d)-[:MANAGES {is_benchmark: true}]->(p)
                """,
                {
                    "pod_name": target_entity,
                    "svc_name": target_service,
                    "deploy_name": f"{target_service}-deploy",
                },
            )

            # Create Git Commit linked to Deployment
            neo4j_client.execute_query(
                """
                MERGE (c:Commit {sha: $commit_sha})
                SET c.message = $commit_msg,
                    c.is_benchmark = true
                WITH c
                MATCH (d:Deployment {name: $deploy_name})
                MERGE (c)-[:TRIGGERED_BY {is_benchmark: true}]->(d)
                """,
                {
                    "commit_sha": f"sha-{scenario_id}",
                    "commit_msg": (
                        f"update {target_service} config settings"
                        f" with root cause {root_cause}"
                    ),
                    "deploy_name": f"{target_service}-deploy",
                },
            )

            # Create Logs linked to Pod
            for idx, claim in enumerate(claims):
                neo4j_client.execute_query(
                    """
                    MATCH (p:Pod {name: $pod_name})
                    CREATE (l:Log {
                        id: $log_id,
                        message: $message,
                        level: 'ERROR',
                        timestamp: 1600000000,
                        is_benchmark: true
                    })
                    CREATE (p)-[:GENERATES {is_benchmark: true}]->(l)
                    """,
                    {
                        "pod_name": target_entity,
                        "log_id": f"log-{scenario_id}-{idx}",
                        "message": claim,
                    },
                )

            # Create Metric linked to Pod
            neo4j_client.execute_query(
                """
                MATCH (p:Pod {name: $pod_name})
                CREATE (m:Metric {
                    id: $metric_id,
                    name: 'container_cpu_usage_seconds_total',
                    value: 95.0,
                    timestamp: 1600000000,
                    is_benchmark: true
                })
                CREATE (p)-[:GENERATES {is_benchmark: true}]->(m)
                """,
                {
                    "pod_name": target_entity,
                    "metric_id": f"metric-{scenario_id}",
                },
            )
            logger.info("Successfully seeded Neo4j for scenario %s", scenario_id)
        except (RuntimeError, OSError) as exc:
            logger.error("Failed to seed Neo4j for scenario %s: %s", scenario_id, exc)

    # 2. Seed Qdrant Vector Store and local fallback cache
    try:
        # Index Commit
        semantic_store.index_document(
            doc_id=f"commit-{scenario_id}",
            text=(
                f"Git revision commit sha-{scenario_id}"
                f" update {target_service} config: {root_cause}"
            ),
            metadata={
                "is_benchmark": True,
                "label": "Commit",
                "name": f"commit-{scenario_id}",
            },
        )

        # Index Logs (Claims)
        for idx, claim in enumerate(claims):
            semantic_store.index_document(
                doc_id=f"log-{scenario_id}-{idx}",
                text=claim,
                metadata={
                    "is_benchmark": True,
                    "label": "Log",
                    "name": target_entity,
                    "pod_name": target_entity,
                },
            )

        # Index Metric
        semantic_store.index_document(
            doc_id=f"metric-{scenario_id}",
            text=(
                "container CPU usage seconds total is 95 percent"
                f" on service {target_service}"
            ),
            metadata={
                "is_benchmark": True,
                "label": "Metric",
                "name": "container_cpu_usage_seconds_total",
                "pod_name": target_entity,
            },
        )
        logger.info(
            "Successfully indexed vector documents for scenario %s", scenario_id
        )
    except (RuntimeError, OSError, ValueError) as exc:
        logger.error("Failed to seed Qdrant for scenario %s: %s", scenario_id, exc)


def teardown_benchmark_data() -> None:
    """Remove all seeded benchmark data from Neo4j and Qdrant."""
    # 1. Teardown Neo4j nodes and edges
    if neo4j_client.driver:
        try:
            neo4j_client.execute_query(
                "MATCH (n) WHERE n.is_benchmark = true DETACH DELETE n"
            )
            logger.info("Cleared all benchmark Neo4j nodes successfully")
        except (RuntimeError, OSError) as exc:
            logger.error("Failed to teardown Neo4j benchmark nodes: %s", exc)

    # 2. Teardown local fallback documents
    try:
        benchmark_doc_ids = [
            doc["id"]
            for doc in semantic_store.documents
            if doc.get("metadata", {}).get("is_benchmark") is True
        ]
        semantic_store.documents = [
            doc
            for doc in semantic_store.documents
            if doc.get("metadata", {}).get("is_benchmark") is not True
        ]
        semantic_store.persist()
        logger.info("Cleared local fallback JSON documents: %s", benchmark_doc_ids)

        # 3. Teardown Qdrant points
        if qdrant_client.client:
            point_ids = []
            for doc_id in benchmark_doc_ids:
                # Reconstruct point_id using same uuid5 strategy from qdrant.py
                point_uuid = str(uuid.uuid5(uuid.NAMESPACE_URL, f"cloudgraph:{doc_id}"))
                point_ids.append(point_uuid)

            if point_ids:
                for collection in qdrant_client.collection_names:
                    qdrant_client.client.delete(
                        collection_name=collection,
                        points_selector=PointIdsList(points=point_ids),
                    )
                logger.info("Deleted Qdrant points: %s", point_ids)
    except (RuntimeError, OSError, ValueError) as exc:
        logger.error("Failed to teardown Qdrant benchmark points: %s", exc)
