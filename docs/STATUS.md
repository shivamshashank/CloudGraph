# CloudGraph Project Status

This document is the single source of truth for the current implementation
status of **CloudGraph**. `ROADMAP.md` is the forward-looking dissertation/PhD
roadmap (what to do next); `internal/archive/audit.new.md` is a historical audit snapshot,
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
  (`app/demo/benchmark_dataset.py`). Note: no standalone saved JSON for
  this 6-baseline sweep exists yet (an earlier draft of this doc referenced
  `experiments/results/day1_real_benchmark.json`, which was never actually
  produced) — the real Agents-baseline arm of the code path is exercised
  and its output saved via the matched-compute control below.
- **GPCS-vs-self-consistency baseline — real data collected, all 25
  scenarios (`experiments/results/`)**:
  `services/api/app/research/self_consistency.py` generates N samples via
  the real orchestrator, extracts claims with the same
  `GraphProvenanceClaimScorer.extract_claims` GPCS uses (so the comparison
  is fair by construction), and flags claims unsupported if they don't
  recur across samples. It refuses to score the deterministic rule-based
  fallback (`SelfConsistencyUnavailableError`) rather than fabricate a
  measurement. Run via `cloudgraph report` (batched, `--limit`/`--offset`,
  merged with `scripts/merge_reports.py` — see `experiments/README.md` for
  why batching exists and the exact workflow) against Meta's Llama API.
  **Result: 1777 claims, 64.0% GPCS/self-consistency agreement.** Getting
  a valid run required fixing four real bugs in GPCS's evidence retrieval
  (truncated entity extraction, an excluded `Deployment` graph label, a
  dead semantic-search callback, an unthresholded vector-search floor) —
  see `experiments/README.md` for the full list and the findings
  themselves. The underlying comparison logic lives in
  `app/research/report_runner.py`, callable directly, via a background HTTP
  job (`POST`/`GET /api/v1/research/report`, driven by the CLI), or via the
  standalone script (`scripts/generate_research_report.py`) — same logic,
  three entry points.
- **Context-condition ablation (Day 3) — real data collected**: the same
  generation+scoring pipeline runs three conditions per scenario — `none`
  (the original Day-2 condition: no retrieved evidence at all, agents
  reason from error_logs alone), `raw` (all scenario-seeded evidence via
  `run_raw_context_search`, unranked/unfiltered), and `hybrid` (the
  existing ranked GraphRAG retrieval). **Result: hybrid retrieval beats
  both `none` and `raw` on every measured column** (agreement rate, GPCS
  unsupported rate, self-consistency unsupported rate) — see
  `experiments/results/raw_context_control.md`. The hybrid-vs-raw
  agreement delta itself isn't statistically significant at n=25
  (p=0.15, `experiments/results/significance_tests.md`) — reported
  honestly rather than oversold.
