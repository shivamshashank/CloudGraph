"""Merges the batched `cloudgraph report` runs into the single dataset the
paper and dissertation are written from.

Batching is an operational artefact, not an experimental factor: the report
job holds its state in memory (app/research/report_runner.py), so a crash
part-way through a full run loses everything since the last saved batch.
Nothing downstream should ever group by batch — and in this dataset it would
be actively misleading, because the stratified selection order makes batch
*confounded with fault type* (each batch of 6 covers only 2 of the 6 fault
types, while being perfectly balanced 2/2/2 across the 3 systems). The
merged rows therefore carry source_system and fault_type, which are the real
pre-specified strata, alongside batch, which is retained only so a
leave-one-batch-out robustness check remains possible.

The summary and crosstab are recomputed from the merged claims using
report_runner's own helpers, so a merged run is computed identically to a
single unbatched run rather than by a parallel implementation that could
drift.

Integrity is enforced, not assumed: the merge aborts on duplicated claims,
on any row whose GPCS score belongs to a different claim than the one it is
reported against, and on any claim that reproduces held-out ground truth.
Each of those has been a real defect in this pipeline, and a silent merge
would launder it into the final dataset.

Usage (from services/api):
    .venv/bin/python scripts/merge_reports.py \\
        ../../experiments/batches/batch-* --out ../../experiments/results
"""

import argparse
import csv
import gzip
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import _bootstrap

from app.demo.datasets import load_scenarios
from app.research.report_runner import (
    CLAIM_FIELDNAMES,
    CONTEXT_CONDITIONS,
    NEUROSYMBOLIC_FIELDNAMES,
    _condition_summary,
    _overall_summary,
    _rows_to_csv,
)

# The stratum columns every merged row carries, plus the operational batch
# label. Kept separate from report_runner's per-batch fieldnames so the
# per-batch artefacts stay exactly as the API produced them.
DEFAULT_OUT_DIR = _bootstrap.REPO_ROOT / "experiments" / "results"

STRATUM_FIELDNAMES = ["source_system", "fault_type", "batch"]
MERGED_CLAIM_FIELDNAMES = CLAIM_FIELDNAMES + STRATUM_FIELDNAMES
# strict_correct re-scores retrieval as "every expected tag retrieved". The
# shipped `correct` flag needs only half the tags, which on this benchmark
# the service name alone satisfies, so it reads 100% for all three methods
# and cannot distinguish them. Both are kept: `correct` is what the run
# produced, `strict_correct` is what discriminates.
MERGED_NEUROSYMBOLIC_FIELDNAMES = (
    NEUROSYMBOLIC_FIELDNAMES
    + ["n_expected_tags", "n_hit_tags", "strict_correct", "recall", "precision", "f1"]
    + STRATUM_FIELDNAMES
)


def _parse_bool_or_none(value: str) -> bool | None:
    if value in ("", "None", "nan"):
        return None
    return value == "True"


def _parse_float_or_none(value: str) -> float | None:
    if value in ("", "None", "nan"):
        return None
    return float(value)


def _scenario_strata() -> dict[str, dict[str, str]]:
    """Map scenario_id -> {source_system, fault_type}.

    fault_type is the fault token of the RCAEval case name
    (e.g. "re2ob_checkoutservice_cpu_1" -> "cpu"); the trailing integer is
    the case index within that cell, not part of the fault name.
    """
    strata = {}
    for scenario in load_scenarios():
        case = scenario.get("source_case", "")
        fault = re.sub(r"_\d+$", "", case).split("_")[-1] if case else ""
        strata[scenario["id"]] = {
            "source_system": scenario.get("source_system", ""),
            "fault_type": fault,
        }
    return strata


