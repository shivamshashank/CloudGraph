#!/usr/bin/env python3
"""CLI Script to execute dynamic evaluation benchmark on all 25 scenarios.

Run from the services/api directory:
    python -m scripts.evaluate_real
"""

import datetime
import json
import os
import time

from app.demo.benchmark_dataset import BENCHMARK_GROUND_TRUTH_SCENARIOS
from app.demo.seeding import seed_scenario_data, teardown_benchmark_data
from app.research.evaluation import evaluate_scenario

BASELINES = [
    "Keyword Search",
    "Vector RAG",
    "GraphRAG",
    "GraphRAG + Agents",
    "GraphRAG + Agents + GCP",
    "GraphRAG + Agents + GCP + GPCS",
]

WORKSPACE_RESULTS_DIR = "/Users/shivam_shashank/CloudGraph/experiments/results"


def _run_scenario(scenario, baselines):
    """Evaluate all baselines against one seeded scenario.

    Returns per-baseline stats dict.
    """
    s_id = scenario["id"]
    print(" -> Seeding mock telemetry...")
    seed_scenario_data(scenario)

    stats = {}
    for baseline in baselines:
        t0 = time.perf_counter()
        tp, fp, fn, correct, unsupp = evaluate_scenario(scenario, baseline)
        latency_ms = max(1, int((time.perf_counter() - t0) * 1000))
        stats[baseline] = {
            "tp": tp,
            "fp": fp,
            "fn": fn,
            "correct": correct,
            "unsupported_claims_count": unsupp,
            "latency_ms": latency_ms,
        }
        print(
            f"    - {baseline:30}: "
            f"TP={tp}, FP={fp}, FN={fn}, Correct={correct}, Latency={latency_ms}ms"
        )

    print(" -> Tearing down telemetry...")
    teardown_benchmark_data()
    return s_id, stats


def _accumulate_baseline(results, baseline):
    """Sum stats for one baseline across all scenarios."""
    totals = {"tp": 0, "fp": 0, "fn": 0, "correct": 0, "unsupp": 0, "latencies": []}
    for s_stats in results.values():
        stat = s_stats[baseline]
        totals["tp"] += stat["tp"]
        totals["fp"] += stat["fp"]
        totals["fn"] += stat["fn"]
        totals["correct"] += stat["correct"]
        totals["unsupp"] += stat["unsupported_claims_count"]
        totals["latencies"].append(stat["latency_ms"])
    return totals


def _summarise(results, scenarios, baselines):
    """Aggregate per-scenario stats into overall baseline summary rows."""
    total_claims = sum(len(s["ground_truth_claims"]) for s in scenarios)
    summary = []
    for baseline in baselines:
        t = _accumulate_baseline(results, baseline)
        prec = round(
            t["tp"] / (t["tp"] + t["fp"]) if (t["tp"] + t["fp"]) > 0 else 0.0, 2
        )
        rec = round(
            t["tp"] / (t["tp"] + t["fn"]) if (t["tp"] + t["fn"]) > 0 else 0.0, 2
        )
        f1 = round((2 * prec * rec) / (prec + rec) if (prec + rec) > 0 else 0.0, 2)
        acc = round(t["correct"] / len(scenarios) if scenarios else 0.0, 2)
        halluc = round(t["unsupp"] / total_claims if total_claims > 0 else 0.0, 2)
        avg_lat = (
            int(sum(t["latencies"]) / len(t["latencies"])) if t["latencies"] else 0
        )
        summary.append(
            {
                "baseline": baseline,
                "accuracy": acc,
                "precision": prec,
                "recall": rec,
                "f1": f1,
                "hallucination_rate": halluc,
                "latency": avg_lat,
            }
        )
    return summary


def main():
    """Run evaluation harness across all benchmark scenarios and baselines."""
    print("=" * 80)
    print("                CLOUDGRAPH E2E EVALUATION HARNESS RUNNER")
    print("=" * 80)

    scenarios = BENCHMARK_GROUND_TRUTH_SCENARIOS
    total = len(scenarios)
    print(f"Loaded {total} ground-truth benchmark scenarios.")

    print("Cleaning up old benchmark entries from database...")
    teardown_benchmark_data()

    results = {}
    for idx, scenario in enumerate(scenarios, 1):
        print(
            f"\n[{idx}/{total}] Processing scenario: "
            f"{scenario['id']} ({scenario['target_service']})"
        )
        s_id, stats = _run_scenario(scenario, BASELINES)
        results[s_id] = stats

    summary = _summarise(results, scenarios, BASELINES)

    os.makedirs(WORKSPACE_RESULTS_DIR, exist_ok=True)
    output_path = os.path.join(WORKSPACE_RESULTS_DIR, "week1_raw.json")
    payload = {
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "total_scenarios": total,
        "scenarios_results": results,
        "baselines_summary": summary,
    }
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    print("\n" + "=" * 80)
    print("                      EVALUATION HARNESS SUMMARY REPORT")
    print("=" * 80)
    header = (
        f"{'Baseline Name':32} | {'Acc':<5} | {'Prec':<5} | "
        f"{'Rec':<5} | {'F1':<5} | {'Halluc':<6} | {'Latency':<7}"
    )
    print(header)
    print("-" * 80)
    for b in summary:
        row = (
            f"{b['baseline']:32} | {b['accuracy']:5.2f} | "
            f"{b['precision']:5.2f} | {b['recall']:5.2f} | "
            f"{b['f1']:5.2f} | {b['hallucination_rate']:6.2f} | "
            f"{b['latency']}ms"
        )
        print(row)
    print("=" * 80)
    print(f"Results successfully saved to: {output_path}")


if __name__ == "__main__":
    main()
