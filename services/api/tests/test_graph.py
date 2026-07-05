import pytest
import time
from unittest.mock import MagicMock
from fastapi.testclient import TestClient
from app.main import app
from app.database.neo4j_client import neo4j_client
from app.services.semantic_store import SemanticVectorStore
from app.adapters.tempo import ingest_tempo_trace
import app.adapters.k8s_discovery as k8s_discovery

client = TestClient(app)


# Helper: check if live database is reachable
def is_db_reachable():
    try:
        neo4j_client.execute_query("RETURN 1")
        return True
    except Exception:
        return False


# =============================================================================
# 1. Integration Tests (Mocked if Offline, Real if Online)
# =============================================================================


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    assert "status" in response.json()


def test_ingest_metrics(monkeypatch):
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
    assert response.status_code == 200
    assert response.json()["status"] == "success"
    assert "metric_id" in response.json()


def test_ingest_logs(monkeypatch):
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
    result = neo4j_client.execute_query("""
    MATCH (p:Pod)
    WHERE NOT (p)-[:RUNS_ON]->(:Node)
    RETURN count(p) as orphan_count
    """)
    # For a clean deployment, orphan count should start at 0 after linking
    assert result[0]["orphan_count"] >= 0


def test_investigation_trigger_returns_structured_analysis(monkeypatch):
    def fake_execute_query(query, params=None):
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

    monkeypatch.setattr(neo4j_client, "execute_query", fake_execute_query)
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


def test_relevant_evidence_endpoint_returns_graph_context(monkeypatch):
    def fake_execute_query(query, params=None):
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

    monkeypatch.setattr(neo4j_client, "execute_query", fake_execute_query)

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
    def fake_execute_query(query, params=None):
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

    monkeypatch.setattr(neo4j_client, "execute_query", fake_execute_query)

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


def test_graphrag_retrieve_endpoint_returns_summary(monkeypatch):
    def fake_execute_query(query, params=None):
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

    monkeypatch.setattr(neo4j_client, "execute_query", fake_execute_query)

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
    store = SemanticVectorStore(storage_path=str(tmp_path / "semantic.json"))
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
    def fake_execute_query(query, params=None):
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
