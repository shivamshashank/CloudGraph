# CloudGraph — Week 4 GraphRAG Demo Checklist

> Scope: Move from "Neo4j graph + keyword-matching stub" to a real, demoable
> **GraphRAG retrieval layer** (Baseline B: vector RAG, Baseline C: GraphRAG),
> wired visibly into the CLI and UI. This is the highest-leverage checklist in
> the whole project — it's the first point where CloudGraph's actual research
> contribution becomes observable rather than theoretical.

**Status legend:** `[ ]` not started · `[~]` partial/stub · `[x]` done and verified

---

## 0. Why Week 4 matters more than it looks

Weeks 1–3 (research docs, K8s/observability stack, Neo4j schema + ingestion)
are infrastructure. They're necessary but not differentiating — any solid
platform engineer could build them. Week 4 is where the dissertation's actual
claim (H1: GraphRAG beats traditional RAG) becomes something you can point at
on screen. Prioritize **visible, comparable retrieval output** over invisible
plumbing quality.

---

## 1. Core Retrieval Engine

### 1.1 Qdrant integration

- [x] Qdrant client wrapper (`services/api/app/database/qdrant_client.py`)
      following the existing `neo4j_client.py` singleton pattern.
- [x] Offline-safe behavior: if Qdrant is unreachable, fall back gracefully
      (log + return empty results) rather than crashing the API — matches the
      project's existing offline-safety principle for Neo4j/Redis.
- [x] Collection creation on startup (`incidents`, `logs`, `metrics_summary`,
      or a single unified `evidence` collection with a `type` payload field).
- [x] Connection wired via `QDRANT_HOST` env var already present in the Helm
      templates (`api.yaml`, `investigation-engine.yaml`,
      `agent-orchestrator.yaml`) — this env var already exists and is
      currently unused; this is where it gets consumed.

### 1.2 Embedding pipeline (replaces the toy hashed-token store)

- [x] Choose and document the embedding approach:
  - Local sentence-transformer (e.g. `all-MiniLM-L6-v2`) — no external API
    dependency, good for offline demo reliability.
  - *or* hosted embedding API — simpler, but adds a network dependency to the
    demo; riskier for a live presentation.
- [x] Chunking strategy for each evidence type:
  - [x] Log lines (already flowing into Neo4j via `loki.py`)
  - [x] Metric summaries (aggregate windows, not raw points)
  - [x] Incident descriptions
  - [x] Deployment/commit metadata
- [x] Replace `SemanticVectorStore._simple_embedding` (hashed bag-of-words) in
      `services/api/app/services/semantic_store.py` with real embeddings, OR
      keep the file-based store as a documented fallback and add a
      Qdrant-backed implementation behind the same interface.
- [x] Batch backfill script: embed everything currently sitting in Neo4j
      (`Log`, `Metric`, `Incident` nodes) into Qdrant on demand
      (`cloudgraph ingest` extension or a one-off script).

### 1.3 Graph traversal retrieval (GraphRAG proper)

- [x] Multi-hop Cypher traversal function seeded from an incident/pod node —
      building on relationships that already exist
      (`BELONGS_TO`, `RUNS_ON`, `MANAGES`, `GENERATES`, `AFFECTED_BY`).
- [x] Context expansion: N-hop neighborhood query with a configurable depth
      (start with depth=2, tune from there).
- [x] Temporal filtering: constrain traversal to an incident time window using
      the `timestamp` properties already indexed in `graph/schema.cypher`.

### 1.4 Hybrid ranking

- [x] Combine vector similarity score + graph proximity (hop distance) +
      recency into one ranked list.
- [x] Document the scoring formula explicitly (even a simple weighted sum) —
      this is dissertation-methodology-relevant, not just code.
- [x] Expose ranking rationale in the API response (which score components
      contributed) so the UI can show *why* something ranked highly —
      directly supports RQ3 (explainability) with almost no extra work.

### 1.5 API surface

- [x] Replace the keyword-`LIKE` implementation behind
      `/api/v1/graphrag/search` with real hybrid retrieval.
- [x] Replace `/api/v1/graphrag/retrieve` similarly.
- [x] Add a `method` query param or separate endpoints so the same query can
      run through **keyword**, **vector-only**, and **hybrid GraphRAG** —
      this one decision is what makes the Week 4 demo actually prove H1
      instead of just "look, search works."
