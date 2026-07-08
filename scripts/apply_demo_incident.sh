#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MANIFEST_PATH="$ROOT_DIR/services/api/app/demo/demo_incident.yaml"

if [[ ! -f "$MANIFEST_PATH" ]]; then
  python3 - <<'PY' "$ROOT_DIR"
from pathlib import Path
import sys
sys.path.insert(0, sys.argv[1])
from services.api.app.demo.incident_scenario import write_demo_incident_manifest
write_demo_incident_manifest()
PY
fi

kubectl apply -f "$MANIFEST_PATH"

echo "Applied demo incident manifest: $MANIFEST_PATH"
echo "Watch the pod rollout with: kubectl -n cloudgraph-system get pods"
