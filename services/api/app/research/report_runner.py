"""Generates CloudGraph's core research report as a background job, exposed
over HTTP so the `cloudgraph report` CLI command can drive it from any
machine without needing a local source checkout.

Three sections make up "the report":

1. GPCS vs. self-consistency (research/7_DAY_SPRINT_CHECKLIST.md Day 2,
   NOVEL_CONTRIBUTIONS.md Contribution 2) — the flagship comparison.
2. Context-condition ablation (Day 3) — the same generation+scoring
   pipeline run under three conditions per scenario: no retrieved context
   (the original Day-2 condition — agents reason from error_logs alone),
   raw unfiltered context (all scenario-seeded evidence, no ranking), and
   ranked hybrid context (GraphRAG's own retrieval). Answers "does
   structured retrieval earn its complexity, or is dumping everything just
   as good."
3. Neuro-symbolic retrieval detail (Day 3, Contribution 3) — per-scenario,
   per-method (keyword=symbolic, vector=neural, hybrid=neuro-symbolic)
   retrieved evidence and tag hit/miss data, for a human qualitative
   failure-mode read — this module exports the data, not a finished
   analysis; categorizing *why* a method failed is a judgment call for
   whoever reads it, not something to fake-automate.

Either via the HTTP-driven `cloudgraph report` CLI command (no source
checkout needed), or directly via scripts/generate_research_report.py for
local-dev use against a full checkout — same underlying logic either way.

State is kept in-memory only (module-level dict, guarded by a lock) — not
persisted to disk or a database. Acceptable for this single-user research
tool: a lost in-progress run just gets re-started, and this avoids adding
any storage/PVC requirement to the deployment for it.
"""

import threading
from io import StringIO
from typing import Any

import pandas as pd

from app.demo.benchmark_dataset import BENCHMARK_GROUND_TRUTH_SCENARIOS
from app.demo.seeding import seed_scenario_data, teardown_benchmark_data
from app.research.evaluation import (
    retrieval_detail_for_scenario,
    run_hybrid_search,
    run_raw_context_search,
)
from app.research.gpcs import GraphProvenanceClaimScorer
from app.research.llm_settings import load_stored_llm_settings
from app.research.self_consistency import (
    SelfConsistencyUnavailableError,
    generate_and_score,
)

CLAIM_FIELDNAMES = [
    "scenario_id",
    "context_condition",
    "claim_id",
    "claim_text",
    "claim_type",
    "gpcs_trust_score",
    "gpcs_unsupported",
    "self_consistency_recurrence_rate",
    "self_consistency_unsupported",
    "agreement",
]

NEUROSYMBOLIC_FIELDNAMES = [
    "scenario_id",
    "method",
    "method_class",
    "n_results",
    "expected_tags",
    "hit_tags",
    "missed_tags",
    "correct",
    "retrieved_text_preview",
]

# Context conditions run per scenario, in this order — "none" first since
# it's the original Day-2 condition and the one most likely to succeed
# (matches the retrieval mode most tested so far).
CONTEXT_CONDITIONS = ("none", "raw", "hybrid")

_lock = threading.Lock()
_state: dict[str, Any] = {
    "status": "idle",  # idle | running | completed | failed
    "progress": "",
    "result": None,
    "error": None,
}


def get_status() -> dict[str, Any]:
    """Returns a snapshot of the current run's status. Safe to poll
    frequently — just reads under the lock, does no work itself."""
    with _lock:
        return dict(_state)


def start_report(scenario_limit: int | None = None) -> bool:
    """Starts generating the report in a background thread. Returns False
    (and does not start a second run) if one is already in progress."""
    with _lock:
        if _state["status"] == "running":
            return False
        _state["status"] = "running"
        _state["progress"] = "starting"
        _state["result"] = None
        _state["error"] = None

    thread = threading.Thread(target=_run, args=(scenario_limit,), daemon=True)
    thread.start()
    return True


def _set_progress(text: str) -> None:
    with _lock:
        _state["progress"] = text


def _run(scenario_limit: int | None) -> None:
    # Broad except is intentional: this runs unattended in a background
    # thread with no caller to propagate an exception to — if anything
    # unexpected happens, it must be recorded in _state (status: "failed",
    # with the reason) rather than left silently stuck on "running"
    # forever with no way for a polling client to ever find out why.
    try:
        result = generate_report(scenario_limit)
        with _lock:
            _state["status"] = "completed"
            _state["progress"] = "done"
            _state["result"] = result
    except Exception as exc:  # pylint: disable=broad-except
        with _lock:
            _state["status"] = "failed"
            _state["error"] = str(exc)


