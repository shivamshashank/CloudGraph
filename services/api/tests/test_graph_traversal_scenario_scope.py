"""The multi-hop traversal must be scopeable to a single benchmark scenario.

Until this was added, only the vector search and the harness's own Cypher
carried a ``scenario_id`` predicate: the traversal that expands outward from a
seed carried none, so a path could in principle route through another
scenario's evidence. Isolation rested entirely on the store holding one
scenario at a time.

These tests use a fake client and assert on the emitted Cypher and parameters.
They do not exercise a live Neo4j instance.
"""

import pytest

from app.retrieval.graph_traversal import GraphTraversalRetriever


class _FakeClient:  # pylint: disable=too-few-public-methods
    """Captures the query and parameters instead of executing them."""

    def __init__(self):
        self.query = None
        self.params = None

    def execute_query(self, query, params):
        """Record the call and return no rows."""
        self.query = query
        self.params = params
        return []


@pytest.fixture(name="client")
def _client():
    return _FakeClient()


@pytest.fixture(name="retriever")
def _retriever(client):
    return GraphTraversalRetriever(client=client)


def test_scenario_id_is_bound_as_a_parameter(retriever, client):
    """The id must travel as a parameter, never interpolated into the Cypher."""
    retriever.retrieve("incident-1", scenario_id="rcaeval-03")

    assert client.params["scenario_id"] == "rcaeval-03"
    assert "rcaeval-03" not in client.query, "scenario_id must not be interpolated"


def test_seed_is_constrained_to_the_scenario(retriever, client):
    """The seed node itself must belong to the scenario."""
    retriever.retrieve("incident-1", scenario_id="rcaeval-03")

    assert "seed.scenario_id = $scenario_id" in client.query


def test_every_path_node_is_constrained_to_the_scenario(retriever, client):
    """A path must not route through another scenario's nodes."""
    retriever.retrieve("incident-1", scenario_id="rcaeval-03")

    assert "path_node.scenario_id = $scenario_id" in client.query


def test_predicates_are_null_guarded_so_unscoped_traversal_is_unchanged(
    retriever, client
):
    """``None`` must disable both predicates.

    Experiment 2 discovers nodes from a live cluster; those carry no
    ``scenario_id``, so an unguarded equality would return nothing.
    """
    retriever.retrieve("incident-1", scenario_id=None)

    assert client.params["scenario_id"] is None
    assert client.query.count("$scenario_id IS NULL OR") == 2


def test_unscoped_call_emits_the_same_query_as_a_scoped_one(retriever, client):
    """The predicate is always present; only the bound value differs.

    This is what makes the addition safe for the already completed evaluation: the
    query text does not branch, so a scoped run and an unscoped run differ
    only in whether the guard short-circuits.
    """
    retriever.retrieve("incident-1", scenario_id=None)
    unscoped = client.query
    retriever.retrieve("incident-1", scenario_id="rcaeval-03")

    assert client.query == unscoped


def test_default_is_unscoped(retriever, client):
    """Callers that do not opt in keep the previous behaviour."""
    retriever.retrieve("incident-1")

    assert client.params["scenario_id"] is None
