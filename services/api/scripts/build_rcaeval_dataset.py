"""Builds CloudGraph benchmark scenarios from the RCAEval RE2 dataset.

RCAEval (Pham et al., FSE'26 / WWW'25 / ASE'24; Zenodo DOI
10.5281/zenodo.14590730, MIT licensed) provides real chaos-injected
failure cases collected from three microservice systems running on
Kubernetes, with per-second metrics, container logs, and distributed
traces. This script selects a stratified subset and converts each case
into the same scenario dict shape `app/demo/benchmark_dataset.py` uses,
so the existing evaluation pipeline runs unchanged over real telemetry.

Why this exists: the hand-authored benchmark in `benchmark_dataset.py`
is synthetic, which limits how far its results generalise. RCAEval cases
are real faults injected into real running systems, so a finding that
holds on both is substantially better evidenced than one that holds only
on authored templates.

## Leakage discipline (read before changing this file)

The same separation `benchmark_dataset.py` enforces applies here, and is
easy to break accidentally:

- `observed_symptoms` is built ONLY from raw telemetry: metric
  before/after deltas and real log lines. Metric deltas are emitted for
  *every* service in the system, never filtered to the faulty one —
  filtering to the anomalous service would be leakage by selection, since
  picking which service to show is itself the answer.
- `ground_truth_claims` is derived from RCAEval's own label (root-cause
  service + fault type) and is held out for scoring only.

## Task shape (an explicit, documented choice)

RCAEval's label identifies *which service* was faulted. This script sets
`target_entity` to that service, matching the existing benchmark's shape:
the system is told which entity is affected and must diagnose *why*.
That means this benchmark measures fault-type diagnosis, NOT root-cause
service localisation — the localisation task would require seeding a
downstream symptom entity instead. Stated plainly so results are not
over-claimed as "the system found the culprit service."

Usage (from services/api):
    .venv/bin/python scripts/build_rcaeval_dataset.py --n-cases 25
"""

import argparse
import collections
import json
import re
import sys
from pathlib import Path

import _bootstrap  # noqa: F401  (sys.path side effect)
import pandas as pd
from huggingface_hub import list_repo_files, snapshot_download

REPO_ID = "phamquiluan/RCAEval"
SUITE = "re2"

# RCAEval encodes the label in the case directory name:
#   re2ob_checkoutservice_cpu_1
#   ^^^^^ ^^^^^^^^^^^^^^^ ^^^ ^
#   suite  root-cause svc  fault  instance
CASE_RE = re.compile(r"^(re2[a-z]+)_(.+)_([a-z]+)_(\d+)$")

SYSTEM_NAMES = {
    "re2ob": "Online Boutique",
    "re2ss": "Sock Shop",
    "re2tt": "Train Ticket",
}

# How RCAEval's fault codes map onto a human-readable cause description.
# Used only to build the held-out ground_truth_claims, never the inputs.
FAULT_DESCRIPTIONS = {
    "cpu": ("cpu_exhaustion", "CPU resource exhaustion"),
    "mem": ("memory_exhaustion", "memory resource exhaustion"),
    "disk": ("disk_saturation", "disk I/O saturation"),
    "delay": ("network_delay", "injected network latency"),
    "loss": ("packet_loss", "network packet loss"),
    "socket": ("socket_exhaustion", "socket/connection exhaustion"),
}

# Number of metric observations to include per case. Covers every service
# in the system (see leakage note above), ranked by magnitude of change
# the way a monitoring dashboard would surface them.
N_METRIC_OBSERVATIONS = 14
N_LOG_OBSERVATIONS = 12

# Some upstream logs (notably Train Ticket's auth service) contain issued
# JWTs and session UUIDs. They are from a public demo system rather than
# real users, but credential-shaped strings should not be committed into
# this repository: they trip secret scanners for everyone who works on it
# and they carry no diagnostic signal for a resource/network fault. The
# structure of the line is what matters — that a token was issued — not
# the token body, so the value is replaced and the line kept.
_REDACTIONS = (
    (
        re.compile(r"eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}(?:\.[A-Za-z0-9_-]+)?"),
        "<JWT_REDACTED>",
    ),
    (
        re.compile(
            r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b",
            re.IGNORECASE,
        ),
        "<UUID_REDACTED>",
    ),
)


def redact_secrets(text: str) -> str:
    """Strip credential-shaped values from a raw log line."""
    for pattern, replacement in _REDACTIONS:
        text = pattern.sub(replacement, text)
    return text


