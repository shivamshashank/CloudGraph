"""Tests for backend LLM settings and live log persistence API endpoints."""

from unittest.mock import MagicMock
from fastapi.testclient import TestClient

from app.main import app
from app.database.neo4j_client import neo4j_client

client = TestClient(app)


def test_settings_endpoints(monkeypatch):
    """Test retrieving, saving, and clearing LLM settings.

    Always mocks neo4j_client.execute_query, regardless of whether a live
    Neo4j happens to be reachable — these endpoints write to a singleton
    Settings node (id="llm_settings"), the same one a developer's real
    Settings UI configuration lives in. Running this test's POST/DELETE
    for real against a live dev database previously overwrote and then
    deleted a real, live-configured provider/key/model.
    """
    mock_records = [
        {
            "provider": "openai",
            "api_key": "sk-test-key",
            "model": "gpt-4o-mini",
        }
    ]
    mock_execute = MagicMock(return_value=mock_records)
    monkeypatch.setattr(neo4j_client, "execute_query", mock_execute)

    # 1. Test GET settings
    response = client.get("/api/v1/settings")
    assert response.status_code == 200
    assert response.json()["status"] == "success"
    assert "settings" in response.json()

    # 2. Test POST settings save
    mock_execute.return_value = [{"id": "llm_settings"}]
    payload = {
        "provider": "gemini",
        "api_key": "test-key",
        "model": "gemini-1.5-flash",
    }
    response = client.post("/api/v1/settings", json=payload)
    assert response.status_code == 200
    assert response.json()["status"] == "success"

    # 3. Test DELETE settings clear
    mock_execute.return_value = []
    response = client.delete("/api/v1/settings")
    assert response.status_code == 200
    assert response.json()["status"] == "success"


def test_logs_endpoints(monkeypatch):
    """Test retrieving, posting, and deleting live logs history.

    Always mocks neo4j_client.execute_query — see test_settings_endpoints
    for why running this for real against a live dev database is unsafe
    (here it would bulk-delete every real LiveLog node).
    """
    mock_records = [
        {
            "timestamp": "2026-07-19 14:00:00",
            "source": "api",
            "level": "info",
            "message": "Scraped metrics successfully",
            "created_at": 1751302800,
        }
    ]
    mock_execute = MagicMock(return_value=mock_records)
    monkeypatch.setattr(neo4j_client, "execute_query", mock_execute)

    # 1. Test GET logs
    response = client.get("/api/v1/logs")
    assert response.status_code == 200
    assert response.json()["status"] == "success"
    assert "logs" in response.json()

    # 2. Test POST log entry
    mock_execute.return_value = []
    payload = {
        "timestamp": "2026-07-19 14:01:00",
        "source": "api",
        "level": "error",
        "message": "Database query timeout",
    }
    response = client.post("/api/v1/logs", json=payload)
    assert response.status_code == 200
    assert response.json()["status"] == "success"

    # 3. Test DELETE logs clear
    response = client.delete("/api/v1/logs")
    assert response.status_code == 200
    assert response.json()["status"] == "success"
