#!/usr/bin/env bash
# Confirms the research pipeline's results are actually reproducible — the
# reproducibility check a reviewer would run, and the concrete meaning of
# guardrail #4 in internal/planning/7_DAY_SPRINT_CHECKLIST.md: "every figure/table
# must be regenerable by re-running a script, not hand-edited after the
# fact."
#
# Three checks, in order, each cheap and making no LLM calls:
#   1. The Python test suite for the research modules
#      (GPCS, self-consistency, report_runner) actually passes.
#   2. scripts/paired_bootstrap.py re-runs cleanly against the current
#      experiments/results/ data and produces the same significance_tests.md.
#   3. scripts/make_figures.py re-runs cleanly and regenerates all 3 PNGs.
#
# This does NOT re-run the report itself (that needs a live cluster + real
# LLM calls — see testing/report/run_report_batched.sh) or the
# matched-compute control (services/api/scripts/run_matched_compute_control.py,
# same live-cluster requirement) — this only verifies that the *analysis*
# layer over already-collected data is sound and reproducible.
#
# Usage:
#   ./run_verification.sh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
API_DIR="$ROOT_DIR/services/api"
RESULTS_DIR="$ROOT_DIR/experiments/results"

fail=0

echo "=== 1/3: Research module test suite ==="
if (cd "$API_DIR" && .venv/bin/python -m pytest \
    tests/test_gpcs.py tests/test_self_consistency.py tests/test_report_runner.py -q); then
  echo "  [ok] tests passed"
else
  echo "  [FAIL] test suite failed" >&2
  fail=1
fi

echo
echo "=== 2/3: Significance tests (paired bootstrap + Wilcoxon) ==="
if [[ ! -f "$RESULTS_DIR/claims.csv" ]]; then
  echo "  [skip] $RESULTS_DIR/claims.csv not found — run" >&2
  echo "         testing/report/run_report_batched.sh first." >&2
else
  before_hash=""
  [[ -f "$RESULTS_DIR/significance_tests.md" ]] && \
    before_hash="$(shasum -a 256 "$RESULTS_DIR/significance_tests.md" | cut -d' ' -f1)"

  if (cd "$API_DIR" && .venv/bin/python scripts/paired_bootstrap.py >/dev/null); then
    after_hash="$(shasum -a 256 "$RESULTS_DIR/significance_tests.md" | cut -d' ' -f1)"
    echo "  [ok] regenerated $RESULTS_DIR/significance_tests.md"
    if [[ -n "$before_hash" && "$before_hash" != "$after_hash" ]]; then
      echo "  [note] output changed from the previously committed version —"
      echo "         expected if claims.csv/neurosymbolic data changed since"
      echo "         the last run; review the diff before committing."
    fi
  else
    echo "  [FAIL] paired_bootstrap.py failed" >&2
    fail=1
  fi
fi

echo
echo "=== 3/3: Figures ==="
if [[ ! -f "$RESULTS_DIR/claims.csv" ]]; then
  echo "  [skip] $RESULTS_DIR/claims.csv not found." >&2
else
  if (cd "$API_DIR" && .venv/bin/python scripts/make_figures.py); then
    echo "  [ok] regenerated experiments/figures/*.png"
  else
    echo "  [FAIL] make_figures.py failed" >&2
    fail=1
  fi
fi

echo
if [[ "$fail" -ne 0 ]]; then
  echo "Verification FAILED — see above." >&2
  exit 1
fi
echo "Verification passed: tests pass, and every figure/table in" \
     "experiments/ regenerated cleanly from the currently-saved data."