- [x] Wire `/api/v1/investigations/trigger` to call the new retrieval layer
      instead of (or in addition to) the current if/else keyword ladder, with
      graceful fallback to the existing rule-based logic if retrieval fails.

---

## 2. What Must Be Visible in the Demo

The engineering above is invisible unless surfaced. This section is the
actual demo script.

### 2.1 CLI-visible

- [x] `cloudgraph deploy` — full clean-cluster bring-up (already works;
      re-verified against the new Qdrant dependency in the Helm chart).
- [x] `cloudgraph status` — extended to show Qdrant collection health/point
      count alongside existing deployment status, so the CLI proves data is
      actually indexed, not just that pods are green.
- [x] `cloudgraph doctor` — includes a Qdrant reachability check next to the
      existing kubectl/helm/memory/CPU checks.
- [ ] Optional: `cloudgraph ingest` extended with a `--seed-demo` flag that
      loads a small canned incident scenario (see §3) in one command, so the
      demo doesn't depend on a live misbehaving cluster.

### 2.2 UI-visible

- [x] GraphRAG search box (already exists in `index.html`/`app.js`) now
      returns real hybrid results instead of keyword `LIKE` matches.
- [x] **Side-by-side comparison panel**: same query run through keyword
      search vs. GraphRAG hybrid, results shown in two columns. This is the
      single highest-value UI addition for Week 4 — it visualizes H1 directly
      for an examiner or interviewer with zero explanation needed.
- [x] Evidence chain / ranking rationale surfaced per result (score
      breakdown from §1.4) — the Evidence page now renders chain steps and
      rationale details inline.
- [x] "Run AI Diagnosis" button: current rule-based output is preserved, but
      the UI now labels it honestly and points users to the GraphRAG evidence
      experience on the Evidence page.

### 2.3 Data/scenario visible

- [x] A small incident-injection script or manifest that deliberately breaks
      something (bad image tag, OOM limit, bad env var causing a DB auth
      failure) so discovery → graph → retrieval has a real signal to chase,
      instead of demoing against a healthy cluster.
- [x] Pre-recorded fallback: a JSON snapshot of graph + Qdrant state from a
      known-good incident run, loadable via `--seed-demo`, in case live
      cluster behavior is flaky during the actual presentation.

      The lightweight incident path is now captured in
      [services/api/app/demo/incident_scenario.py](services/api/app/demo/incident_scenario.py)
      and [scripts/apply_demo_incident.sh](scripts/apply_demo_incident.sh).

---

## 3. Recommended Demo Script (5–7 minutes)

1. `cloudgraph deploy` on a clean VM (or skip to a pre-deployed cluster if
   time-constrained) — narrate: "one command, full stack including Neo4j and
   Qdrant."
2. `cloudgraph status` — show Qdrant point count, Neo4j node count, all pods
   healthy.
3. Trigger the incident-injection script (§2.3) — a payment pod starts
   failing with a DB auth error.
4. UI: Discover Cluster → topology view updates, failing pod turns red.
5. UI: GraphRAG search box — type "payment database" — show the **side-by-side
   keyword vs. GraphRAG panel**: keyword search returns weak/no results,
   GraphRAG returns the deployment → secret change → DB auth failure →
   payment crash chain with ranked evidence.
6. UI: Run AI Diagnosis — show current rule-based output, be upfront that
   Week 5–6 replaces this with the multi-agent consensus engine.
7. Close with the roadmap: "Week 4 delivers retrieval; Week 5–6 add
   reasoning agents on top of this same evidence base."

---

## 4. Extras Worth Adding (stretch, high ROI/effort ratio)

- [ ] Fix the Redis-declared-but-unused gap: use Redis to cache repeated
      GraphRAG queries (`REDIS_HOST` env var already exists and is wired into
      Helm templates, just never consumed by any service code). Cheap,
      visible in `cloudgraph status`, and removes an audit flag.
