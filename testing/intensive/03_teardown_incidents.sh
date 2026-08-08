#!/usr/bin/env bash
# Deletes all demo incident deployments. Split out of the old
# apply_demo_incidents.sh --teardown flag into its own script — see
# 01_apply_incidents.sh's header for why.
#
# Usage:
#   ./03_teardown_incidents.sh
set -euo pipefail

# shellcheck source=testing/intensive/_common.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_common.sh"

echo "Deleting all demo incident deployments in $NAMESPACE..."
for name in "${DEMO_DEPLOYMENTS[@]}"; do
  kubectl delete deployment "$name" -n "$NAMESPACE" --ignore-not-found
done
