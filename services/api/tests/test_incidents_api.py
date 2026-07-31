"""Tests for backend incident and comments persistence API endpoints."""

import time
from unittest.mock import MagicMock
from fastapi.testclient import TestClient
from neo4j.exceptions import Neo4jError, ServiceUnavailable

from app.main import app
from app.database.neo4j_client import neo4j_client

client = TestClient(app)


def is_db_reachable():
    """Verify if the live Neo4j database is reachable."""
    try:
        neo4j_client.execute_query("RETURN 1")
        return True
    except (RuntimeError, Neo4jError, ServiceUnavailable):
        return False


def test_incidents_endpoints(monkeypatch):
    """Test incident creation, retrieval, patching, and comments endpoints."""
    # If DB is not reachable, mock execute_query
    if not is_db_reachable():
        mock_records = [
            {
                "id": "inc-1",
                "title": "Test Anomaly",
                "severity": "HIGH",
                "status": "Active",
                "cause": "Mock cause",
                "remediation": "Mock remediation",
                "timestamp": int(time.time()),
                "assigned": "SRE Team",
                "error_logs": ["err1", "err2"],
                "pod_name": "test-pod",
            }
        ]
        mock_execute = MagicMock(return_value=mock_records)
        monkeypatch.setattr(neo4j_client, "execute_query", mock_execute)

    # 1. Test GET incidents
    response = client.get("/api/v1/incidents")
    assert response.status_code == 200
    assert response.json()["status"] == "success"
    assert "incidents" in response.json()

    # 2. Test POST incident creation
    if not is_db_reachable():
        mock_execute.return_value = [{"id": "new-incident-123"}]

    payload = {
        "title": "Manual Test Incident",
        "severity": "CRITICAL",
        "status": "Active",
        "cause": "Manual test trigger",
        "remediation": "Fix password",
        "assigned": "Unassigned",
        "error_logs": ["wrong credentials"],
    }
    response = client.post("/api/v1/incidents", json=payload)
    assert response.status_code == 200
    assert response.json()["status"] == "success"
    assert "id" in response.json()

    # 3. Test PATCH incident update
    incident_id = response.json()["id"]
    if not is_db_reachable():
        # First query checks current state: status and assigned
        # Second query updates
        # Third query adds system comments
        # Fourth query adds system comments
        mock_execute.side_effect = [
            [{"status": "Active", "assigned": "Unassigned"}],
            [{"id": incident_id}],
            [],
            [],
        ]

    update_payload = {"status": "Investigating", "assigned": "SRE Team"}
    response = client.patch(f"/api/v1/incidents/{incident_id}", json=update_payload)
    assert response.status_code == 200
    assert response.json()["status"] == "success"

    # 4. Test POST comment
    if not is_db_reachable():
        mock_execute.side_effect = None
        mock_execute.return_value = [{"id": incident_id}]

    comment_payload = {"author": "Lead Triage Analyst", "text": "This is a note"}
    response = client.post(
        f"/api/v1/incidents/{incident_id}/comments", json=comment_payload
    )
    assert response.status_code == 200
    assert response.json()["status"] == "success"

    # 5. Test GET comments
    if not is_db_reachable():
        mock_execute.return_value = [
            {
                "author": "Lead Triage Analyst",
                "text": "This is a note",
                "timestamp": int(time.time() * 1000),
            }
        ]
    response = client.get(f"/api/v1/incidents/{incident_id}/comments")
    assert response.status_code == 200
    assert response.json()["status"] == "success"
    assert "comments" in response.json()