def parse_case_name(case: str):
    """Return (system_key, root_cause_service, fault_code, instance)."""
    match = CASE_RE.match(case)
    if not match:
        return None
    return match.group(1), match.group(2), match.group(3), int(match.group(4))


def _group_cases_into_cells(all_cases):
    """Bucket case names by (system, fault-type), instance-ordered."""
    cells = collections.defaultdict(list)
    for case in all_cases:
        parsed = parse_case_name(case)
        if parsed:
            system, _service, fault, _inst = parsed
            cells[(system, fault)].append(case)
    for key in cells:
        cells[key].sort(key=lambda c: parse_case_name(c)[3])
    return cells


def _partial_round_order(available, remaining, stride):
    """Choose which cells give up a case in an incomplete final round.

    Taking `available[:remaining]` would pile every extra case onto
    whichever system (or fault type) sorts first. Walking with a stride
    coprime to the cell count spreads the extras across both axes: for 25
    cases over 18 cells this holds the max-min spread at 1 for systems
    *and* fault types, where the naive slice gives a 3x imbalance.
    """
    order, seen, pos = [], set(), 0
    while len(order) < remaining:
        cell = available[pos % len(available)]
        if cell not in seen:
            seen.add(cell)
            order.append(cell)
        pos += stride
    return order


def select_stratified_cases(all_cases, n_cases):
    """Pick n_cases balanced across (system x fault-type) cells.

    Round-robins over the cells in a fixed order, taking the
    lowest-numbered unused instance from each in turn, so the selection is
    deterministic and reproducible rather than randomly sampled.
    """
    cells = _group_cases_into_cells(all_cases)
    ordered_cells = sorted(cells.keys(), key=lambda cell: (cell[1], cell[0]))
    stride = 5 if len(ordered_cells) % 5 else 1

    selected, round_idx = [], 0
    while len(selected) < n_cases:
        remaining = n_cases - len(selected)
        available = [c for c in ordered_cells if round_idx < len(cells[c])]
        if not available:
            break
        round_order = (
            available
            if remaining >= len(available)
            else _partial_round_order(available, remaining, stride)
        )
        for cell in round_order:
            selected.append(cells[cell][round_idx])
        round_idx += 1
    return selected


def _metric_observations(metrics_df, inject_time):
    """Render before/after metric changes as raw observation strings.

    Emits observations across ALL services, ranked by magnitude of
    change — never filtered to the faulted service (see module docstring
    on leakage by selection).
    """
    before = metrics_df[metrics_df["time"] < inject_time]
    after = metrics_df[metrics_df["time"] >= inject_time]
    if before.empty or after.empty:
        return []

    changes = []
    for col in metrics_df.columns:
        if col == "time":
            continue
        b_mean, a_mean = before[col].mean(), after[col].mean()
        if pd.isna(b_mean) or pd.isna(a_mean):
            continue
        # Relative change, guarding a near-zero baseline.
        denom = abs(b_mean) if abs(b_mean) > 1e-9 else 1e-9
        ratio = abs(a_mean - b_mean) / denom
        changes.append((ratio, col, b_mean, a_mean))

    changes.sort(reverse=True)
    observations = []
    for _ratio, col, b_mean, a_mean in changes[:N_METRIC_OBSERVATIONS]:
        observations.append(
            f"metric {col}: mean {b_mean:.4g} in the 12min before "
            f"{inject_time}, {a_mean:.4g} in the 12min after"
        )
    return observations


def _log_observations(logs_df, inject_time):
    """Sample real container log lines from around the injection window."""
    if logs_df.empty:
        return []
    window = logs_df[
        (logs_df["timestamp"] >= inject_time - 60)
        & (logs_df["timestamp"] <= inject_time + 300)
    ]
    if window.empty:
        window = logs_df

    # Spread across containers rather than taking the first N rows, which
    # would over-represent whichever service is chattiest.
    observations, seen = [], set()
    for _idx, row in window.iterrows():
        key = (row["container_name"], str(row["message"])[:120])
        if key in seen:
            continue
        seen.add(key)
        observations.append(
            f"log [{row['container_name']}] "
            f"{redact_secrets(str(row['message']))[:200]}"
        )
        if len(observations) >= N_LOG_OBSERVATIONS:
            break
    return observations


