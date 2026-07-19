# CloudGraph — Consolidated Audit & Checklist (July 18, 2026)

**Purpose of this file:** This replaces the previous, mutually contradictory
status documents (`Final.md`, `PROJECT_AUDIT_CHECKLIST.md`,
`CLOUDGRAPH_END_TO_END_COMPLETION_CHECKLIST.md`). Every line item below was
checked directly against the code in this repository as of this date, not
against prior checkboxes. Where prior docs were wrong in either direction
(overclaiming or underclaiming), that is noted explicitly.

**Method:** code-first. A box is only `[x]` if the corresponding file/function
exists and does what it claims. `[~]` means partially real — infra exists but
is thin, gated, or a fallback path. `[ ]` means not implemented, regardless of
what any other doc says.

---

## 0. TL;DR

- Weeks 1–4 (research docs, K8s/observability, Neo4j knowledge graph, GraphRAG
  hybrid retrieval) are **genuinely complete and demoable.**
- **LLM integration now exists and is real** — this reverses the prior
  "zero LLM calls anywhere" finding. `agent-orchestrator` and
  `investigation-engine` both call OpenAI/Gemini/Claude directly when a key is
  configured, with a rule-based fallback when it isn't.
- **LangGraph does not exist.** Orchestration is custom Python
  `http.server` JSON-over-HTTP, not a LangGraph state graph. Any doc or
  resume line claiming LangGraph is inaccurate and should be corrected to
  "custom LLM-backed multi-agent orchestration."
- **GPCS (Graph-Provenance Claim Scoring) — the dissertation's stated
  centerpiece — is 0% implemented.** Only a design doc exists
  (`HALLUCINATION_SCORING_DESIGN.md`). This is the single highest-priority
  gap relative to your own stated 95+ strategy.
- The Incident Workbench UI is polished but still **100% `localStorage`** —
  no backend persistence, despite one audit doc claiming this is done.
- No API authentication, open CORS (`allow_origins=["*"]`), LLM API keys
  passed from browser `localStorage` into unauthenticated backend calls.
- No evaluation dataset, no baselines run end-to-end, no statistics, no
  human evaluation — Week 7 is genuinely unstarted despite one doc marking
  it fully complete.

---

## 1. Corrections to prior audit docs (read this before anything else)

| Prior claim | Source doc | Actual current state |
| --- | --- | --- |
| "No LLM integration exists anywhere in the codebase" | `Final.md`, `PROJECT_AUDIT_CHECKLIST.md` | **False now.** `agent-orchestrator/main.py::call_llm()` and `investigation-engine/main.py::_call_llm_agent()` make real OpenAI/Gemini/Claude HTTP calls, gated by API key presence, with rule-based fallback. |
| "LangGraph agent orchestration" `[x]` | `ROADMAP.md` Week 5 | **False.** No LangGraph/LangChain import anywhere. Custom `http.server` orchestration only. |
| `build_service_dependency_map()` just counts services, does nothing | `PROJECT_AUDIT_CHECKLIST.md`, `Final.md` §5 | **Stale.** Function now builds real `CALLS` edges from trace `parentSpanId` matching (`graph_constructor.py`). |
| "Redis declared but entirely unused" | `PROJECT_AUDIT_CHECKLIST.md`, `Final.md` §5 | **Stale.** `redis_client.py` is connected in `main.py` lifespan and used to cache/invalidate `graphrag/search` results. |
| "No Tempo API endpoint exists" | `PROJECT_AUDIT_CHECKLIST.md` | **Stale.** `POST /api/v1/telemetry/traces` exists and calls `ingest_tempo_trace`. Tempo itself is still **not deployed** in the observability manifests, so the endpoint has no live producer yet. |
| GPCS, human evaluation, 60–80 incident dataset, statistical tests, dissertation chapters all `[x]` | `CLOUDGRAPH_END_TO_END_COMPLETION_CHECKLIST.md` | **False across the board.** None of these exist in the repo. This file reads as an aspirational target-state template, not a status report — recommend deleting or retitling it. |
| Incident Workbench has "session-based authentication" and "persistent state" | `PROJECT_AUDIT_CHECKLIST.md` (Partially Done section) | **False.** `workbench.html` reads/writes only `localStorage`. No backend incident persistence, no auth. |

---

## 2. What is genuinely done

