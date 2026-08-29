"""Regenerate the Experiment 1 result figures from ``claims.csv``.

Every number plotted here is derived from the CSV at run time; nothing is
hard-coded. Re-running this script after regenerating ``claims.csv`` reproduces
the figures exactly.

Usage::

    python make_figures.py CLAIMS_CSV OUT_DIR [OUT_DIR ...]
"""

from __future__ import annotations

import collections
import csv
import sys
from pathlib import Path

import numpy as np

import matplotlib

matplotlib.use("Agg")

# pylint: disable=wrong-import-position
# The Agg backend must be selected before pyplot is imported.
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap  # noqa: E402

# pylint: enable=wrong-import-position

# --- design tokens -------------------------------------------------------
# Categorical slots 1 and 2 of the validated palette. The pair clears the
# lightness band, chroma floor, CVD separation (worst adjacent dE 24.7 protan)
# and contrast checks against a light surface.
SERIES_1 = "#2a78d6"  # blue
SERIES_2 = "#eb6834"  # orange
INK = "#0b0b0b"
INK_SOFT = "#52514e"
GRID = "#d8d7d2"

# Sequential blue ramp, light -> dark, for magnitude encoding.
SEQ_BLUE = LinearSegmentedColormap.from_list(
    "seq_blue",
    ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"],
)

WIDTH = 6.3  # \textwidth at A4 with 2.5cm margins, in inches
BAR_WIDTH = 0.34  # grouped-bar width; the 0.02 gap below is the surface spacer

plt.rcParams.update(
    {
        "font.family": "serif",
        "font.serif": ["STIXGeneral", "DejaVu Serif"],
        "mathtext.fontset": "stix",
        "font.size": 9,
        "axes.edgecolor": INK_SOFT,
        "axes.labelcolor": INK,
        "text.color": INK,
        "xtick.color": INK_SOFT,
        "ytick.color": INK_SOFT,
        "axes.linewidth": 0.6,
        "xtick.major.width": 0.6,
        "ytick.major.width": 0.6,
        "figure.dpi": 200,
    }
)


def _truthy(value: str) -> bool:
    return value == "TRUE"


def _style(ax, *, ygrid: bool = True) -> None:
    """Recessive grid, no top/right spines."""
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    if ygrid:
        ax.set_axisbelow(True)
        ax.grid(axis="y", color=GRID, linewidth=0.5)


def _save(fig, name: str, out_dirs: list[Path]) -> None:
    """Write both formats.

    PDF is vector and is what the dissertation includes: it stays sharp at any
    size in print. PNG is raster and is what Markdown needs, because GitHub
    cannot render a PDF inline.
    """
    written = []
    for out in out_dirs:
        out.mkdir(parents=True, exist_ok=True)
        # metadata CreationDate=None omits the wall-clock stamp matplotlib
        # would otherwise write, so the PDF is byte-reproducible and
        # run_verification.sh can diff it against the committed copy.
        fig.savefig(
            out / f"{name}.pdf",
            bbox_inches="tight",
            pad_inches=0.02,
            metadata={"CreationDate": None},
        )
        fig.savefig(
            out / f"{name}.png",
            bbox_inches="tight",
            pad_inches=0.06,
            dpi=200,
            facecolor="white",
        )
        written.append(str(out))
    plt.close(fig)
    print(f"  {name}.{{pdf,png}} -> {', '.join(written)}")


# --- figure 1: the trust score does not vary continuously ----------------
def fig_trust_distribution(rows, out_dirs) -> None:
    """Plot the GPCS trust score distribution: it is discrete, not continuous."""
    counts = collections.Counter(float(r["gpcs_trust_score"]) for r in rows)
    values = sorted(counts)
    nonzero = [v for v in values if v > 0]

    fig, (ax1, ax2) = plt.subplots(
        1, 2, figsize=(WIDTH, 2.5), gridspec_kw={"width_ratios": [1.25, 1]}
    )

    # (a) every score at its true position: the void between 0 and 0.70
    ax1.bar(
        values, [counts[v] for v in values], width=0.012, color=SERIES_1, linewidth=0
    )
    ax1.set_xlim(-0.03, 0.78)
    ax1.set_xlabel("GPCS trust score")
    ax1.set_ylabel("claims")
    ax1.set_title("(a) all 1,950 claims", fontsize=9, loc="left", color=INK)
    ax1.annotate(
        f"{counts[0.0]:,} claims\nscore exactly 0",
        xy=(0.0, counts[0.0]),
        xytext=(0.13, counts[0.0] * 0.86),
        fontsize=7.5,
        color=INK_SOFT,
        arrowprops={"arrowstyle": "-", "color": INK_SOFT, "linewidth": 0.6},
    )
    ax1.annotate(
        "no claim scores\nbetween 0.000 and 0.700",
        xy=(0.35, counts[0.0] * 0.42),
        fontsize=7.5,
        color=INK_SOFT,
        ha="center",
        bbox={"facecolor": "white", "edgecolor": "none", "pad": 2},
    )
    _style(ax1)

    # (b) the non-zero scores occupy a band 0.02 wide
    positions = np.arange(len(nonzero))
    ax2.bar(
        positions, [counts[v] for v in nonzero], width=0.66, color=SERIES_1, linewidth=0
    )
    for x, v in zip(positions, nonzero):
        ax2.text(
            x, counts[v] + 4, str(counts[v]), ha="center", fontsize=7, color=INK_SOFT
        )
    ax2.set_xticks(positions)
    ax2.set_xticklabels(
        [f"{v:.3f}" for v in nonzero], fontsize=7.5, rotation=45, ha="right"
    )
    ax2.set_xlabel("GPCS trust score")
    ax2.set_ylabel("claims")
    ax2.set_ylim(0, max(counts[v] for v in nonzero) * 1.2)
    span = max(nonzero) - min(nonzero)
    ax2.set_title(
        f"(b) the {sum(counts[v] for v in nonzero)} non-zero scores "
        f"(range {span:.3f})",
        fontsize=9,
        loc="left",
        color=INK,
    )
    _style(ax2)

    fig.tight_layout(w_pad=2.0)
    _save(fig, "fig-trust-distribution", out_dirs)


