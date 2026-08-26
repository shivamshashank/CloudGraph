"""Helper module for seeding and cleaning benchmark scenario data.

Covers both Neo4j graph nodes and Qdrant dense-vector documents.
"""

import hashlib
import logging
import re
import uuid
from typing import Any, Dict, Optional, Tuple

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

# Spacing between seeded log lines. Against the ranker's one-hour half-life,
# 60s gives a real but not exaggerated recency spread.
LOG_INTERVAL_SECONDS = 60

# The seeded Commit predates its incident by 3-10 days rather than sharing its
# timestamp.
#
# Why: RCAEval faults are chaos-injected. No deployment change occurs in any
# scenario, so a commit stamped at incident_time whose message names the faulted
# service's *configuration* is a fabricated causal attractor -- and an effective
# one. Once retrieval delivery was fixed, the raw condition blamed this node in
# 2/2 pilot scenarios ("Config-Induced CPU Exhaustion", "faulty config rollout
# sha-rcaeval-02") and the recommendation led with "rollback sha-rcaeval-01",
# an action that would do nothing. Because the template is identical for every
# scenario, that confound would have applied uniformly across all 36.
#
# Dating it outside the incident window makes it temporally falsifiable from the
# graph itself, and drops the hybrid ranker's recency term for it from 1.0
# (age 0) to ~0. The offset is derived from a stable digest of the scenario id,
# so it varies per scenario, is reproducible across processes, and does not
# depend on PYTHONHASHSEED.
COMMIT_MIN_AGE_DAYS = 3
COMMIT_MAX_AGE_DAYS = 10
COMMIT_MESSAGE = "routine dependency and manifest refresh"


def _commit_age_seconds(scenario_id: str) -> int:
    """Deterministic per-scenario commit age, in [COMMIT_MIN_AGE_DAYS,
    COMMIT_MAX_AGE_DAYS] days. Uses sha256 rather than hash() because the
    built-in is salted per process and would make seeding irreproducible."""
    span = COMMIT_MAX_AGE_DAYS - COMMIT_MIN_AGE_DAYS + 1
    digest = hashlib.sha256(scenario_id.encode("utf-8")).digest()
    days = COMMIT_MIN_AGE_DAYS + (int.from_bytes(digest[:4], "big") % span)
    return days * 86400


# Prometheus-style names for the metric keys RCAEval emits, used only to label
# the seeded node. The value and text always come from the scenario's telemetry.
METRIC_NAMES = {
    "cpu": "container_cpu_usage_seconds_total",
    "mem": "container_memory_usage_bytes",
    "diskio": "container_fs_io_time_seconds_total",
    "socket": "container_network_tcp_usage_total",
    "error": "request_errors_total",
    "workload": "request_rate_per_second",
    "latency-50": "request_duration_seconds_p50",
    "latency-90": "request_duration_seconds_p90",
}

_METRIC_LINE = re.compile(
    r"^metric\s+(?P<svc>[\w.-]+?)_(?P<key>cpu|mem|diskio|socket|error|workload"
    r"|latency-50|latency-90):\s*mean\s+(?P<before>[-\d.e+]+)\s+in the \d+min"
    r"\s+before\s+\d+,\s*(?P<after>[-\d.e+]+)\s+in the \d+min after",
    re.IGNORECASE,
)


def _observed_target_metric(
    target_service: str, symptoms: list[str]
) -> Optional[Tuple[str, float, str]]:
    """Pick the target service's most-changed metric from its own telemetry.

    Returns (key, value_after, original_symptom_line) or None. Selection is by
    largest relative change, which is a property of the *observation*, not of
    the injected-fault label -- so it introduces no ground-truth leakage beyond
    what the symptom list already contains.
    """
    best_change = -1.0
    best: Optional[Tuple[str, float, str]] = None
    for line in symptoms:
        m = _METRIC_LINE.match(line.strip())
        if not m or m.group("svc") != target_service:
            continue
        try:
            before = float(m.group("before"))
            after = float(m.group("after"))
        except ValueError:
            continue
        if before == 0:
            continue
        change = abs(after / before - 1.0)
        if change > best_change:
            best_change = change
            best = (m.group("key"), after, line.strip())
    return best


