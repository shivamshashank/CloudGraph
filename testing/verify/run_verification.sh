#!/usr/bin/env bash
#
# run_verification.sh — the project's reproducibility guardrail.
#
# Every published claim-and-verdict number is supposed to be regenerable from
# the raw run logs. This script proves that rather than asserting it:
#
#   1. the research-module test suite passes
#   2. claims.csv rebuilds from logs/ and matches the committed copy byte for byte
#   3. the figures rebuild from claims.csv and match their committed checksums
#   4. the published Zenodo copy of claims.csv has not drifted
#   5. MANIFEST.json's derived fields still agree with claims.csv
#
# Any mismatch is a hard failure: a published figure no longer follows from the
# evidence it claims to rest on.
#
# NOT covered, because no artefact retains the inputs: the mean request-payload
# sizes behind the 51.9% reduction. MANIFEST.json's call count and wall clock
# are likewise raw run-time records — readable, not recomputable. Both are
# flagged as such in the dissertation's Appendix B.
#
# Usage:  testing/verify/run_verification.sh
# Exit:   0 = everything regenerates identically, 1 = drift detected
#
# Call it directly, not through a pipe: `set -o pipefail` applies inside this
# script but a caller's pipeline will mask the exit code.

set -uo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO" || exit 1

PY="services/api/.venv/bin/python"
LOGS="experiment-1-benchmark/logs"
DATASET="services/api/app/demo/rcaeval_dataset_generated.json"
CLAIMS="experiment-1-benchmark/results/claims.csv"
FIGDIR="experiment-1-benchmark/results/figures"
MANIFEST="experiment-1-benchmark/results/MANIFEST.json"

# The Zenodo upload directory has lived in more than one place. Look for it
# rather than hard-coding one path, so a move downgrades this to a real search
# miss instead of a silent skip that still reports PASS.
ZENODO_CLAIMS=""
for candidate in zenodo/results/claims.csv tmp/zenodo/results/claims.csv; do
  [[ -f "$candidate" ]] && { ZENODO_CLAIMS="$candidate"; break; }
done

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

PASS=0
FAIL=0

ok()    { printf '  \033[32mPASS\033[0m  %s\n' "$1"; PASS=$((PASS + 1)); }
bad()   { printf '  \033[31mFAIL\033[0m  %s\n' "$1"; FAIL=$((FAIL + 1)); }
skip()  { printf '  \033[33mSKIP\033[0m  %s\n' "$1"; }
head_() { printf '\n\033[1m%s\033[0m\n' "$1"; }

# --------------------------------------------------------------------------
head_ "0. Preconditions"

if [[ ! -x "$PY" ]]; then
  bad "no interpreter at $PY — create it: cd services/api && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt"
  printf '\nCannot continue without the virtualenv.\n'
  exit 1
fi
ok "interpreter $PY"

for f in "$DATASET" "$CLAIMS"; do
  if [[ -f "$f" ]]; then ok "present: $f"; else bad "missing: $f"; fi
done

n_logs=$(find "$LOGS" -name '*.log.gz' | wc -l | tr -d ' ')
if [[ "$n_logs" -eq 54 ]]; then
  ok "run logs: $n_logs"
else
  bad "run logs: expected 54, found $n_logs"
fi

# --------------------------------------------------------------------------
head_ "1. Research-module test suite"

if (cd services/api && .venv/bin/python -m pytest -q \
      tests/test_gpcs.py \
      tests/test_self_consistency.py \
      tests/test_evaluation_integrity.py \
      tests/test_benchmark_dynamic_eval.py \
      tests/test_retrieval_isolation.py \
      tests/test_graph_traversal_scenario_scope.py \
      > "$TMP/pytest.out" 2>&1); then
  ok "pytest: $(grep -oE '[0-9]+ passed' "$TMP/pytest.out" | tail -1)"
else
  bad "pytest failed — output follows"
  tail -25 "$TMP/pytest.out" | sed 's/^/        /'
fi

# --------------------------------------------------------------------------
head_ "2. claims.csv regenerates from the raw logs"

if "$PY" services/api/scripts/build_claims_csv.py \
      "$LOGS" "$DATASET" "$TMP/claims.csv" > "$TMP/build.out" 2>&1; then
  if diff -q "$CLAIMS" "$TMP/claims.csv" > /dev/null 2>&1; then
    ok "claims.csv is byte-identical to the rebuild ($(wc -l < "$CLAIMS" | tr -d ' ') lines)"
  else
    bad "claims.csv DIFFERS from the rebuild — it no longer follows from the logs"
    diff "$CLAIMS" "$TMP/claims.csv" | head -15 | sed 's/^/        /'
  fi
else
  bad "build_claims_csv.py failed"
  tail -15 "$TMP/build.out" | sed 's/^/        /'
fi

# --------------------------------------------------------------------------
head_ "3. Figures regenerate from claims.csv"

if [[ ! -d "$FIGDIR" ]]; then
  bad "figure directory missing: $FIGDIR"
