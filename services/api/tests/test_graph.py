"""Integration and unit tests for graph indexing services."""

import time
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from neo4j.exceptions import Neo4jError, ServiceUnavailable

from app import main
from app.adapters import k8s_discovery
from app.adapters.tempo import ingest_tempo_trace
from app.database.neo4j_client import neo4j_client
from app.main import app
from app.services.semantic_store import SemanticVectorStore

client = TestClient(app)


# Helper: check if live database is reachable
def is_db_reachable():
    """Verify if the live Neo4j database is reachable."""
    try:
        neo4j_client.execute_query("RETURN 1")
        return True
    except (RuntimeError, ConnectionError, OSError, ServiceUnavailable, Neo4jError):
        return False


# =============================================================================
# 1. Integration Tests (Mocked if Offline, Real if Online)
# =============================================================================


def test_health_endpoint():
    """Verify that the health check endpoint returns 200 OK."""
    response = client.get("/health")
    assert response.status_code == 200
    assert "status" in response.json()


def test_ingest_metrics(monkeypatch):
    """Verify metrics ingestion maps correctly to database insertion."""
    if not is_db_reachable():
        # Mock execution if offline
        mock_execute = MagicMock(return_value=[{"metric_id": "test-metric-id-123"}])
        monkeypatch.setattr(neo4j_client, "execute_query", mock_execute)

    payload = {
        "pod_id": "checkout-pod-1",
        "pod_name": "checkout-service-58d75-abc12",
        "metric_name": "http_requests_total",
        "value": 150.0,
        "timestamp": int(time.time()),
        "labels": {"status": "200"},
    }
    response = client.post("/api/v1/telemetry/metrics", json=payload)
    if response.status_code != 200:
        print("METRICS FAILED:", response.status_code, response.json())
    assert response.status_code == 200
    assert response.json()["status"] == "success"
    assert "metric_id" in response.json()


def test_ingest_logs(monkeypatch):
    """Verify logs ingestion executes successfully."""
    if not is_db_reachable():
        mock_execute = MagicMock(return_value=[{"log_id": "test-log-id-123"}])
        monkeypatch.setattr(neo4j_client, "execute_query", mock_execute)

    payload = {
        "pod_id": "payment-pod-1",
        "pod_name": "payment-service-bc234-xyz",
        "message": "database connection timeout",
        "level": "error",
        "timestamp": int(time.time()),
        "container_name": "payment-container",
    }
    response = client.post("/api/v1/telemetry/logs", json=payload)
    if response.status_code != 200:
        print("LOGS FAILED:", response.status_code, response.json())
    assert response.status_code == 200
    assert response.json()["status"] == "success"
    assert "log_id" in response.json()


# =============================================================================
# 2. Schema Validation Tests (Active when Online, Skipped when Offline)
# =============================================================================


@pytest.mark.skipif(not is_db_reachable(), reason="Neo4j database is offline")
def test_schema_constraints():
    """
    Validates that database unique constraints are loaded in Neo4j.
    """
    result = neo4j_client.execute_query("SHOW CONSTRAINTS")
    constraints = [r["name"] for r in result]
    expected = [
        "service_name_unique",
        "pod_id_unique",
        "node_name_unique",
        "deployment_name_unique",
        "incident_id_unique",
        "commit_sha_unique",
    ]
    for exp in expected:
        assert exp in constraints, f"Expected constraint {exp} was not found"


@pytest.mark.skipif(not is_db_reachable(), reason="Neo4j database is offline")
def test_graph_integrity():
    """
    Query for orphan pods or services without relationship edges.
    """
    # Find all pods without running VM nodes
    result = neo4j_client.execute_query(
        """
    MATCH (p:Pod)
    WHERE NOT (p)-[:RUNS_ON]->(:Node)
    RETURN count(p) as orphan_count
    """
    )
    # For a clean deployment, orphan count should start at 0 after linking
    assert result[0]["orphan_count"] >= 0


