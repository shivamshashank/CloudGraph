# CloudGraph — Path to 100% (End-to-End)

**Audit basis:** Actual code inspection against every claim in `ROADMAP.md`,
`PROJECT_AUDIT_CHECKLIST.md`, `PROJECT_DIRECTION_CHECKLIST.md`,
`PROJECT_COMPLETION_CHECKLIST.md`, and `Week4_Demo_Checklist.md`. Where those
documents contradict each other or contradict the code, this file follows the
code. "100%" here means: the system does what the README/dissertation claims,
with no rule-based logic silently standing in for AI/agent claims, and no audit
checkbox unbacked by a file.

**Current real state in one sentence:** Weeks 1–4 (infra, observability,
knowledge graph, GraphRAG retrieval) are genuinely complete and demoable.
Many parts of the current multi-agent investigation path remain a rule-based
stand-in rather than a fully realized LLM/GraphRAG RCA system, and Weeks 6–8
have not been started in any form.

---

## 0. The single most important gap (fix this first)

- [ ] **LLM integration exists in the orchestrator and investigation engine, but it is conditional and partial.**
      `services/investigation-engine/main.py` and `services/agent-orchestrator/main.py`
      both include direct OpenAI/Gemini/Claude request code paths, but several
      agent and consensus flows still fall back to rule-based logic when an
      LLM provider/API key is missing or when an LLM response is invalid.
- [ ] Until this path is hardened and the fallback logic is reduced, any claim
      that the pipeline is fully LLM-backed or fully multi-agent should be
      qualified as "LLM-capable with rule-based fallback" or relabeled
      accordingly.

---

## 1. Week 5 — Real Multi-Agent Framework (currently: rule-based stand-in)

- [ ] Replace the keyword-ladder agents in `investigation-engine/main.py`
      (`run_monitoring_agent`, `run_log_agent`, `run_deployment_agent`,
      `run_topology_agent`, `run_security_agent`) with LLM-backed reasoning —
      each agent should call an LLM with its slice of GraphRAG-retrieved
      evidence and produce a structured hypothesis + confidence + rationale, not
      a hardcoded string.
- [ ] Actually integrate a real orchestration framework (or an equivalent
      orchestration design) for agent message passing and shared state — currently
      the "orchestrator" is a single HTTP POST to a Python `http.server` that
      forwards a JSON blob and gets a JSON blob back.
- [ ] Rebuild the Consensus Engine (`agent-orchestrator/main.py`
      `ConsensusEngine.resolve_incident`) to compute confidence from actual
      agent-reported evidence quality and cross-agent agreement, not from a
      static `WEIGHTS` dict applied to whatever confidence number the rule
      ladder emitted.
- [ ] Add per-agent and full-orchestration integration tests against the new
      LLM-backed agents (the existing tests in `test_graph.py` only validate the
      rule-based path and will need rewriting).
- [ ] Add prompt versioning / prompt files under source control so the
      dissertation methodology chapter can cite exactly what was run.

## 2. Week 6 — RCA & Recommendation Engine (not started)

- [ ] Build a real Root Cause Agent: hypothesis generation and ranking from
      fused, LLM-reasoned agent evidence — not the current title/cause/
      recommendation string templates keyed off a `category` variable.
- [ ] Build the **hallucination-checking layer**. This does not exist in any
      form today. It is the direct evidence for RQ3/H3 and needs: claim
      extraction from generated RCA text, a check that each claim is supported
      by a graph node/edge or retrieved evidence chunk, and an unsupported-claim
      rate metric logged per investigation.
- [ ] Generate real evidence-chain explanations tying each RCA line back to
      specific Neo4j node IDs and Qdrant document IDs (the UI already has a
      place to render this — `evidence.js`/`workbench.html` — it just needs real
      chain data instead of the rule-based `evidence` list).
- [ ] Replace `/api/v1/investigations/trigger`'s current logic (which already
      calls the orchestrator, but the orchestrator is rule-based) so the full
      chain — trigger → retrieval → agents → consensus → RCA — is LLM-backed end
      to end.
- [ ] Add remediation/rollback recommendation generation with actual risk
      scoring, not a fixed string per category.

## 3. Week 7 — Real Experimental Evaluation (currently: 4-doc synthetic test)

- [ ] Build the labeled incident dataset: minimum 100 incidents across the 5
      categories already defined in `research-methodology.md` (Kubernetes,
      networking, security, deployment, observability), each with a ground-truth
      root cause label. `test_graphrag_validation.py` currently validates
      against 4 hand-built synthetic documents — this is a good _pattern_ but
      not the dataset.
- [ ] Implement and run all 4 baselines end-to-end on that dataset: keyword
      search, vector-only RAG, GraphRAG-only, GraphRAG + multi-agent. Only
      keyword/vector/GraphRAG paths exist today; there is no GraphRAG+agent
      baseline because the agent layer isn't LLM-backed yet (depends on §1–2).
- [ ] Compute and store: precision, recall, F1, top-1/top-3 RCA accuracy,
      hallucination rate, MTTR proxy — per baseline, per incident, exported to
      CSV/JSON for the dissertation.
- [ ] Run the actual statistical tests (t-test, Wilcoxon) with confidence
      intervals comparing baselines against H1–H4. None of this exists yet;
      `ROADMAP.md` Week 7 is entirely unchecked and that is accurate.
