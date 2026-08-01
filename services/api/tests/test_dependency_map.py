"""Tests for service dependency mapping logic and fallback paths."""

import importlib.util
import os
import sys

# Load graph_constructor using absolute path
gc_path = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        "../app/adapters/graph_constructor.py",
    )
)
gc_spec = importlib.util.spec_from_file_location("graph_constructor", gc_path)
graph_constructor = importlib.util.module_from_spec(gc_spec)
sys.modules["graph_constructor"] = graph_constructor
gc_spec.loader.exec_module(graph_constructor)

build_service_dependency_map = graph_constructor.build_service_dependency_map


def test_dependency_map_traces_success(monkeypatch):
    """Test dependency builder when traces are present in database."""
    # Mock execute_query to return relationships on first (trace) query

    def mock_query(query, _params=None):
        if "t2.parentSpanId = t1.spanId" in query:
            return [{"relationships_created": 5}]
        return [{"relationships_created": 0}]

    monkeypatch.setattr(graph_constructor.neo4j_client, "execute_query", mock_query)

    created = build_service_dependency_map()
    assert created == 5


def test_dependency_map_env_variables_fallback(monkeypatch):
    """Test dependency builder falling back to environment variable match."""
    # Mock execute_query to return 0 on trace query, but 3 on env query

    def mock_query(query, _params=None):
        if "t2.parentSpanId = t1.spanId" in query:
            return [{"relationships_created": 0}]
        if "p1.env IS NOT NULL" in query:
            return [{"relationships_created": 3}]
        return [{"relationships_created": 0}]

    monkeypatch.setattr(graph_constructor.neo4j_client, "execute_query", mock_query)

    created = build_service_dependency_map()
    assert created == 3


def test_dependency_map_conventions_fallback(monkeypatch):
    """Test dependency builder falling back to service name conventions."""
    # Mock execute_query to return 0 on traces/env query, but 2 on convention query

    def mock_query(query, _params=None):
        if "t2.parentSpanId = t1.spanId" in query:
            return [{"relationships_created": 0}]
        if "p1.env IS NOT NULL" in query:
            return [{"relationships_created": 0}]
        if "s1.name CONTAINS" in query:
            return [{"relationships_created": 2}]
        return [{"relationships_created": 0}]

    monkeypatch.setattr(graph_constructor.neo4j_client, "execute_query", mock_query)

    created = build_service_dependency_map()
    assert created == 2