### Weeks 1–3 — Research, Infra, Knowledge Graph

- [x] Literature review, RQ1–RQ4, H1–H4, methodology, architecture design docs.
- [x] Kubernetes manifests, Helm chart (`deployments/helm/cloudgraph`), Go CLI (`cmd/cloudgraph`) with `deploy`/`status`/`doctor`/`uninstall`.
- [x] Observability stack manifests: Prometheus, Grafana, Loki, OTel Collector (Tempo is documented but **not deployed** — see gap list).
- [x] Neo4j schema (`graph/schema.cypher`), ingestion adapters: metrics, logs, git commits, ArgoCD deployments — all real Cypher.
- [x] `k8s_discovery.py` — live cluster discovery via the `kubernetes` Python client, not mocked.
- [x] `build_service_dependency_map()` — now builds real `CALLS` edges (previously fake; now fixed).

### Week 4 — GraphRAG Retrieval

- [x] Qdrant client wrapper with offline-safe fallback (`app/database/qdrant.py`).
- [x] Local sentence-transformer embeddings (`all-MiniLM-L6-v2`), baked into the Docker image.
- [x] Evidence chunking strategy per evidence type (`evidence_chunking.py`).
- [x] Multi-hop Cypher graph traversal with temporal windowing (`graph_traversal.py`).
- [x] Hybrid ranker: documented formula `0.50·vector + 0.30·graph + 0.20·recency`, with per-result rationale (`hybrid_ranker.py`).
- [x] `/api/v1/graphrag/search` and `/retrieve` support `method=keyword|vector|hybrid`.
- [x] `test_graphrag_validation.py` — actual benchmark asserting hybrid RR ≥ vector-only RR and <100ms latency (not just "endpoint returns 200").
- [x] Side-by-side keyword-vs-hybrid comparison UI (`evidence.html`/`evidence.js`).

### Week 5 — Multi-Agent System (real, but not what the docs say it is)

- [x] 5 specialist agents in `investigation-engine/main.py`: monitoring, logs, deployments, topology, security.
- [x] Each agent calls an LLM (OpenAI/Gemini/Claude) first via `_call_llm_agent()`, with a documented rule-based fallback (`_analyze_*_rules()` helpers) if no key/provider is configured or the call fails.
- [x] `ConsensusEngine.resolve_incident()` in `agent-orchestrator/main.py` — attempts LLM-based consensus synthesis first, falls back to weighted rule-based classification (`WEIGHTS` dict) otherwise.
- [x] LLM credentials configurable via UI (`settings.html`/`settings.js`), stored in browser `localStorage`, sent per-request to the backend.
- [ ] **LangGraph** — does not exist. This is plain HTTP JSON request/response between two `http.server`-based Python processes. Rename this internally as "custom LLM orchestration," not LangGraph.
- [x] Graph Confidence Propagation (GCP) — `app/research/gcp.py`, real Noisy-OR propagation math, wired into `/investigations/trigger`, unit-tested (`test_gcp.py`).

### Cross-cutting

- [x] Redis caching wired: `redis_client.py` connected at app startup, used for `graphrag:search:*` cache keys, invalidated on every ingestion call.
- [x] CI (`ci.yml`): Go + Python tests with coverage upload.
- [x] Demo incident injection script + manifest generator (`incident_scenario.py`, `apply_demo_incident.sh`).

---

## 3. What is real but thin / partially implemented

- [~] **Tempo tracing** — ingestion adapter and API route exist (`tempo.py`, `POST /api/v1/telemetry/traces`), but Grafana Tempo itself is not deployed anywhere in `deployments/kubernetes/observability/`. The endpoint currently has no live data source.
- [~] **`CALLS` relationship generation** — depends entirely on `HAS_TRACE` edges existing, which depends on the Tempo gap above. The Cypher logic is correct but will produce zero edges until traces are actually flowing.
- [~] **LLM-backed agents** — real, but with no prompt versioning/source control for the actual prompts used, and no evaluation of LLM-vs-rule-based output quality. Useful for a demo; not yet evaluation-grade.
- [~] **Redis caching** — works, but only caches `graphrag/search`; no caching for the more expensive `/investigations/trigger` path.
- [~] **Incident Workbench UI** — fully built, polished, interactive (filters, triage status, comments) — but entirely client-side. No backend incident model, so nothing survives a browser cache clear or works across users/devices.

