"""Unit tests for report_runner.py — the GPCS-vs-self-consistency
comparison across all three context conditions (none/raw/hybrid), plus the
neuro-symbolic retrieval detail export, behind `cloudgraph report`."""

import pytest

from app.demo.benchmark_dataset import BENCHMARK_GROUND_TRUTH_SCENARIOS
from app.research import report_runner
from app.research.self_consistency import SelfConsistencyUnavailableError

SCENARIO = BENCHMARK_GROUND_TRUTH_SCENARIOS[0]

_METHOD_CLASS = {"keyword": "symbolic", "vector": "neural", "hybrid": "neuro-symbolic"}


def _fake_sc_result(tag: str) -> dict:
    return {
        "generations": [{"title": "", "summary": f"summary-{tag}", "cause": "x"}],
        "claims": [
            {
                "claim_id": "claim-1",
                "text": f"claim text {tag}",
                "claim_type": "state",
                "recurrence_rate": 0.8,
                "unsupported": False,
            }
        ],
    }


class _FakeScorer:  # pylint: disable=too-few-public-methods
    """Stands in for GraphProvenanceClaimScorer — agreement is fixed True
    since these tests are about the ablation plumbing, not scoring math
    (that's covered in test_gpcs.py / test_self_consistency.py). Only needs
    the one method report_runner actually calls."""

    def score_claims(self, _analysis, _search_func):
        """Fixed-agreement stand-in for GraphProvenanceClaimScorer.score_claims."""
        return {
            "claims": [
                {"claim_id": "claim-1", "trust_score": 0.9, "unsupported": False}
            ]
        }


def _fake_retrieval_detail(scenario: dict, method: str) -> dict:
    return {
        "scenario_id": scenario["id"],
        "method": method,
        "method_class": _METHOD_CLASS[method],
        "n_results": 3,
        "expected_tags": "a;b",
        "hit_tags": "a",
        "missed_tags": "b",
        "correct": 0,
        "retrieved_text_preview": "preview",
    }


@pytest.fixture(autouse=True)
def no_real_io(monkeypatch):
    """Every test here is about report_runner's own orchestration logic —
    seeding, teardown, retrieval, and scoring are all real, tested
    elsewhere (test_self_consistency.py, test_gpcs.py, test_graph.py's
    seeding coverage); mocking them here keeps these tests fast and
    focused on what's actually new."""
    monkeypatch.setattr(report_runner, "seed_scenario_data", lambda scenario: None)
    monkeypatch.setattr(report_runner, "teardown_benchmark_data", lambda: None)
    monkeypatch.setattr(report_runner, "GraphProvenanceClaimScorer", _FakeScorer)
    monkeypatch.setattr(
        report_runner, "run_hybrid_search", lambda query: [{"id": "hybrid-hit"}]
    )
    monkeypatch.setattr(
        report_runner, "run_raw_context_search", lambda query: [{"id": "raw-hit"}]
    )
    monkeypatch.setattr(
        report_runner, "retrieval_detail_for_scenario", _fake_retrieval_detail
    )


def test_generate_report_runs_all_three_context_conditions(monkeypatch):
    """The whole point of Day 3's ablation: each scenario must be run under
    all three conditions, with the right retrieval fed to each — not just
    the original Day-2 no-context condition."""
    seen_retrieval_args = []

    # Real call site binds n_samples/temperature/request_logger by keyword
    # (see report_runner._run_condition) — these names can't be
    # underscore-prefixed without breaking that binding, so disable rather
    # than rename.
    def fake_generate_and_score(  # pylint: disable=unused-argument
        scenario, n_samples, temperature, request_logger, retrieval_results
    ):
        seen_retrieval_args.append(retrieval_results)
        return _fake_sc_result(str(retrieval_results))

    monkeypatch.setattr(report_runner, "generate_and_score", fake_generate_and_score)

    result = report_runner.generate_report(scenario_limit=1)

    assert len(seen_retrieval_args) == 3
    assert seen_retrieval_args[0] is None  # "none" — original Day-2 condition
    assert seen_retrieval_args[1] == [{"id": "raw-hit"}]  # "raw"
    assert seen_retrieval_args[2] == [{"id": "hybrid-hit"}]  # "hybrid"

    assert result["n_scenarios"] == 1
    assert result["n_claims"] == 3  # one claim row per condition
    for condition in ("none", "raw", "hybrid"):
        assert condition in result["claims_csv"]
    assert set(result["context_condition_summary"].keys()) == {"none", "raw", "hybrid"}


def test_generate_report_excludes_per_condition_independently(monkeypatch):
    """A scenario failing under one context condition must not prevent the
    other two conditions from being attempted and scored — these are
    independent runs sharing only the same seeded scenario data."""

    def fake_generate_and_score(  # pylint: disable=unused-argument
        scenario, n_samples, temperature, request_logger, retrieval_results
    ):
        if retrieval_results is None:
            raise SelfConsistencyUnavailableError("no-context condition excluded")
        return _fake_sc_result("ok")

    monkeypatch.setattr(report_runner, "generate_and_score", fake_generate_and_score)

    result = report_runner.generate_report(scenario_limit=1)

    assert result["n_excluded"] == 1
    assert result["excluded_scenarios"][0]["context_condition"] == "none"
    assert result["excluded_scenarios"][0]["scenario_id"] == SCENARIO["id"]
    # raw and hybrid conditions still succeeded independently
    assert result["n_claims"] == 2


def test_generate_report_includes_neurosymbolic_export(monkeypatch):
    """The neuro-symbolic retrieval-detail export (Contribution 3) must be
    produced regardless of what happens with generation — it's cheap,
    LLM-free, and captured once per scenario."""
    monkeypatch.setattr(
        report_runner, "generate_and_score", lambda *a, **k: _fake_sc_result("x")
    )

    result = report_runner.generate_report(scenario_limit=1)

    for method in ("keyword", "vector", "hybrid"):
        assert method in result["neurosymbolic_csv"]
    assert SCENARIO["id"] in result["neurosymbolic_csv"]


def test_generate_report_zero_claims_still_returns_valid_shape(monkeypatch):
    """Every condition excluded must still produce a well-formed result
    (empty CSVs, no crash) — not a partially-filled or malformed dict."""

    def always_fail(*_args, **_kwargs):
        raise SelfConsistencyUnavailableError("always excluded")

    monkeypatch.setattr(report_runner, "generate_and_score", always_fail)

    result = report_runner.generate_report(scenario_limit=1)

    assert result["n_claims"] == 0
    assert result["n_excluded"] == 3  # all 3 conditions excluded for the 1 scenario
    assert result["agreement_summary"] == "no claims scored"
    assert not result["context_condition_summary"]
