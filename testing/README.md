# Testing

**Full Linux-server-to-report walkthrough, every command, exact paths:**
[`END_TO_END_RUNBOOK.md`](./END_TO_END_RUNBOOK.md).

Three kinds of testing this project needs, kept separate because they
answer different questions and run on different timescales:

- **`intensive/`** — manual/exploratory testing against a live cluster.
  Numbered scripts, each doing one thing:
  - `00_check_prereqs.sh` — cluster reachable, API healthy, LLM provider
    connected. Run this first; everything else assumes it passed.
  - `01_apply_incidents.sh` — deploys real broken pods (5 distinct failure
    modes — ImagePullBackOff, CrashLoopBackOff, OOMKilled,
    CreateContainerConfigError, a failing liveness probe) so there's
    something genuine for "Run AI Diagnosis" or the discovery pipeline to
    actually investigate.
  - `02_verify_incidents.sh` — confirms the incidents are actually visible
    to CloudGraph (triggers discovery, checks the graph), not just that
    `kubectl apply` succeeded, then prints exactly what to click in the UI.
  - `03_teardown_incidents.sh` — deletes them.

- **`report/`** — generating CloudGraph's core research report: the
  GPCS-vs-self-consistency comparison, context-condition ablation, and
  neuro-symbolic retrieval detail (`research/NOVEL_CONTRIBUTIONS.md`
  Contributions 2-3; see
  narrative account) — the actual result
  this is all for, now real data in `experiment-1-benchmark/`. Two ways to run it,
  same underlying logic either way:
  - **`cloudgraph report`** — works from any machine that can reach the
    CloudGraph API, including an `install.sh`-only install with no local
    source checkout. Drives the API's background-job endpoints over HTTP,
    saves each run to `~/.cloudgraph/reports/report-<timestamp>/`.
  - **`report/run_report_batched.sh`** — for local dev against a full
    source checkout, wraps `services/api/scripts/generate_research_report.py`
    directly (no HTTP round-trip). Runs in batches by default (`--full` for
    the old single-shot behavior) and merges automatically with
    `scripts/merge_reports.py` — batching exists because the report job's
    state is in-memory only (`app/research/report_runner.py`'s own
    docstring): a crash mid-run loses everything since the last saved
    batch, not just the current scenario. This already happened once in
    real operation, at real cost.

- **`verify/`** — confirms the *analysis* layer over already-collected
  data is reproducible, not just that it ran once:
  - `run_verification.sh` — re-runs the research module test suite,
    `scripts/paired_bootstrap.py`, and `scripts/make_figures.py` against
    the current `experiment-1-benchmark/results/`, and reports whether everything
    regenerates cleanly — the project's honesty guardrail that every
    figure/table must be regenerable by re-running a script, made concrete
    and checkable.

`intensive/`, the local-checkout `report/` path, and `verify/` all expect
the full stack (Neo4j, Qdrant, investigation-engine, agent-orchestrator,
api) already running and reachable — none of them starts it for you.

## Quick reference

```bash
# --- intensive/ ---
testing/intensive/00_check_prereqs.sh                  # cluster + API + LLM provider reachable
testing/intensive/01_apply_incidents.sh --list          # see available demo incidents
testing/intensive/01_apply_incidents.sh                 # apply all of them (or one by name, e.g. crashloop)
testing/intensive/02_verify_incidents.sh                # confirm visible to CloudGraph, print UI instructions
testing/intensive/03_teardown_incidents.sh              # tear them down

# --- report/ ---
cloudgraph report --limit 3          # pilot, verifies the pipeline works
cloudgraph report --limit 5 --offset 0   # batch 1 of 5, primary path (no local checkout needed)
# results saved to ~/.cloudgraph/reports/report-<timestamp>/ per run

NEO4J_PASSWORD=<password> testing/report/run_report_batched.sh   # local-checkout, batched (recommended)
testing/report/run_report_batched.sh --full                       # local-checkout, old single-shot behavior

# --- verify/ ---
testing/verify/run_verification.sh   # tests pass + significance tests/figures regenerate cleanly
```
