"""Tests verifying the multi-hop Cypher-based graph traversal retriever."""

import pytest

from app.retrieval.graph_traversal import GraphTraversalRetriever


class RecordingNeo4jClient:
    """Mock Neo4j client recording execution queries for checking parameters."""

    def __init__(self, rows=None):
        self.rows = rows or []
        self.calls = []

    def execute_query(self, query, parameters=None):
        """Record and return stub query response."""
        self.calls.append((query, parameters))
        return self.rows

    def reset(self):
        """Clear query call records."""
        self.calls.clear()


def test_traversal_expands_allowed_relationships_to_configured_depth():
    """
    Verify that retrieval maps target relationships and depth values
    correctly into Cypher.
    """
    client = RecordingNeo4jClient(
        [
            {
                "id": "log-1",
                "labels": ["Log"],
                "properties": {
                    "id": "log-1",
                    "message": "database authentication failed",
                    "timestamp": 1050,
                },
                "hop_distance": 2,
                "relationships": ["AFFECTED_BY", "GENERATES"],
                "path": [
                    {"id": "incident-1", "labels": ["Incident"], "name": "failure"},
                    {"id": "pod-1", "labels": ["Pod"], "name": "payment"},
                    {"id": "log-1", "labels": ["Log"], "name": "auth failed"},
                ],
            }
        ]
    )
    retriever = GraphTraversalRetriever(client=client)

    results = retriever.retrieve("incident-1", depth=3, limit=25)

    query, params = client.calls[0]
    assert "*1..3" in query
    assert "BELONGS_TO|RUNS_ON|MANAGES|GENERATES|AFFECTED_BY" in query
    assert params["seed_id"] == "incident-1"
    assert params["limit"] == 25
    assert results[0]["hop_distance"] == 2
    assert results[0]["type"] == "log"
    assert results[0]["relationships"] == ["AFFECTED_BY", "GENERATES"]


def test_temporal_filter_uses_explicit_or_incident_derived_window():
    """Verify that start_time, end_time, or default windows are populated correctly."""
    client = RecordingNeo4jClient()
    retriever = GraphTraversalRetriever(client=client, default_window_seconds=1800)

    retriever.retrieve("incident-1", start_time=1000, end_time=2000)

    _, params = client.calls[0]
    assert params["start_time"] == 1000
    assert params["end_time"] == 2000
    assert params["window_seconds"] == 1800


@pytest.mark.parametrize("depth", [0, 5])
def test_traversal_rejects_unsafe_depth_before_query(depth):
    """
    Verify that retrieval requests validation triggers ValueError on
    out of bounds depths.
    """
    client = RecordingNeo4jClient()
    retriever = GraphTraversalRetriever(client=client)

    with pytest.raises(ValueError, match="depth must be between"):
        retriever.retrieve("incident-1", depth=depth)

    assert not client.calls


def test_traversal_rejects_inverted_time_window():
    """
    Verify that start_time exceeding end_time triggers ValueError validation failure.
    """
    retriever = GraphTraversalRetriever(client=RecordingNeo4jClient())

    with pytest.raises(ValueError, match="start_time"):
        retriever.retrieve("incident-1", start_time=2000, end_time=1000)
