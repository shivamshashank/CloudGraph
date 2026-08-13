"""Tests for advanced Kubernetes graph nodes ingestion endpoints."""

from types import SimpleNamespace
from unittest.mock import MagicMock
from fastapi.testclient import TestClient
from neo4j.exceptions import Neo4jError, ServiceUnavailable

from app.adapters.k8s_discovery import _resolve_pod_status
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


# --- pod status resolution ------------------------------------------------
#
# `_resolve_pod_status` used to return the first terminated reason it found
# across the main *and* init container lists, without checking the exit code.
# Every pod with an init container therefore reported "Completed" instead of
# "Running": the topology drew healthy pods red, and the log view keyed off
# that status to fabricate crash/OOM lines for them.


def _container(waiting=None, terminated=None):
    """A container *status* — what `container_statuses` holds, wrapping a state."""
    return SimpleNamespace(
        state=SimpleNamespace(waiting=waiting, terminated=terminated)
    )


def _waiting(reason):
    """A waiting container state with the given reason."""
    return SimpleNamespace(reason=reason)


def _terminated(reason, exit_code):
    """A terminated container state; exit_code 0 means it succeeded."""
    return SimpleNamespace(reason=reason, exit_code=exit_code)


def _pod(phase, containers=None, init_containers=None):
    """A pod whose status is what `_resolve_pod_status` reads."""
    return SimpleNamespace(
        status=SimpleNamespace(
            phase=phase,
            container_statuses=containers,
            init_container_statuses=init_containers,
        )
    )


def test_successful_init_container_does_not_mask_running_phase():
    """The regression: an init container exiting 0 must not read as Completed."""
    pod = _pod(
        phase="Running",
        containers=[_container()],
        init_containers=[_container(terminated=_terminated("Completed", 0))],
    )
    assert _resolve_pod_status(pod) == "Running"


def test_failed_init_container_is_surfaced():
    """A non-zero init container exit is a genuine fault and must surface."""
    pod = _pod(
        phase="Pending",
        init_containers=[_container(terminated=_terminated("Error", 1))],
    )
    assert _resolve_pod_status(pod) == "Error"


def test_image_pull_failure_still_overrides_running_phase():
    """A stuck container must still beat the pod phase."""
    pod = _pod(
        phase="Running",
        containers=[_container(waiting=_waiting("ImagePullBackOff"))],
    )
    assert _resolve_pod_status(pod) == "ImagePullBackOff"


def test_benign_startup_waiting_reasons_are_not_faults():
    """Normal start-up states must not be reported as failures."""
    pod = _pod(
        phase="Pending",
        containers=[_container(waiting=_waiting("PodInitializing"))],
    )
    assert _resolve_pod_status(pod) == "Pending"


def test_completed_job_pod_still_reports_succeeded():
    """A Job's main container exits 0; the phase, not "Completed", wins."""
    pod = _pod(
        phase="Succeeded",
        containers=[_container(terminated=_terminated("Completed", 0))],
    )
    assert _resolve_pod_status(pod) == "Succeeded"
