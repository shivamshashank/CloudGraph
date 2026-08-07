# CloudGraph Project Status

This document is the single source of truth for the current implementation
status of **CloudGraph**. `TODO.md` is the forward-looking dissertation/PhD
roadmap (what to do next); `audit.new.md` is a historical audit snapshot,
now superseded by this file — see the note at the top of each.

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

---

## ✅ Completed

- **Cloud LLM provider integration**: `call_llm` in
  `services/agent-orchestrator/main.py`, `services/investigation-engine/main.py`,
  and `services/api/app/research/gpcs.py` supports three OpenAI-compatible
  cloud providers — OpenAI, Gemini, and Meta's official Llama API — selected
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
  parsing only if no LLM provider is connected — the fallback gate checks
  `if provider` alone, letting `call_llm`'s own env-var key fallback and
  error handling do the rest.
- **GCP & GPCS**: Graph Confidence Propagation (`gcp.py`, BFS + Noisy-OR edge
  decay) and Graph-Provenance Claim Scoring (`gpcs.py`, claim extraction +
  evidence retrieval + trust scoring) are both implemented and wired into
  `_investigate_pod`.
- **Real (non-heuristic) benchmark evaluation**: `routers/benchmark.py` and
  `POST /api/v1/benchmark/run` call the real `evaluate_scenario()` function
  (`app/research/evaluation.py`) — the old `_calc_kw`/`_calc_vector`/etc.
  fabricated-offset heuristics have been fully removed. All 6 baselines
  (Keyword, Vector, GraphRAG, +Agents, +GCP, +GPCS) run real retrieval/
  orchestration/scoring against the 25-scenario ground-truth dataset
  (`app/demo/benchmark_dataset.py`). A saved real run is in
  `experiments/results/day1_real_benchmark.json`.
- **GPCS-vs-self-consistency baseline (code complete, data pending)**:
  `services/api/app/research/self_consistency.py` generates N samples via
  the real orchestrator, extracts claims with the same
  `GraphProvenanceClaimScorer.extract_claims` GPCS uses (so the comparison
  is fair by construction), and flags claims unsupported if they don't
  recur across samples. It refuses to score the deterministic rule-based
  fallback (`SelfConsistencyUnavailableError`) rather than fabricate a
  measurement. **The actual data run has not yet succeeded** — every prior
  attempt hit either a cloud provider's quota wall or a timeout-chain bug
  (since fixed). Running `cloudgraph report` with a paid-tier API key
  connected (or, for a full local checkout,
  `scripts/generate_research_report.py` / `testing/report/run_report_full.sh`)
  is the next concrete step. The underlying comparison logic now lives in
  `app/research/report_runner.py`, callable directly, via a background HTTP
  job (`POST`/`GET /api/v1/research/report`, driven by the CLI), or via the
  standalone script — same logic, three entry points.
- **Context-condition ablation (Day 3, code complete, data pending)**: the
  same generation+scoring pipeline now runs three conditions per scenario —
  `none` (the original Day-2 condition: no retrieved evidence at all,
  agents reason from error_logs alone), `raw` (all scenario-seeded evidence
  via `run_raw_context_search`, unranked/unfiltered — a new function in
  `evaluation.py`), and `hybrid` (the existing ranked GraphRAG retrieval).
  Answers whether structured retrieval earns its complexity or dumping
  everything works just as well. `generate_and_score`/`_generate_samples`/
  `_generate_one_sample`/`_request_one_sample` in `self_consistency.py` all
  take an optional `retrieval_results` param now (defaults to `None`,
  preserving the original behavior) to make this possible without
  duplicating the generation pipeline. Tripling generation volume (9
  orchestrator calls per scenario instead of 3) is a real, expected cost
  increase, not a bug.
- **Neuro-symbolic retrieval detail export (Day 3, Contribution 3)**:
  `evaluation.retrieval_detail_for_scenario` captures per-scenario,
  per-method (keyword=symbolic, vector=neural, hybrid=neuro-symbolic)
  retrieved evidence and tag hit/miss detail, exported as
  `neurosymbolic_retrieval_detail.csv`. Deliberately exports data, not a
  finished analysis — categorizing *why* a method failed on a given
  scenario is a qualitative read for a human, not something automated.
  Both of the above are covered by `tests/test_report_runner.py` (new) and
  wired into `cloudgraph report`'s saved output alongside the GPCS-vs-
  self-consistency files.
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
- **UI**: 6 static HTML/CSS/vanilla-JS pages (Topology Map, AI Diagnosis,
  Log Stream, Evidence & Search, Benchmark, LLM Settings) served with no
  framework and no build step — no page uses React/Vue/Svelte or a
  charting library; the topology graph is hand-built SVG DOM manipulation
  (`topology.js`). Fully wired to backend endpoints for real Neo4j-backed
  persistence.