def _retrieval_results_for_condition(
    condition: str, scenario: dict[str, Any]
) -> list[dict[str, Any]] | None:
    if condition == "none":
        return None
    if condition == "raw":
        return run_raw_context_search(scenario["query"])
    return run_hybrid_search(scenario["query"])


def _neurosymbolic_row(scenario: dict[str, Any], method_key: str) -> dict[str, Any]:
    """One method's retrieval detail for one scenario — cheap (no LLM
    calls), so captured regardless of what happens with generation."""
    try:
        return retrieval_detail_for_scenario(scenario, method_key)
    except (RuntimeError, ValueError, KeyError) as exc:
        return {
            "scenario_id": scenario["id"],
            "method": method_key,
            "method_class": "",
            "n_results": 0,
            "expected_tags": "",
            "hit_tags": "",
            "missed_tags": "",
            "correct": 0,
            "retrieved_text_preview": f"ERROR: {exc}",
        }


def _claim_row(
    scenario: dict[str, Any],
    condition: str,
    sc_claim: dict[str, Any],
    gpcs_by_id: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Builds one comparison row for one self-consistency claim, joined
    against GPCS's scoring of the same claim ID (same extractor for both,
    so IDs line up by construction, not convention)."""
    gpcs_claim = gpcs_by_id.get(sc_claim["claim_id"])
    agreement = (
        gpcs_claim["unsupported"] == sc_claim["unsupported"]
        if gpcs_claim is not None
        else None
    )
    return {
        "scenario_id": scenario["id"],
        "context_condition": condition,
        "claim_id": sc_claim["claim_id"],
        "claim_text": sc_claim["text"],
        "claim_type": sc_claim["claim_type"],
        "gpcs_trust_score": gpcs_claim["trust_score"] if gpcs_claim else None,
        "gpcs_unsupported": gpcs_claim["unsupported"] if gpcs_claim else None,
        "self_consistency_recurrence_rate": sc_claim["recurrence_rate"],
        "self_consistency_unsupported": sc_claim["unsupported"],
        "agreement": agreement,
    }


def _run_condition(
    scenario: dict[str, Any],
    condition: str,
    scorer: GraphProvenanceClaimScorer,
    request_logger: Any,
) -> tuple[list[dict[str, Any]], dict[str, str] | None]:
    """Runs one context condition for one scenario. Returns (claim rows,
    exclusion record or None) — retrieval failures and generation failures
    both exclude just this (scenario, condition) pair, never the whole
    scenario, since the other conditions are independent attempts."""
    try:
        retrieval_results = _retrieval_results_for_condition(condition, scenario)
    except (RuntimeError, ValueError) as exc:
        return [], {
            "scenario_id": scenario["id"],
            "context_condition": condition,
            "reason": f"retrieval failed: {exc}",
        }

    try:
        sc_result = generate_and_score(
            scenario,
            n_samples=3,
            temperature=0.8,
            request_logger=request_logger,
            retrieval_results=retrieval_results,
        )
    except SelfConsistencyUnavailableError as exc:
        return [], {
            "scenario_id": scenario["id"],
            "context_condition": condition,
            "reason": str(exc),
        }

    primary_generation = sc_result["generations"][0]
    gpcs_result = scorer.score_claims(primary_generation, run_hybrid_search)
    gpcs_by_id = {c["claim_id"]: c for c in gpcs_result["claims"]}
    rows = [
        _claim_row(scenario, condition, sc_claim, gpcs_by_id)
        for sc_claim in sc_result["claims"]
    ]
    return rows, None


def _run_scenario(
    scenario: dict[str, Any],
    position: str,
    scorer: GraphProvenanceClaimScorer,
    request_logger: Any,
) -> tuple[list[dict[str, Any]], list[dict[str, str]], list[dict[str, Any]]]:
    """Runs every context condition plus the neuro-symbolic capture for one
    scenario. Returns (claim rows, exclusion records, neurosymbolic rows)."""
    seed_scenario_data(scenario)
    try:
        neurosymbolic_rows = [
            _neurosymbolic_row(scenario, method_key)
            for method_key in ("keyword", "vector", "hybrid")
        ]

        all_rows: list[dict[str, Any]] = []
        excluded: list[dict[str, str]] = []
        for condition in CONTEXT_CONDITIONS:
            _set_progress(f"{position} ({scenario['id']}) — context: {condition}")
            rows, exclusion = _run_condition(
                scenario, condition, scorer, request_logger
            )
            all_rows.extend(rows)
            if exclusion:
                excluded.append(exclusion)

        return all_rows, excluded, neurosymbolic_rows
    finally:
        teardown_benchmark_data()


class _ReportAccumulator:  # pylint: disable=too-few-public-methods
    """Collects one scenario's results at a time — a single local in
    generate_report instead of three separate accumulator lists."""

    def __init__(self) -> None:
        self.claim_rows: list[dict[str, Any]] = []
        self.excluded: list[dict[str, str]] = []
        self.neurosymbolic_rows: list[dict[str, Any]] = []

    def add_scenario_result(
        self,
        rows: list[dict[str, Any]],
        excluded: list[dict[str, str]],
        neurosymbolic_rows: list[dict[str, Any]],
    ) -> None:
        """Extend all three accumulators with one scenario's results."""
        self.claim_rows.extend(rows)
        self.excluded.extend(excluded)
        self.neurosymbolic_rows.extend(neurosymbolic_rows)


