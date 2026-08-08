#!/usr/bin/env bash
# Confirms the applied demo incidents are actually visible to CloudGraph —
# not just "kubectl apply succeeded," which apply_demo_incidents.sh's old
# monolithic version stopped at. Triggers cluster discovery (the same step
# the UI does before "Run AI Diagnosis" works) and checks the broken pods
# actually appear as graph nodes, then prints exactly what to click next.
#
# Usage:
#   ./02_verify_incidents.sh [api-base-url] [ui-base-url]
#   ./02_verify_incidents.sh                                    # defaults below
set -euo pipefail

# shellcheck source=testing/intensive/_common.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_common.sh"

API_BASE="${1:-http://localhost:8000}"
UI_BASE="${2:-http://localhost:3000}"

echo "=== Pod status ($NAMESPACE) ==="
kubectl get pods -n "$NAMESPACE"

not_ready=0
for name in "${DEMO_DEPLOYMENTS[@]}"; do
  status="$(kubectl get pods -n "$NAMESPACE" -l "app=$name" \
    -o jsonpath='{.items[0].status.phase}' 2>/dev/null || echo "NotFound")"
  echo "  $name: ${status:-NotFound}"
  if [[ "$status" == "NotFound" || -z "$status" ]]; then
    not_ready=$((not_ready + 1))
  fi
done

if [[ "$not_ready" -gt 0 ]]; then
  echo
  echo "$not_ready demo deployment(s) not found — run ./01_apply_incidents.sh first." >&2
  exit 1
fi

echo
echo "=== Triggering cluster discovery ==="
discover_json="$(curl -s -m 30 -X POST "$API_BASE/api/v1/graph/discover" || echo '{}')"
discover_status="$(echo "$discover_json" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("status",""))' 2>/dev/null || echo "")"
if [[ "$discover_status" != "success" ]]; then
  echo "  [FAIL] discovery did not report success: $discover_json" >&2
  exit 1
fi
echo "  [ok] discovery succeeded"

echo
echo "=== Confirming demo pods are visible in the graph ==="
graph_json="$(curl -s -m 15 "$API_BASE/api/v1/graph/data" || echo '{}')"
missing=0
for name in "${DEMO_DEPLOYMENTS[@]}"; do
  if echo "$graph_json" | python3 -c "
import json, sys
data = json.load(sys.stdin)
names = [n.get('name', '') for n in data.get('nodes', [])]
sys.exit(0 if any('$name' in n for n in names) else 1)
" 2>/dev/null; then
    echo "  [ok] $name visible in graph"
  else
    echo "  [FAIL] $name not found in graph data" >&2
    missing=$((missing + 1))
  fi
done

echo
if [[ "$missing" -gt 0 ]]; then
  echo "$missing incident(s) applied but not yet showing in the graph —" >&2
  echo "discovery may need a moment, or check cloudgraph-api logs." >&2
  exit 1
fi

echo "All demo incidents are live and visible to CloudGraph."
echo
echo "Next: open $UI_BASE, navigate to Topology Map or AI Diagnosis, and"
echo "click 'Run AI Diagnosis' on one of the broken pods above."
echo "(If $UI_BASE isn't reachable, port-forward first:"
echo "  kubectl port-forward -n $NAMESPACE svc/cloudgraph-ui 3000:3000)"
