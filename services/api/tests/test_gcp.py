"""Unit tests for the Graph Confidence Propagation (GCP) research algorithm."""

import pytest

from app.database.neo4j_client import neo4j_client
from app.research.gcp import GraphConfidencePropagator


def test_gcp_initial_confidence_assignment():
    """Verify that GCP assigns correct initial confidences based on telemetry labels."""
    propagator = GraphConfidencePropagator()

    # Log node confidences
    assert (
        propagator.assign_initial_confidence(["Log"], {"message": "oom killed"}) == 0.95
    )
    assert (
        propagator.assign_initial_confidence(
            ["Log"], {"message": "database connection failure"}
        )
        == 0.85
    )

    # Metric node confidences
    assert (
        propagator.assign_initial_confidence(
            ["Metric"], {"name": "cpu_utilization", "value": 85.0}
        )
        == 0.85
    )
    assert (
        propagator.assign_initial_confidence(
            ["Metric"], {"name": "memory_utilization", "value": 95.0}
        )
        == 0.90
    )

    # Fallback/Custom confidence
    assert propagator.assign_initial_confidence(["Pod"], {"confidence": 0.42}) == 0.42
    assert propagator.assign_initial_confidence(["Pod"], {}) == 0.0


def test_gcp_adjacency_builder():
    """Verify that GCP correctly constructs bidirectional adjacency map from edges."""
    propagator = GraphConfidencePropagator()
    edges = [
        {"start_id": "a", "end_id": "b", "type": "BELONGS_TO"},
        {"start_id": "b", "end_id": "c", "type": "CALLS"},
    ]
    adj = propagator.build_adjacency_map(edges)
    assert ("b", "BELONGS_TO") in adj["a"]
    assert ("a", "BELONGS_TO") in adj["b"]
    assert ("c", "CALLS") in adj["b"]
    assert ("b", "CALLS") in adj["c"]


def test_gcp_propagation_noisy_or_math(monkeypatch):
    """Verify that BFS propagation decays scores and performs Noisy-OR combinations."""
    propagator = GraphConfidencePropagator(max_depth=2, decay_factor=1.0)

    nodes_mock = [
        {"id": "pod-1", "labels": ["Pod"], "props": {"name": "test-pod"}},
        {"id": "log-1", "labels": ["Log"], "props": {"message": "oom killed"}},
        {
            "id": "metric-1",
            "labels": ["Metric"],
            "props": {"name": "cpu", "value": 90.0},
        },
    ]
    edges_mock = [
        {"start_id": "log-1", "end_id": "pod-1", "type": "GENERATES"},
        {"start_id": "metric-1", "end_id": "pod-1", "type": "GENERATES"},
    ]

    monkeypatch.setattr(neo4j_client, "driver", True)

    def mock_query(query, _params=None):
        if "MATCH (p:Pod {name: $pod_name})-[*0..3]-(n)" in query:
            return nodes_mock
        if "MATCH (p:Pod {name: $pod_name})-[*0..3]-(a)-[r]-(b)" in query:
            return edges_mock
        return []

    monkeypatch.setattr(neo4j_client, "execute_query", mock_query)

    res = propagator.run_propagation("test-pod")

    # Initial confidences:
    # log-1: 0.95
    # metric-1: 0.85
    # Path log-1 -> pod-1: 0.95 * GENERATES (0.95) = 0.9025
    # Path metric-1 -> pod-1: 0.85 * GENERATES (0.95) = 0.8075
    # Noisy-OR combined confidence at pod-1:
    # 1 - (1 - 0.9025) * (1 - 0.8075) = 1 - 0.0975 * 0.1925
    # = 1 - 0.01876875 = 0.98123125
    assert res["root_cause"] == pytest.approx(0.98, abs=0.01)
    assert res["recommendation"] == pytest.approx(0.98 * 0.90, abs=0.01)
