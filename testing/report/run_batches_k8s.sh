#!/usr/bin/env bash
# Runs the research report over the full benchmark in batches, against a
# CloudGraph API deployed in Kubernetes.
#
# Why batches: the report job keeps its state in memory only
# (app/research/report_runner.py). A crash, an OOM kill, or a pod restart
# part-way through a full run loses everything since the start — which has
# already happened once, costing 19 scenarios of real LLM spend. Each batch
# here is fetched and written to disk as soon as it finishes, so a failure
# costs at most one batch.
#
# The API is ClusterIP-only, so every call goes through `kubectl exec` into
# the API pod rather than over the network from this host.
#
# Usage (from the repo root):
#   testing/report/run_batches_k8s.sh [BATCH_SIZE] [OUT_DIR]
#
# Then merge:
#   cd services/api && .venv/bin/python scripts/merge_reports.py \
#       <OUT_DIR>/batch-* --out ../../experiments/results
set -euo pipefail

BATCH_SIZE="${1:-6}"
OUT_DIR="${2:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)/experiments/batches}"
NAMESPACE="cloudgraph-system"
POLL_SECONDS=20
# A batch of 6 scenarios is 18 generation passes, each 3 samples x 6 LLM
# calls, and providers rate-limit. Generous ceiling; batches normally
# finish well inside it.
MAX_POLLS=540

kexec() {
  orb -m ubuntu sudo kubectl exec -n "$NAMESPACE" "$API_POD" -- "$@"
}

api_pod() {
  orb -m ubuntu sudo kubectl get pods -n "$NAMESPACE" --no-headers 2>/dev/null \
    | grep cloudgraph-api | grep Running | awk '{print $1}' | head -1
}

API_POD="$(api_pod)"
if [ -z "$API_POD" ]; then
  echo "No running cloudgraph-api pod found in $NAMESPACE." >&2
  exit 1
fi
echo "API pod: $API_POD"

# Scenario count comes from the deployed pod, not this checkout, so the
# batch plan always matches the dataset the run will actually use.
TOTAL="$(kexec python -c \
  'from app.demo.datasets import load_scenarios; print(len(load_scenarios()))')"
TOTAL="${TOTAL//[$'\r\n']/}"
echo "Scenarios in deployed dataset: $TOTAL"
mkdir -p "$OUT_DIR"

offset=0
batch=1
while [ "$offset" -lt "$TOTAL" ]; do
  batch_dir="$OUT_DIR/batch-$(printf '%02d' "$batch")"
  if [ -f "$batch_dir/claims.csv" ]; then
    echo "[batch $batch] already complete at $batch_dir — skipping"
    offset=$((offset + BATCH_SIZE)); batch=$((batch + 1)); continue
  fi

  echo "[batch $batch] starting: offset=$offset limit=$BATCH_SIZE"
  kexec python -c "
import urllib.request
req = urllib.request.Request(
    'http://localhost:8080/api/v1/research/report?limit=$BATCH_SIZE&offset=$offset',
    method='POST')
print(urllib.request.urlopen(req, timeout=30).read().decode())
"

  status=""
  for _ in $(seq 1 "$MAX_POLLS"); do
    sleep "$POLL_SECONDS"
    line="$(kexec python -c "
import urllib.request, json
d = json.load(urllib.request.urlopen(
    'http://localhost:8080/api/v1/research/report', timeout=20))
print(d['status'] + '|' + str(d.get('progress', '')))
" 2>/dev/null | tr -d '\r' | head -1)"
    status="${line%%|*}"
    echo "  [batch $batch] $line"
    [ "$status" = "completed" ] && break
    [ "$status" = "failed" ] && break
  done

  if [ "$status" != "completed" ]; then
    echo "[batch $batch] did not complete (status=$status). Stopping so the" >&2
    echo "  partial state can be inspected; completed batches are on disk." >&2
    exit 1
  fi

  # Write the batch out immediately — this is the whole point of batching.
  mkdir -p "$batch_dir"
  kexec python -c "
import urllib.request, json
d = json.load(urllib.request.urlopen(
    'http://localhost:8080/api/v1/research/report', timeout=60))
r = d['result']
out = {
    'claims.csv': r['claims_csv'],
    'neurosymbolic_retrieval_detail.csv': r['neurosymbolic_csv'],
    'agreement_crosstab.csv': r['agreement_crosstab_csv'],
    'excluded_scenarios.json': json.dumps(r['excluded_scenarios'], indent=2),
    # The per-call LLM audit trail exists only inside the in-memory job
    # result, so it has to be pulled here with everything else: starting the
    # next batch replaces it and it is gone. It is the only record of what
    # was actually sent to the provider, which is what the ground-truth
    # leakage check runs against.
    'requests_log.jsonl': '\n'.join(json.dumps(x) for x in r['requests_log']),
    'summary.txt': (
        f\"n_scenarios={r['n_scenarios']}\n\"
        f\"n_claims={r['n_claims']}\n\"
        f\"n_excluded={r['n_excluded']}\n\"
        f\"agreement_summary={r['agreement_summary']}\n\"
        f\"context_condition_summary=\"
        f\"{json.dumps(r['context_condition_summary'], indent=2)}\n\"
    ),
}
print(json.dumps(out))
" > "$batch_dir/_payload.json"

  python3 - "$batch_dir" <<'PY'
import json, pathlib, sys
d = pathlib.Path(sys.argv[1])
payload = json.loads((d / "_payload.json").read_text())
for name, content in payload.items():
    (d / name).write_text(content, encoding="utf-8")
(d / "_payload.json").unlink()
print(f"  wrote {len(payload)} files to {d}")
PY

  echo "[batch $batch] done -> $batch_dir"
  offset=$((offset + BATCH_SIZE))
  batch=$((batch + 1))
done

echo
echo "All batches complete. Merge with:"
echo "  cd services/api && .venv/bin/python scripts/merge_reports.py \\"
echo "      $OUT_DIR/batch-* --out ../../experiments/results"
