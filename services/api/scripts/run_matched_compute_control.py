"""Matched-compute control (research/NOVEL_CONTRIBUTIONS.md Contribution 5,
internal/planning/7_DAY_SPRINT_CHECKLIST.md Day 4).

Compares the real 5-specialist-agent consensus system against a single LLM
sampled DEFAULT_MATCHED_COMPUTE_SAMPLES times and self-consistency-scored
(app.research.self_consistency.generate_and_score_single_llm), at roughly
matched LLM call count per scenario — isolating whether the specialist
architecture itself earns its complexity, or whether raw compute (repeated
single-LLM sampling) performs comparably. This is the cheap slice of
Contribution 5 in scope for this pass; the interaction-round condition is
not built here.

Both arms use the SAME hybrid-retrieval evidence per scenario (fetched
once, passed to both) so the only variable that differs is architecture
(5 specialists + consensus vote) vs. compute (N independent single-LLM
samples), not what evidence they saw. Both arms are scored by the same
GPCS instance the same way, so "hallucination rate" means the same thing
for both.

Real LLM calls: ~6/scenario for the Agents arm (5 specialists + 1
consensus, via evaluate_scenario — reusing Day 1's already-tested harness
unmodified), DEFAULT_MATCHED_COMPUTE_SAMPLES/scenario for the single-LLM
arm — roughly matched, not identical; the exact counts are recorded and
reported, never just claimed.

Saves:
  experiments/results/matched_compute_raw.csv — per-scenario numbers
  experiments/results/logs/matched_compute_llm_requests.jsonl — every real
    LLM request/response from the single-LLM arm (the Agents arm's calls
    are already covered by the orchestrator's own service logs, same as
    every other real run this session)

Usage (from services/api):
    .venv/bin/python scripts/run_matched_compute_control.py [--limit N]
"""

import argparse
import csv
import json
from pathlib import Path
from typing import Any

import _bootstrap

from app.demo.benchmark_dataset import BENCHMARK_GROUND_TRUTH_SCENARIOS
from app.demo.seeding import seed_scenario_data, teardown_benchmark_data
from app.research.evaluation import (
    evaluate_scenario,
    extract_text_from_results,
    run_hybrid_search,
)
from app.research.self_consistency import (
    DEFAULT_MATCHED_COMPUTE_SAMPLES,
    SelfConsistencyUnavailableError,
    generate_and_score_single_llm,
)

DEFAULT_RESULTS_DIR = _bootstrap.REPO_ROOT / "experiments" / "results"
AGENTS_LLM_CALLS_PER_SCENARIO = 6  # 5 specialists + 1 consensus call
SINGLE_LLM_CALLS_PER_SCENARIO = DEFAULT_MATCHED_COMPUTE_SAMPLES

FIELDNAMES = [
    "scenario_id",
    "excluded",
    "reason",
    "agents_unsupported_rate",
    "agents_llm_calls",
    "single_llm_unsupported_rate",
    "single_llm_claim_count",
    "single_llm_llm_calls",
]


def _make_request_logger(log_path: Path):
    def _log(record: dict) -> None:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, default=str) + "\n")

    return _log


def run_one_scenario(scenario: dict[str, Any], request_logger) -> dict[str, Any]:
    """Runs both arms for one scenario. Returns a result row, or an
    exclusion record if either arm couldn't get a real generation —
    excluded, never fabricated."""
    seed_scenario_data(scenario)
    try:
        hybrid_results = run_hybrid_search(scenario["query"])

        agents_result = evaluate_scenario(scenario, "Agents")
        if agents_result is None:
            return {
                "scenario_id": scenario["id"],
                "excluded": True,
                "reason": "Agents baseline: orchestrator unavailable",
            }
        _, _, _, _, agents_unsupported_claims = agents_result
        n_ground_truth = len(scenario["ground_truth_claims"])
        agents_unsupported_rate = (
            round(agents_unsupported_claims / n_ground_truth, 3)
            if n_ground_truth and agents_unsupported_claims is not None
            else None
        )

        try:
            single_llm_result = generate_and_score_single_llm(
                scenario,
                request_logger=request_logger,
                retrieval_text=extract_text_from_results(hybrid_results, "hybrid"),
            )
        except SelfConsistencyUnavailableError as exc:
            return {
                "scenario_id": scenario["id"],
                "excluded": True,
                "reason": f"single-LLM baseline: {exc}",
            }

        return {
            "scenario_id": scenario["id"],
            "excluded": False,
            "reason": "",
            "agents_unsupported_rate": agents_unsupported_rate,
            "agents_llm_calls": AGENTS_LLM_CALLS_PER_SCENARIO,
            "single_llm_unsupported_rate": single_llm_result["unsupported_claim_rate"],
            "single_llm_claim_count": single_llm_result["claim_count"],
            "single_llm_llm_calls": single_llm_result["llm_call_count"],
        }
    finally:
        teardown_benchmark_data()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--limit", type=int, default=None, help="Only run the first N scenarios"
    )
    parser.add_argument(
        "--results-dir",
        type=Path,
        default=DEFAULT_RESULTS_DIR,
        help=(
            "Where to write output (default: experiments/results/ relative "
            "to a full repo checkout — override when running inside a "
            "container that only has the app/ package, e.g. --results-dir "
            "/tmp/matched_compute_results)"
        ),
    )
    return parser.parse_args()


def _write_results_csv(results_dir: Path, rows: list[dict[str, Any]]) -> Path:
    csv_path = results_dir / "matched_compute_raw.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in FIELDNAMES})
    return csv_path


def _run_all_scenarios(
    scenarios: list[dict[str, Any]], request_logger
) -> list[dict[str, Any]]:
    rows = []
    for i, scenario in enumerate(scenarios, start=1):
        print(f"... scenario {i}/{len(scenarios)} ({scenario['id']})")
        rows.append(run_one_scenario(scenario, request_logger))
    return rows


def main() -> None:
    """CLI entry point: run both arms across the benchmark and save raw
    per-scenario results + LLM logs."""
    args = _parse_args()
    results_dir = args.results_dir

    scenarios = BENCHMARK_GROUND_TRUTH_SCENARIOS
    if args.limit:
        scenarios = scenarios[: args.limit]

    results_dir.mkdir(parents=True, exist_ok=True)
    logs_dir = results_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_path = logs_dir / "matched_compute_llm_requests.jsonl"
    request_logger = _make_request_logger(log_path)

    rows = _run_all_scenarios(scenarios, request_logger)
    excluded = [r for r in rows if r["excluded"]]

    csv_path = _write_results_csv(results_dir, rows)
    print(
        f"\n{len(rows) - len(excluded)}/{len(scenarios)} scenarios completed, "
        f"{len(excluded)} excluded"
    )
    for r in excluded:
        print(f"  excluded: {r['scenario_id']} — {r['reason']}")
    print(f"Saved raw data to {csv_path}")
    print(f"Saved LLM logs to {log_path}")


if __name__ == "__main__":
    main()
