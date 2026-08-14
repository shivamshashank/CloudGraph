"""Regression tests for benchmark scenario isolation in the vector store.

The evaluation treats each scenario as an independent trial, which is only
true if retrieval returns that scenario's evidence and nothing else. It did
not: the Qdrant collection is one global namespace that outlives the API
pod, teardown could only delete point ids the current process had in
memory, and search took no scenario filter. A full 18-scenario run was
produced in which every raw-context request carried 82 evidence items drawn
from scenarios that had never been run, invalidating the retrieval ablation
and the GPCS scores together.

These tests pin the three properties that make that impossible to repeat.
"""

import types

import pytest
from neo4j.exceptions import ServiceUnavailable

from app.demo import seeding
from app.research import evaluation
from app.research import report_runner
from app.services.semantic_store import SemanticVectorStore, _scenario_filter


def _doc(doc_id: str, scenario_id: str, text: str) -> dict:
    return {
        "id": doc_id,
        "text": text,
        "embedding": [1.0, 0.0, 0.0],
        "metadata": {"is_benchmark": True, "scenario_id": scenario_id},
        "hash": doc_id,
    }


@pytest.fixture(name="store")
def _store(monkeypatch) -> SemanticVectorStore:
    """A store whose vector backend is offline, exercising the fallback
    path — the one that silently reintroduced contamination when only the
    Qdrant filter was added."""
    store = SemanticVectorStore.__new__(SemanticVectorStore)
    store.documents = [
        _doc("log-a", "rcaeval-01", "checkoutservice cpu saturation"),
        _doc("log-b", "rcaeval-08", "cartservice cpu saturation"),
    ]
    monkeypatch.setattr(
        store, "_embed", lambda _text: ([1.0, 0.0, 0.0], "hashed-fallback")
    )
    return store


def test_search_scoped_to_scenario_excludes_other_scenarios(store):
    """The core guarantee: another scenario's evidence is never returned,
    however similar it is to the query."""
    results = store.search("cpu saturation", limit=10, scenario_id="rcaeval-01")

    assert results, "the scenario's own evidence must still be retrievable"
    assert {r["id"] for r in results} == {"log-a"}


def test_unscoped_search_still_returns_everything(store):
    """Production search is unscoped and must keep working — the filter is
    an evaluation-time restriction, not a change to the product."""
    results = store.search("cpu saturation", limit=10)

    assert {r["id"] for r in results} == {"log-a", "log-b"}


def test_scenario_filter_is_none_when_unscoped():
    """A None scenario must produce no Qdrant filter at all, rather than a
    filter that matches nothing."""
    assert _scenario_filter(None) is None
    assert _scenario_filter("rcaeval-01") is not None


def test_isolation_assertion_raises_on_foreign_residue(monkeypatch):
    """Residue left by an earlier process must abort the run.

    Simulates exactly the real failure: points that this process never
    seeded and cannot delete, sitting in the collection at seed time."""

    residue = types.SimpleNamespace(
        scroll=lambda **_kwargs: ([{"id": "left-over-from-a-previous-run"}], None)
    )
    monkeypatch.setattr(seeding.qdrant_client, "connect", lambda: True)
    monkeypatch.setattr(seeding.qdrant_client, "client", residue)
    monkeypatch.setattr(seeding.qdrant_client, "collection_names", ("evidence",))

    with pytest.raises(seeding.SemanticStoreNotIsolatedError, match="rcaeval-01"):
        seeding.assert_semantic_store_isolated("rcaeval-01")


def test_isolation_assertion_passes_on_clean_store(monkeypatch):
    """A store holding only this scenario's evidence must not raise."""

    clean = types.SimpleNamespace(scroll=lambda **_kwargs: ([], None))
    monkeypatch.setattr(seeding.qdrant_client, "connect", lambda: True)
    monkeypatch.setattr(seeding.qdrant_client, "client", clean)
    monkeypatch.setattr(seeding.qdrant_client, "collection_names", ("evidence",))
    # Passing the vector check falls through to the graph check, which would
    # open a real Bolt connection. driver is pinned as well as execute_query:
    # it is created lazily, so whether it is None depends on test order in the
    # worker. Unpinned, this either passes for the wrong reason or dials a real
    # server, which is how it reached CI.
    monkeypatch.setattr(seeding.neo4j_client, "driver", object())
    monkeypatch.setattr(
        seeding.neo4j_client, "execute_query", lambda *_a, **_k: [{"foreign": 0}]
    )

    seeding.assert_semantic_store_isolated("rcaeval-01")