def build_scenario(case_dir: Path, case_name: str, index: int):
    """Convert one downloaded RCAEval case into a CloudGraph scenario."""
    parsed = parse_case_name(case_name)
    if not parsed:
        return None
    system_key, service, fault, _instance = parsed

    inject_time = int((case_dir / "inject_time.txt").read_text().strip())
    metrics_df = pd.read_parquet(case_dir / "metrics.parquet")
    logs_df = pd.read_parquet(case_dir / "logs.parquet")

    observed = _metric_observations(metrics_df, inject_time) + _log_observations(
        logs_df, inject_time
    )
    root_cause_code, fault_phrase = FAULT_DESCRIPTIONS[fault]

    return {
        "id": f"rcaeval-{index:02d}",
        "source_case": case_name,
        "source_system": SYSTEM_NAMES.get(system_key, system_key),
        "query": f"{service} degraded performance investigation",
        "target_service": service,
        "target_entity": service,
        "root_cause": root_cause_code,
        "expected_tags": sorted({service, fault, root_cause_code.split("_")[0]}),
        "inject_time": inject_time,
        "observed_symptoms": observed,
        # Held out for scoring only — never seeded, never prompted.
        "ground_truth_claims": [
            f"Service {service} was affected by {fault_phrase}",
            f"The {fault} fault on {service} degraded its observed behaviour",
        ],
    }


def _parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n-cases", type=int, default=25)
    parser.add_argument(
        "--data-dir",
        default=str(_bootstrap.REPO_ROOT / "experiments" / "rcaeval_data"),
    )
    parser.add_argument(
        "--out",
        default=str(
            _bootstrap.API_ROOT / "app" / "demo" / "rcaeval_dataset_generated.json"
        ),
    )
    return parser.parse_args()


def _list_complete_cases():
    """Return case names carrying every file the conversion needs.

    Upstream ships a small number of incomplete cases (at time of
    writing, exactly one RE2 case has no logs.parquet). Filtering them
    here rather than after download means the stratified selection still
    returns a full, balanced n.
    """
    required = {"inject_time.txt", "metrics.parquet", "logs.parquet"}
    per_case = collections.defaultdict(set)
    for path in list_repo_files(REPO_ID, repo_type="dataset"):
        parts = path.split("/")
        if len(parts) == 2 and parts[0].startswith(SUITE):
            per_case[parts[0]].add(parts[1])
    complete = sorted(c for c, files in per_case.items() if required <= files)
    return complete, len(per_case) - len(complete)


def _download_cases(selected, data_dir):
    """Fetch only metrics/logs/inject_time. Traces are ~10MB per case and
    unused by this conversion, so they are deliberately not downloaded."""
    data_dir.mkdir(parents=True, exist_ok=True)
    snapshot_download(
        repo_id=REPO_ID,
        repo_type="dataset",
        allow_patterns=[f"{case}/metrics.parquet" for case in selected]
        + [f"{case}/logs.parquet" for case in selected]
        + [f"{case}/inject_time.txt" for case in selected],
        local_dir=str(data_dir),
    )


def _convert_cases(selected, data_dir):
    """Convert each downloaded case, skipping any that fail to parse."""
    scenarios = []
    for index, case in enumerate(selected, start=1):
        try:
            scenario = build_scenario(data_dir / case, case, index)
        except (OSError, ValueError, KeyError) as exc:
            print(f"  SKIP {case}: {exc}", file=sys.stderr, flush=True)
            continue
        if scenario:
            scenarios.append(scenario)
            print(
                f"  [{index:2}/{len(selected)}] {case} -> "
                f"{len(scenario['observed_symptoms'])} observations",
                flush=True,
            )
    return scenarios


def main():
    """Select, download, and convert an RCAEval RE2 subset."""
    args = _parse_args()

    print(f"Listing {REPO_ID} ...", flush=True)
    all_cases, incomplete = _list_complete_cases()
    print(
        f"  {len(all_cases)} complete {SUITE} cases available"
        f" ({incomplete} skipped as incomplete)",
        flush=True,
    )

    selected = select_stratified_cases(all_cases, args.n_cases)
    print(f"Selected {len(selected)} stratified cases:", flush=True)
    dist = collections.Counter(
        (parse_case_name(c)[0], parse_case_name(c)[2]) for c in selected
    )
    for (system, fault), count in sorted(dist.items()):
        print(f"  {system:8} {fault:8} x{count}", flush=True)

    data_dir = Path(args.data_dir)
    print(f"\nDownloading metrics/logs for {len(selected)} cases ...", flush=True)
    _download_cases(selected, data_dir)

    scenarios = _convert_cases(selected, data_dir)

    out_path = Path(args.out)
    out_path.write_text(json.dumps(scenarios, indent=2), encoding="utf-8")
    print(f"\nWrote {len(scenarios)} scenarios to {out_path}", flush=True)


if __name__ == "__main__":
    main()
