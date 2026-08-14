# CloudGraph Project Status

**v1 is complete.** Everything below marked as implemented is built,
deployed and — where relevant — exercised by the 36-scenario evaluation.
Anything still outstanding is deferred to v2 and listed in `ROADMAP.md`; none
of it blocks the v1 results.

This document is the single source of truth for the current implementation
status of **CloudGraph**. `ROADMAP.md` is the forward-looking dissertation/PhD
roadmap (what to do next); `dissertation/PROGRESS.md` is the week-by-week
narrative of how the project got here.

---

## 📌 Project Overview

**CloudGraph** is a GraphRAG-powered AIOps incident root-cause analysis (RCA)
platform for Kubernetes. It integrates a property graph in Neo4j and semantic
indices in Qdrant, built from cluster logs, metrics, events, and Git webhook
deployments. This knowledge graph is queried using a hybrid ranker to
formulate GraphRAG retrieval contexts, which are processed by a multi-agent
system comprising 5 domain-specific specialist agents and a central
consensus engine. The platform is deployed cluster-agnostically via a custom
Go CLI and Helm charts, and contains mathematical layers for Graph Confidence
Propagation (GCP) and Graph-Provenance Claim Scoring (GPCS).

> **The evaluation is complete.** The corrected pipeline was run over
> **36 RCAEval RE2 scenarios**, producing **3,685 scored claims** across
> 3 context conditions × 3 retrieval methods, with **0 scenarios excluded**
> and `integrity_checks_passed: true`. An earlier run was invalidated by a
> ground-truth leak; its outputs were deleted rather than reinterpreted, and
> the dataset was rebuilt from RCAEval before re-running.
>
> Four of the project's seven research questions are answered: **three of
> them against the design's predictions**:
>
> | RQ | Result |
> |---|---|
> | **RQ1** GPCS vs self-consistency | Stricter (Δ +0.1185, p<0.0001) but **neither verifier tracks correctness** (both gaps −0.8 pp) |
> | **RQ2** Is the result real end-to-end | **Yes**: every baseline invokes the real pipeline |
> | **RQ3** Graph retrieval vs raw context | **Null** (Δ +0.024, CI [−0.028, +0.077], p=0.302) |
> | **RQ4** Symbolic vs neural retrieval | **Negative**: vector ≡ hybrid on all 36 scenarios |
>
> RQ5–RQ7 are deferred to v2. Full detail:
> [`research/RESEARCH_QUESTIONS.md`](../../research/RESEARCH_QUESTIONS.md),
> [`experiments/README.md`](../../experiments/README.md),
> `dissertation/PROGRESS.md`.

---

## ✅ Completed

