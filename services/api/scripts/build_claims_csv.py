#!/usr/bin/env python3
"""Rebuild `claims.csv` from the raw run logs.

The logs in `experiment-1-benchmark/logs/` are the authority: they are the only
artefact produced by a committed tool (`scripts/trace_scenario.py`). Every field
`claims.csv` holds is present in them, so the CSV is a deterministic function of
the logs rather than a hand-derived file.

This script makes that derivation reproducible by command. It performs **no
labelling of its own** -- the correctness verdicts it reads were already decided
during the run by the deterministic labeller in `label_claim_correctness.py`.
Nothing here is manual, and re-running it on the same logs yields the same CSV.

Usage:
    .venv/bin/python scripts/build_claims_csv.py LOG_DIR DATASET_JSON OUT_CSV
"""

from __future__ import annotations

import csv
import gzip
import json
import pathlib
import re
import sys

COLUMNS = [
    "scenario_id",
    "system",
    "target_entity",
    "injected_fault",
    "context_condition",
    "claim_id",
    "claim_text",
    "gpcs_trust_score",
    "gpcs_unsupported",
    "sc_recurrence_rate",
    "sc_unsupported",
    "verifiers_agree",
    "joint_verdict",
    "correctness_label",
    "label_reason",
    "evaluable",
]

# One row of the side-by-side verdict table:
#   #   TRUST  GPCS         RECUR  SELF-CONSISTENCY  CLAIM
#   1   0.708  supported      1.0  supported         Pod '...' is located on ...
TABLE_ROW = re.compile(
    r"^\s+(\d+)\s+"
    r"(\d\.\d{3})\s+"
    r"(supported|UNSUPPORTED)\s+"
    r"(\d\.\d)\s+"
    r"(supported|UNSUPPORTED)\s+"
    r"(.*?)\s*$"
)

# `  claim  7: CONSISTENT    (names the injected mechanism (cpu))`
LABEL_LINE = re.compile(
    r"claim\s+(\d+):\s+(CONSISTENT|CONTRADICTED|UNVERIFIABLE)\s*\((.*)\)\s*$"
)

CLAIM_TEXT_WIDTH = 52


def _read(path: pathlib.Path) -> str:
    if path.suffix == ".gz":
        with gzip.open(path, "rt", errors="replace") as handle:
            return handle.read()
    return path.read_text(errors="replace")


def _scenario_and_condition(name: str) -> tuple[str, str]:
    """Split `rcaeval-03-HYBRID.log.gz` into ("rcaeval-03", "hybrid")."""
    for suffix in (".log.gz", ".log"):
        if name.endswith(suffix):
            name = name[: -len(suffix)]
            break
    scenario_id, _, condition = name.rpartition("-")
    return scenario_id, condition.lower()


def _verdict_table(text: str) -> dict[int, tuple[str, str, str, str, str]]:
    """Read the side-by-side verdict table: index -> (trust, gpcs, recur, sc, text)."""
    found: dict[int, tuple[str, str, str, str, str]] = {}
    for line in text.splitlines():
        match = TABLE_ROW.match(line)
        if match:
            # Keep the first occurrence: that is the scored run.
            found.setdefault(int(match.group(1)), match.group(2, 3, 4, 5, 6))
    return found


def _labels(text: str) -> dict[int, tuple[str, str]]:
    """Read the labeller's verdicts: index -> (label, reason)."""
    found: dict[int, tuple[str, str]] = {}
    for line in text.splitlines():
        match = LABEL_LINE.search(line)
        if match:
            found.setdefault(int(match.group(1)), (match.group(2), match.group(3)))
    return found


def _joint(gpcs_unsupported: bool, sc_unsupported: bool) -> str:
    """Name the agreement cell the two verifiers land in."""
    if gpcs_unsupported and sc_unsupported:
        return "both_unsupported"
    if gpcs_unsupported:
        return "gpcs_only_flagged"
    if sc_unsupported:
        return "sc_only_flagged"
    return "both_supported"


def _row(scenario_id: str, condition: str, index: int, entry, label_pair) -> dict:
    """Build one CSV row from a verdict-table entry and its label."""
    trust, gpcs_word, recur, sc_word, claim_text = entry
    gpcs_flagged = gpcs_word == "UNSUPPORTED"
    sc_flagged = sc_word == "UNSUPPORTED"
    label, reason = label_pair
    return {
        "scenario_id": scenario_id,
        "context_condition": condition,
        "claim_id": f"claim-{index}",
        "claim_text": claim_text[:CLAIM_TEXT_WIDTH],
        "gpcs_trust_score": trust,
        "gpcs_unsupported": "TRUE" if gpcs_flagged else "FALSE",
        "sc_recurrence_rate": recur,
        "sc_unsupported": "TRUE" if sc_flagged else "FALSE",
        "verifiers_agree": "TRUE" if gpcs_flagged == sc_flagged else "FALSE",
        "joint_verdict": _joint(gpcs_flagged, sc_flagged),
        "correctness_label": label.lower(),
        "label_reason": reason,
        "evaluable": "TRUE" if label != "UNVERIFIABLE" else "FALSE",
    }


def parse_log(path: pathlib.Path) -> tuple[str, list[dict[str, str]]]:
    """Return (scenario_id, rows) for one run log."""
    scenario_id, condition = _scenario_and_condition(path.name)
    text = _read(path)
    labels = _labels(text)
    return scenario_id, [
        _row(scenario_id, condition, i, e, labels.get(i, ("UNVERIFIABLE", "")))
        for i, e in sorted(_verdict_table(text).items())
    ]


def _sorted_logs(log_dir: pathlib.Path, order: dict[str, int]) -> list[pathlib.Path]:
    """Logs in dataset order, then none -> raw -> hybrid within each scenario."""
    conditions = {"none": 0, "raw": 1, "hybrid": 2}

    def key(path: pathlib.Path) -> tuple[int, int]:
        scenario_id, condition = _scenario_and_condition(path.name)
        return order.get(scenario_id, 1 << 30), conditions.get(condition, 1 << 30)

    return sorted(list(log_dir.glob("*.log.gz")) + list(log_dir.glob("*.log")), key=key)


def _collect(log_dir: pathlib.Path, meta: dict) -> list[dict[str, str]]:
    """Parse every log in dataset order and stamp each row with scenario metadata."""
    order = {scenario_id: i for i, scenario_id in enumerate(meta)}
    rows: list[dict[str, str]] = []
    for path in _sorted_logs(log_dir, order):
        scenario_id, parsed = parse_log(path)
        if scenario_id not in meta:
            print(f"  skip (not in dataset): {path.name}", file=sys.stderr)
            continue
        system, target, fault = meta[scenario_id]
        for row in parsed:
            row["system"] = system
            row["target_entity"] = target
            row["injected_fault"] = fault
        rows.extend(parsed)
        print(f"  {path.name}: {len(parsed)} claims", file=sys.stderr)
    return rows


def main(argv: list[str]) -> int:
    """Parse every log in LOG_DIR and write the claims CSV."""
    if len(argv) != 4:
        print(__doc__, file=sys.stderr)
        return 2
    log_dir, dataset_path, out_csv = (pathlib.Path(a) for a in argv[1:])

    meta = {
        s["id"]: (s["source_system"], s["target_service"], s["root_cause"])
        for s in json.loads(dataset_path.read_text())
    }
    rows = _collect(log_dir, meta)

    with out_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row[k] for k in COLUMNS})

    print(f"wrote {len(rows)} rows to {out_csv}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
