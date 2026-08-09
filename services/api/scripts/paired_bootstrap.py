"""Paired bootstrap confidence intervals + Wilcoxon signed-rank tests for
CloudGraph's real result deltas (see dissertation/PROGRESS.md Week 8).

Reads experiments/results/claims.csv,
experiments/results/neurosymbolic_retrieval_detail.csv, and (if present)
experiments/results/matched_compute_raw.csv — already-collected real data,
this script makes no LLM calls — and reports significance for four paired
deltas:

1. GPCS vs. self-consistency unsupported-rate, per (scenario, context
   condition) — is one method systematically stricter than the other?
2. hybrid vs. raw context, per-scenario claim-agreement rate — does ranked
   retrieval actually beat an unranked evidence dump?
3. hybrid vs. keyword retrieval, per-scenario tag recall. Note: the saved
   neurosymbolic data tracks hit/missed tags only, no false-positive
   count, so this is recall, not full F1 — F1 would need re-running
   retrieval with precision tracking, out of scope here.
4. (Only if matched_compute_raw.csv exists — see
   scripts/run_matched_compute_control.py) the real 5-agent system vs. a
   matched-compute single-LLM baseline, per-scenario GPCS-unsupported rate
   — does the specialist architecture earn its complexity over raw
   compute?

n=25 scenarios gives wide confidence intervals by construction — every
result below must be read as such, never as a precise point estimate
(guardrail #3, 7_DAY_SPRINT_CHECKLIST.md).

Usage (from services/api):
    .venv/bin/python scripts/paired_bootstrap.py
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

RESULTS_DIR = (
    Path(__file__).resolve().parent.parent.parent.parent / "experiments" / "results"
)


def paired_bootstrap_ci(
    deltas: np.ndarray, n_resamples: int = 10000, seed: int = 42
) -> tuple[float, float]:
    """95% CI on the mean paired delta via percentile bootstrap."""
    rng = np.random.default_rng(seed)
    means = np.array(
        [
            rng.choice(deltas, size=len(deltas), replace=True).mean()
            for _ in range(n_resamples)
        ]
    )
    low, high = np.percentile(means, [2.5, 97.5])
    return float(low), float(high)


def _report(name: str, deltas: np.ndarray) -> str:
    ci_low, ci_high = paired_bootstrap_ci(deltas)
    mean_delta = float(deltas.mean())
    try:
        wilcoxon_result = stats.wilcoxon(deltas)
        wilcoxon_stat, wilcoxon_p = wilcoxon_result.statistic, wilcoxon_result.pvalue
    except ValueError as exc:
        # All-zero deltas (or n<1) — wilcoxon can't run on a degenerate
        # input; report why instead of crashing the whole script.
        wilcoxon_stat, wilcoxon_p = float("nan"), float("nan")
        print(f"  [{name}] Wilcoxon skipped: {exc}", file=sys.stderr)

    significant = not np.isnan(wilcoxon_p) and wilcoxon_p < 0.05
    return (
        f"### {name}\n\n"
        f"n = {len(deltas)} paired observations\n"
        f"mean delta = {mean_delta:+.4f}\n"
        f"95% bootstrap CI = [{ci_low:+.4f}, {ci_high:+.4f}]\n"
        f"Wilcoxon signed-rank: statistic={wilcoxon_stat:.2f}, p={wilcoxon_p:.4f}\n"
        f"significant at alpha=0.05: {'yes' if significant else 'no'}\n"
    )


def gpcs_vs_self_consistency_deltas(claims: pd.DataFrame) -> np.ndarray:
    """Per (scenario, context_condition): GPCS unsupported rate minus
    self-consistency unsupported rate, over that group's scored claims."""
    scored = claims.dropna(subset=["gpcs_trust_score"])
    grouped = scored.groupby(["scenario_id", "context_condition"])
    gpcs_rate = grouped["gpcs_unsupported"].mean()
    sc_rate = grouped["self_consistency_unsupported"].mean()
    return (gpcs_rate - sc_rate).to_numpy(dtype=float)


