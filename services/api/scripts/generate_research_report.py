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

Every /orchestrate request and response this run makes is appended, one
JSON object per line, to experiments/results/requests_log.jsonl as it
happens (crash-safe) — the api_key field is always redacted before it's
written.
"""

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# pylint: disable=wrong-import-position
from app.research.report_runner import generate_report  # noqa: E402

# pylint: enable=wrong-import-position

RESULTS_DIR = (
    Path(__file__).resolve().parent.parent.parent.parent / "experiments" / "results"
)
REQUESTS_LOG_PATH = RESULTS_DIR / "requests_log.jsonl"


def main() -> None:
    """Run GPCS + self-consistency (across all three context conditions) on
    every benchmark scenario, and write the per-claim comparison table,
    exclusion log, agreement cross-tab, and neuro-symbolic retrieval detail.

    Note: running all three context conditions triples generation volume
    versus the original Day-2-only report (9 orchestrator calls per
    scenario instead of 3) — expect roughly 3x the runtime."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    scenario_limit_env = os.getenv("REPORT_SCENARIO_LIMIT")
    scenario_limit = int(scenario_limit_env) if scenario_limit_env else None
    if scenario_limit:
        print(
            f"REPORT_SCENARIO_LIMIT set — running {scenario_limit} scenarios.",
            flush=True,
        )

    result = generate_report(scenario_limit)

    with open(REQUESTS_LOG_PATH, "w", encoding="utf-8") as f:
        for record in result["requests_log"]:
            f.write(json.dumps(record) + "\n")

    claims_path = RESULTS_DIR / "claims.csv"
    claims_path.write_text(result["claims_csv"], encoding="utf-8")

    excluded_path = RESULTS_DIR / "excluded_scenarios.json"
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
    print(f"Full request/response log written to {REQUESTS_LOG_PATH}")

    if not result["n_claims"]:
        print("No claims scored — nothing to cross-tabulate.")
        return

    crosstab_path = RESULTS_DIR / "agreement_crosstab.csv"
    crosstab_path.write_text(result["agreement_crosstab_csv"], encoding="utf-8")
    print(f"Agreement/disagreement cross-tab by claim type written to {crosstab_path}")
    print(f"GPCS vs self-consistency agreement: {result['agreement_summary']}")
    for condition, summary in result.get("context_condition_summary", {}).items():
        print(f"  context={condition}: {summary}")

    neurosymbolic_path = RESULTS_DIR / "neurosymbolic_retrieval_detail.csv"
    neurosymbolic_path.write_text(result["neurosymbolic_csv"], encoding="utf-8")
    print(
        f"Neuro-symbolic retrieval detail (for qualitative failure-mode "
        f"reading) written to {neurosymbolic_path}"
    )


if __name__ == "__main__":
    main()
