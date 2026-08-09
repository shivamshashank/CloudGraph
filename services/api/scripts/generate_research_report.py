"""Generates CloudGraph's core research report — GPCS vs. self-consistency
across three context conditions (none/raw/hybrid), plus the neuro-symbolic
retrieval detail export — directly from a full source checkout. A thin
wrapper around app.research.report_runner.generate_report for local
dev/debugging use.

For anyone without a full checkout (e.g. installed via install.sh), use
`cloudgraph report` instead — it drives the same underlying logic over
HTTP against a running CloudGraph API, no local Python environment needed.

Requires an LLM provider connected via `POST /api/v1/settings` (or the
Settings page in the UI) with a valid API key for one of the supported
providers (OpenAI, Gemini, or Meta's Llama API) — self-consistency is not a
meaningful measurement without genuine LLM stochasticity across samples.
Scenarios where the orchestrator falls back to its deterministic rule-based
path are excluded, not fabricated (see
app.research.self_consistency.SelfConsistencyUnavailableError).

Usage (from services/api, with the full stack running):
    .venv/bin/python scripts/generate_research_report.py
    REPORT_SCENARIO_LIMIT=10 .venv/bin/python scripts/generate_research_report.py

    # Batched run (see testing/report/run_report_batched.sh) — writes to a
    # separate directory per batch so consecutive batches don't clobber
    # each other; combine with scripts/merge_reports.py afterward.
    REPORT_SCENARIO_LIMIT=5 REPORT_SCENARIO_OFFSET=5 REPORT_RESULTS_DIR=/tmp/batch2 \\
      .venv/bin/python scripts/generate_research_report.py

Every /orchestrate request and response this run makes is appended, one
JSON object per line, to <results-dir>/requests_log.jsonl as it happens
(crash-safe) — the api_key field is always redacted before it's written.
"""

import json
import os
from pathlib import Path

import _bootstrap

from app.research.report_runner import generate_report

DEFAULT_RESULTS_DIR = _bootstrap.REPO_ROOT / "experiments" / "results"


def _resolve_results_dir() -> Path:
    results_dir = (
        Path(os.environ["REPORT_RESULTS_DIR"])
        if os.getenv("REPORT_RESULTS_DIR")
        else DEFAULT_RESULTS_DIR
    )
    results_dir.mkdir(parents=True, exist_ok=True)
    return results_dir


def _scenario_selection() -> tuple[int | None, int]:
    """Read REPORT_SCENARIO_LIMIT/OFFSET from the environment, printing a
    note for whichever ones are set (used by batched runs, see
    testing/report/run_report_batched.sh)."""
    scenario_limit_env = os.getenv("REPORT_SCENARIO_LIMIT")
    scenario_limit = int(scenario_limit_env) if scenario_limit_env else None
    if scenario_limit:
        print(
            f"REPORT_SCENARIO_LIMIT set — running {scenario_limit} scenarios.",
            flush=True,
        )

    scenario_offset_env = os.getenv("REPORT_SCENARIO_OFFSET")
    scenario_offset = int(scenario_offset_env) if scenario_offset_env else 0
    if scenario_offset:
        print(
            f"REPORT_SCENARIO_OFFSET set — starting at scenario {scenario_offset + 1}.",
            flush=True,
        )
    return scenario_limit, scenario_offset


def _write_requests_log(requests_log_path: Path, requests_log: list) -> None:
    with open(requests_log_path, "w", encoding="utf-8") as f:
        for record in requests_log:
            f.write(json.dumps(record) + "\n")
    print(f"Full request/response log written to {requests_log_path}")


def _write_claims_output(results_dir: Path, result: dict) -> None:
    claims_path = results_dir / "claims.csv"
    claims_path.write_text(result["claims_csv"], encoding="utf-8")

    excluded_path = results_dir / "excluded_scenarios.json"
    with open(excluded_path, "w", encoding="utf-8") as f:
        json.dump(result["excluded_scenarios"], f, indent=2)

    n_evaluated = result["n_scenarios"] - result["n_excluded"]
    print(
        f"\nWrote {result['n_claims']} claim rows from {n_evaluated}/"
        f"{result['n_scenarios']} scenarios to {claims_path}"
    )
    if result["n_excluded"]:
        print(
            f"{result['n_excluded']} scenarios excluded (see {excluded_path}) — "
            "self-consistency requires a real, LLM-backed generation."
        )


def _write_crosstab_and_neurosymbolic(results_dir: Path, result: dict) -> None:
    crosstab_path = results_dir / "agreement_crosstab.csv"
    crosstab_path.write_text(result["agreement_crosstab_csv"], encoding="utf-8")
    print(f"Agreement/disagreement cross-tab by claim type written to {crosstab_path}")
    print(f"GPCS vs self-consistency agreement: {result['agreement_summary']}")
    for condition, summary in result.get("context_condition_summary", {}).items():
        print(f"  context={condition}: {summary}")

    neurosymbolic_path = results_dir / "neurosymbolic_retrieval_detail.csv"
    neurosymbolic_path.write_text(result["neurosymbolic_csv"], encoding="utf-8")
    print(
        f"Neuro-symbolic retrieval detail (for qualitative failure-mode "
        f"reading) written to {neurosymbolic_path}"
    )


def main() -> None:
    """Run GPCS + self-consistency (across all three context conditions) on
    every benchmark scenario, and write the per-claim comparison table,
    exclusion log, agreement cross-tab, and neuro-symbolic retrieval detail.

    Note: running all three context conditions triples generation volume
    versus the original Day-2-only report (9 orchestrator calls per
    scenario instead of 3) — expect roughly 3x the runtime."""
    results_dir = _resolve_results_dir()
    scenario_limit, scenario_offset = _scenario_selection()
    result = generate_report(scenario_limit, scenario_offset)

    _write_requests_log(results_dir / "requests_log.jsonl", result["requests_log"])
    _write_claims_output(results_dir, result)

    if not result["n_claims"]:
        print("No claims scored — nothing to cross-tabulate.")
        return

    _write_crosstab_and_neurosymbolic(results_dir, result)


if __name__ == "__main__":
    main()
