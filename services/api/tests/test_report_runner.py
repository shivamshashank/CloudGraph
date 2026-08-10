"""Unit tests for report_runner.py — the GPCS-vs-self-consistency
comparison across all three context conditions (none/raw/hybrid), plus the
neuro-symbolic retrieval detail export, behind `cloudgraph report`."""

import types

import pytest

from app.demo.datasets import load_scenarios
from app.research import report_runner
from app.research.self_consistency import SelfConsistencyUnavailableError

SCENARIO = load_scenarios()[0]

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
        # The segmentation self-consistency actually scored, which GPCS must
        # be handed rather than re-deriving — see _fake_score_claims.
        "extracted_claims": [
            {"id": "claim-1", "text": f"claim text {tag}", "type": "state"}
        ],
    }


def _fake_score_claims(_analysis, _search_func, claims=None) -> dict:
    """Fixed-agreement stand-in for GraphProvenanceClaimScorer.score_claims.

    Echoes back whatever segmentation it was given, exactly as the real one
    does when `claims` is passed — so a caller that stopped forwarding
    self-consistency's claims would produce empty GPCS columns here rather
    than silently still passing."""
    return {
        "claims": [
            {
                "claim_id": c["id"],
                "text": c["text"],
                "trust_score": 0.9,
                "unsupported": False,
            }
            for c in (claims or [])
        ]
    }


def _fake_claim_scorer(**_kwargs):
    """Stands in for GraphProvenanceClaimScorer — agreement is fixed True
    since these tests are about the ablation plumbing, not scoring math
    (that's covered in test_gpcs.py / test_self_consistency.py). A plain
    factory function rather than a class, since the real constructor's
    llm_provider/llm_api_key/llm_model kwargs are ignored (this stand-in
    doesn't call an LLM) and there's only the one method to stand in for."""
    return types.SimpleNamespace(score_claims=_fake_score_claims)


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
    monkeypatch.setattr(report_runner, "GraphProvenanceClaimScorer", _fake_claim_scorer)
    monkeypatch.setattr(
        report_runner,
        "run_hybrid_search",
        # **_kwargs absorbs reference_time, which the real call passes so
        # the ranker's recency term has a meaningful "now" to measure age
        # against (see evaluation.run_hybrid_search).
        lambda query, **_kwargs: [{"id": "hybrid-hit"}],
    )
    monkeypatch.setattr(
        # **_kwargs absorbs scenario_id, which the real call passes so
        # retrieval is scoped to the scenario under evaluation (see
        # evaluation.run_raw_context_search).
        report_runner,
        "run_raw_context_search",
        lambda query, **_kwargs: [{"id": "raw-hit"}],
    )
    # Vector-store isolation is enforced against a live Qdrant; these tests
    # are about report_runner's orchestration and must not require one.
    monkeypatch.setattr(report_runner, "purge_semantic_store", lambda: 0)
    monkeypatch.setattr(
        report_runner, "assert_semantic_store_isolated", lambda _id: None
    )
    monkeypatch.setattr(
        report_runner, "retrieval_detail_for_scenario", _fake_retrieval_detail
    )


def test_generate_report_runs_all_three_context_conditions(monkeypatch):
    """The whole point of Day 3's ablation: each scenario must be run under
    all three conditions, with the right retrieval fed to each — not just
    the original Day-2 no-context condition."""
    seen_retrieval_args = []

    # Real call site (report_runner._run_condition) binds n_samples/
    # temperature/call_options by keyword — only call_options is read here,
    # so n_samples/temperature are absorbed into **_kwargs instead of named
    # (and therefore unused-argument-flagged) parameters.
    def fake_generate_and_score(_scenario, **_kwargs):
        retrieval_results = _kwargs["call_options"]["retrieval_results"]
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


def test_gpcs_scores_the_same_segmentation_self_consistency_scored(monkeypatch):
    """Regression guard for a silent-mis-join bug: extract_claims is an LLM
    call, so letting GPCS re-extract the primary generation produced a
    *different* segmentation — different claim count, different text under
    the same positional "claim-N" id. _claim_row joins the two by claim_id,
    so that paired unrelated claims (blank GPCS columns where the counts
    differed, wrong-but-populated rows where they happened to match),
    corrupting the headline agreement metric.

    GPCS must therefore be handed self-consistency's own claim list, and
    every emitted row must carry identical claim_text and gpcs_claim_text."""
    seen_claims = []

    def recording_score_claims(_analysis, _search_func, claims=None):
        seen_claims.append(claims)
        return _fake_score_claims(_analysis, _search_func, claims)

    monkeypatch.setattr(
        report_runner,
        "GraphProvenanceClaimScorer",
        lambda **_kwargs: types.SimpleNamespace(score_claims=recording_score_claims),
    )
    monkeypatch.setattr(
        report_runner, "generate_and_score", lambda *a, **k: _fake_sc_result("x")
    )

    result = report_runner.generate_report(scenario_limit=1)

    # Passed explicitly on every condition, never left to re-extraction.
    assert len(seen_claims) == 3
    for claims in seen_claims:
        assert claims == _fake_sc_result("x")["extracted_claims"]

    rows = [r for r in result["claims_csv"].splitlines() if r.strip()]
    header = rows[0].split(",")
    text_idx = header.index("claim_text")
    gpcs_text_idx = header.index("gpcs_claim_text")
    assert len(rows) == 4  # header + one row per condition
    for row in rows[1:]:
        cells = row.split(",")
        assert cells[text_idx] == cells[gpcs_text_idx] != ""


def test_generate_report_excludes_per_condition_independently(monkeypatch):
    """A scenario failing under one context condition must not prevent the
    other two conditions from being attempted and scored — these are
    independent runs sharing only the same seeded scenario data."""

    def fake_generate_and_score(_scenario, **_kwargs):
        retrieval_results = _kwargs["call_options"]["retrieval_results"]
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
