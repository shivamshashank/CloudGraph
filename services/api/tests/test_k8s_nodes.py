"""Tests for advanced Kubernetes graph nodes ingestion endpoints."""

from unittest.mock import MagicMock
from fastapi.testclient import TestClient
from neo4j.exceptions import Neo4jError, ServiceUnavailable

from app.main import app
from app.database.neo4j_client import neo4j_client
from app.dependencies import semantic_store

client = TestClient(app)


def is_db_reachable():
    """Verify if the Neo4j database is reachable."""
    try:
        neo4j_client.execute_query("RETURN 1")
        return True
    except (RuntimeError, Neo4jError, ServiceUnavailable):
        return False


def test_tempo_trace_span_ingestion(monkeypatch):
    """Test trace spans and TraceSpan call tree logic ingestion."""
    # Mock Neo4j execute_query if database is unreachable
    if not is_db_reachable():
        mock_records = [{"trace_id": "test-trace-123"}]
        mock_execute = MagicMock(return_value=mock_records)
        monkeypatch.setattr(neo4j_client, "execute_query", mock_execute)

    # Mock Qdrant index_document
    mock_index = MagicMock()
    monkeypatch.setattr(semantic_store, "index_document", mock_index)

    payload = {
        "pod_id": "pod-123",
        "pod_name": "auth-service-pod",
        "span_id": "span-abc",
        "trace_id": "trace-123",
        "parent_span_id": "span-xyz",
        "service_name": "auth-service",
        "duration": 12.5,
        "timestamp": 1751302800,
        "status": "success",
    }
    response = client.post("/api/v1/telemetry/traces", json=payload)
    assert response.status_code == 200
    assert response.json()["status"] == "success"
    assert mock_index.called


def test_security_event_ingestion(monkeypatch):
    """Test security event route maps event and indexes in vector store."""
    if not is_db_reachable():
        mock_records = [{"event_id": "event-123"}]
        mock_execute = MagicMock(return_value=mock_records)
        monkeypatch.setattr(neo4j_client, "execute_query", mock_execute)

    mock_index = MagicMock()
    monkeypatch.setattr(semantic_store, "index_document", mock_index)

    payload = {
        "event_id": "evt-falco-456",
        "pod_id": "pod-123",
        "pod_name": "payment-pod",
        "rule": "Write below binary dir",
        "priority": "Critical",
        "output": "File written under /bin/sh",
        "timestamp": 1751302805,
        "service_account": "payment-sa",
    }
    response = client.post("/api/v1/telemetry/security", json=payload)
    assert response.status_code == 200
    assert response.json()["status"] == "success"
    assert response.json()["event_id"] is not None
    assert mock_index.called


def test_chaos_experiment_ingestion(monkeypatch):
    """Test chaos experiment route maps event and indexes in vector store."""
    if not is_db_reachable():
        mock_records = [{"experiment_id": "chaos-123"}]
        mock_execute = MagicMock(return_value=mock_records)
        monkeypatch.setattr(neo4j_client, "execute_query", mock_execute)

    mock_index = MagicMock()
    monkeypatch.setattr(semantic_store, "index_document", mock_index)

    payload = {
        "experiment_id": "chaos-litmus-789",
        "name": "pod-network-latency",
        "target_pod_name": "payment-pod",
        "action": "pod-network-delay",
        "status": "InjectionStarted",
        "timestamp": 1751302810,
    }
    response = client.post("/api/v1/telemetry/chaos", json=payload)
    assert response.status_code == 200
    assert response.json()["status"] == "success"
    assert response.json()["experiment_id"] is not None
    assert mock_index.called