- [ ] Add the missing Tempo/tracing API endpoint: `ingest_tempo_trace` in
      `tempo.py` already has working Cypher but no route in `main.py`, and
      Tempo itself isn't deployed in `deployments/kubernetes/observability/`.
      Even a minimal `POST /api/v1/telemetry/traces` + Tempo deployment closes
      a documented gap cheaply.
- [ ] Retrieval relevance smoke test: 5–10 hand-labeled query→expected-result
      pairs, asserted in a pytest file. Doesn't need to be the full Week 7
      benchmark — just enough to say "retrieval is tested, not just demoed."
- [ ] Latency benchmark for hybrid retrieval (mirrors the existing 100ms
      Neo4j traversal benchmark pattern in `test_graph.py`) — cheap, reuses
      an existing test pattern, gives you a number for the dissertation.
- [ ] `/api/v1/graphrag/search?method=keyword|vector|hybrid` documented in a
      short `docs/week-4/README.md` following the exact style of the
      existing `docs/week-1/README.md` / `docs/week-3/README.md` —
      keeps the dissertation-evidence trail consistent.
- [ ] `docs/week-4/task-evidence-matrix.md` — same pattern as Weeks 1–3, ties
      each checked box here to a concrete file/line reference. Supervisors
      have already been shown this pattern; keep it consistent.

---

## 5. Technical / Architecture / Stack Reference

Use this section to keep the demo narrative technically precise.

### 5.1 New components introduced this week

| Component | Role | Where it lives |
| --- | --- | --- |
| Qdrant client wrapper | Vector storage + similarity search | `services/api/app/database/qdrant_client.py` (new) |
| Embedding model | Turns text evidence into vectors | Local sentence-transformer or hosted API |
| Graph traversal module | Multi-hop Cypher context expansion | `services/api/app/adapters/` or a new `retrieval/` package |
| Hybrid ranker | Combines vector + graph + recency scores | New module, called by `/api/v1/graphrag/*` |

### 5.2 Data flow (Week 4 target state)

    User query (UI search box / CLI)
        │
        ▼
    FastAPI  /api/v1/graphrag/search
        │
        ├─► Vector path: embed query → Qdrant similarity search → top-k evidence
        │
        ├─► Graph path: seed node lookup (Neo4j) → N-hop traversal → context nodes
        │
        ▼
    Hybrid ranker (vector score + graph distance + recency)
        │
        ▼
    Ranked, explainable result set → UI side-by-side panel / CLI output

### 5.3 Existing stack this builds on (already real, unchanged)

- **Orchestration**: Kubernetes (kubeadm/Rancher), Helm, ArgoCD
- **Graph store**: Neo4j (schema in `graph/schema.cypher`, already has the
  constraints/indexes and relationship types this week's traversal needs)
- **Backend**: FastAPI (Python), Go CLI
- **Observability**: Prometheus, Grafana, Loki, OTel Collector (Tempo still
  pending — see §4)
- **CI/CD**: GitHub Actions (Go + Python tests, Docker image publishing)

### 5.4 Stack additions this week

- **Vector store**: Qdrant (already declared in `docker-compose.yml`,
  Helm `Chart.yaml` dependency, and `values.yaml` — currently unused, this
  is where it gets activated)
- **Embedding runtime**: sentence-transformers (or equivalent) — new
  Python dependency in `services/api/requirements.txt`
- **Caching (stretch)**: Redis, already declared and wired via env vars,
  currently unused — see §4

---

## 6. Definition of Done for "Week 4 Complete"

Week 4 should not be marked complete until all of the following are true
simultaneously — matching the project's existing "stub vs. real" audit
discipline (see `PROJECT_AUDIT_CHECKLIST.md`):

- [ ] A query run through `/api/v1/graphrag/search` returns different,
      demonstrably better results via GraphRAG than via plain keyword search
      on the same incident scenario.
- [ ] Qdrant actually contains embedded documents (verifiable via
      `cloudgraph status` or a direct API check), not just a running empty
      container.
- [ ] The UI shows this difference without requiring the presenter to read
      raw JSON.
- [ ] At least one automated test asserts retrieval returns non-trivial,
      relevant results (not just "endpoint returns 200").
- [ ] `ROADMAP.md` Week 4 checkboxes are updated to reflect reality, and a
      `docs/week-4/task-evidence-matrix.md` exists linking each box to code.