- **Cloud LLM provider integration**: `call_llm` in
  `services/agent-orchestrator/main.py`, `services/investigation-engine/main.py`,
  and `services/api/app/research/gpcs.py` supports three OpenAI-compatible
  cloud providers (OpenAI, Gemini, and Meta's official Llama API), selected
  per-request via stored settings, not an env var. The Settings UI page
  (`services/ui/static/settings.html`/`.js`) lets users enter a provider,
  API key, and optional model name, which is saved through
  `POST /api/v1/settings` (Neo4j-backed). "Run AI Diagnosis" shows a toast
  pointing at the Settings page when no provider is connected. An earlier,
  local-only-via-Ollama iteration of this integration (including a
  `cloudgraph deploy llm` CLI command and an in-cluster Ollama Helm
  deployment) was tried and then fully reverted after real-world timeouts
  made local CPU inference impractical for this workload.
- **Core FastAPI Backend (`services/api`)**: live API server with lifespan
  connection management and CORS, endpoints for health checks, cluster
  discovery, incident CRUD, comments, settings, and webhook-driven `Commit`
  node generation correlated to deployments.
- **Dual Database Storage**: Neo4j graph schema (`graph/schema.cypher`) for
  `Service`/`Pod`/`Node`/`Deployment`/`Incident`/`Comment`/`LiveLog`/`Commit`;
  Qdrant semantic index via `sentence-transformers` (`all-MiniLM-L6-v2`),
  with a TF-IDF fallback when torch isn't loaded.
- **Multi-Agent Specialist RCA & Consensus Pipeline**: 5 specialist agents
  (Monitoring, Log, Deployment, Topology, Security) in
  `investigation-engine`, aggregated by a `ConsensusEngine` in
  `agent-orchestrator`. Each falls back to deterministic rule-based
  parsing only if no LLM provider is connected: the fallback gate checks
  `if provider` alone, letting `call_llm`'s own env-var key fallback and
  error handling do the rest.
- **GCP & GPCS**: Graph Confidence Propagation (`gcp.py`, BFS + Noisy-OR edge
  decay) and Graph-Provenance Claim Scoring (`gpcs.py`, claim extraction +
  evidence retrieval + trust scoring) are both implemented and wired into
  `_investigate_pod`.
- **Real (non-heuristic) benchmark evaluation**: `routers/benchmark.py`
  and `POST /api/v1/benchmark/run` call the real `evaluate_scenario()`
  (`app/research/evaluation.py`) — the old `_calc_kw`/`_calc_vector`
  fabricated-offset heuristics are gone. All 6 baselines (Keyword,
  Vector, GraphRAG, +Agents, +GCP, +GPCS) run real retrieval /
  orchestration / scoring.
- **Real-telemetry benchmark (36 scenarios)**: scenarios are derived
  from chaos-injected failures in RCAEval RE2: real faults in real
  running Kubernetes systems — via `scripts/build_rcaeval_dataset.py`,
  balanced 2 per (system × fault-type) cell. Provenance, licence,
  citation and per-case table in `experiments/DATA_PROVENANCE.md`. The
  earlier hand-authored benchmark has been removed; its incidents were
  written rather than observed.
- **Evaluation machinery, all implemented and tested**: GPCS-vs-
  self-consistency comparison (`app/research/self_consistency.py`,
  `report_runner.py`), the 3-condition context ablation
  (none/raw/hybrid), the neuro-symbolic retrieval ablation, paired
  bootstrap CIs + Wilcoxon tests (`scripts/paired_bootstrap.py`,
  seeded), the matched-compute control
  (`scripts/run_matched_compute_control.py`), and figure generation
  (`scripts/make_figures.py`). Three entry points to the same logic:
  direct call, background HTTP job (`POST`/`GET
  /api/v1/research/report`, driven by `cloudgraph report`), or
  `scripts/generate_research_report.py`.
- **Evaluation-integrity fixes (Week 9)**: four defects found and
  fixed, each pinned by regression tests
  (`tests/test_evaluation_integrity.py`, `tests/test_rcaeval_dataset.py`):
  ground-truth claims leaking into the system's own input; an inert
  recency term (all seeded timestamps identical, collapsing a
  three-signal hybrid score to two); GCP returning a confident-looking
  0.80 in three places where it had computed nothing (above the 0.50
  correctness threshold, so an unreachable database scored as
  *correct*); and the matched-compute arms using separate retrieval
  fetches despite claiming to share one. Full account in
  `dissertation/PROGRESS.md`, Week 9.

- **Hybrid Retrieval & GraphRAG**: multi-hop Cypher traversal
  (`graph_traversal.py`) and a hybrid ranker (`hybrid_ranker.py`) combining
  semantic similarity, hop distance, node importance, and recency decay.
  Context-comparison route exposes keyword/vector/hybrid/agent modes.
- **Telemetry & OpenTelemetry Ingestion**: active ingestion endpoints for
  traces, metrics, logs, security, and chaos events; parent-child span
  mapping builds service dependency maps.
- **Go CLI (`cmd/cloudgraph`)**: `version`, `doctor`, `status`, `health`,
  `ingest`, `deploy`, `report`, `uninstall`. Embeds the Helm chart
  manifests. Go test suite: passing (`deploy_test.go`, `uninstall_test.go`,
  `report_test.go`).
- **UI**: 6 static HTML/CSS/vanilla-JS pages: 5 reachable from the sidebar
  (Topology Map, AI Diagnosis, Log Stream, Evidence & Search, LLM Settings)
  plus Benchmark, whose nav link is **commented out in this release** and
  deferred to the next version (code retained in full; the page is still
  reachable directly at `/benchmark.html`) — served with no
  framework and no build step: no page uses React/Vue/Svelte or a
  charting library; the topology graph is hand-built SVG DOM manipulation
  (`topology.js`). Fully wired to backend endpoints for real Neo4j-backed
  persistence.
- **Helm & Kubernetes Deployments**: production Helm chart with Neo4j/Qdrant
  subcharts, validated via `validate_helm.sh`. Redis fully removed from
  chart dependencies. No in-cluster LLM component: the API,
  agent-orchestrator, and investigation-engine Deployments call out to
  whichever cloud provider is configured via the Settings API; no LLM
  env vars are wired into the chart.
- **Testing** (`testing/`, restructured this pass): `testing/intensive/`
  is 4 numbered scripts (`00_check_prereqs`/`01_apply_incidents`/
  `02_verify_incidents`/`03_teardown_incidents`) deploying 5 distinct real
  failure modes (ImagePullBackOff, CrashLoopBackOff, OOMKilled,
  CreateContainerConfigError, failing liveness probe — see
  `services/api/app/demo/incident_scenario.py`'s `DEMO_INCIDENTS`) for
  manual/UI-driven RCA testing — split from a single monolithic script so
  each step is independently runnable, and `02_verify_incidents.sh`
  actually confirms the incidents are visible to CloudGraph (triggers
  discovery, checks the graph), not just that `kubectl apply` succeeded.
  `testing/report/run_report_batched.sh` replaces the old
  `run_report_full.sh` — runs the local-checkout report in batches by
  default (`--full` for the old single-shot behavior) and merges
  automatically, since the report job's in-memory-only state means a
  mid-run crash previously cost 19/25 scenarios of real progress.
  `testing/verify/run_verification.sh` re-runs the test suite plus
  `paired_bootstrap.py`/`make_figures.py` against the current
  `experiments/results/` once a run has produced them, confirming
  every figure and statistic regenerates from saved data.
- **`cloudgraph report [--limit N] [--offset N]`**: generates the research
  report via the API's background-job endpoints
  (`POST`/`GET /api/v1/research/report`, `app/research/report_runner.py`)
  — works from any machine that can reach the API, including an
  `install.sh`-only install with no local source checkout. Checks a local
  model is connected first (same check the UI toast uses), polls with live
  progress, and saves each run to
  `~/.cloudgraph/reports/report-<timestamp>/`. `--offset` (added this pass)
  enables the batched-run workflow above; `scripts/merge_reports.py`
  combines multiple batch directories into one dataset.
- **Automated Test Coverage**: Python test suite **129/129 passing**
  (`services/api/tests`, full run verified). Note the runner needs
  `-n auto --dist loadfile`: plain `-n auto` fails non-deterministically
  because tests sharing module-level store state get split across workers,
  and `loadfile` pins each file to one worker. `.github/workflows/ci.yml`
  carries this flag with the measured evidence in a comment. One test,
  `test_benchmark_export_endpoint_supports_json_and_csv`, needs a live
  `agent-orchestrator` reachable and is environment-dependent rather than
  always-on, but passed when run against the deployed stack. Go CLI tests
  passing, including tests for `cloudgraph report`'s `--limit`/`--offset`.
  All 22 pre-commit hooks pass.

---

## 🔶 Partially Done

- **Tempo Tracing Deployment**: the OTel ingestion adapter and API endpoints
  exist, but Grafana Tempo is not deployed in the observability manifests,
  so trace-driven `CALLS` service-dependency edges fall back to
  naming-convention heuristics rather than live trace data.
- **Benchmark data hygiene**: over a long real session, CloudGraph's own
  operational incidents (pod restarts, a kubelet/swap crash and recovery —
  see `testing/END_TO_END_RUNBOOK.md`'s troubleshooting section) accumulate
  as genuine `Incident` nodes in Neo4j alongside the seeded demo scenarios.
  Confirmed live: this measurably degrades *ad-hoc* retrieval quality over
  time (`scripts/compute_retrieval_f1.py`'s docstring has the specifics).

  **Resolved for evaluation runs, still open for interactive use.** The
  vector collection is a single global namespace that outlives any one
  process, so an unscoped search returns evidence from every scenario ever
  seeded — including runs from previous deployments whose points teardown
  can no longer reach. `scenario_id` is now **mandatory for evaluation
  runs** (`semantic_store.py`'s `_scenario_filter`), which is what makes
  each scenario an isolated trial and what makes the shipped results valid.
  Interactive UI retrieval remains unscoped by design and can still surface
  CloudGraph's own incidents. Cleaning that up is a v2 item.

---

## ⛔ Still Left

- **WebSocket/SSE live push** — UI still relies on HTTP polling.
- **React/Next.js SPA refactor** — never started; current UI is, and is
  accurately documented as, static vanilla HTML/JS. Not currently planned
  (the vanilla UI works and isn't a priority versus the research/evaluation
  work below). See `docs/architecture/design-evolution.md`.
- **Multi-cluster / native cloud provider discovery**: `k8s_discovery.py`
  is limited to local kubeconfig; no AWS EKS/GCP GKE/Azure AKS SDK
  integration or multi-cluster federation.
- **Calibration analysis** (Brier score, reliability diagrams for GCP/GPCS
  confidence) — **deliberately deferred**, not just "not yet done." It's
  specifically for uncertainty-quantification-adjacent PhD applications,
  not required for the workshop paper this project targets first (see Day
  4's note in `dissertation/PROGRESS.md` (Week 8) for the reasoning).
- **GPCS claim-extraction determinism**: `GraphProvenanceClaimScorer.
  extract_claims()` is called independently by both `self_consistency.py`
  and the GPCS scoring path: two separate LLM calls on the same
  generation text, which can re-segment claims differently at nonzero
  temperature. Affects 2.7%-9.1% of claims per batch in the real run
  (`experiments/README.md`'s Known Limitations) — not a correctness bug
  (those rows are correctly excluded, not miscounted), but shrinks the
  joined sample. Clean fix: have GPCS reuse self-consistency's already-
  extracted claims instead of re-extracting; not yet done.
- **Human evaluation** — no user study on RCA usefulness/trust exists yet.
- **API authentication** — `/api/v1/settings` and other routes have no auth
  layer (`allow_origins=["*"]`, no API-key check). `/api/v1/settings` now
  stores a real cloud provider API key, so this endpoint being unauthenticated
  is a genuine credential-exposure risk, not a theoretical one: worth
  prioritizing before this is exposed beyond a trusted network.
- **Dissertation chapter writing** — 0% complete; the chapter plan and
  evidence map are in `dissertation/DISSERTATION_OUTLINE.md`.

---

## 📝 Notes

1. **LangGraph**: historical documentation claims about LangGraph
   orchestration have already been corrected: the actual orchestrator is a
   custom Python `http.server`-based JSON pipeline
   (`agent-orchestrator/main.py`, `investigation-engine/main.py`).
2. **Redis**: fully removed from chart dependencies, configs, and docs.
3. **Frontend framework claims**: corrected: README's frontend section
   accurately describes the static HTML/CSS/vanilla-JS stack, no
   React/Vue/Svelte claim remains. See `docs/architecture/design-evolution.md`
   for this and the other two documented design deviations
   (AWS→Helm/kubeadm, LangGraph→custom orchestrator).
4. **Where to look next**: see `dissertation/PROGRESS.md` for the full
   week-by-week account of how this project reached its current state,
   including the real evaluation results. The earlier paper drafts were
   retired on 2026-08-11 — every number in them predated the integrity
   fixes — and will be rewritten from `experiments/results/`.
