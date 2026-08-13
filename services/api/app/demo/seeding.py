"""Helper module for seeding and cleaning benchmark scenario data.

Covers both Neo4j graph nodes and Qdrant dense-vector documents.
"""

import logging
import uuid
from typing import Any, Dict

from qdrant_client.models import (
    FieldCondition,
    Filter,
    FilterSelector,
    MatchValue,
    PointIdsList,
)

from app.database.neo4j_client import NEO4J_CONNECTION_ERRORS, neo4j_client
from app.database.qdrant import qdrant_client
from app.demo.datasets import scenario_incident_time
from app.dependencies import semantic_store

logger = logging.getLogger(__name__)

# Spacing between consecutive seeded log lines, stepping back from the
# incident time. With the ranker's default one-hour recency half-life,
# 60s steps give a real but not exaggerated spread in recency score
# across a scenario's evidence.
LOG_INTERVAL_SECONDS = 60


def seed_scenario_data(scenario: Dict[str, Any]) -> None:
    """Seed Neo4j graph nodes and Qdrant semantic vectors for a benchmark
    scenario.

    Seeds `observed_symptoms` (raw, low-level telemetry text) as the
    evidence an investigation would actually retrieve — never
    `ground_truth_claims`, which is the held-out answer key used only for
    scoring extracted claims after the fact. Conflating the two is a
    data-leakage bug: see `rcaeval_dataset.py`'s module docstring and
    `dissertation/PROGRESS.md` (Week 9).
    """
    scenario_id = scenario["id"]
    target_service = scenario["target_service"]
    target_entity = scenario["target_entity"]
    symptoms = scenario["observed_symptoms"]
    incident_time = scenario_incident_time(scenario)

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
                    p.scenario_id = $scenario_id,
                    p.id = $pod_name
                MERGE (s:Service {name: $svc_name})
                SET s.is_benchmark = true,
                    s.scenario_id = $scenario_id
                MERGE (n:Node {name: 'node-worker-01'})
                SET n.status = 'Ready',
                    n.is_benchmark = true,
                    n.scenario_id = $scenario_id
                MERGE (d:Deployment {name: $deploy_name})
                SET d.status = 'Degraded',
                    d.is_benchmark = true,
                    d.scenario_id = $scenario_id

                MERGE (p)-[:BELONGS_TO {is_benchmark: true}]->(s)
                MERGE (p)-[:RUNS_ON {is_benchmark: true}]->(n)
                MERGE (d)-[:MANAGES {is_benchmark: true}]->(p)
                """,
                {
                    "pod_name": target_entity,
                    "svc_name": target_service,
                    "deploy_name": f"{target_service}-deploy",
                    "scenario_id": scenario_id,
                },
            )

            # Create Git Commit linked to Deployment — deliberately does
            # not name the root cause; a real commit message wouldn't
            # announce the incident it's about to trigger.
            neo4j_client.execute_query(
                """
                MERGE (c:Commit {sha: $commit_sha})
                SET c.message = $commit_msg,
                    c.is_benchmark = true,
                    c.scenario_id = $scenario_id
                WITH c
                MATCH (d:Deployment {name: $deploy_name})
                MERGE (c)-[:TRIGGERED_BY {is_benchmark: true}]->(d)
                """,
                {
                    "commit_sha": f"sha-{scenario_id}",
                    "commit_msg": f"update {target_service} configuration",
                    "deploy_name": f"{target_service}-deploy",
                    "scenario_id": scenario_id,
                },
            )

            # Create Logs linked to Pod, from the raw observed symptoms —
            # not the ground-truth claims (see module docstring).
            #
            # Timestamps step back from the incident time rather than all
            # sharing one value. Identical timestamps make the hybrid
            # ranker's recency term a constant across every candidate,
            # silently reducing a three-signal score to two — the seeded
            # data would then decide the outcome of a retrieval ablation
            # by construction. Stepping them also matches how real
            # evidence arrives: the newest line is the closest to the
            # incident.
            for idx, symptom in enumerate(symptoms):
                age = (len(symptoms) - 1 - idx) * LOG_INTERVAL_SECONDS
                neo4j_client.execute_query(
                    """
                    MATCH (p:Pod {name: $pod_name})
                    CREATE (l:Log {
                        id: $log_id,
                        message: $message,
                        level: 'ERROR',
                        timestamp: $timestamp,
                        is_benchmark: true,
                        scenario_id: $scenario_id
                    })
                    CREATE (p)-[:GENERATES {is_benchmark: true}]->(l)
                    """,
                    {
                        "pod_name": target_entity,
                        "log_id": f"log-{scenario_id}-{idx}",
                        "message": symptom,
                        "timestamp": incident_time - age,
                        "scenario_id": scenario_id,
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
                    timestamp: $timestamp,
                    is_benchmark: true,
                    scenario_id: $scenario_id
                })
                CREATE (p)-[:GENERATES {is_benchmark: true}]->(m)
                """,
                {
                    "pod_name": target_entity,
                    "metric_id": f"metric-{scenario_id}",
                    "timestamp": incident_time,
                    "scenario_id": scenario_id,
                },
            )
            logger.info("Successfully seeded Neo4j for scenario %s", scenario_id)
        except (RuntimeError, OSError) as exc:
            logger.error("Failed to seed Neo4j for scenario %s: %s", scenario_id, exc)

    # 2. Seed Qdrant Vector Store and local fallback cache
    try:
        # Index Commit — same non-revealing message as the Neo4j node.
        semantic_store.index_document(
            doc_id=f"commit-{scenario_id}",
            text=(
                f"Git revision commit sha-{scenario_id}"
                f" update {target_service} configuration"
            ),
            metadata={
                "is_benchmark": True,
                "scenario_id": scenario_id,
                "label": "Commit",
                "name": f"commit-{scenario_id}",
            },
        )

        # Index Logs from the raw observed symptoms — not the
        # ground-truth claims (see module docstring).
        for idx, symptom in enumerate(symptoms):
            semantic_store.index_document(
                doc_id=f"log-{scenario_id}-{idx}",
                text=symptom,
                metadata={
                    "is_benchmark": True,
                    "scenario_id": scenario_id,
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
                "scenario_id": scenario_id,
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


def _protected_collections() -> set[str]:
    """Collections that serve real traffic and must never be purged.

    Taken from the configured product collections, not from "everything
    that is not the evaluation collection" — the latter is circular, since
    an evaluation collection misconfigured to a live name would exclude
    itself from the very set meant to protect it.
    """
    return set(qdrant_client.product_collection_names)


class SemanticStoreNotIsolatedError(RuntimeError):
    """Raised when the vector store holds evidence that is not the current
    scenario's, which would silently contaminate every retrieval condition."""


def purge_semantic_store() -> int:
    """Delete every point in the evidence collection and every local
    fallback document, returning how many vector points were removed.

    Teardown alone is not sufficient to guarantee a clean store. It deletes
    reconstructed point ids drawn from this process's in-memory document
    list, so points written by any earlier process are unreachable forever
    — and Qdrant outlives the API pod, which is restarted routinely. Points
    seeded before scenario tagging existed carry no is_benchmark flag
    either, so a predicate-based delete cannot find them. A full purge is
    the only reliable reset, and an evaluation run must start from one.
    """
    semantic_store.documents = []
    semantic_store.persist()

    removed = 0
    if not qdrant_client.connect():
        logger.warning("Qdrant unavailable; purged local fallback documents only")
        return removed

    # Only ever the evaluation collection. This deletes every point it
    # touches, so pointing it at the collection serving real traffic would
    # destroy production evidence to set up a benchmark run.
    collection = qdrant_client.eval_collection_name
    if collection in _protected_collections():
        raise RuntimeError(
            f"refusing to purge {collection!r}: it is a live evidence "
            "collection, not the dedicated evaluation one"
        )
    try:
        before = qdrant_client.client.get_collection(collection).points_count
        qdrant_client.client.delete(
            collection_name=collection,
            points_selector=FilterSelector(filter=Filter(must=[])),
            wait=True,
        )
        after = qdrant_client.client.get_collection(collection).points_count
        removed = before - after
        logger.info(
            "Purged evaluation collection %s: %s -> %s points",
            collection,
            before,
            after,
        )
    except (RuntimeError, OSError, ValueError) as exc:
        logger.error("Failed to purge evaluation collection %s: %s", collection, exc)
    return removed


def assert_semantic_store_isolated(scenario_id: str) -> None:
    """Fail the run if the vector store holds anything but this scenario.

    Deliberately fatal rather than best-effort. Cross-scenario residue does
    not announce itself in the results — it silently inflates every
    retrieval condition and invalidates the raw-vs-hybrid ablation and the
    GPCS scores together, which is only discoverable afterwards by
    inspecting request logs. Losing a run to a loud failure is far cheaper
    than publishing a quiet one.
    """
    if not qdrant_client.connect():
        return

    foreign = 0
    for collection in (qdrant_client.eval_collection_name,):
        try:
            records, _ = qdrant_client.client.scroll(
                collection_name=collection,
                scroll_filter=Filter(
                    must_not=[
                        FieldCondition(
                            key="scenario_id", match=MatchValue(value=scenario_id)
                        )
                    ]
                ),
                limit=1,
                with_payload=False,
            )
            foreign += len(records)
        except (RuntimeError, OSError, ValueError) as exc:
            logger.error("Could not verify isolation of %s: %s", collection, exc)

    if foreign:
        raise SemanticStoreNotIsolatedError(
            f"vector store holds evidence not belonging to {scenario_id}; "
            "every retrieval condition would be contaminated. Purge the "
            "store (app.demo.seeding.purge_semantic_store) and re-run."
        )

    assert_graph_isolated(scenario_id)


def assert_graph_isolated(scenario_id: str) -> None:
    """Fail the run if Neo4j holds benchmark nodes from another scenario.

    The graph side has the same exposure as the vector side: keyword and
    raw-context retrieval read seeded nodes, and until those queries were
    scenario-scoped the only thing keeping them honest was that teardown
    happens to delete every is_benchmark node globally. Checking it here
    means a partial teardown surfaces as a failed run rather than as
    quietly contaminated evidence.
    """
    if not neo4j_client.driver:
        return
    try:
        records = neo4j_client.execute_query(
            """
            MATCH (n)
            WHERE n.is_benchmark = true
              AND (n.scenario_id IS NULL OR n.scenario_id <> $scenario_id)
            RETURN count(n) AS foreign
            """,
            {"scenario_id": scenario_id},
        )
    except NEO4J_CONNECTION_ERRORS as exc:
        # Being unable to check is not the same as having checked. A driver
        # that exists but cannot reach the server raises a raw
        # ServiceUnavailable from session.run — narrower except clauses let
        # that escape as an unhandled traceback mid-run. Failing here with a
        # clear reason keeps the guarantee this assertion exists to provide:
        # a run either verified its isolation or stopped.
        raise SemanticStoreNotIsolatedError(
            f"could not verify graph isolation for {scenario_id}: {exc}"
        ) from exc

    foreign = records[0].get("foreign", 0) if records else 0
    if foreign:
        raise SemanticStoreNotIsolatedError(
            f"graph holds {foreign} benchmark nodes not belonging to "
            f"{scenario_id}; keyword and raw-context retrieval would read "
            "another incident's evidence. Tear down and re-run."
        )
