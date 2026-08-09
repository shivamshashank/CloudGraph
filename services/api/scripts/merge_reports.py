"""Merges multiple `cloudgraph report` output directories (e.g. from
batched runs — see `cloudgraph report --limit N --offset M`) into one
combined dataset, recomputing the overall summary/crosstab fresh from the
merged claims rather than trying to average the separate summaries.

Each input directory is expected to have the same layout `cloudgraph
report`/`generate_research_report.py` produce: claims.csv,
neurosymbolic_retrieval_detail.csv, excluded_scenarios.json, summary.txt.
Reuses report_runner's own summary/crosstab logic so the merged output is
computed identically to a single non-batched run — not a separate,
possibly-drifting reimplementation.

Usage (from services/api):
    .venv/bin/python scripts/merge_reports.py \\
        ~/.cloudgraph/reports/report-A ~/.cloudgraph/reports/report-B \\
        --out ~/.cloudgraph/reports/report-merged

Batches aren't validated for scenario overlap — if you accidentally merge
two batches covering the same scenario, that scenario's claims will simply
appear twice. Keep offsets/limits non-overlapping when running batches.
"""

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any


from app.research.report_runner import (
    CLAIM_FIELDNAMES,
    NEUROSYMBOLIC_FIELDNAMES,
    CONTEXT_CONDITIONS,
    _overall_summary,
    _condition_summary,
    _rows_to_csv,
)


def _parse_bool_or_none(value: str) -> bool | None:
    if value in ("", "None", "nan"):
        return None
    return value == "True"


def _parse_float_or_none(value: str) -> float | None:
    if value in ("", "None", "nan"):
        return None
    return float(value)


def _load_claims(report_dir: Path) -> list[dict[str, Any]]:
    path = report_dir / "claims.csv"
    if not path.exists():
        print(f"  [skip] no claims.csv in {report_dir}")
        return []
    with open(path, encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    parsed = []
    for row in rows:
        parsed.append(
            {
                "scenario_id": row["scenario_id"],
                "context_condition": row["context_condition"],
                "claim_id": row["claim_id"],
                "claim_text": row["claim_text"],
                "claim_type": row["claim_type"],
                "gpcs_trust_score": _parse_float_or_none(row["gpcs_trust_score"]),
                "gpcs_unsupported": _parse_bool_or_none(row["gpcs_unsupported"]),
                "self_consistency_recurrence_rate": float(
                    row["self_consistency_recurrence_rate"]
                ),
                "self_consistency_unsupported": _parse_bool_or_none(
                    row["self_consistency_unsupported"]
                ),
                "agreement": _parse_bool_or_none(row["agreement"]),
            }
        )
    return parsed


def _load_excluded(report_dir: Path) -> list[dict[str, str]]:
    path = report_dir / "excluded_scenarios.json"
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _load_neurosymbolic(report_dir: Path) -> list[dict[str, Any]]:
    path = report_dir / "neurosymbolic_retrieval_detail.csv"
    if not path.exists():
        return []
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def merge(report_dirs: list[Path], out_dir: Path) -> None:
    """Read claims/neurosymbolic/excluded data from each report_dirs entry,
    concatenate, recompute the summary, and write it all to out_dir."""
    all_claims: list[dict[str, Any]] = []
    all_excluded: list[dict[str, str]] = []
    all_neurosymbolic: list[dict[str, Any]] = []
    scenario_ids: set[str] = set()

    for report_dir in report_dirs:
        print(f"Reading {report_dir}...")
        claims = _load_claims(report_dir)
        all_claims.extend(claims)
        all_excluded.extend(_load_excluded(report_dir))
        all_neurosymbolic.extend(_load_neurosymbolic(report_dir))
        scenario_ids.update(c["scenario_id"] for c in claims)
        scenario_ids.update(e["scenario_id"] for e in all_excluded)

    agreement_summary, crosstab_csv = _overall_summary(all_claims)
    condition_summary = _condition_summary(all_claims) if all_claims else {}

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "claims.csv").write_text(
        _rows_to_csv(all_claims, CLAIM_FIELDNAMES), encoding="utf-8"
    )
    (out_dir / "agreement_crosstab.csv").write_text(crosstab_csv, encoding="utf-8")
    (out_dir / "excluded_scenarios.json").write_text(
        json.dumps(all_excluded, indent=2), encoding="utf-8"
    )
    (out_dir / "neurosymbolic_retrieval_detail.csv").write_text(
        _rows_to_csv(all_neurosymbolic, NEUROSYMBOLIC_FIELDNAMES), encoding="utf-8"
    )

    total_attempts = len(scenario_ids) * len(CONTEXT_CONDITIONS)
    condition_lines = "\n".join(
        f"  context={condition:<6} "
        f"{condition_summary.get(condition, 'no claims scored')}"
        for condition in CONTEXT_CONDITIONS
    )
    summary_text = (
        "CloudGraph Research Report (merged)\n"
        "====================================\n"
        f"Source directories:  {len(report_dirs)}\n"
        f"Scenarios:           {len(scenario_ids)}\n"
        f"Excluded attempts:   {len(all_excluded)}/{total_attempts} "
        "(scenario x context-condition)\n"
        f"Claims scored:       {len(all_claims)}\n"
        f"Agreement:           {agreement_summary}\n"
        f"{condition_lines}\n"
    )
    (out_dir / "summary.txt").write_text(summary_text, encoding="utf-8")

    print()
    print(summary_text)
    print(f"Merged report saved to: {out_dir}")


def main() -> None:
    """CLI entry point: parse args and merge the given report directories."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "report_dirs", nargs="+", type=Path, help="Report directories to merge"
    )
    parser.add_argument(
        "--out", required=True, type=Path, help="Output directory for the merged report"
    )
    args = parser.parse_args()

    missing = [d for d in args.report_dirs if not d.is_dir()]
    if missing:
        print(f"Error: these directories don't exist: {missing}", file=sys.stderr)
        sys.exit(1)

    merge(args.report_dirs, args.out)


if __name__ == "__main__":
    main()