- **Neuro-symbolic retrieval detail + qualitative read (Day 3,
  Contribution 3) — done**: `evaluation.retrieval_detail_for_scenario`
  captures per-scenario, per-method (keyword=symbolic, vector=neural,
  hybrid=neuro-symbolic) retrieved evidence and tag hit/miss detail,
  exported as `experiments/results/neurosymbolic_retrieval_detail.csv`.
  The qualitative failure-mode read is in
  `experiments/results/neurosymbolic_failure_modes.md` — honest finding:
  hybrid does *not* clearly beat keyword or vector on this dataset (vector
  actually scored 100% vs. hybrid's 96% on the tag-hit metric), reported
  as-is per the sprint's own guardrail against flattering results.
- **Statistical significance testing (Day 4) — done**:
  `scripts/paired_bootstrap.py` computes paired bootstrap CIs (10000
  resamples) and Wilcoxon signed-rank tests for four key deltas — see
  `experiments/results/significance_tests.md`.
- **Matched-compute control (Day 4, Contribution 5) — done, real negative
  result**: `scripts/run_matched_compute_control.py` compares the real
  5-specialist-agent consensus system against a single LLM sampled 5 times
  (self-consistency-checked, same GPCS scorer, same retrieved evidence —
  only architecture differs), across all 25 scenarios.
  **Result: the 5-agent system does *not* earn its complexity — it
  hallucinates *more* than the matched-compute single-LLM baseline** (44.2%
  vs. 31.5% mean unsupported rate, single-LLM won 19/25 scenarios, paired
  delta p=0.0018 — significant). See
  `experiments/results/matched_compute_control.md`.
- **Figures (Day 5) — done**: `scripts/make_figures.py` generates
  `experiments/figures/retrieval_recall.png`,
  `unsupported_rate_by_claim_type.png`, and `agreement_heatmap.png` from
  the saved result data, no LLM calls. Random-seed audit: the only local
  Python-side randomness across the week's scripts is
  `paired_bootstrap.py`'s bootstrap resampling, already seeded (`seed=42`)
  — everything else's variability is the LLM provider's own sampling
  temperature, not locally seedable.
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
  `experiments/results/`, confirming reproducibility (guardrail #4).
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
- **Automated Test Coverage**: Python test suite 88/88 passing
  (`services/api/tests`, full run verified this pass — one test,
  `test_benchmark_export_endpoint_supports_json_and_csv`, needs a live
  `agent-orchestrator` reachable and is environment-dependent rather than
  always-on, but passed when actually run against the deployed stack). Go
  CLI tests passing, including tests for `cloudgraph report`'s
  `--limit`/`--offset`.

---

## 🔶 Partially Done

- **Tempo Tracing Deployment**: the OTel ingestion adapter and API endpoints
  exist, but Grafana Tempo is not deployed in the observability manifests,
  so trace-driven `CALLS` service-dependency edges fall back to
  naming-convention heuristics rather than live trace data.
- **Benchmark data hygiene**: over a long real session, CloudGraph's own
  operational incidents (pod restarts, a kubelet/swap crash and recovery —
  see `testing/END_TO_END_RUNBOOK.md`'s troubleshooting section) have
  accumulated as genuine `Incident` nodes in Neo4j alongside the seeded
  demo scenarios, since keyword/vector/hybrid retrieval have no
  demo-vs-real scoping filter. Confirmed live: this measurably degrades
  retrieval quality over time (`scripts/compute_retrieval_f1.py`'s
  docstring has the specifics). Not yet fixed — the current figures/
  results use the original report run's saved data, from before this
  accumulated, rather than a contaminated fresh re-query.

---

## ⛔ Still Left

- **WebSocket/SSE live push** — UI still relies on HTTP polling.
- **React/Next.js SPA refactor** — never started; current UI is, and is
  accurately documented as, static vanilla HTML/JS. Not currently planned
  (the vanilla UI works and isn't a priority versus the research/evaluation
  work below). See `docs/design-evolution.md`.
- **Multi-cluster / native cloud provider discovery** — `k8s_discovery.py`
  is limited to local kubeconfig; no AWS EKS/GCP GKE/Azure AKS SDK
  integration or multi-cluster federation.
- **Calibration analysis** (Brier score, reliability diagrams for GCP/GPCS
  confidence) — **deliberately deferred**, not just "not yet done." It's
  specifically for uncertainty-quantification-adjacent PhD applications,
  not required for the workshop paper this project targets first (see Day
  4's note in `research/7_DAY_SPRINT_CHECKLIST.md` for the reasoning).
- **GPCS claim-extraction determinism**: `GraphProvenanceClaimScorer.
  extract_claims()` is called independently by both `self_consistency.py`
  and the GPCS scoring path — two separate LLM calls on the same
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
  is a genuine credential-exposure risk, not a theoretical one — worth
  prioritizing before this is exposed beyond a trusted network.
- **Dissertation chapter writing** — 0% complete; only structural outlines
  exist in `internal/dissertation/week-1/`.

---

## 📝 Notes

1. **LangGraph**: historical documentation claims about LangGraph
   orchestration have already been corrected — the actual orchestrator is a
   custom Python `http.server`-based JSON pipeline
   (`agent-orchestrator/main.py`, `investigation-engine/main.py`).
2. **Redis**: fully removed from chart dependencies, configs, and docs.
3. **Frontend framework claims**: corrected — README's frontend section
   accurately describes the static HTML/CSS/vanilla-JS stack, no
   React/Vue/Svelte claim remains. See `docs/design-evolution.md` for this
   and the other two documented design deviations (AWS→Helm/kubeadm,
   LangGraph→custom orchestrator).
4. **Where to look next**: `research/7_DAY_SPRINT_CHECKLIST.md` Days 1-5
   are complete with real data — see `experiments/README.md` for the
   findings themselves. Day 6 (docs accuracy — this pass; API auth
   explicitly deferred) and Day 7 (workshop draft + venue targeting)
   remain; `internal/planning/OXBRIDGE_READINESS.md` is the readiness assessment
   against that goal.
