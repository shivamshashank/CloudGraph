"""Tests for backend LLM settings and live log persistence API endpoints."""

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


def test_settings_endpoints(monkeypatch):
    """Test retrieving, saving, and clearing LLM settings."""
    if not is_db_reachable():
        mock_records = [
            {
                "provider": "openai",
                "api_key": "sk-12345",
                "model": "gpt-4o",
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
    if not is_db_reachable():
        mock_execute.return_value = [{"id": "llm_settings"}]

    payload = {
        "provider": "gemini",
        "api_key": "gemini-key",
        "model": "gemini-1.5-flash",
    }
    response = client.post("/api/v1/settings", json=payload)
    assert response.status_code == 200
    assert response.json()["status"] == "success"

    # 3. Test DELETE settings clear
    if not is_db_reachable():
        mock_execute.return_value = []

    response = client.delete("/api/v1/settings")
    assert response.status_code == 200
    assert response.json()["status"] == "success"


def test_logs_endpoints(monkeypatch):
    """Test retrieving, posting, and deleting live logs history."""
    if not is_db_reachable():
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
    if not is_db_reachable():
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
