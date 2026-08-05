#!/usr/bin/env bash
# Runs the full 25-scenario GPCS-vs-self-consistency comparison from a full
# source checkout (services/api/scripts/generate_research_report.py) — the
# actual result behind research/7_DAY_SPRINT_CHECKLIST.md's Day 2 and
# research/NOVEL_CONTRIBUTIONS.md's Contribution 2.
#
# If you installed via install.sh (no local checkout), use
# `cloudgraph report` instead — it drives the same underlying logic over
# HTTP against a running CloudGraph API. This script is for local dev
# against a full clone, where running it directly avoids the extra HTTP
# round-trip and lets you inspect intermediate files as they're written.
#
# This is a thin wrapper, not a reimplementation: it exists to (a) verify
# the stack is actually reachable before burning potentially hours of local
# LLM inference, (b) set the one env var that's bitten us every session
# (NEO4J_PASSWORD), and (c) print a real summary at the end instead of
# leaving you to go read three separate output files by hand.
#
# Usage:
#   NEO4J_PASSWORD=... ./run_report_full.sh [api-base-url]
#   ./run_report_full.sh                          # defaults to http://localhost:8000
#   REPORT_SCENARIO_LIMIT=5 ./run_report_full.sh  # pilot run, not the full 25
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
API_DIR="$ROOT_DIR/services/api"
API_BASE="${1:-http://localhost:8000}"
RESULTS_DIR="$ROOT_DIR/experiments/results"

if [[ -z "${NEO4J_PASSWORD:-}" ]]; then
  echo "NEO4J_PASSWORD is not set." >&2
  echo "This has silently broken every prior run this session — the API and" >&2
  echo "this script both talk to Neo4j directly, and its actual password is" >&2
  echo "whatever was set when the container/pod was first created, not the" >&2
  echo "client library's empty-string default." >&2
  echo "Set it explicitly, e.g.: NEO4J_PASSWORD=cloudgraph_dev_password $0" >&2
  exit 1
fi

echo "=== Pre-flight checks ==="

check_url() {
  local label="$1" url="$2"
  if curl -s -m 5 -o /dev/null -w "" "$url"; then
    echo "  [ok] $label ($url)"
  else
    echo "  [FAIL] $label unreachable at $url" >&2
    return 1
  fi
}

fail=0
check_url "CloudGraph API" "$API_BASE/health" || fail=1
check_url "Ollama" "http://localhost:11434/api/tags" || fail=1

settings_json="$(curl -s -m 5 "$API_BASE/api/v1/settings" || echo '{}')"
provider="$(echo "$settings_json" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("settings",{}).get("provider",""))' 2>/dev/null || echo "")"
model="$(echo "$settings_json" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("settings",{}).get("model",""))' 2>/dev/null || echo "")"

if [[ "$provider" == "ollama" && -n "$model" ]]; then
  echo "  [ok] CloudGraph connected to local model: $model"
else
  echo "  [FAIL] No local model connected (provider='$provider' model='$model')." >&2
  echo "         Run: cloudgraph deploy llm $API_BASE" >&2
  fail=1
fi

if [[ "$fail" -ne 0 ]]; then
  echo
  echo "Pre-flight checks failed — not starting the run. Fix the above first." >&2
  exit 1
fi

echo
if [[ -n "${REPORT_SCENARIO_LIMIT:-}" ]]; then
  echo "=== Generating report (PILOT — REPORT_SCENARIO_LIMIT=$REPORT_SCENARIO_LIMIT) ==="
else
  echo "=== Generating report (FULL — all 25 scenarios; this can take a long" \
       "time on local CPU inference, easily an hour or more) ==="
fi

cd "$API_DIR"
NEO4J_PASSWORD="$NEO4J_PASSWORD" .venv/bin/python scripts/generate_research_report.py

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
