#!/usr/bin/env bash
# Shared setup for the testing/intensive/ scripts — sourced, not run
# directly. Keeps manifest generation in exactly one place rather than
# duplicated across 01_apply_incidents.sh and 03_teardown_incidents.sh.
#
# Uses plain system `python3`, not services/api/.venv — incident_scenario.py
# has zero third-party dependencies (stdlib only), so there's no need to
# set up the full API venv just to generate these manifests.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
API_DIR="$ROOT_DIR/services/api"
MANIFEST_DIR="$ROOT_DIR/testing/intensive/manifests"
# shellcheck disable=SC2034  # used by scripts that source this file
NAMESPACE="cloudgraph-system"

# Must match app/demo/incident_scenario.py's DEMO_INCIDENTS deployment
# names exactly — kept here as the single list both apply and teardown use.
# shellcheck disable=SC2034  # used by scripts that source this file
DEMO_DEPLOYMENTS=(
  demo-payment-app
  demo-checkout-app
  demo-cache-app
  demo-notification-app
  demo-search-app
)

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
