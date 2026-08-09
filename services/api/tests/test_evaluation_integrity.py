"""Guards for evaluation-integrity fixes.

Each test here pins a specific way the benchmark could silently report
something it never measured. All three failure modes below were live in
the pipeline at one point, and none of them announced themselves — they
just produced plausible numbers.
"""

import math

import pytest

from app.demo.datasets import DEFAULT_INCIDENT_TIME, scenario_incident_time
from app.demo.seeding import LOG_INTERVAL_SECONDS
from app.research import evaluation
from app.research.gcp import GraphConfidencePropagator, GraphUnavailableError
from app.retrieval.hybrid_ranker import hybrid_ranker


class TestIncidentTime:
    """Seeding and retrieval must derive the same reference time."""

    def test_real_inject_time_preferred(self):
        """RCAEval scenarios carry the real chaos-injection timestamp."""
        scenario = {"id": "x", "inject_time": 1705354566}
        assert scenario_incident_time(scenario) == 1705354566

    def test_falls_back_to_fixed_constant(self):
        """Authored scenarios carry no real injection time; the fallback
        must be fixed so runs stay reproducible."""
        assert scenario_incident_time({"id": "x"}) == DEFAULT_INCIDENT_TIME


class TestRecencyIsDiscriminative:
    """The hybrid score advertises three signals. If seeded evidence all
    shares one timestamp, recency is constant and the score silently
    collapses to two — which would hollow out any retrieval ablation."""

    def test_staggered_timestamps_produce_distinct_recency(self):
        """Every seeded entry must land on its own recency score."""
        half_life = hybrid_ranker.recency_half_life_seconds
        n_entries = 5
        scores = {
            math.exp(
                -math.log(2) * ((n_entries - 1 - i) * LOG_INTERVAL_SECONDS) / half_life
            )
            for i in range(n_entries)
        }
        assert len(scores) == n_entries, "recency scores must not all collapse"

    def test_log_interval_is_positive(self):
        """A zero interval would restore the original bug."""
        assert LOG_INTERVAL_SECONDS > 0


class TestGcpReportsUnavailabilityHonestly:
    """GCP used to return a hard-coded 0.80 when Neo4j was unreachable.
    0.80 clears GCP_CORRECTNESS_THRESHOLD, so an unreachable database
    scored as a *correct* result."""

    def test_raises_when_graph_unavailable(self, monkeypatch):
        """No driver means no propagation, so it must refuse to answer."""
        monkeypatch.setattr(
            "app.research.gcp.neo4j_client",
            type("FakeClient", (), {"driver": None})(),
        )
        with pytest.raises(GraphUnavailableError):
            GraphConfidencePropagator().run_propagation("some-pod")

    def test_evaluation_step_scores_zero_not_confident(self, monkeypatch):
        """The honest score for 'no confidence was computed' is 0.0."""
        monkeypatch.setattr(
            "app.research.gcp.neo4j_client",
            type("FakeClient", (), {"driver": None})(),
        )
        score = evaluation.run_gcp_step("some-pod")
        assert score == 0.0
        assert score < evaluation.GCP_CORRECTNESS_THRESHOLD

    def test_unavailable_error_is_a_runtime_error(self):
        """Existing callers guard with `except RuntimeError`; the new
        exception must stay catchable by them."""
        assert issubclass(GraphUnavailableError, RuntimeError)


class TestMatchedComputeSharesEvidence:
    """The matched-compute control claims both arms saw identical
    evidence. That only holds if the caller's fetched results are
    actually used rather than silently re-queried."""

    def test_supplied_retrieval_results_are_used(self, monkeypatch):
        """Handing in evidence must suppress the internal re-query."""
        called = {"hybrid_search": 0}

        def _fake_hybrid_search(*_args, **_kwargs):
            called["hybrid_search"] += 1
            return []

        monkeypatch.setattr(evaluation, "run_hybrid_search", _fake_hybrid_search)
        monkeypatch.setattr(
            evaluation,
            "_run_agents_step",
            lambda *_a, **_k: None,
        )
        monkeypatch.setattr(evaluation, "calculate_fp", lambda *_a, **_k: 0)

        scenario = {
            "id": "s1",
            "query": "q",
            "target_entity": "svc",
            "expected_tags": ["tag"],
            "ground_truth_claims": ["c"],
            "observed_symptoms": ["o"],
        }
        evaluation.evaluate_scenario(scenario, "Agents", retrieval_results=[])

        assert called["hybrid_search"] == 0, (
            "evaluate_scenario re-queried retrieval despite being handed "
            "results; the two arms would not be comparing like with like"
        )

    def test_keyword_baseline_still_runs_its_own_retrieval(self, monkeypatch):
        """The override applies only to the hybrid path: keyword and
        vector baselines are *defined* by their retrieval mode, so
        substituting hybrid evidence into them would silently turn a
        retrieval comparison into a generation comparison."""
        called = {"keyword": 0}

        def _fake_keyword_search(*_args, **_kwargs):
            called["keyword"] += 1
            return []

        monkeypatch.setattr(evaluation, "run_keyword_search", _fake_keyword_search)
        monkeypatch.setattr(evaluation, "calculate_fp", lambda *_a, **_k: 0)

        scenario = {
            "id": "s1",
            "query": "q",
            "target_entity": "svc",
            "expected_tags": ["tag"],
            "ground_truth_claims": ["c"],
            "observed_symptoms": ["o"],
        }
        evaluation.evaluate_scenario(
            scenario, "Keyword Search", retrieval_results=[{"ignored": True}]
        )

        assert called["keyword"] == 1
