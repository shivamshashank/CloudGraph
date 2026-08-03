"""Day 2: run GPCS and self-consistency on the same real generations across
the benchmark dataset, and save the per-claim comparison table + cross-tab.

Requires a real LLM key configured for the agent-orchestrator process
(OPENAI_API_KEY / GEMINI_API_KEY / ANTHROPIC_API_KEY) — self-consistency is
not a meaningful measurement without genuine LLM stochasticity across
samples. Scenarios where the orchestrator falls back to its deterministic
rule-based path are excluded, not fabricated (see
app.research.self_consistency.SelfConsistencyUnavailableError).

Usage (from services/api, with the full stack running):
    .venv/bin/python scripts/run_day2_self_consistency.py
    DAY2_SCENARIO_LIMIT=10 .venv/bin/python scripts/run_day2_self_consistency.py

Every /orchestrate request and response this run makes is appended, one
JSON object per line, to experiments/results/day2_requests_log.jsonl as it
happens (crash-safe) — the API key is always redacted before it's written.
"""

import csv
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# pylint: disable=wrong-import-position
import pandas as pd  # noqa: E402

from app.demo.benchmark_dataset import BENCHMARK_GROUND_TRUTH_SCENARIOS  # noqa: E402
from app.demo.seeding import seed_scenario_data, teardown_benchmark_data  # noqa: E402
from app.research.evaluation import run_hybrid_search  # noqa: E402
from app.research.gpcs import GraphProvenanceClaimScorer  # noqa: E402
from app.research.self_consistency import (  # noqa: E402
    SelfConsistencyUnavailableError,
    generate_and_score,
)

# pylint: enable=wrong-import-position

RESULTS_DIR = (
    Path(__file__).resolve().parent.parent.parent.parent / "experiments" / "results"
)
REQUESTS_LOG_PATH = RESULTS_DIR / "day2_requests_log.jsonl"
FIELDNAMES = [
    "scenario_id",
    "claim_id",
    "claim_text",
    "claim_type",
    "gpcs_trust_score",
    "gpcs_unsupported",
    "self_consistency_recurrence_rate",
    "self_consistency_unsupported",
    "agreement",
]


def _score_one_scenario(
    scenario: dict,
    scorer: GraphProvenanceClaimScorer,
    request_logger=None,
) -> tuple[list[dict], str | None]:
    """Returns (rows, exclusion_reason). Seeds/tears down real telemetry so
    both GPCS and self-consistency retrieve against real evidence, matching
    how Day 1's benchmark harness seeds each scenario."""
    seed_scenario_data(scenario)
    try:
        try:
            sc_result = generate_and_score(
                scenario, n_samples=3, temperature=0.8, request_logger=request_logger
            )
        except SelfConsistencyUnavailableError as exc:
            return [], str(exc)

        primary_generation = sc_result["generations"][0]
        # Same extractor, same input dict as generate_and_score used for its
        # own claims[0] — guardrail #2 (identical claim segmentation for
        # both methods) holds by construction, not by convention.
        gpcs_result = scorer.score_claims(primary_generation, run_hybrid_search)
        gpcs_by_id = {c["claim_id"]: c for c in gpcs_result["claims"]}

        rows = []
        for sc_claim in sc_result["claims"]:
            gpcs_claim = gpcs_by_id.get(sc_claim["claim_id"])
            agreement = (
                gpcs_claim["unsupported"] == sc_claim["unsupported"]
                if gpcs_claim is not None
                else None
            )
            rows.append(
                {
                    "scenario_id": scenario["id"],
                    "claim_id": sc_claim["claim_id"],
                    "claim_text": sc_claim["text"],
                    "claim_type": sc_claim["claim_type"],
                    "gpcs_trust_score": (
                        gpcs_claim["trust_score"] if gpcs_claim else None
                    ),
                    "gpcs_unsupported": (
                        gpcs_claim["unsupported"] if gpcs_claim else None
                    ),
                    "self_consistency_recurrence_rate": sc_claim["recurrence_rate"],
                    "self_consistency_unsupported": sc_claim["unsupported"],
                    "agreement": agreement,
                }
            )
        return rows, None
    finally:
        teardown_benchmark_data()


