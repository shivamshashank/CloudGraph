"""Generates the 3 figures this project's results section needs (see
dissertation/PROGRESS.md Week 8), script-generated (not hand-edited) from
the already-saved real result
data under experiments/results/ — makes no LLM calls, no live cluster
access needed.

1. Bar chart: retrieval recall by method, with 95% bootstrap CI error bars.
   Not F1 — experiments/results/neurosymbolic_retrieval_detail.csv (from
   the actual Day 2/3 report run) only tracked hit/missed expected tags,
   never false positives, so precision/F1 can't be reconstructed from that
   run without re-querying live. A fresh live re-query was tried and
   rejected: over this long session, real CloudGraph operational incidents
   (unrelated pod restarts, etc.) have accumulated in Neo4j and now
   pollute keyword search's top-k results for the benchmark scenarios —
   confirmed live (scenario-01's keyword TP dropped from 2, in the
   original saved run, to 0 against current graph state). Re-querying now
   would show retrieval performing worse than what was actually measured,
   an apples-to-oranges comparison against every other figure/number in
   this directory. Using the original run's saved counts keeps this
   figure consistent with the rest of experiments/results/ — labeled
   accurately as recall, not mislabeled as F1.
2. Grouped bar chart: unsupported-claim-rate by claim type — GPCS
   (all conditions) vs. self-consistency (all conditions) vs. GPCS under
   the raw-context condition specifically (ties Day 2's core comparison to
   Day 3's raw-context finding in one figure).
3. Heatmap: the agreement/disagreement cross-tab
   (agreement_crosstab.csv) — claim_type x (gpcs_unsupported,
   self_consistency_unsupported).

Usage (from services/api):
    .venv/bin/python scripts/make_figures.py
"""

import sys
from pathlib import Path

import _bootstrap
import _mpl_backend

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

print(f"[make_figures] matplotlib backend: {_mpl_backend.BACKEND}", file=sys.stderr)

RESULTS_DIR = _bootstrap.REPO_ROOT / "experiments" / "results"
FIGURES_DIR = _bootstrap.REPO_ROOT / "experiments" / "figures"

BOOTSTRAP_SEED = 42
BOOTSTRAP_RESAMPLES = 10000

METHOD_ORDER = ["keyword", "vector", "hybrid"]
METHOD_LABELS = {
    "keyword": "keyword\n(symbolic)",
    "vector": "vector\n(neural)",
    "hybrid": "hybrid\n(neuro-symbolic)",
}
CLAIM_TYPE_ORDER = ["state", "causal", "entity_relationship", "general", "temporal"]


def _bootstrap_mean_ci(
    values: np.ndarray,
    n_resamples: int = BOOTSTRAP_RESAMPLES,
    seed: int = BOOTSTRAP_SEED,
) -> tuple[float, float, float]:
    """Returns (mean, ci_low, ci_high) via percentile bootstrap on the mean."""
    rng = np.random.default_rng(seed)
    means = np.array(
        [
            rng.choice(values, size=len(values), replace=True).mean()
            for _ in range(n_resamples)
        ]
    )
    ci_low, ci_high = np.percentile(means, [2.5, 97.5])
    return float(values.mean()), float(ci_low), float(ci_high)


def make_retrieval_recall_figure(neurosymbolic: pd.DataFrame, out_path: Path) -> None:
    """Figure 1: retrieval recall by method with bootstrap CI error bars."""

    def _recall(row: pd.Series) -> float:
        expected = [t for t in str(row["expected_tags"]).split(";") if t]
        hit = [t for t in str(row["hit_tags"]).split(";") if t]
        return len(hit) / len(expected) if expected else np.nan

    df = neurosymbolic.copy()
    df["recall"] = df.apply(_recall, axis=1)

    means, lowers, uppers = [], [], []
    for method in METHOD_ORDER:
        values = df.loc[df["method"] == method, "recall"].dropna().to_numpy(dtype=float)
        mean, ci_low, ci_high = _bootstrap_mean_ci(values)
        means.append(mean)
        lowers.append(mean - ci_low)
        uppers.append(ci_high - mean)

    fig, ax = plt.subplots(figsize=(6, 4.5))
    x = np.arange(len(METHOD_ORDER))
    ax.bar(
        x,
        means,
        yerr=[lowers, uppers],
        capsize=6,
        color=["#4C72B0", "#DD8452", "#55A868"],
    )
    ax.set_xticks(x)
    ax.set_xticklabels([METHOD_LABELS[m] for m in METHOD_ORDER])
    ax.set_ylabel("Tag recall (mean, 95% bootstrap CI)")
    ax.set_ylim(0, 1.05)
    # Derived, never hardcoded: this read "n=25" through a 36-scenario run.
    ax.set_title(
        f"Retrieval recall by method (n={neurosymbolic['scenario_id'].nunique()}"
        " scenarios)"
    )
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    print(f"Saved {out_path}")


