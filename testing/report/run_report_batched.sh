#!/usr/bin/env bash
# Runs the full GPCS-vs-self-consistency comparison from a full source
# checkout, in batches, then merges them — this is how the real 36-scenario
# result in experiments/ was actually produced (6 batches of 6). Replaces the old
# run_report_full.sh, which only ran a single monolithic pass with no
# offset/batching support — a real mid-run crash cost 19/25 scenarios of
# progress once this session (the report job's state is in-memory only, by
# design — see app/research/report_runner.py's docstring), which is why
# batching exists: a crash mid-batch only costs that batch, not the whole
# run.
#
# Each batch writes to its own temp directory (REPORT_RESULTS_DIR) so
# batches don't clobber each other, then scripts/merge_reports.py combines
# them into experiments/results/.
#
# Usage:
#   NEO4J_PASSWORD=... ./run_report_batched.sh [api-base-url]
#   ./run_report_batched.sh                              # 5 batches of 5 (25 total)
#   REPORT_BATCH_SIZE=10 REPORT_TOTAL_SCENARIOS=20 ./run_report_batched.sh
#   ./run_report_batched.sh --full                        # old single-shot behavior, no batching
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
API_DIR="$ROOT_DIR/services/api"
RESULTS_DIR="$ROOT_DIR/experiments/results"
PREREQS_SCRIPT="$ROOT_DIR/testing/intensive/00_check_prereqs.sh"

full_mode=0
api_base="http://localhost:8000"
for arg in "$@"; do
  case "$arg" in
    --full) full_mode=1 ;;
    *) api_base="$arg" ;;
  esac
done

if [[ -z "${NEO4J_PASSWORD:-}" ]]; then
  echo "NEO4J_PASSWORD is not set." >&2
  echo "This has silently broken prior runs — the API and this script both" >&2
  echo "talk to Neo4j directly, and its actual password is whatever was set" >&2
  echo "when the container/pod was first created, not the client library's" >&2
  echo "empty-string default." >&2
  echo "Set it explicitly, e.g.: NEO4J_PASSWORD=cloudgraph_dev_password $0" >&2
  exit 1
fi

"$PREREQS_SCRIPT" "$api_base"
echo

run_batch() {
  local results_dir="$1" limit="${2:-}" offset="${3:-}"
  mkdir -p "$results_dir"
  local env_args=("NEO4J_PASSWORD=$NEO4J_PASSWORD" "REPORT_RESULTS_DIR=$results_dir")
  [[ -n "$limit" ]] && env_args+=("REPORT_SCENARIO_LIMIT=$limit")
  [[ -n "$offset" ]] && env_args+=("REPORT_SCENARIO_OFFSET=$offset")
  (cd "$API_DIR" && env "${env_args[@]}" .venv/bin/python scripts/generate_research_report.py)
}

if [[ "$full_mode" -eq 1 ]]; then
  echo "=== Generating report (FULL — single pass, no batching; can take" \
       "hours on local CPU inference) ==="
  run_batch "$RESULTS_DIR"
else
  batch_size="${REPORT_BATCH_SIZE:-5}"
  total="${REPORT_TOTAL_SCENARIOS:-25}"
  echo "=== Generating report in batches of $batch_size (total $total scenarios) ==="

  work_dir="$(mktemp -d)"
  trap 'rm -rf "$work_dir"' EXIT
  batch_dirs=()

  offset=0
  batch_num=1
  while [[ "$offset" -lt "$total" ]]; do
    batch_dir="$work_dir/batch_${batch_num}"
    echo
    echo "--- Batch $batch_num: --limit $batch_size --offset $offset ---"
    run_batch "$batch_dir" "$batch_size" "$offset"
    batch_dirs+=("$batch_dir")
    offset=$((offset + batch_size))
    batch_num=$((batch_num + 1))
  done

  echo
  echo "=== Merging ${#batch_dirs[@]} batches into $RESULTS_DIR ==="
  (cd "$API_DIR" && .venv/bin/python scripts/merge_reports.py "${batch_dirs[@]}" --out "$RESULTS_DIR")
fi

echo
echo "=== Summary ==="
python3 - "$RESULTS_DIR" <<'PY'
import csv
import json
import sys
from pathlib import Path

results_dir = Path(sys.argv[1])
claims_path = results_dir / "claims.csv"
excluded_path = results_dir / "excluded_scenarios.json"
crosstab_path = results_dir / "agreement_crosstab.csv"

n_claims = 0
if claims_path.exists():
    with claims_path.open() as f:
        n_claims = sum(1 for _ in csv.DictReader(f))

n_excluded = 0
if excluded_path.exists():
    n_excluded = len(json.loads(excluded_path.read_text() or "[]"))

print(f"Claims scored:      {n_claims}")
print(f"Scenarios excluded: {n_excluded}")
print(f"Claims file:        {claims_path}")
print(f"Excluded file:      {excluded_path}")
print(f"Crosstab file:      {crosstab_path}")

if n_claims == 0:
    print()
    print("No real data was produced — every scenario was excluded. Check")
    print(f"{excluded_path} for why before trusting anything downstream.")
    sys.exit(1)
PY

echo
echo "Next: scripts/paired_bootstrap.py and scripts/make_figures.py (or"
echo "just run testing/verify/run_verification.sh) to regenerate the"
echo "significance tests and figures from this new data."