def test_teardown_runs_even_when_isolation_check_fails(monkeypatch):
    """An isolation failure must still tear down what it just seeded.

    The assertion fires *after* seeding, so raising before the try/finally
    left this scenario's evidence in the store — the failure would strand
    exactly the data it was complaining about and contaminate whatever ran
    next, turning one loud abort into silent contamination downstream."""
    torn_down = []
    monkeypatch.setattr(report_runner, "seed_scenario_data", lambda _s: None)
    monkeypatch.setattr(
        report_runner, "teardown_benchmark_data", lambda: torn_down.append(True)
    )
    monkeypatch.setattr(report_runner, "purge_semantic_store", lambda: 0)
    monkeypatch.setattr(report_runner.qdrant_client, "ensure_collections", lambda: True)

    def _raise(_scenario_id):
        raise seeding.SemanticStoreNotIsolatedError("residue")

    monkeypatch.setattr(report_runner, "assert_semantic_store_isolated", _raise)

    with pytest.raises(seeding.SemanticStoreNotIsolatedError):
        report_runner.generate_report(scenario_limit=1)

    assert torn_down == [True], "teardown must run despite the isolation failure"


def test_purge_refuses_to_touch_a_live_evidence_collection(monkeypatch):
    """The purge deletes every point it touches, so it must be structurally
    incapable of pointing at the collection serving real traffic."""
    monkeypatch.setattr(seeding.qdrant_client, "connect", lambda: True)
    monkeypatch.setattr(seeding.qdrant_client, "collection_names", ("evidence",))
    # Misconfiguration: the "evaluation" collection is in fact the live one.
    monkeypatch.setattr(seeding.qdrant_client, "eval_collection_name", "evidence")
    monkeypatch.setattr(seeding.semantic_store, "documents", [])
    monkeypatch.setattr(seeding.semantic_store, "persist", lambda: None)

    with pytest.raises(RuntimeError, match="refusing to purge"):
        seeding.purge_semantic_store()


def test_purge_targets_only_the_evaluation_collection(monkeypatch):
    """The live collection must never appear in a delete call."""
    deleted = []
    client = types.SimpleNamespace(
        get_collection=lambda name: types.SimpleNamespace(points_count=0),
        delete=lambda **kwargs: deleted.append(kwargs["collection_name"]),
    )
    monkeypatch.setattr(seeding.qdrant_client, "connect", lambda: True)
    monkeypatch.setattr(seeding.qdrant_client, "client", client)
    monkeypatch.setattr(
        seeding.qdrant_client, "collection_names", ("evidence", "evidence_eval")
    )
    monkeypatch.setattr(seeding.qdrant_client, "eval_collection_name", "evidence_eval")
    monkeypatch.setattr(seeding.semantic_store, "documents", [])
    monkeypatch.setattr(seeding.semantic_store, "persist", lambda: None)

    seeding.purge_semantic_store()

    assert deleted == ["evidence_eval"]
    assert "evidence" not in deleted


def test_keyword_search_is_scenario_scoped():
    """Keyword retrieval must filter on scenario_id in the query itself.

    Previously it matched every benchmark node in the graph and was
    correct only because teardown deletes them all globally — an invariant
    owned by a different function, which is the same shape as the vector
    contamination bug."""
    captured = {}

    def _fake_execute(query, params=None):
        captured["query"] = query
        captured["params"] = params or {}
        return []

    original = evaluation.neo4j_client.execute_query
    evaluation.neo4j_client.execute_query = _fake_execute
    try:
        evaluation.run_keyword_search("cpu saturation", scenario_id="rcaeval-01")
    finally:
        evaluation.neo4j_client.execute_query = original

    assert "n.scenario_id = $scenario_id" in captured["query"]
    assert captured["params"].get("scenario_id") == "rcaeval-01"


def test_graph_isolation_assertion_raises_on_foreign_benchmark_nodes(monkeypatch):
    """Benchmark nodes from another scenario must abort the run, the same
    way foreign vector points do."""
    monkeypatch.setattr(
        seeding.neo4j_client, "execute_query", lambda *_a, **_k: [{"foreign": 4}]
    )
    with pytest.raises(seeding.SemanticStoreNotIsolatedError, match="graph holds 4"):
        seeding.assert_graph_isolated("rcaeval-01")


def test_isolation_fails_loudly_when_the_graph_cannot_be_checked(monkeypatch):
    """Being unable to verify isolation is not the same as being isolated.

    A driver that exists but cannot reach the server raises ServiceUnavailable
    out of session.run, which is not an OSError — narrow except clauses let it
    escape as an unhandled traceback mid-run. It must surface as the same
    fatal, explicable error as real contamination."""

    def _unreachable(*_args, **_kwargs):
        raise ServiceUnavailable("connection refused")

    monkeypatch.setattr(seeding.neo4j_client, "driver", object())
    monkeypatch.setattr(seeding.neo4j_client, "execute_query", _unreachable)

    with pytest.raises(seeding.SemanticStoreNotIsolatedError, match="could not verify"):
        seeding.assert_graph_isolated("rcaeval-01")


def test_graph_isolation_raises_on_foreign_nodes(monkeypatch):
    """Benchmark nodes belonging to another scenario must stop the run."""
    monkeypatch.setattr(seeding.neo4j_client, "driver", object())
    monkeypatch.setattr(
        seeding.neo4j_client, "execute_query", lambda *_a, **_k: [{"foreign": 7}]
    )

    with pytest.raises(seeding.SemanticStoreNotIsolatedError, match="graph holds 7"):
        seeding.assert_graph_isolated("rcaeval-01")