---

## 4. What is not implemented (confirmed absent in code)

### Research centerpiece

- [ ] **GPCS (Graph-Provenance Claim Scoring)** — zero implementation. No claim extraction, no trust scoring, no self-consistency baseline, no unsupported-claim-rate metric. Only `HALLUCINATION_SCORING_DESIGN.md` exists. This is the RQ3/H3 evidence your dissertation strategy depends on.
- [ ] Ablation study isolating GraphRAG / agents / GCP / GPCS contributions individually.
- [ ] Human evaluation (3–5 raters, blind comparison, inter-rater agreement).
- [ ] Statistical analysis: confidence intervals, effect sizes, significance tests, held-out generalization split.
- [ ] 60–100 incident labeled benchmark dataset with ground-truth root causes.
- [ ] End-to-end baseline comparison run (keyword / vector RAG / GraphRAG / GraphRAG+agents) producing real precision/recall/F1/hallucination-rate/MTTR numbers.

### Platform / production basics

- [ ] API authentication of any kind. `main.py` has zero auth middleware.
- [ ] CORS is wide open (`allow_origins=["*"]`).
- [ ] LLM API keys stored in browser `localStorage` and sent to an unauthenticated backend on every diagnosis request.
- [ ] Incident Workbench backend (`GET /api/v1/incidents`, `/incidents/{id}`, `POST /api/v1/demo/seed-incident`, Markdown export) — none of these routes exist in `main.py`.
- [ ] CRDs — the Helm chart no longer declares `crds.enabled`; the chart does not ship any custom resource manifests.
- [ ] TLS, network policies, pod disruption budgets.
- [ ] Secret hygiene — `argocd-applications.yaml` uses a blank `neo4j.password` value so the Neo4j subchart can generate the `cloudgraph-neo4j-auth` secret. The docs now explain how to retrieve it rather than relying on a hardcoded password.
- [ ] `TraceSpan` (parent/child span nodes), `SecurityEvent`, `ChaosExperiment` node types — schema promises them, nothing writes them.

### Dissertation writing

- [ ] All dissertation chapters — only the chapter plan exists (`docs/week-1/dissertation-evidence.md`).
- [ ] Final README/screenshot pass reflecting current (not historical AWS) architecture.
- [ ] Demo video, viva prep.

---

## 5. Documentation hygiene actions

- [ ] Delete or explicitly retitle `CLOUDGRAPH_END_TO_END_COMPLETION_CHECKLIST.md` as `TARGET_STATE.md` — as written it is indistinguishable from a real status report and directly contradicts the code.
- [ ] Update `Final.md` and `PROJECT_AUDIT_CHECKLIST.md`: remove the "zero LLM calls" finding, the stale dependency-map/Redis/Tempo-route gaps (all fixed), and correct any "LangGraph" language to "custom LLM orchestration."
- [ ] Update `ROADMAP.md` Week 5 "LangGraph" checkboxes — either implement LangGraph for real, or change the label to match what was actually built.
- [ ] Update resume/portfolio language to say "LLM-backed multi-agent investigation pipeline (custom orchestration)" rather than implying LangGraph, since that's a checkable claim.
- [ ] Keep this file (`PROJECT_AUDIT_CHECKLIST_2026-07-18.md`) as the single source of truth going forward; archive or delete the three prior conflicting docs rather than maintaining all of them in parallel.

---

## 6. Recommended next steps, in priority order

1. **Doc reconciliation** (§5 above) — cheap, removes the risk of an examiner catching a self-contradiction before they even reach the technical content.
2. **Build GPCS** — your last real research-novelty gap. Reuses `hybrid_ranker.py` and `graph_traversal.py` primitives per the existing design doc; this is the highest-leverage engineering task remaining.
3. **Build the labeled incident dataset + baseline comparison run** — required to answer RQ1–RQ4 quantitatively and to evaluate GPCS against anything.
4. **Add minimal API auth** — cheap fix for a real, currently-live security gap (open CORS + unauthenticated LLM-key-bearing endpoint).
5. **Incident Workbench backend** — the UI is already done; wire it to real `Incident` nodes in Neo4j instead of `localStorage`.
6. **Deploy Tempo** (or drop the tracing claims from docs) — small, unblocks the `CALLS` relationship generation you already built.