elif "$PY" -c "import matplotlib" 2>/dev/null; then
  before="$TMP/before.md5"; after="$TMP/after.md5"
  find "$FIGDIR" -type f \( -name '*.pdf' -o -name '*.png' \) | sort \
    | xargs md5 -q 2>/dev/null > "$before"
  if [[ ! -s "$before" ]]; then
    bad "$FIGDIR holds no figures to compare against"
  elif "$PY" experiment-1-benchmark/scripts/make_figures.py \
        "$CLAIMS" "$TMP/figs" > "$TMP/figs.out" 2>&1; then
    find "$TMP/figs" -type f \( -name '*.pdf' -o -name '*.png' \) | sort \
      | xargs md5 -q 2>/dev/null > "$after"
    if diff -q "$before" "$after" > /dev/null 2>&1; then
      ok "all $(wc -l < "$before" | tr -d ' ') figure files reproduce identically"
    else
      bad "figures DIFFER from the committed copies"
      paste "$before" "$after" | head -8 | sed 's/^/        /'
    fi
  else
    bad "make_figures.py failed"
    tail -15 "$TMP/figs.out" | sed 's/^/        /'
  fi
else
  skip "matplotlib not installed in $PY — figure regeneration not checked"
fi

# --------------------------------------------------------------------------
head_ "4. Published dataset has not drifted"

if [[ -n "$ZENODO_CLAIMS" ]]; then
  if diff -q "$CLAIMS" "$ZENODO_CLAIMS" > /dev/null 2>&1; then
    ok "$ZENODO_CLAIMS matches the repository copy"
  else
    bad "$ZENODO_CLAIMS has DIVERGED from the repository copy"
  fi
else
  skip "no zenodo/ upload directory found — parity not checked"
fi

# --------------------------------------------------------------------------
head_ "5. MANIFEST.json still agrees with claims.csv"

# MANIFEST.json is a raw record written by the harness as it ran, so its call
# count and wall clock cannot be recomputed. Its claim and verdict fields can
# be, and are the ones the dissertation quotes — so those get checked.
if [[ -f "$MANIFEST" ]]; then
  if "$PY" - "$CLAIMS" "$MANIFEST" > "$TMP/manifest.out" 2>&1 <<'PYEOF'; then
import csv, json, sys

rows = list(csv.DictReader(open(sys.argv[1], encoding="utf-8")))
m = json.load(open(sys.argv[2], encoding="utf-8"))
h = m["headline"]
T = lambda r, k: r[k] == "TRUE"

n = len(rows)
ev = [r for r in rows if T(r, "evaluable")]
cor = [r for r in ev if r["correctness_label"] == "consistent"]
wro = [r for r in ev if r["correctness_label"] == "contradicted"]


def gap(key):
    return round(
        sum(T(r, key) for r in wro) / len(wro) * 100
        - sum(T(r, key) for r in cor) / len(cor) * 100,
        1,
    )


def rate(key):
    f = sum(T(r, key) for r in rows)
    return f"{f}/{n} = {f / n * 100:.1f}%"


agree = sum(T(r, "gpcs_unsupported") == T(r, "sc_unsupported") for r in rows)
checks = [
    ("total_claims_scored", m["total_claims_scored"], n),
    ("evaluable_claims", m["evaluable_claims"], len(ev)),
    ("evaluable_coverage_pct", m["evaluable_coverage_pct"], round(len(ev) / n * 100, 1)),
    ("total_execution_runs", m["total_execution_runs"],
     len({(r["scenario_id"], r["context_condition"]) for r in rows})),
    ("gpcs_unsupported", h["gpcs_unsupported"], rate("gpcs_unsupported")),
    ("self_consistency_unsupported", h["self_consistency_unsupported"], rate("sc_unsupported")),
    ("verifier_concordance", h["verifier_concordance"], f"{agree}/{n} = {agree / n * 100:.1f}%"),
    ("correctness_split", h["correctness_split"], f"{len(cor)} consistent : {len(wro)} contradicted"),
    ("gpcs_flag_rate_gap_pp", h["gpcs_flag_rate_gap_pp"], gap("gpcs_unsupported")),
    ("self_consistency_flag_rate_gap_pp", h["self_consistency_flag_rate_gap_pp"], gap("sc_unsupported")),
]

bad = [(k, a, b) for k, a, b in checks if str(a) != str(b)]
for k, a, b in bad:
    print(f"{k}: manifest={a} data={b}")
print(f"OK {len(checks) - len(bad)}/{len(checks)}")
sys.exit(1 if bad else 0)
PYEOF
    ok "MANIFEST.json: $(grep -o 'OK .*' "$TMP/manifest.out" | sed 's/OK //') derived fields reproduce from claims.csv"
  else
    bad "MANIFEST.json DISAGREES with claims.csv"
    grep -v '^OK ' "$TMP/manifest.out" | head -10 | sed 's/^/        /'
  fi
else
  bad "missing: $MANIFEST"
fi

# --------------------------------------------------------------------------
printf '\n\033[1mSummary\033[0m\n'
printf '  %d passed, %d failed\n\n' "$PASS" "$FAIL"

if [[ "$FAIL" -gt 0 ]]; then
  printf 'Verification FAILED. A published artefact no longer follows from the raw\n'
  printf 'evidence it rests on. The run logs are authoritative: where a derived file\n'
  printf 'disagrees with them, the derived file is wrong.\n'
  exit 1
fi

printf 'Verification PASSED. Every derived artefact regenerates from the raw logs.\n'
exit 0