def _ground_truth() -> dict[str, list[str]]:
    return {s["id"]: s.get("ground_truth_claims", []) for s in load_scenarios()}


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
                "gpcs_claim_text": row.get("gpcs_claim_text", ""),
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
                "batch": report_dir.name,
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
        rows = list(csv.DictReader(f))
    for row in rows:
        expected = [t for t in row.get("expected_tags", "").split(";") if t]
        hit = [t for t in row.get("hit_tags", "").split(";") if t]
        row["n_expected_tags"] = len(expected)
        row["n_hit_tags"] = len(hit)
        row["strict_correct"] = 1 if expected and len(hit) == len(expected) else 0
        # Report these rather than the shipped `correct` flag, which needs
        # only half the expected tags and is satisfied by the service name
        # alone — it reads 6/6 for all three methods and cannot separate
        # them, while strict matching gives keyword 0/6 vs vector and
        # hybrid 3/6 on the same data.
        #
        # precision divides by the retrieval cutoff (n_results), so it is
        # bounded above by n_expected_tags/n_results and is not comparable
        # to a standard IR precision. It ranks the methods against each
        # other on identical cutoffs; recall and strict accuracy are the
        # figures to quote.
        n_results = int(row.get("n_results") or 0)
        recall = len(hit) / len(expected) if expected else 0.0
        precision = len(hit) / n_results if n_results else 0.0
        row["recall"] = round(recall, 4)
        row["precision"] = round(precision, 4)
        row["f1"] = (
            round(2 * precision * recall / (precision + recall), 4)
            if precision + recall
            else 0.0
        )
        row["batch"] = report_dir.name
    return rows


def _load_requests_log(report_dir: Path) -> list[dict[str, Any]]:
    path = report_dir / "requests_log.jsonl"
    if not path.exists():
        print(
            f"  [warn] no requests_log.jsonl in {report_dir} — LLM audit trail"
            " for this batch is missing"
        )
        return []
    records = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                record = json.loads(line)
                record["batch"] = report_dir.name
                records.append(record)
    return records


def _check_integrity(
    claims: list[dict[str, Any]], ground_truth: dict[str, list[str]]
) -> list[str]:
    """Return a list of integrity failures; empty means the merge is sound."""
    failures = []

    seen: set[tuple[str, str, str]] = set()
    duplicates = set()
    for claim in claims:
        key = (claim["scenario_id"], claim["context_condition"], claim["claim_id"])
        if key in seen:
            duplicates.add(key)
        seen.add(key)
    if duplicates:
        failures.append(
            f"{len(duplicates)} duplicated (scenario, condition, claim_id) keys — "
            f"overlapping batch offsets? e.g. {sorted(duplicates)[:3]}"
        )

    # A populated GPCS score must belong to the claim it is reported against.
    mismatched = [
        c
        for c in claims
        if c["gpcs_claim_text"]
        and c["claim_text"].strip() != c["gpcs_claim_text"].strip()
    ]
    if mismatched:
        failures.append(
            f"{len(mismatched)} rows where gpcs_claim_text != claim_text — the "
            "GPCS/self-consistency join is broken; scores describe other claims"
        )

    echoed = [
        c
        for c in claims
        if any(
            gt.strip() and gt.strip().lower() == c["claim_text"].strip().lower()
            for gt in ground_truth.get(c["scenario_id"], [])
        )
    ]
    if echoed:
        failures.append(
            f"{len(echoed)} claims reproduce held-out ground truth verbatim — "
            "possible ground-truth leakage into generation"
        )

    return failures


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_json(path: Path) -> dict[str, Any] | None:
    """Per-batch provenance, absent for batches produced before it was
    recorded — reported as None rather than silently omitted, so a mixed
    dataset is visible in the manifest."""
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None


def _read_text(path: Path) -> str | None:
    return path.read_text().strip() if path.exists() else None