- **Helm & Kubernetes Deployments**: production Helm chart with Neo4j/Qdrant
  subcharts, validated via `validate_helm.sh`. Redis fully removed from
  chart dependencies. No in-cluster LLM component — the API,
  agent-orchestrator, and investigation-engine Deployments call out to
  whichever cloud provider is configured via the Settings API; no LLM
  env vars are wired into the chart.
- **Testing** (`testing/`, new): `testing/intensive/apply_demo_incidents.sh`
  deploys 5 distinct real failure modes (ImagePullBackOff, CrashLoopBackOff,
  OOMKilled, CreateContainerConfigError, failing liveness probe — see
  `services/api/app/demo/incident_scenario.py`'s `DEMO_INCIDENTS`) for
  manual/UI-driven RCA testing, replacing the old
  `scripts/apply_demo_incident.sh` (a single ImagePullBackOff scenario only).
  `testing/report/run_report_full.sh` wraps the full 25-scenario
  self-consistency run (local-checkout path) with pre-flight checks and a
  real summary.
- **`cloudgraph report [--limit N]`** (new): generates the research report
  via the API's background-job endpoints
  (`POST`/`GET /api/v1/research/report`, `app/research/report_runner.py`)
  — works from any machine that can reach the API, including an
  `install.sh`-only install with no local source checkout. Checks a local
  model is connected first (same check the UI toast uses), polls with live
  progress, and saves the result to `~/.cloudgraph/reports/report-<timestamp>/`.
- **Automated Test Coverage**: Python test suite 79/79 passing
  (`services/api/tests`); Go CLI tests passing, including 8 new tests for
  `cloudgraph report`.

---

## 🔶 Partially Done

- **Tempo Tracing Deployment**: the OTel ingestion adapter and API endpoints
  exist, but Grafana Tempo is not deployed in the observability manifests,
  so trace-driven `CALLS` service-dependency edges fall back to
  naming-convention heuristics rather than live trace data.
- **Documentation accuracy**: `README.md` and `deep-research-report.md`'s
  frontend descriptions have been corrected to match the real static-UI
  stack (this pass). Not yet done: reframing the AWS EKS/IAM/S3 references
  in `README.md` as historical/superseded, matching the annotations already
  present in `docs/week-1/architecture-design.md`.

---

## ⛔ Still Left

- **WebSocket/SSE live push** — UI still relies on HTTP polling.
- **React/Next.js SPA refactor** — never started; current UI is, and is
  accurately documented as, static vanilla HTML/JS. Not currently planned
  (the vanilla UI works and isn't a priority versus the research/evaluation
  work below).
- **Multi-cluster / native cloud provider discovery** — `k8s_discovery.py`
  is limited to local kubeconfig; no AWS EKS/GCP GKE/Azure AKS SDK
  integration or multi-cluster federation.
- **Statistical rigor on the benchmark**: paired bootstrap CIs, Wilcoxon
  signed-rank testing, and the matched-compute control are not yet
  implemented — scoped as Day 4 of `research/7_DAY_SPRINT_CHECKLIST.md`.
  Calibration analysis (Brier score, reliability diagrams for GCP/GPCS
  confidence) was also scoped there originally but is now **deliberately
  deferred**, not just "not yet done" — it's specifically for
  uncertainty-quantification-adjacent PhD applications, not required for
  the workshop paper this project targets first (see Day 4's note in the
  checklist for the reasoning).
- **Raw-context control & neuro-symbolic ablation write-up** — scoped as
  Day 3 of the same checklist, not started.
- **Human evaluation** — no user study on RCA usefulness/trust exists yet.
- **API authentication** — `/api/v1/settings` and other routes have no auth
  layer (`allow_origins=["*"]`, no API-key check). `/api/v1/settings` now
  stores a real cloud provider API key, so this endpoint being unauthenticated
  is a genuine credential-exposure risk, not a theoretical one — worth
  prioritizing before this is exposed beyond a trusted network.
- **Dissertation chapter writing** — 0% complete; only structural outlines
  exist in `docs/week-1/`.

---

## 📝 Notes

1. **LangGraph**: historical documentation claims about LangGraph
   orchestration have already been corrected — the actual orchestrator is a
   custom Python `http.server`-based JSON pipeline
   (`agent-orchestrator/main.py`, `investigation-engine/main.py`).
2. **Redis**: fully removed from chart dependencies, configs, and docs.
3. **Frontend framework claims**: corrected in this pass — see
   "Documentation accuracy" above.
4. **Where to look next**: `research/7_DAY_SPRINT_CHECKLIST.md` Days 2
   (re-run, now unblocked) through 7 (statistics + matched-compute control,
   trimmed figures, write-up — calibration deliberately deferred, see
   Day 4) is the concrete path from here to a citable result;
   `research/OXBRIDGE_READINESS.md` is the readiness assessment against
   that goal.
