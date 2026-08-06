# Testing

**Full OrbStack-VM-to-report walkthrough, every command, exact paths:**
[`END_TO_END_RUNBOOK.md`](./END_TO_END_RUNBOOK.md).

Two kinds of testing this project needs, kept separate because they answer
different questions and run on different timescales:

- **`intensive/`** — manual/exploratory testing against a live cluster.
  `apply_demo_incidents.sh` deploys real broken pods (5 distinct failure
  modes — ImagePullBackOff, CrashLoopBackOff, OOMKilled,
  CreateContainerConfigError, a failing liveness probe) so there's
  something genuine for "Run AI Diagnosis" in the UI, or the discovery
  pipeline, to actually investigate. Replaces the old
  `scripts/apply_demo_incident.sh`, which only had one incident.

- **`report/`** — generating CloudGraph's core research report: the
  GPCS-vs-self-consistency comparison
  (`research/7_DAY_SPRINT_CHECKLIST.md` Day 2,
  `research/NOVEL_CONTRIBUTIONS.md` Contribution 2), the actual result this
  is all for — the dissertation/publication evidence, not a dev checklist
  item. Two ways to run it, same underlying logic either way:
  - **`cloudgraph report`** — the primary way. Works from any machine that
    can reach the CloudGraph API, including an `install.sh`-only install
    with no local source checkout — it drives the API's background-job
    endpoints over HTTP and saves the result to `~/.cloudgraph/reports/`.
  - **`run_report_full.sh`** — for local dev against a full source
    checkout, wraps `services/api/scripts/generate_research_report.py`
    directly (no HTTP round-trip). Same pre-flight checks (stack reachable,
    an LLM provider actually connected) and end-of-run summary either way.

Both `intensive/` and the local-checkout `report/` path expect the full
stack (Neo4j, Qdrant, investigation-engine, agent-orchestrator, api)
already running and reachable — neither script starts it for you.

## Quick reference

```bash
# See available demo incidents
testing/intensive/apply_demo_incidents.sh --list

# Apply all of them (or one by name, e.g. crashloop)
testing/intensive/apply_demo_incidents.sh

# Tear them down
testing/intensive/apply_demo_incidents.sh --teardown

# Generate the report — primary path, works anywhere the API is reachable
cloudgraph report --limit 3          # pilot, verifies the pipeline works
cloudgraph report                    # full 25-scenario run
# results saved to ~/.cloudgraph/reports/report-<timestamp>/

# Generate the report — local full-checkout alternative
REPORT_SCENARIO_LIMIT=3 NEO4J_PASSWORD=<password> testing/report/run_report_full.sh
NEO4J_PASSWORD=<password> testing/report/run_report_full.sh
```
