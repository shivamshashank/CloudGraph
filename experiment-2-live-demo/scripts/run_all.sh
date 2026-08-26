#!/bin/bash
# Run all three retrieval conditions sequentially against the live cluster.
#
# 2700s budget per run: a single orchestrator call was measured at 280s
# (reasoning.effort=high), so 900s could not reliably fit 3 generations.
#
# PRECONDITION: backfill_from_neo4j() MUST run AFTER the fault is injected.
# Discovery writes the faulted container's logs into Neo4j, but they only become
# searchable once the backfill copies them into Qdrant. Run it before injecting
# and vector retrieval cannot see the fault.
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOGS="$ROOT/logs"
cd "$ROOT/../services/api" || exit 1
AUTH=$(kubectl get secret cloudgraph-neo4j-auth -n cloudgraph-system -o jsonpath='{.data.NEO4J_AUTH}' | base64 -d)
export NEO4J_URI=bolt://127.0.0.1:7687 NEO4J_AUTH="$AUTH"
export QDRANT_HOST=127.0.0.1 QDRANT_PORT=6333
export AGENT_ORCHESTRATOR_URL=http://localhost:8082
for C in none hybrid raw; do
  U=$(echo "$C" | tr '[:lower:]' '[:upper:]')
  if grep -q "FINAL RESULT" "$LOGS/live-$U.log" 2>/dev/null; then
    echo "=== $U already complete, skipping ==="
    continue
  fi
  echo "=== $U start $(date -u +%H:%M:%S) ==="
  timeout 2700 .venv/bin/python "$ROOT/scripts/trace_live.py" \
    live-checkout "$C" "$LOGS/live-$U.log" >/dev/null 2>&1
  echo "=== $U rc=$? $(date -u +%H:%M:%S) ==="
done
echo "FULL RUN COMPLETE"
for U in NONE RAW HYBRID; do
  grep -q "FINAL RESULT" "$LOGS/live-$U.log" 2>/dev/null && echo "  $U: OK" || echo "  $U: INCOMPLETE"
done