def make_unsupported_rate_figure(claims: pd.DataFrame, out_path: Path) -> None:
    """Figure 2: unsupported-claim-rate by claim type — GPCS vs.
    self-consistency vs. GPCS-under-raw-context."""
    scored = claims.dropna(subset=["gpcs_trust_score"])

    gpcs_rate = scored.groupby("claim_type")["gpcs_unsupported"].mean()
    sc_rate = scored.groupby("claim_type")["self_consistency_unsupported"].mean()
    raw_only = scored[scored["context_condition"] == "raw"]
    gpcs_raw_rate = raw_only.groupby("claim_type")["gpcs_unsupported"].mean()

    types = [t for t in CLAIM_TYPE_ORDER if t in gpcs_rate.index]
    x = np.arange(len(types))
    width = 0.25

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.bar(
        x - width,
        gpcs_rate.reindex(types),
        width,
        label="GPCS (all conditions)",
        color="#4C72B0",
    )
    ax.bar(
        x,
        sc_rate.reindex(types),
        width,
        label="Self-consistency (all conditions)",
        color="#DD8452",
    )
    ax.bar(
        x + width,
        gpcs_raw_rate.reindex(types),
        width,
        label="GPCS (raw-context only)",
        color="#C44E52",
    )
    ax.set_xticks(x)
    ax.set_xticklabels(types, rotation=20, ha="right")
    ax.set_ylabel("Unsupported-claim rate")
    ax.set_ylim(0, 1.0)
    ax.set_title("Unsupported-claim rate by claim type")
    ax.legend()
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    print(f"Saved {out_path}")


def make_agreement_heatmap(crosstab_path: Path, out_path: Path) -> None:
    """Figure 3: the GPCS/self-consistency agreement crosstab as a heatmap."""
    df = pd.read_csv(crosstab_path, header=[0, 1], index_col=0)
    col_order = [
        ("False", "False"),
        ("False", "True"),
        ("True", "False"),
        ("True", "True"),
    ]
    df = df[[c for c in col_order if c in df.columns]]
    col_labels = [
        "GPCS: Sup.\nSC: Sup.",
        "GPCS: Sup.\nSC: Unsup.",
        "GPCS: Unsup.\nSC: Sup.",
        "GPCS: Unsup.\nSC: Unsup.",
    ]

    fig, ax = plt.subplots(figsize=(8, 5))
    im = ax.imshow(df.to_numpy(), cmap="Blues", aspect="auto")
    ax.set_xticks(np.arange(len(col_labels)))
    ax.set_xticklabels(col_labels, fontsize=9)
    ax.set_yticks(np.arange(len(df.index)))
    ax.set_yticklabels(df.index)
    for i in range(df.shape[0]):
        for j in range(df.shape[1]):
            value = df.iat[i, j]
            ax.text(
                j,
                i,
                str(value),
                ha="center",
                va="center",
                color="white" if value > df.to_numpy().max() / 2 else "black",
            )
    ax.set_title("GPCS vs. self-consistency agreement, by claim type (counts)")
    fig.colorbar(im, ax=ax, label="claim count")
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    print(f"Saved {out_path}")


def main() -> None:
    """Load the real result data and generate all 3 figures."""
    claims_path = RESULTS_DIR / "claims.csv"
    ns_path = RESULTS_DIR / "neurosymbolic_retrieval_detail.csv"
    crosstab_path = RESULTS_DIR / "agreement_crosstab.csv"
    missing = [p for p in (claims_path, ns_path, crosstab_path) if not p.exists()]
    if missing:
        print(f"Error: missing input files: {missing}", file=sys.stderr)
        sys.exit(1)

    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    claims = pd.read_csv(claims_path)
    neurosymbolic = pd.read_csv(ns_path)

    make_retrieval_recall_figure(neurosymbolic, FIGURES_DIR / "retrieval_recall.png")
    make_unsupported_rate_figure(
        claims, FIGURES_DIR / "unsupported_rate_by_claim_type.png"
    )
    make_agreement_heatmap(crosstab_path, FIGURES_DIR / "agreement_heatmap.png")


if __name__ == "__main__":
    main()