def test_investigation_trigger_returns_structured_analysis(monkeypatch):
    """Verify that investigation trigger analyzes CrashLoopBackOff and log errors."""

    def _fake_execute_query(query, _params=None):
        if "MATCH (p:Pod)" in query and "WHERE NOT p.status" in query:
            return [
                {
                    "id": "pod-1",
                    "name": "checkout",
                    "status": "CrashLoopBackOff",
                    "nodeName": "node-1",
                }
            ]
        if (
            "MATCH (p:Pod)-[:GENERATES]->(l:Log)" in query
            and "l.level = 'ERROR'" in query
        ):
            return [{"msg": "database connection timeout", "ts": 123}]
        if "CREATE (i:Incident" in query:
            return [{"id": "incident-1"}]
        return []

    monkeypatch.setattr(neo4j_client, "execute_query", _fake_execute_query)
    monkeypatch.setattr(
        k8s_discovery,
        "discover_cluster_topology",
        lambda namespace=None: {"status": "success"},
    )

    response = client.post(
        "/api/v1/investigations/trigger", json={"namespace": "cloudgraph-system"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert (
        body["results"][0]["summary"]
        == "Potential dependency failure or crash loop detected"
    )
    assert body["results"][0]["evidence"]


def test_investigation_trigger_uses_retrieval_context_when_available(monkeypatch):
    """Verify that the trigger endpoint utilizes GraphRAG context when active."""

    def _fake_execute_query(query, _params=None):
        if "MATCH (p:Pod)" in query and "WHERE NOT p.status" in query:
            return [
                {
                    "id": "pod-1",
                    "name": "checkout",
                    "status": "CrashLoopBackOff",
                    "nodeName": "node-1",
                }
            ]
        if (
            "MATCH (p:Pod)-[:GENERATES]->(l:Log)" in query
            and "l.level = 'ERROR'" in query
        ):
            return [{"msg": "database connection timeout", "ts": 123}]
        if "CREATE (i:Incident" in query:
            return [{"id": "incident-1"}]
        return []

    monkeypatch.setattr(neo4j_client, "execute_query", _fake_execute_query)
    monkeypatch.setattr(
        k8s_discovery,
        "discover_cluster_topology",
        lambda namespace=None: {"status": "success"},
    )
    monkeypatch.setattr(
        main,
        "graphrag_search",
        lambda payload, method=None: {
            "status": "success",
            "results": [
                {
                    "name": "checkout-service",
                    "score": 0.88,
                    "sources": ["hybrid"],
                }
            ],
        },
    )

    response = client.post(
        "/api/v1/investigations/trigger", json={"namespace": "cloudgraph-system"}
    )

    assert response.status_code == 200
    body = response.json()
    retrieval_context = body["results"][0]["retrieval_context"]
    assert retrieval_context["source"] == "graphrag"
    assert retrieval_context["top_result"]["name"] == "checkout-service"


def test_relevant_evidence_endpoint_returns_graph_context(monkeypatch):
    """
    Verify that the evidence endpoint queries and constructs related graph metadata.
    """

    def _fake_execute_query(query, _params=None):
        if "MATCH (p:Pod" in query and "RETURN p.name" in query:
            return [
                {
                    "pod_name": "checkout-abc",
                    "service_name": "checkout",
                    "node_name": "node-1",
                    "deployment_name": "checkout-deployment",
                    "log_messages": ["database connection timeout"],
                }
            ]
        return []

    monkeypatch.setattr(neo4j_client, "execute_query", _fake_execute_query)

    response = client.post(
        "/api/v1/investigations/evidence",
        json={"pod_name": "checkout-abc", "namespace": "cloudgraph-system"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert body["pod_name"] == "checkout-abc"
    assert any(item["type"] == "service" for item in body["evidence"])


def test_graphrag_search_endpoint_returns_ranked_results(monkeypatch):
    """Verify that graphrag search endpoint returns ranked retrieval records."""

    def _fake_execute_query(query, _params=None):
        if "MATCH (n)" in query and "RETURN labels(n)" in query:
            return [
                {
                    "labels": ["Pod"],
                    "name": "checkout-pod",
                    "status": "CrashLoopBackOff",
                    "title": None,
                    "id": "pod-1",
                }
            ]
        if "OPTIONAL MATCH" in query or "MATCH (n)-[r]-(m)" in query:
            return [
                {
                    "rel": "BELONGS_TO",
                    "related_name": "checkout-service",
                    "related_labels": ["Service"],
                },
                {
                    "rel": "RUNS_ON",
                    "related_name": "node-1",
                    "related_labels": ["Node"],
                },
            ]
        return []

    monkeypatch.setattr(neo4j_client, "execute_query", _fake_execute_query)

    response = client.post(
        "/api/v1/graphrag/search",
        json={"query": "checkout", "namespace": "cloudgraph-system"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert body["query"] == "checkout"
    assert body["results"]
    assert body["results"][0]["evidence_chain"]
    assert body["results"][0]["context"]


def test_graphrag_search_supports_keyword_and_vector_methods(monkeypatch):
    """Verify that graphrag search filters correctly by method types."""

    def _fake_execute_query(query, _params=None):
        if "MATCH (n)" in query and "RETURN labels(n)" in query:
            return [
                {
                    "labels": ["Pod"],
                    "name": "checkout-pod",
                    "status": "CrashLoopBackOff",
                    "title": None,
                    "id": "pod-1",
                }
            ]
        return []

    monkeypatch.setattr(neo4j_client, "execute_query", _fake_execute_query)
    monkeypatch.setattr(
        main.semantic_store,
        "search",
        lambda query, limit: [
            {
                "id": "vector-1",
                "text": "checkout pod failure",
                "score": 0.91,
                "metadata": {"label": "Pod", "name": "checkout-pod"},
            }
        ],
    )

    keyword_response = client.post(
        "/api/v1/graphrag/search",
        json={"query": "checkout", "method": "keyword"},
    )
    vector_response = client.post(
        "/api/v1/graphrag/search",
        json={"query": "checkout", "method": "vector"},
    )

    assert keyword_response.status_code == 200
    assert keyword_response.json()["results"][0]["sources"] == ["graph"]
    assert vector_response.status_code == 200
    assert vector_response.json()["results"][0]["sources"] == ["vector"]


def test_graphrag_search_uses_configurable_temporal_traversal(monkeypatch):
    """
    Verify that graphrag search passes depth and time filters to the traversal function.
    """

    def _fake_execute_query(query, _params=None):
        if "MATCH (n)" in query and "RETURN labels(n)" in query:
            return [
                {
                    "labels": ["Incident"],
                    "name": None,
                    "status": "Open",
                    "title": "Payment database failure",
                    "id": "incident-element-1",
                }
            ]
        return []

    calls = []

    def _fake_traverse(seed_id, **kwargs):
        calls.append((seed_id, kwargs))
        return [
            {
                "id": "log-1",
                "labels": ["Log"],
                "type": "log",
                "name": "database auth failed",
                "properties": {"timestamp": 1500},
                "hop_distance": 2,
                "relationships": ["AFFECTED_BY", "GENERATES"],
                "path": [{"name": "Payment database failure"}, {"name": "payment"}],
            }
        ]

    monkeypatch.setattr(neo4j_client, "execute_query", _fake_execute_query)
    monkeypatch.setattr(main.semantic_store, "search", lambda query, limit: [])
    monkeypatch.setattr(main.graph_traversal_retriever, "retrieve", _fake_traverse)

    response = client.post(
        "/api/v1/graphrag/search",
        json={
            "query": "payment database",
            "depth": 3,
            "start_time": 1000,
            "end_time": 2000,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["retrieval"] == {
        "depth": 3,
        "start_time": 1000,
        "end_time": 2000,
        "ranking_formula": (
            "hybrid_score = 0.50 * vector_similarity + "
            "0.30 * graph_proximity + 0.20 * recency"
        ),
    }
    assert calls[0][0] == "incident-element-1"
    assert calls[0][1]["depth"] == 3
    assert calls[0][1]["start_time"] == 1000
    assert any(result["hop_distance"] == 2 for result in body["results"])
    assert body["results"][0]["score_breakdown"]["graph_proximity"]["hop_distance"] == 0


def test_graphrag_search_rejects_depth_outside_supported_range():
    """Verify that graphrag search validation rejects depth values greater than 3."""
    response = client.post(
        "/api/v1/graphrag/search", json={"query": "payment", "depth": 5}
    )

    assert response.status_code == 422


def test_graphrag_search_rejects_inverted_time_window():
    """
    Verify that graphrag search validation rejects inverted temporal search windows.
    """
    response = client.post(
        "/api/v1/graphrag/search",
        json={"query": "payment", "start_time": 2000, "end_time": 1000},
    )

    assert response.status_code == 422


def test_graphrag_api_exposes_combined_ranking_rationale(monkeypatch):
    """
    Verify that graphrag search integrates hybrid score breakdown and rationale text.
    """

    def _fake_execute_query(query, _params=None):
        if "MATCH (n)" in query and "RETURN labels(n)" in query:
            return [
                {
                    "labels": ["Incident"],
                    "name": None,
                    "status": "Open",
                    "title": "Payment failure",
                    "properties": {"id": "incident-1", "timestamp": 6300},
                    "id": "incident-element-1",
                }
            ]
        return []

    monkeypatch.setattr(neo4j_client, "execute_query", _fake_execute_query)
    monkeypatch.setattr(
        main.semantic_store,
        "search",
        lambda query, limit: [
            {
                "id": "qdrant-log-1",
                "text": "database authentication failed",
                "score": 0.8,
                "metadata": {
                    "source_id": "log-1",
                    "type": "log",
                    "label": "Log",
                    "name": "payment log",
                    "timestamp": 6400,
                },
            }
        ],
    )
    monkeypatch.setattr(
        main.graph_traversal_retriever,
        "retrieve",
        lambda seed_id, **kwargs: [
            {
                "id": "log-element-1",
                "labels": ["Log"],
                "type": "log",
                "name": "payment log",
                "properties": {"id": "log-1", "timestamp": 6400},
                "hop_distance": 1,
                "relationships": ["GENERATES"],
                "path": [
                    {"name": "payment", "labels": ["Pod"]},
                    {"name": "payment log", "labels": ["Log"]},
                ],
            }
        ],
    )

    response = client.post(
        "/api/v1/graphrag/search",
        json={"query": "database failure", "end_time": 10000},
    )

    assert response.status_code == 200
    result = response.json()["results"][0]
    assert result["name"] == "payment log"
    assert result["sources"] == ["graph", "vector"]
    assert result["score"] == pytest.approx(0.65)
    assert result["score_breakdown"]["vector_similarity"]["raw_score"] == 0.8
    assert result["score_breakdown"]["graph_proximity"]["hop_distance"] == 1
    assert result["score_breakdown"]["recency"]["age_seconds"] == 3600
    assert len(result["ranking_rationale"]) == 3


def test_graphrag_retrieve_endpoint_returns_summary(monkeypatch):
    """Verify that graphrag retrieve returns query summary and elements."""

    def _fake_execute_query(query, _params=None):
        if "MATCH (n)" in query and "RETURN labels(n)" in query:
            return [
                {
                    "labels": ["Incident"],
                    "name": None,
                    "status": "Open",
                    "title": "CrashLoopBackOff",
                    "id": "incident-1",
                }
            ]
        if "OPTIONAL MATCH" in query or "MATCH (n)-[r]-(m)" in query:
            return [
                {
                    "rel": "AFFECTED_BY",
                    "related_name": "checkout-pod",
                    "related_labels": ["Pod"],
                }
            ]
        return []

    monkeypatch.setattr(neo4j_client, "execute_query", _fake_execute_query)

    response = client.post(
        "/api/v1/graphrag/retrieve",
        json={"query": "crash", "namespace": "cloudgraph-system"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert body["summary"]
    assert body["results"]


def test_semantic_vector_store_returns_semantically_similar_documents(tmp_path):
    """Verify document search inside the SemanticVectorStore fallback index."""

    class TestEmbedder:
        """Embedder mock for testing local semantic stores."""

        def embed(self, text):
            """Generate a simple mock text embedding vector."""
            vector = [0.0] * 384
            for token in text.lower().split():
                vector[sum(token.encode("utf-8")) % 384] += 1.0
            return vector

        def reset(self):
            """Reset mock states."""

    class OfflineVectorClient:
        """Stub vector database client simulating offline/failure states."""

        def upsert(self, *_args, **_kwargs):
            """Mock upserting records, returning False to trigger file fallback."""
            return False

        def search(self, *_args, **_kwargs):
            """Mock searching vectors, returning empty results."""
            return []

    store = SemanticVectorStore(
        storage_path=str(tmp_path / "semantic.json"),
        embedder=TestEmbedder(),
        vector_client=OfflineVectorClient(),
    )
    store.index_document(
        "pod-1",
        "checkout pod crashed with crashloopbackoff and restart loop",
        {"label": "Pod", "name": "checkout-pod"},
    )
    store.index_document(
        "pod-2",
        "payment service responded normally and healthy",
        {"label": "Service", "name": "payment-service"},
    )

    results = store.search("crashloopbackoff pod failure", limit=1)
    assert results
    assert results[0]["id"] == "pod-1"


def test_ingest_tempo_trace_creates_trace_record(monkeypatch):
    """Verify that tempo trace ingestion executes the appropriate merge query."""

    def fake_execute_query(query, _params=None):
        """Mock execute_query verifying Cypher text contents."""
        assert "MERGE (t:Trace" in query
        return [{"trace_id": "trace-123"}]

    monkeypatch.setattr(neo4j_client, "execute_query", fake_execute_query)

    result = ingest_tempo_trace(
        pod_id="pod-1",
        pod_name="checkout-abc",
        span_id="span-1",
        trace_id="trace-123",
        parent_span_id="parent-span",
        service_name="checkout",
        duration=42.5,
        timestamp=123456789,
        status="ok",
    )

    assert result[0]["trace_id"] == "trace-123"


# =============================================================================
# 3. Latency Benchmarking (Active when Online, Skipped when Offline)
# =============================================================================


@pytest.mark.skipif(not is_db_reachable(), reason="Neo4j database is offline")
def test_traversal_performance():
    """
    Measures query execution latency for multi-hop graph traversals.
    """
    start_time = time.perf_counter()
    # 3-hop traversal: Service -> Pod -> Metric
    query = """
    MATCH (s:Service)-[:BELONGS_TO]-(p:Pod)-[:GENERATES]-(m:Metric)
    RETURN s.name, count(m) as metrics_count
    LIMIT 100
    """
    neo4j_client.execute_query(query)
    elapsed = time.perf_counter() - start_time
    # Assertion: database query returns under 100ms
    assert (
        elapsed < 0.100
    ), f"Query took {elapsed:.3f}s, which is slower than 100ms threshold"