- [ ] Separate retrieval-quality evaluation from generation-quality evaluation
      per the methodology doc's own validity section.

## 4. Week 8 — Dissertation & Final Submission (not started)

- [ ] Write all dissertation chapters — only the chapter _plan_ exists today
      (`docs/week-1/dissertation-evidence.md`), not chapter content.
- [ ] Populate the evaluation chapter with the real Week 7 results (depends on
      §3 being done first — do not backfill this with synthetic numbers).
- [ ] Final README pass: screenshots, architecture diagrams reflecting the
      actual current implementation (not the AWS/Terraform historical images).
- [ ] End-to-end, load, security, and performance testing passes.
- [ ] Record a demonstration video and prepare viva/presentation slides.

## 5. Known real bugs and half-implementations (fix regardless of week)

- [ ] `build_service_dependency_map()` in `graph_constructor.py` does not build
      a dependency map. It runs `MATCH (s:Service) RETURN count(s)` and returns
      a number. No relationships are created. Multiple audit docs claim this is
      done — it is not.
- [ ] Wire the Tempo tracing adapter (`tempo.py::ingest_tempo_trace`) to an
      actual FastAPI route — the function exists and works, but nothing in
      `main.py` calls it. Also deploy Grafana Tempo itself; it's referenced in
      docs but never appears in `deployments/kubernetes/observability/`.
- [x] Wire Redis. It's declared in `Chart.yaml`, `values.yaml`, and service env vars (`REDIS_HOST`) and now backs GraphRAG search caching using `redis_client.py`.
- [x] Remove the stale Helm CRD configuration. `crds.enabled` has been removed from `deployments/helm/cloudgraph/values.yaml` because no CRD templates existed in the chart.
- [ ] Remove hardcoded credentials: `cloudgraph_dev_password` / `changeme`
      appear in `docker-compose.yml`, `argocd-applications.yaml`, and
      `values.yaml`. Move to Kubernetes Secrets generated at install time or an
      external secrets operator.
- [ ] Add real API authentication/authorization. Currently zero auth on any
      FastAPI endpoint. The UI has session-based auth, but the API behind it
      does not.
- [ ] Add TLS, network policies, and pod disruption budgets — none exist.
- [ ] Give the Incident Workbench a real backend. `workbench.html` is fully
      built and polished but reads/writes only `localStorage`. Add
      `GET /api/v1/incidents`, `GET /api/v1/incidents/{id}`,
      `POST /api/v1/demo/seed-incident`, and persist incidents/comments in Neo4j
      instead of the browser.
- [ ] Create the missing node types the schema promises but nothing writes:
      `TraceSpan` (with parent-child spans, not just flat `Trace` nodes),
      `SecurityEvent`, `ChaosExperiment`. No ingestion path creates any of these
      today.
- [ ] Implement real `CALLS` relationship generation from trace span call-trees
      — `docs/week-3/ROADMAP.md` checks this off, but no code creates `CALLS`
      edges anywhere in the repo.

## 6. Documentation hygiene (low effort, do in parallel)

- [ ] Resolve the direct contradiction between `PROJECT_AUDIT_CHECKLIST.md`
      (claims agent-orchestrator/investigation-engine are "fully implemented"
      multi-agent systems) and `PROJECT_DIRECTION_CHECKLIST.md` (says to
      "replace mock agent-orchestrator and investigation-engine services with
      real services or remove the service split") — both dated the same audit
      pass. Pick one accurate version and delete/update the other.
- [ ] Fill in `Week4_Demo_Checklist.md` §6 "Definition of Done" — every item in
      the body of that doc is checked, but the doc's own completion criteria at
      the bottom are all unchecked. Resolve that inconsistency.
- [ ] Once §1–2 are done, do a full pass removing "mock," "rule-based
      placeholder," and "keyword ladder" language that will no longer be
      accurate — and conversely, do **not** flip any checkbox to `[x]` until the
      corresponding code exists (this is the exact failure mode this audit keeps
      finding).
- [ ] Keep `ROADMAP.md` as the source of truth for what's actually unfinished —
      it's currently the most internally-consistent doc in the repo (Weeks 6–8
      correctly unchecked) and should stay that way rather than being
      "corrected" to look more complete.

---

## Suggested execution order

1. **§5 quick wins** (Redis, Tempo route, dependency-map fix, credentials) — low
   effort, removes several audit red flags immediately.
2. **§1 LLM-backed agents** — this unblocks everything else and is the actual
   differentiator the dissertation needs.
3. **§2 RCA + hallucination-checking** — depends on §1.
4. **§3 Evaluation** — depends on §1–2 existing to have a GraphRAG+agent
   baseline to test at all.
5. **§4 Dissertation writing** — depends on §3 producing real numbers.
6. **§6 documentation cleanup** — ongoing, in parallel with all of the above.

**Definition of "100% end-to-end":** a single incident can go telemetry →
knowledge graph → GraphRAG retrieval → LLM-backed multi-agent investigation →
consensus → hallucination-checked RCA → stored, queryable incident record, and
the same pipeline has been run against a 100+ incident labeled benchmark with
statistically significant baseline comparisons backing H1–H4.