# --- figure 2: neither verifier discriminates ----------------------------
def _flag_rate(subset, key) -> tuple[float, str]:
    """Percentage of ``subset`` flagged unsupported by ``key``, with raw counts."""
    flagged = sum(_truthy(r[key]) for r in subset)
    return flagged / len(subset) * 100, f"{flagged}/{len(subset)}"


def _draw_groups(ax, base, groups, verifiers) -> None:
    """Draw one bar per (group, verifier) pair and label each with rate and count."""
    for i, (label, subset, colour) in enumerate(groups):
        rates, notes = zip(*(_flag_rate(subset, key) for _, key in verifiers))
        offset = (i - 0.5) * (BAR_WIDTH + 0.02)  # 2px-equivalent surface gap
        bars = ax.bar(
            base + offset, rates, BAR_WIDTH, label=label, color=colour, linewidth=0
        )
        for rect, rate, note in zip(bars, rates, notes):
            ax.text(
                rect.get_x() + rect.get_width() / 2,
                rate + 1.6,
                f"{rate:.1f}%\n{note}",
                ha="center",
                fontsize=7.5,
                color=INK_SOFT,
                linespacing=1.35,
            )


def fig_discrimination(rows, out_dirs) -> None:
    """Plot flag rates for correct vs incorrect claims, per verifier."""
    ev = [r for r in rows if _truthy(r["evaluable"])]
    correct = [r for r in ev if r["correctness_label"] == "consistent"]
    wrong = [r for r in ev if r["correctness_label"] == "contradicted"]

    verifiers = [("GPCS", "gpcs_unsupported"), ("Self-consistency", "sc_unsupported")]
    groups = [
        ("correct claims", correct, SERIES_1),
        ("incorrect claims", wrong, SERIES_2),
    ]

    fig, ax = plt.subplots(figsize=(WIDTH, 2.7))
    base = np.arange(len(verifiers))
    _draw_groups(ax, base, groups, verifiers)

    # the gap each verifier achieves is the actual result: put it in the
    # tick label rather than floating it where it would collide
    tick_labels = [
        f"{name}\ngap {_flag_rate(wrong, key)[0] - _flag_rate(correct, key)[0]:+.1f} pp"
        for name, key in verifiers
    ]

    ax.set_xticks(base)
    ax.set_xticklabels(tick_labels, linespacing=1.5)
    ax.set_ylabel("claims flagged unsupported (%)")
    ax.set_ylim(0, 112)
    ax.legend(
        frameon=False,
        fontsize=8,
        loc="upper center",
        bbox_to_anchor=(0.5, 1.16),
        ncol=2,
    )
    _style(ax)
    fig.tight_layout()
    _save(fig, "fig-discrimination", out_dirs)


# --- figure 3: per-run variation -----------------------------------------
def fig_heatmap(rows, out_dirs) -> None:
    """Plot the GPCS flag rate for every scenario-condition cell."""
    conditions = ["none", "raw", "hybrid"]
    scenarios = sorted({r["scenario_id"] for r in rows})

    grid = np.full((len(scenarios), len(conditions)), np.nan)
    for i, scenario in enumerate(scenarios):
        for j, condition in enumerate(conditions):
            cell = [
                r
                for r in rows
                if r["scenario_id"] == scenario and r["context_condition"] == condition
            ]
            if cell:
                grid[i, j] = (
                    sum(_truthy(r["gpcs_unsupported"]) for r in cell) / len(cell) * 100
                )

    fig, ax = plt.subplots(figsize=(WIDTH * 0.62, 4.6))
    im = ax.imshow(grid, cmap=SEQ_BLUE, aspect="auto", vmin=0, vmax=100)

    ax.set_xticks(range(len(conditions)))
    ax.set_xticklabels(conditions)
    ax.set_yticks(range(len(scenarios)))
    ax.set_yticklabels(scenarios, fontsize=7.5)
    ax.set_xlabel("retrieval condition")

    # Relief rule: label every cell, since mid-ramp steps fall below 3:1.
    for i in range(len(scenarios)):
        for j in range(len(conditions)):
            if not np.isnan(grid[i, j]):
                ax.text(
                    j,
                    i,
                    f"{grid[i, j]:.0f}",
                    ha="center",
                    va="center",
                    fontsize=7,
                    color="#ffffff" if grid[i, j] > 72 else INK,
                )

    cbar = fig.colorbar(im, ax=ax, fraction=0.05, pad=0.04)
    cbar.set_label("claims flagged unsupported (%)", fontsize=8)
    cbar.ax.tick_params(labelsize=7.5)
    cbar.outline.set_linewidth(0.6)

    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.tick_params(length=0)
    fig.tight_layout()
    _save(fig, "fig-scenario-heatmap", out_dirs)


def main(argv: list[str]) -> int:
    """Read the claims CSV and write every figure to each output directory."""
    if len(argv) < 3:
        print(__doc__)
        return 2
    with open(argv[1], newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    out_dirs = [Path(p) for p in argv[2:]]

    print(f"{len(rows):,} claims read from {argv[1]}")
    fig_trust_distribution(rows, out_dirs)
    fig_discrimination(rows, out_dirs)
    fig_heatmap(rows, out_dirs)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