def _stratum_counts(
    scenario_ids: set[str], strata: dict[str, dict[str, str]], key: str
) -> dict[str, int]:
    counts: dict[str, int] = {}
    for scenario_id in scenario_ids:
        value = strata.get(scenario_id, {}).get(key, "?")
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def _build_summary(
    collected: dict[str, Any],
    strata: dict[str, dict[str, str]],
    expected_scenarios: int,
    agreement_summary: str,
    condition_summary: dict[str, str],
) -> str:
    """Render summary.txt, including the stratum breakdowns that should be
    reported and an explicit warning against reporting by batch."""
    scenario_ids = collected["scenario_ids"]
    total_attempts = len(scenario_ids) * len(CONTEXT_CONDITIONS)
    condition_lines = "\n".join(
        f"  context={condition:<6} "
        f"{condition_summary.get(condition, 'no claims scored')}"
        for condition in CONTEXT_CONDITIONS
    )
    by_system = _stratum_counts(scenario_ids, strata, "source_system")
    system_lines = "\n".join(
        f"  {name:<18} {count} scenarios" for name, count in by_system.items()
    )
    fault_lines = "\n".join(
        f"  {name:<18} {count} scenarios"
        for name, count in _stratum_counts(scenario_ids, strata, "fault_type").items()
    )

    warning = ""
    if len(scenario_ids) != expected_scenarios:
        warning = (
            f"\n!! INCOMPLETE: {len(scenario_ids)} of {expected_scenarios} scenarios.\n"
            "!! Batch is confounded with fault type, so a partial merge is\n"
            "!! skewed, not merely smaller — some fault types are absent\n"
            "!! entirely. Do not report results from this dataset.\n"
        )

    return (
        "CloudGraph Research Report (merged)\n"
        "===================================\n"
        f"Generated:           {datetime.now(timezone.utc).isoformat()}\n"
        f"Source batches:      {collected['n_batches']}\n"
        f"Scenarios:           {len(scenario_ids)}/{expected_scenarios}\n"
        f"Excluded attempts:   {len(collected['excluded'])}/{total_attempts} "
        "(scenario x context-condition)\n"
        f"Claims scored:       {len(collected['claims'])}\n"
        f"LLM calls logged:    {len(collected['requests'])}\n"
        f"Agreement:           {agreement_summary}\n"
        f"{condition_lines}\n"
        f"{warning}"
        "\nScenarios by system (pre-specified stratum):\n"
        f"{system_lines}\n"
        "\nScenarios by fault type (pre-specified stratum):\n"
        f"{fault_lines}\n"
        "\nNote: `batch` is operational only and is confounded with fault\n"
        "type. Report by system or fault type, never by batch.\n"
    )


