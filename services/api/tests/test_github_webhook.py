"""Tests for raw GitHub webhook payload parsing and ingestion."""

from unittest.mock import patch
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


@patch("app.routers.webhooks.ingest_git_commit")
@patch("app.routers.webhooks.semantic_store.index_document")
def test_github_webhook_push_event(mock_index, mock_ingest):
    """Test raw GitHub push event ingestion with multiple commits."""
    mock_ingest.return_value = [{"sha": "a1b2c3d4e5f6"}]

    payload = {
        "ref": "refs/heads/main",
        "repository": {"name": "billing-service"},
        "pusher": {"name": "alice"},
        "commits": [
            {
                "id": "a1b2c3d4e5f6",
                "message": "fix: update db connection pool",
                "author": {"name": "Alice Developer"},
                "added": ["config/db.json"],
                "modified": ["src/db.py"],
                "removed": [],
            }
        ],
    }

    response = client.post("/api/v1/webhook/github", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["repository"] == "billing-service"
    assert data["commits_ingested"] == 1
    assert data["shas"] == ["a1b2c3d4e5f6"]

    mock_ingest.assert_called_once()
    mock_index.assert_called_once()


@patch("app.routers.webhooks.ingest_git_commit")
@patch("app.routers.webhooks.semantic_store.index_document")
def test_github_webhook_alias_endpoint(mock_index, mock_ingest):
    """Test /api/v1/webhooks/github alias route with head_commit payload."""
    mock_ingest.return_value = [{"sha": "f6e5d4c3b2a1"}]

    payload = {
        "repository": {"name": "auth-service"},
        "head_commit": {
            "id": "f6e5d4c3b2a1",
            "message": "feat: add OAuth2 refresh token strategy",
            "author": {"name": "Bob SRE"},
            "added": ["src/auth.py"],
            "modified": [],
            "removed": [],
        },
    }

    response = client.post("/api/v1/webhooks/github", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["repository"] == "auth-service"
    assert data["commits_ingested"] == 1
    assert data["shas"] == ["f6e5d4c3b2a1"]

    mock_ingest.assert_called_once()
    mock_index.assert_called_once()
