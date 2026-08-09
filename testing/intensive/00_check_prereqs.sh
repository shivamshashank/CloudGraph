#!/usr/bin/env bash
# Pre-flight checks before applying demo incidents or running a report —
# same discipline as testing/report/run_report_batched.sh: fail fast with a
# clear reason rather than leave you debugging "nothing happened" further
# down the pipeline.
#
# Checks: kubectl reaches a cluster, the cloudgraph-system namespace and
# cloudgraph-api Deployment exist, the API's /health responds, and an LLM
# provider is actually connected via Settings (not just the API being up —
# "Run AI Diagnosis" and the report both need a real, non-fallback model).
#
# Usage:
#   ./00_check_prereqs.sh [api-base-url]
#   ./00_check_prereqs.sh                          # defaults to http://localhost:8000
set -euo pipefail

API_BASE="${1:-http://localhost:8000}"
fail=0

check() {
  local label="$1"
  shift
  if "$@" >/dev/null 2>&1; then
    echo "  [ok] $label"
  else
    echo "  [FAIL] $label" >&2
    fail=1
  fi
}

echo "=== Pre-flight checks ($API_BASE) ==="

check "kubectl reaches a cluster" kubectl cluster-info
check "cloudgraph-system namespace exists" kubectl get namespace cloudgraph-system
check "cloudgraph-api Deployment exists" kubectl get deployment cloudgraph-api -n cloudgraph-system

if curl -s -m 5 -o /dev/null "$API_BASE/health"; then
  echo "  [ok] CloudGraph API responds ($API_BASE/health)"
else
  echo "  [FAIL] CloudGraph API unreachable at $API_BASE/health" >&2
  fail=1
fi

settings_json="$(curl -s -m 5 "$API_BASE/api/v1/settings" || echo '{}')"
provider="$(echo "$settings_json" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("settings",{}).get("provider",""))' 2>/dev/null || echo "")"
model="$(echo "$settings_json" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("settings",{}).get("model",""))' 2>/dev/null || echo "")"

if [[ -n "$provider" && -n "$model" ]]; then
  echo "  [ok] LLM provider connected: $provider ($model)"
else
  echo "  [FAIL] No LLM provider connected (provider='$provider' model='$model')." >&2
  echo "         Configure one on the Settings page, or:" >&2
  echo "         curl -X POST $API_BASE/api/v1/settings -H 'Content-Type: application/json' \\" >&2
  echo "           -d '{\"provider\":\"openai\",\"api_key\":\"...\",\"model\":\"gpt-4o-mini\"}'" >&2
  fail=1
fi

echo
if [[ "$fail" -ne 0 ]]; then
  echo "Pre-flight checks failed — fix the above before applying incidents" >&2
  echo "or running a report." >&2
  exit 1
fi
echo "All checks passed."