def _run_all_scenarios(
    scenarios: list[dict],
    scorer: GraphProvenanceClaimScorer,
    request_logger,
) -> tuple[list[dict], list[dict]]:
    """Run _score_one_scenario for every scenario, collecting claim rows and
    exclusion records separately."""
    all_rows: list[dict] = []
    excluded: list[dict] = []
    for scenario in scenarios:
        print(f"[{scenario['id']}] generating + scoring...", flush=True)
        rows, exclusion_reason = _score_one_scenario(
            scenario, scorer, request_logger=request_logger
        )
        if exclusion_reason:
            print(f"[{scenario['id']}] EXCLUDED: {exclusion_reason}", flush=True)
            excluded.append({"scenario_id": scenario["id"], "reason": exclusion_reason})
            continue
        all_rows.extend(rows)
    return all_rows, excluded


def _write_claims_csv(csv_path: Path, rows: list[dict]) -> None:
    """Write the per-claim GPCS vs self-consistency comparison table."""
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)


def _write_agreement_crosstab(results_dir: Path, rows: list[dict]) -> Path:
    """Cross-tabulate GPCS vs self-consistency agreement by claim type."""
    df = pd.DataFrame(rows)
    cross_tab = pd.crosstab(
        df["claim_type"],
        [df["gpcs_unsupported"], df["self_consistency_unsupported"]],
    )
    cross_tab_path = results_dir / "day2_agreement_crosstab.csv"
    cross_tab.to_csv(cross_tab_path)
    return cross_tab_path


def main() -> None:
    """Run GPCS + self-consistency on every benchmark scenario and write the
    per-claim comparison table, exclusion log, and agreement cross-tab."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    scorer = GraphProvenanceClaimScorer()

    scenario_limit = os.getenv("DAY2_SCENARIO_LIMIT")
    scenarios = BENCHMARK_GROUND_TRUTH_SCENARIOS
    if scenario_limit:
        scenarios = scenarios[: int(scenario_limit)]
        print(
            f"DAY2_SCENARIO_LIMIT set — running {len(scenarios)} of "
            f"{len(BENCHMARK_GROUND_TRUTH_SCENARIOS)} scenarios.",
            flush=True,
        )

    # Fresh log file per run (not appended across runs) so it always
    # reflects exactly this run's requests/responses, not a prior one's.
    with open(REQUESTS_LOG_PATH, "w", encoding="utf-8") as f:
        pass

    def request_logger(record: dict) -> None:
        with open(REQUESTS_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")

    all_rows, excluded = _run_all_scenarios(scenarios, scorer, request_logger)

    csv_path = RESULTS_DIR / "day2_claims.csv"
    _write_claims_csv(csv_path, all_rows)

    excluded_path = RESULTS_DIR / "day2_excluded_scenarios.json"
    with open(excluded_path, "w", encoding="utf-8") as f:
        json.dump(excluded, f, indent=2)

    n_evaluated = len(scenarios) - len(excluded)
    print(
        f"\nWrote {len(all_rows)} claim rows from {n_evaluated}/"
        f"{len(scenarios)} scenarios to {csv_path}"
    )
    if excluded:
        print(
            f"{len(excluded)} scenarios excluded (see {excluded_path}) — "
            "self-consistency requires a real, LLM-backed generation."
        )
    print(f"Full request/response log written to {REQUESTS_LOG_PATH}")

    if not all_rows:
        print("No claims scored — nothing to cross-tabulate.")
        return

    cross_tab_path = _write_agreement_crosstab(RESULTS_DIR, all_rows)
    print(f"Agreement/disagreement cross-tab by claim type written to {cross_tab_path}")

    n_total = sum(1 for r in all_rows if r["agreement"] is not None)
    n_agree = sum(1 for r in all_rows if r["agreement"] is True)
    print(f"GPCS vs self-consistency agreement: {n_agree}/{n_total} claims")


if __name__ == "__main__":
    main()
