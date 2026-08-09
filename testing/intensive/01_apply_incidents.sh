#!/usr/bin/env bash
# Applies one or more demo incident manifests to a live cluster so there's
# something real and broken for CloudGraph's "Run AI Diagnosis" / the
# benchmark pipeline to actually investigate. The incidents themselves are
# defined in services/api/app/demo/incident_scenario.py (DEMO_INCIDENTS) —
# this script is just the thin kubectl-apply wrapper around them.
#
# Split out of the old apply_demo_incidents.sh into the 00/01/02/03
# sequence (prereqs / apply / verify / teardown) — each step now does one
# thing, and 02_verify_incidents.sh is new: confirming the incidents are
# actually visible to CloudGraph (not just "kubectl apply succeeded") is
# what "so a user can click Run AI Diagnosis" actually requires.
#
# Usage:
#   ./01_apply_incidents.sh                  # apply all incidents
#   ./01_apply_incidents.sh crashloop         # apply just one, by name
#   ./01_apply_incidents.sh --list            # list available incident names
set -euo pipefail

# shellcheck source=testing/intensive/_common.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_common.sh"

if [[ "${1:-}" == "--list" ]]; then
  generate_manifests | cut -f1
  exit 0
fi

echo "Generating demo incident manifests..."
manifest_list="$(generate_manifests)"
echo "$manifest_list"
echo

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
echo "Watch rollout with: kubectl -n $NAMESPACE get pods"
echo "Verify visible to CloudGraph: ./02_verify_incidents.sh"
echo "Teardown with:                ./03_teardown_incidents.sh"