def _write_manifest(
    report_dirs: list[Path],
    collected: dict[str, Any],
    out_dir: Path,
    expected_scenarios: int,
) -> None:
    """Record provenance: which batch produced which scenarios, and the
    checksum of every input and output, so the dataset backing a published
    number can be traced to the runs that produced it."""
    scenario_ids = collected["scenario_ids"]
    claims = collected["claims"]
    manifest = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "n_scenarios": len(scenario_ids),
        "n_expected_scenarios": expected_scenarios,
        "complete": len(scenario_ids) == expected_scenarios,
        "n_claims": len(claims),
        "n_excluded_attempts": len(collected["excluded"]),
        "n_llm_calls": len(collected["requests"]),
        "integrity_checks_passed": True,
        "source_batches": [
            {
                "dir": str(report_dir),
                "run_metadata": _read_json(report_dir / "run_metadata.json"),
                "image_digest": _read_text(report_dir / "image_digest.txt"),
                "claims_sha256": (
                    _sha256(report_dir / "claims.csv")
                    if (report_dir / "claims.csv").exists()
                    else None
                ),
                "scenarios": sorted(
                    {c["scenario_id"] for c in claims if c["batch"] == report_dir.name}
                ),
            }
            for report_dir in report_dirs
        ],
        "outputs": {
            name: _sha256(out_dir / name)
            for name in (
                "claims.csv",
                "agreement_crosstab.csv",
                "neurosymbolic_retrieval_detail.csv",
                "requests_log.jsonl.gz",
                "summary.txt",
            )
        },
    }
    (out_dir / "MANIFEST.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )


def _collect(report_dirs: list[Path]) -> dict[str, Any]:
    """Read every batch directory into one set of concatenated records."""
    claims: list[dict[str, Any]] = []
    excluded: list[dict[str, str]] = []
    neurosymbolic: list[dict[str, Any]] = []
    requests: list[dict[str, Any]] = []
    scenario_ids: set[str] = set()

    for report_dir in report_dirs:
        print(f"Reading {report_dir}...")
        batch_claims = _load_claims(report_dir)
        claims.extend(batch_claims)
        excluded.extend(_load_excluded(report_dir))
        neurosymbolic.extend(_load_neurosymbolic(report_dir))
        requests.extend(_load_requests_log(report_dir))
        scenario_ids.update(c["scenario_id"] for c in batch_claims)
        scenario_ids.update(e["scenario_id"] for e in excluded)

    return {
        "claims": claims,
        "excluded": excluded,
        "neurosymbolic": neurosymbolic,
        "requests": requests,
        "scenario_ids": scenario_ids,
        "n_batches": len(report_dirs),
    }


def merge(report_dirs: list[Path], out_dir: Path, expected_scenarios: int) -> None:
    """Concatenate every batch, enrich with strata, verify, and write out."""
    collected = _collect(report_dirs)
    strata = _scenario_strata()
    blank = {"source_system": "", "fault_type": ""}
    for row in collected["claims"] + collected["neurosymbolic"]:
        row.update(strata.get(row["scenario_id"], blank))

    failures = _check_integrity(collected["claims"], _ground_truth())
    if failures:
        print("\nMerge aborted — integrity checks failed:", file=sys.stderr)
        for failure in failures:
            print(f"  - {failure}", file=sys.stderr)
        sys.exit(1)

    agreement_summary, crosstab_csv = _overall_summary(collected["claims"])
    condition_summary = (
        _condition_summary(collected["claims"]) if collected["claims"] else {}
    )

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "claims.csv").write_text(
        _rows_to_csv(collected["claims"], MERGED_CLAIM_FIELDNAMES), encoding="utf-8"
    )
    (out_dir / "agreement_crosstab.csv").write_text(crosstab_csv, encoding="utf-8")
    (out_dir / "excluded_scenarios.json").write_text(
        json.dumps(collected["excluded"], indent=2), encoding="utf-8"
    )
    (out_dir / "neurosymbolic_retrieval_detail.csv").write_text(
        _rows_to_csv(collected["neurosymbolic"], MERGED_NEUROSYMBOLIC_FIELDNAMES),
        encoding="utf-8",
    )
    # Gzipped: this is ~7MB of raw JSON per full run, and it is evidence
    # rather than a convenience artefact — the ground-truth leakage checks
    # run against it, so it has to stay in the repo rather than be
    # regenerated. Compressed it is small enough to track honestly.
    with gzip.open(out_dir / "requests_log.jsonl.gz", "wt", encoding="utf-8") as fh:
        fh.write("\n".join(json.dumps(r) for r in collected["requests"]) + "\n")

    summary_text = _build_summary(
        collected, strata, expected_scenarios, agreement_summary, condition_summary
    )
    (out_dir / "summary.txt").write_text(summary_text, encoding="utf-8")
    _write_manifest(report_dirs, collected, out_dir, expected_scenarios)

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
        "--out",
        type=Path,
        default=DEFAULT_OUT_DIR,
        help=f"Output directory for the merged report (default: {DEFAULT_OUT_DIR})",
    )
    parser.add_argument(
        "--expected-scenarios",
        type=int,
        default=36,
        help="Scenario count a complete run should cover (default: the full benchmark)",
    )
    args = parser.parse_args()

    missing = [d for d in args.report_dirs if not d.is_dir()]
    if missing:
        print(f"Error: these directories don't exist: {missing}", file=sys.stderr)
        sys.exit(1)

    merge(sorted(args.report_dirs), args.out, args.expected_scenarios)


if __name__ == "__main__":
    main()
