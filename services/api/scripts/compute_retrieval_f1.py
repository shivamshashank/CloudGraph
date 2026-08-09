"""Computes real per-scenario retrieval F1 for keyword/vector/hybrid
(see dissertation/PROGRESS.md Week 8, figure 1).

experiments/results/neurosymbolic_retrieval_detail.csv (from the main
report run) only tracks hit/missed expected tags — enough for the recall
figure used in scripts/paired_bootstrap.py, but not full F1, since it
never counted false positives. This script re-runs retrieval only (no LLM
calls — run_keyword_search/run_vector_search/run_hybrid_search and
calculate_fp are pure Neo4j/Qdrant queries) to get real TP/FP/FN/F1 per
scenario per method, reusing the exact same tag-matching and false-
positive-counting logic evaluate_scenario() already uses internally, just
without the LLM-calling Agents/GCP/GPCS steps this figure doesn't need.

Needs live Neo4j/Qdrant access — run this the same way as other
live-cluster scripts this sprint (e.g. inside the cloudgraph-api pod via
kubectl cp + kubectl exec), not from a bare checkout with no cluster
reachable.

Saves experiments/results/retrieval_f1.csv (or --results-dir override).

Usage (from services/api):
    .venv/bin/python scripts/compute_retrieval_f1.py [--limit N] [--results-dir DIR]
"""

import argparse
import csv
from pathlib import Path
from typing import Any

import _bootstrap

from app.demo.datasets import load_scenarios
from app.demo.seeding import seed_scenario_data, teardown_benchmark_data
from app.research.evaluation import (
    calculate_fp,
    extract_text_from_results,
    run_hybrid_search,
    run_keyword_search,
    run_vector_search,
)

DEFAULT_RESULTS_DIR = _bootstrap.REPO_ROOT / "experiments" / "results"

FIELDNAMES = ["scenario_id", "method", "tp", "fp", "fn", "precision", "recall", "f1"]

_SEARCH_FUNCS = {
    "keyword": run_keyword_search,
    "vector": run_vector_search,
    "hybrid": run_hybrid_search,
}


def _f1_row(scenario: dict[str, Any], method_key: str) -> dict[str, Any]:
    # Same retrieval + tag-matching logic evaluate_scenario()/
    # retrieval_detail_for_scenario() use, so tp/fn here are identical to
    # what's already in neurosymbolic_retrieval_detail.csv — this only
    # adds the false-positive count that data never tracked.
    results = _SEARCH_FUNCS[method_key](scenario["query"])
    expected_tags = scenario["expected_tags"]
    retrieved_text = extract_text_from_results(results, method_key).lower()
    tp = sum(1 for tag in expected_tags if tag.lower() in retrieved_text)
    fn = len(expected_tags) - tp
    fp = calculate_fp(results, method_key, expected_tags)

    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return {
        "scenario_id": scenario["id"],
        "method": method_key,
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
    }


def main() -> None:
    """CLI entry point: compute retrieval F1 for every scenario/method and
    save the raw per-scenario numbers."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--results-dir", type=Path, default=DEFAULT_RESULTS_DIR)
    args = parser.parse_args()

    scenarios = load_scenarios()
    if args.limit:
        scenarios = scenarios[: args.limit]

    args.results_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for i, scenario in enumerate(scenarios, start=1):
        print(f"... scenario {i}/{len(scenarios)} ({scenario['id']})")
        seed_scenario_data(scenario)
        try:
            for method_key in ("keyword", "vector", "hybrid"):
                rows.append(_f1_row(scenario, method_key))
        finally:
            teardown_benchmark_data()

    out_path = args.results_dir / "retrieval_f1.csv"
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nSaved {len(rows)} rows to {out_path}")


if __name__ == "__main__":
    main()