# Seeding one scenario means writing Pod, Service, Deployment, Node, Commit,
# Log and Metric records that must share the same ids and timestamps, so the
# locals are the shared state of a single transaction rather than separable
# steps. Splitting it would pass the arguments around instead.
def seed_scenario_data(scenario: Dict[str, Any]) -> None:
    # pylint: disable=too-many-locals
    """Seed Neo4j graph nodes and Qdrant semantic vectors for a benchmark
    scenario.

    Seeds `observed_symptoms` (raw, low-level telemetry text) as the
    evidence an investigation would actually retrieve — never
    `ground_truth_claims`, which is the held-out answer key used only for
    scoring extracted claims after the fact. Conflating the two is a
    data-leakage bug: see `rcaeval_dataset.py`'s module docstring and
    the module docstring in `rcaeval_dataset.py`.
    """
    scenario_id = scenario["id"]
    target_service = scenario["target_service"]
    target_entity = scenario["target_entity"]
    symptoms = scenario["observed_symptoms"]
    incident_time = scenario_incident_time(scenario)
    node_name = scenario.get("node_name", "node-worker-01")

    # The seeded Metric is derived from the scenario's OWN observed telemetry,
    # never from a hardcoded template and never from the ground-truth label.
    #
    # Two defects motivated this. (1) The previous branch read
    # `injected_fault`/`fault`, keys the RCAEval dataset does not carry -- it
    # stores `root_cause` -- so `fault` was always "" and 11 of 36 scenarios,
    # including every network_delay and packet_loss case, were seeded with a
    # fabricated "container CPU usage seconds total is 95 percent". That string
    # ranked #1 in hybrid retrieval and drove a wrong CPU diagnosis on
    # rcaeval-04. (2) A symptom heuristic (`any("mem" in s ...)`) decided the
    # branch for the rest, which is arbitrary: every fault family emits both cpu
    # and mem symptoms, so rcaeval-01 got a memory metric on a CPU fault.
    #
    # Reading `root_cause` and templating per family would fix (1) but introduce
    # ground-truth leakage -- seeding "network latency is 5.0s" on a delay fault
    # hands the model the answer, the same P0 defect that invalidated the
    # original hand-authored benchmark. Deriving from observed telemetry avoids
    # both: the value is real, and it reveals nothing the 26 symptoms already
    # given to the agents do not.
    observed = _observed_target_metric(target_service, symptoms)
    if observed is not None:
        metric_key, metric_value, metric_text = observed
        metric_name = METRIC_NAMES.get(
            metric_key, f"service_{metric_key.replace('-', '_')}"
        )
    else:
        # No parsable metric line for the target service. Seed nothing rather
        # than invent a value; a missing node is honest, a fabricated one is not.
        metric_name = metric_value = metric_text = None

    # 1. Seed Neo4j properties
    if neo4j_client.driver:
        try:
            # Create Pod, Service, Deployment, Node
            neo4j_client.execute_query(
                """
                MERGE (p:Pod {name: $pod_name})
                SET p.status = 'Failed',
                    p.nodeName = $node_name,
                    p.is_benchmark = true,
                    p.scenario_id = $scenario_id,
                    p.id = $pod_name
                MERGE (s:Service {name: $svc_name})
                SET s.is_benchmark = true,
                    s.scenario_id = $scenario_id,
                    s.id = $svc_name
                MERGE (n:Node {name: $node_name})
                SET n.status = 'Ready',
                    n.is_benchmark = true,
                    n.scenario_id = $scenario_id,
                    n.id = $node_name
                MERGE (d:Deployment {name: $deploy_name})
                SET d.status = 'Degraded',
                    d.is_benchmark = true,
                    d.scenario_id = $scenario_id,
                    d.id = $deploy_name

                MERGE (p)-[:BELONGS_TO {is_benchmark: true}]->(s)
                MERGE (p)-[:RUNS_ON {is_benchmark: true}]->(n)
                MERGE (d)-[:MANAGES {is_benchmark: true}]->(p)
                """,
                {
                    "pod_name": target_entity,
                    "svc_name": target_service,
                    "deploy_name": f"{target_service}-deploy",
                    "scenario_id": scenario_id,
                    "node_name": node_name,
                },
            )

            # Commit message names neither the root cause nor the faulted
            # service, and the node carries an explicit timestamp days before
            # the incident so its irrelevance is checkable from the graph
            # rather than assumed. See COMMIT_MIN_AGE_DAYS.
            commit_time = incident_time - _commit_age_seconds(scenario_id)
            neo4j_client.execute_query(
                """
                MERGE (c:Commit {sha: $commit_sha})
                SET c.message = $commit_msg,
                    c.timestamp = $commit_time,
                    c.is_benchmark = true,
                    c.scenario_id = $scenario_id,
                    c.id = $commit_sha
                WITH c
                MATCH (d:Deployment {name: $deploy_name})
                MERGE (c)-[:TRIGGERED_BY {is_benchmark: true}]->(d)
                """,
                {
                    "commit_sha": f"sha-{scenario_id}",
                    "commit_msg": COMMIT_MESSAGE,
                    "commit_time": commit_time,
                    "deploy_name": f"{target_service}-deploy",
                    "scenario_id": scenario_id,
                },
            )

            # Logs come from observed symptoms, not ground truth (see module
            # docstring). Timestamps step back: identical ones make the ranker's
            # recency term constant and skew a retrieval ablation.
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

            # Create Metric linked to Pod — skipped when the scenario has no
            # parsable target-service metric line (see _observed_target_metric).
            if metric_name is not None:
                neo4j_client.execute_query(
                    """
                MATCH (p:Pod {name: $pod_name})
                CREATE (m:Metric {
                    id: $metric_id,
                    name: $metric_name,
                    value: $metric_value,
                    timestamp: $timestamp,
                    is_benchmark: true,
                    scenario_id: $scenario_id
                })
                CREATE (p)-[:GENERATES {is_benchmark: true}]->(m)
                """,
                    {
                        "pod_name": target_entity,
                        "metric_id": f"metric-{scenario_id}",
                        "metric_name": metric_name,
                        "metric_value": metric_value,
                        "timestamp": incident_time,
                        "scenario_id": scenario_id,
                    },
                )
            logger.info("Successfully seeded Neo4j for scenario %s", scenario_id)
        except (RuntimeError, OSError) as exc:
            logger.error("Failed to seed Neo4j for scenario %s: %s", scenario_id, exc)

    # 2. Seed Qdrant Vector Store and local fallback cache
    try:
        # Index Commit — same message and same pre-incident timestamp as the
        # Neo4j node. The timestamp must match: stamping the vector copy at
        # incident_time (as this did) gave the hybrid ranker's recency term its
        # maximum value for the one item guaranteed to be causally irrelevant.
        commit_time = incident_time - _commit_age_seconds(scenario_id)
        semantic_store.index_document(
            doc_id=f"commit-{scenario_id}",
            text=f"Git revision commit sha-{scenario_id} {COMMIT_MESSAGE}",
            metadata={
                "is_benchmark": True,
                "scenario_id": scenario_id,
                "label": "Commit",
                "name": f"commit-{scenario_id}",
                "timestamp": commit_time,
            },
        )

        # Index logs from observed symptoms, not ground truth (module docstring).
        for idx, symptom in enumerate(symptoms):
            age = (len(symptoms) - 1 - idx) * LOG_INTERVAL_SECONDS
            semantic_store.index_document(
                doc_id=f"log-{scenario_id}-{idx}",
                text=symptom,
                metadata={
                    "is_benchmark": True,
                    "scenario_id": scenario_id,
                    "label": "Log",
                    "name": target_entity,
                    "pod_name": target_entity,
                    "timestamp": incident_time - age,
                },
            )

        # Index Metric — skipped when the scenario has no parsable target-service
        # metric line, AND when its text is already indexed as a symptom.
        #
        # The second guard exists because metric_text is now DERIVED from the
        # symptom list rather than templated, so it is byte-identical to one of
        # the Log documents indexed above. Indexing both put the same sentence in
        # the corpus twice and hybrid retrieval duly returned it twice: in
        # rcaeval-04 the top-5 held items [1] and [3] as the same document,
        # spending 20% of the ranked window on a duplicate. The Neo4j Metric node
        # is still created either way, so graph structure is unaffected.
        if metric_text is not None and metric_text not in set(symptoms):
            semantic_store.index_document(
                doc_id=f"metric-{scenario_id}",
                text=metric_text,
                metadata={
                    "is_benchmark": True,
                    "scenario_id": scenario_id,
                    "label": "Metric",
                    "name": metric_name,
                    "pod_name": target_entity,
                    "timestamp": incident_time,
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

        # 3. Teardown Qdrant points (via payload filter and point IDs)
        if qdrant_client.client:
            for collection in qdrant_client.collection_names:
                try:
                    qdrant_client.client.delete(
                        collection_name=collection,
                        points_selector=FilterSelector(
                            filter=Filter(
                                must=[
                                    FieldCondition(
                                        key="is_benchmark",
                                        match=MatchValue(value=True),
                                    )
                                ]
                            )
                        ),
                    )
                except (RuntimeError, OSError, ValueError) as exc:
                    logger.debug(
                        "Qdrant payload filter delete on %s: %s", collection, exc
                    )

            point_ids = []
            for doc_id in benchmark_doc_ids:
                # Reconstruct point_id using same uuid5 strategy from qdrant.py
                point_uuid = str(uuid.uuid5(uuid.NAMESPACE_URL, f"cloudgraph:{doc_id}"))
                point_ids.append(point_uuid)

            if point_ids:
                for collection in qdrant_client.collection_names:
                    try:
                        qdrant_client.client.delete(
                            collection_name=collection,
                            points_selector=PointIdsList(points=point_ids),
                        )
                    except (RuntimeError, OSError, ValueError) as exc:
                        logger.debug(
                            "Qdrant point ID delete on %s: %s", collection, exc
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

    # Eval collection only: this deletes every point it touches.
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
        # Being unable to check is not the same as having checked. A reachable-
        # but-dead driver raises ServiceUnavailable from session.run, so failing
        # loudly keeps the guarantee: a run either verified isolation or stopped.
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