def hybrid_vs_raw_agreement_deltas(claims: pd.DataFrame) -> np.ndarray:
    """Per scenario: hybrid's claim-agreement rate minus raw's, paired on
    scenario_id (only scenarios with both conditions present)."""
    scored = claims.dropna(subset=["gpcs_trust_score"])
    # "agreement" is an object-dtype column of real bool/None values (same
    # CSV round-trip as gpcs_unsupported above) — .mean() already treats
    # True=1/False=0/None=skipped correctly, no need for an explicit
    # comparison to True (which also trips flake8's E712).
    per_condition = scored.groupby(["scenario_id", "context_condition"])[
        "agreement"
    ].mean()
    pivot = per_condition.unstack("context_condition").dropna(subset=["hybrid", "raw"])
    return (pivot["hybrid"] - pivot["raw"]).to_numpy(dtype=float)


def hybrid_vs_keyword_recall_deltas(neurosymbolic: pd.DataFrame) -> np.ndarray:
    """Per scenario: hybrid's tag recall minus keyword's, paired on
    scenario_id."""

    def _recall(row: pd.Series) -> float:
        expected = [t for t in str(row["expected_tags"]).split(";") if t]
        hit = [t for t in str(row["hit_tags"]).split(";") if t]
        return len(hit) / len(expected) if expected else np.nan

    df = neurosymbolic.copy()
    df["recall"] = df.apply(_recall, axis=1)
    pivot = df.pivot(index="scenario_id", columns="method", values="recall")
    pivot = pivot.dropna(subset=["hybrid", "keyword"])
    return (pivot["hybrid"] - pivot["keyword"]).to_numpy(dtype=float)


def agents_vs_single_llm_deltas(matched_compute: pd.DataFrame) -> np.ndarray:
    """Per scenario: the real 5-agent system's GPCS-unsupported rate minus
    the matched-compute single-LLM baseline's — the matched-compute
    control (see dissertation/PROGRESS.md Week 8,
    NOVEL_CONTRIBUTIONS.md Contribution 5). Both arms are scored by the
    same GPCS instance on the same hybrid-retrieval evidence, so this
    isolates architecture (5 specialists + consensus) from raw compute (5
    independent single-LLM samples)."""
    df = matched_compute[~matched_compute["excluded"]]
    return (df["agents_unsupported_rate"] - df["single_llm_unsupported_rate"]).to_numpy(
        dtype=float
    )


def main() -> None:
    """Load the real result data, compute the four paired deltas, and
    write the significance report."""
    claims_path = RESULTS_DIR / "claims.csv"
    ns_path = RESULTS_DIR / "neurosymbolic_retrieval_detail.csv"
    matched_compute_path = RESULTS_DIR / "matched_compute_raw.csv"
    if not claims_path.exists() or not ns_path.exists():
        print(
            f"Error: expected data files not found under {RESULTS_DIR}",
            file=sys.stderr,
        )
        sys.exit(1)

    claims = pd.read_csv(claims_path)
    neurosymbolic = pd.read_csv(ns_path)
    matched_compute = (
        pd.read_csv(matched_compute_path) if matched_compute_path.exists() else None
    )

    sections = [
        _report(
            "GPCS vs. self-consistency unsupported-rate delta "
            "(positive = GPCS flags MORE unsupported than self-consistency)",
            gpcs_vs_self_consistency_deltas(claims),
        ),
        _report(
            "hybrid vs. raw-context claim-agreement-rate delta "
            "(positive = hybrid agrees with self-consistency more often)",
            hybrid_vs_raw_agreement_deltas(claims),
        ),
        _report(
            "hybrid vs. keyword retrieval tag-recall delta "
            "(positive = hybrid recovers more expected tags; this is "
            "recall, not full F1 -- see module docstring)",
            hybrid_vs_keyword_recall_deltas(neurosymbolic),
        ),
    ]
    if matched_compute is not None:
        sections.append(
            _report(
                "real 5-agent system vs. matched-compute single-LLM "
                "unsupported-rate delta (positive = the 5-agent system "
                "hallucinates MORE than a single LLM sampled the same "
                "number of times)",
                agents_vs_single_llm_deltas(matched_compute),
            )
        )

    header = (
        "# Significance tests (paired bootstrap CI + Wilcoxon)\n\n"
        "n=25 scenarios gives wide confidence intervals by construction — "
        "treat every result below as such, not as a precise point "
        "estimate.\n\n"
    )
    output = header + "\n".join(sections)
    out_path = RESULTS_DIR / "significance_tests.md"
    out_path.write_text(output, encoding="utf-8")
    print(output)
    print(f"Saved to {out_path}")


if __name__ == "__main__":
    main()
