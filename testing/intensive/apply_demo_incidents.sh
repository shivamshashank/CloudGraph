#!/usr/bin/env bash
# Applies one or more demo incident manifests to a live cluster so there's
# something real and broken for CloudGraph's "Run AI Diagnosis" / the
# benchmark pipeline to actually investigate.
#
# Replaces the old scripts/apply_demo_incident.sh, which only had one
# failure mode (ImagePullBackOff). The incidents themselves are defined in
# services/api/app/demo/incident_scenario.py (DEMO_INCIDENTS) — this script
# is just the thin kubectl-apply wrapper around them.
#
# Uses plain system `python3`, not services/api/.venv — incident_scenario.py
# has zero third-party dependencies (stdlib only), so there's no need to
# set up the full API venv just to generate these manifests.
#
# Usage:
#   ./apply_demo_incidents.sh                  # apply all incidents
#   ./apply_demo_incidents.sh crashloop         # apply just one, by name
#   ./apply_demo_incidents.sh --list            # list available incident names
#   ./apply_demo_incidents.sh --teardown        # delete all demo incident deployments
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
API_DIR="$ROOT_DIR/services/api"
MANIFEST_DIR="$ROOT_DIR/testing/intensive/manifests"

generate_manifests() {
  mkdir -p "$MANIFEST_DIR"
  python3 - "$API_DIR" "$MANIFEST_DIR" <<'PY'
import sys
sys.path.insert(0, sys.argv[1])
from app.demo.incident_scenario import write_all_demo_incident_manifests

written = write_all_demo_incident_manifests(sys.argv[2])
for name, path in written.items():
    print(f"{name}\t{path}")
PY
}

case "${1:-}" in
  --list)
    generate_manifests | cut -f1
    exit 0
    ;;
  --teardown)
    echo "Deleting all demo incident deployments in cloudgraph-system..."
    for name in demo-payment-app demo-checkout-app demo-cache-app \
                demo-notification-app demo-search-app; do
      kubectl delete deployment "$name" -n cloudgraph-system --ignore-not-found
    done
    exit 0
    ;;
esac

echo "Generating demo incident manifests..."
manifest_list="$(generate_manifests)"
echo "$manifest_list"

if [[ -n "${1:-}" ]]; then
  target_name="$1"
  target_path="$(echo "$manifest_list" | awk -F'\t' -v n="$target_name" '$1 == n { print $2 }')"
  if [[ -z "$target_path" ]]; then
    echo "Unknown incident: $target_name" >&2
    echo "Available: $(echo "$manifest_list" | cut -f1 | tr '\n' ' ')" >&2
    exit 1
  fi
  echo "Applying incident: $target_name"
  kubectl apply -f "$target_path"
else
  echo "Applying all incidents..."
  while IFS=$'\t' read -r name path; do
    echo "  -> $name"
    kubectl apply -f "$path"
  done <<< "$manifest_list"
fi

echo
echo "Watch rollout with: kubectl -n cloudgraph-system get pods"
echo "Teardown with:      $0 --teardown"