def _overall_summary(all_rows: list[dict[str, Any]]) -> tuple[str, str]:
    """Overall (across all conditions) agreement summary and crosstab CSV.
    Returns ("no claims scored", "") if all_rows is empty."""
    if not all_rows:
        return "no claims scored", ""
    df = pd.DataFrame(all_rows)
    cross_tab = pd.crosstab(
        df["claim_type"],
        [df["gpcs_unsupported"], df["self_consistency_unsupported"]],
    )
    n_total = sum(1 for r in all_rows if r["agreement"] is not None)
    n_agree = sum(1 for r in all_rows if r["agreement"] is True)
    return f"{n_agree}/{n_total} claims agree", cross_tab.to_csv()


def _condition_summary(all_rows: list[dict[str, Any]]) -> dict[str, str]:
    """Per-context-condition agreement summary — e.g. how the 'raw' and
    'hybrid' conditions compare to the original no-context condition."""
    summary: dict[str, str] = {}
    for condition in CONTEXT_CONDITIONS:
        condition_rows = [r for r in all_rows if r["context_condition"] == condition]
        if not condition_rows:
            summary[condition] = "no claims scored"
            continue
        c_total = sum(1 for r in condition_rows if r["agreement"] is not None)
        c_agree = sum(1 for r in condition_rows if r["agreement"] is True)
        summary[condition] = (
            f"{c_agree}/{c_total} claims agree ({len(condition_rows)} claims)"
        )
    return summary


def generate_report(scenario_limit: int | None) -> dict[str, Any]:
    """Runs the full report synchronously and returns the result dict — the
    actual report-generation logic, callable directly (e.g. from
    scripts/generate_research_report.py for local-dev use against a full
    source checkout) or via start_report/_run above for the HTTP-driven,
    backgrounded `cloudgraph report` path.

    Note on cost: running all three context conditions triples generation
    volume versus Day 2 alone (9 orchestrator calls per scenario instead of
    3) — this is real compute, not a free ablation, and takes proportionally
    longer.
    """
    llm_settings = load_stored_llm_settings()
    scorer = GraphProvenanceClaimScorer(
        llm_provider=llm_settings.get("provider") or "",
        llm_api_key=llm_settings.get("api_key") or "",
        llm_model=llm_settings.get("model") or "",
    )
    scenarios = BENCHMARK_GROUND_TRUTH_SCENARIOS
    if scenario_limit:
        scenarios = scenarios[:scenario_limit]

    accumulator = _ReportAccumulator()
    requests_log: list[dict[str, Any]] = []

    def request_logger(record: dict[str, Any]) -> None:
        requests_log.append(record)

    for i, scenario in enumerate(scenarios, start=1):
        accumulator.add_scenario_result(
            *_run_scenario(
                scenario, f"scenario {i}/{len(scenarios)}", scorer, request_logger
            )
        )

    all_rows = accumulator.claim_rows
    agreement_summary, crosstab_csv = _overall_summary(all_rows)
    condition_summary = _condition_summary(all_rows) if all_rows else {}

    return {
        "n_scenarios": len(scenarios),
        "n_excluded": len(accumulator.excluded),
        "n_claims": len(all_rows),
        "excluded_scenarios": accumulator.excluded,
        "agreement_summary": agreement_summary,
        "context_condition_summary": condition_summary,
        "claims_csv": _rows_to_csv(all_rows, CLAIM_FIELDNAMES),
        "agreement_crosstab_csv": crosstab_csv,
        "neurosymbolic_csv": _rows_to_csv(
            accumulator.neurosymbolic_rows, NEUROSYMBOLIC_FIELDNAMES
        ),
        "requests_log": requests_log,
    }


def _rows_to_csv(rows: list[dict[str, Any]], fieldnames: list[str]) -> str:
    df = pd.DataFrame(rows, columns=fieldnames)
    buf = StringIO()
    df.to_csv(buf, index=False)
    return buf.getvalue()
