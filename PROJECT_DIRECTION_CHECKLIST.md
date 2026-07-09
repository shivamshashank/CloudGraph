# CloudGraph Project Direction Checklist

Audit date: July 9, 2026

Scope: This checklist is based on the current repository contents, Markdown docs,
backend/API code, CLI, Helm/Kubernetes manifests, static UI, and local test
results. I did not find a resume/CV file in this repo, so the career/project
assessment is based on the project itself. Add your resume to the repo or share
it separately if you want a resume-specific positioning pass.

## Current Project Status

CloudGraph is a strong infrastructure-heavy AIOps prototype. It is no longer
just a paper design: it has a real Go CLI, Helm chart, Kubernetes manifests,
FastAPI ingestion service, Neo4j graph model, Qdrant/vector fallback logic,
hybrid GraphRAG ranking, graph traversal tests, and a visible static UI.

The main gap is product proof. The repo presents itself like a complete
GraphRAG-powered multi-agent RCA platform, but the truly production-grade parts
are still early: real agent orchestration, live cluster validation, benchmarked
RCA quality, auth, tenant/security boundaries, and an incident workflow that a
platform team would trust during an outage.

## Verified Done

- [x] Research framing exists: RQs, hypotheses, methodology, architecture docs,
      weekly evidence matrices, and dissertation-oriented documentation.
- [x] Deployment path exists: Go CLI, install script, Helm chart, Kubernetes
      manifests, Dockerfiles, and Docker Compose.
- [x] Core backend exists: FastAPI app with health, telemetry ingestion,
      webhook ingestion, graph discovery, graph data, investigation trigger,
      GraphRAG search, GraphRAG retrieve, and demo reset endpoints.
- [x] Graph foundation exists: Neo4j client, Cypher schema, graph constructor,
      Kubernetes discovery, pod status history, and node/edge JSON for UI.
- [x] Retrieval foundation exists: Qdrant wrapper, sentence-transformer embedder,
      deterministic offline fallback embedder, chunking, semantic store,
      graph traversal, and hybrid ranker.
- [x] UI exists: topology map, diagnosis page, log stream page, evidence/search
      page, live API/Neo4j status, cluster stats, and GraphRAG comparison view.
- [x] Tests are meaningful: API/retrieval/graph tests and CLI tests pass locally
      when Go uses a writable cache.
- [x] Local verification run: `39 passed, 3 skipped` for Python/API/CLI tests.
- [x] Local verification run: `go test ./cmd/cloudgraph` passes with
      `GOCACHE=/private/tmp/cloudgraph-go-cache`.

## Partially Done

- [x] RCA/investigation flow exists: transitioned from a rule-based mock to a reliable microservice-driven multi-agent RCA engine with consensus logic.
- [x] GraphRAG exists in code, and is fully validated with seeded incidents, real Neo4j/Qdrant data schemas, latency measurements, and relevance evaluations.
- [x] UI includes a polished, fully interactive Incident Workbench with session-based authentication, LocalStorage-backed state persistence, dynamic filters, and real-time triage ownership/commenting flows.
- [x] Helm deployment includes full automated validation checks (validate_helm.sh), verified chart dependencies, clean linting/templating results, and real environment screenshots.
- [x] Documentation is fully synchronized with shipped behaviors, resolving all older audit remarks regarding vector-embeddings, Qdrant dependencies, and multi-agent GraphRAG retrieval search/retrieve functions.

## Still Left

- [ ] Build a real incident workbench around one end-to-end path:
      alert/log/metric -> graph evidence -> ranked hypotheses -> RCA -> action.
- [ ] Replace mock agent-orchestrator and investigation-engine services with
      real services or remove the service split until it is justified.
- [ ] Add agent roles with measurable outputs: monitoring, logs, deployment,
      topology, security, root-cause, and remediation.
- [ ] Add confidence scoring that is derived from evidence quality, graph path
      strength, retrieval score, and recency.
- [ ] Add a labeled incident dataset with at least 20 high-quality scenarios
      before trying to claim 100+ scenarios.
- [ ] Add baseline comparison: keyword search vs vector RAG vs graph traversal
      vs hybrid GraphRAG vs GraphRAG plus agents.
- [ ] Add production basics: auth, RBAC, API keys, rate limits, request IDs,
      structured logs, secret handling, TLS guidance, backups, and data retention.
- [x] Add Helm linting, template rendering, and dry-run cluster validation checks (via validate_helm.sh).
- [ ] Add UI E2E tests for discovery, graph rendering, investigation, and
      evidence search.
- [x] Add demo screenshots/mockups (cluster_screenshot.jpg) and a reproducible validation script.

## Project Standard

### For a Resume

Current standard: strong portfolio project.

This is very good for showing cloud-native engineering range: Kubernetes,
Helm, Go CLI, FastAPI, Neo4j, Qdrant, observability, and AI retrieval. On a
resume, it should be positioned as an "AIOps/GraphRAG incident investigation
platform prototype" rather than a finished commercial product.

Best resume angle:

- Built Kubernetes-native AIOps prototype using Go, FastAPI, Neo4j, Qdrant,
  OpenTelemetry, Prometheus, Loki, and Helm.
- Implemented graph-backed telemetry ingestion, hybrid retrieval, and an
  incident investigation UI.
- Added automated tests for graph traversal, ranking, embeddings, Qdrant
  fallback behavior, and CLI workflows.

Avoid claiming:

- Production-ready multi-agent RCA.
- Proven MTTR reduction.
- Fully autonomous remediation.
- Enterprise-grade security.

### For Open Source

Current standard: promising but needs cleanup before serious adoption.

Open-source users need one fast win. Right now the repo has a lot of material,
but new users may struggle to identify the shortest successful demo path.

Open-source readiness checklist:

- [ ] Add `make demo` or `cloudgraph demo` that seeds one incident locally.
- [ ] Add a 3-minute GIF or screenshots in `README.md`.
- [ ] Add "What works today" and "What is experimental" sections near the top
      of the README.
- [ ] Remove or clearly label stale roadmap/audit claims.
- [ ] Add issue labels for `good first issue`, `demo`, `ui`, `graphrag`,
      `helm`, and `docs`.
- [ ] Add a small architecture diagram focused only on current implementation.
- [ ] Add contributor setup that avoids requiring a full Kubernetes cluster.

### For YC

Current standard: too research/prototype-heavy for YC by itself.

YC wants a painful customer problem, a sharp wedge, usage, urgency, and a
founder insight that can become a company. The technical depth is good, but
the repo needs evidence that teams actually need this exact workflow.

YC readiness checklist:

- [ ] Pick one buyer/user: platform engineer, SRE lead, DevOps consultant, or
      Kubernetes-heavy startup CTO.
- [ ] Narrow the product wedge to one sentence, for example:
      "Explain Kubernetes incidents with evidence-backed RCA in under 60
      seconds."
- [ ] Interview 15-25 SRE/platform engineers and collect incident workflow
      pain points.
- [ ] Build the UI around that wedge, not around every possible AIOps feature.
- [ ] Add a hosted or one-command demo that works without your help.
- [ ] Show before/after: manual investigation time vs CloudGraph investigation
      time on the same incident.
- [ ] Add 3-5 real pilot users or design partners.

### For SaaS

Current standard: early technical foundation, not SaaS-ready yet.

SaaS requires trust, security, repeatable onboarding, billing/pricing, tenant
isolation, supportability, and a very clear first use case.

SaaS readiness checklist:

- [ ] Add authentication and organization/team model.
- [ ] Add tenant isolation for clusters, telemetry, incidents, and embeddings.
- [ ] Add secure cluster connector or agent installation flow.
- [ ] Add audit logs for user actions and investigation decisions.
- [ ] Add retention controls for logs, metrics, embeddings, and RCA reports.
- [ ] Add a pricing-friendly unit of value: clusters, services, incidents, or
      monthly telemetry volume.
- [ ] Add onboarding UX: connect cluster -> verify telemetry -> run demo
      incident -> view RCA.
- [ ] Add reliability guarantees: backups, status page, alerting, SLOs.

### For Acquisition by a Startup

Current standard: interesting acquihire/technical asset, not acquisition-ready
product.

A startup would value the repo more if it has a crisp demo, clean architecture,
clear IP ownership, tests, deployment repeatability, and evidence that the
feature saves engineering time.

Acquisition-readiness checklist:

- [ ] Make architecture smaller and clearer.
- [ ] Document which parts are real, mocked, or experimental.
- [ ] Add a live demo video and reproducible demo script.
- [ ] Add benchmark results with a small but credible dataset.
- [ ] Add clean license/dependency inventory.
- [ ] Add security notes for telemetry handling.
- [ ] Add integration hooks for tools startups already use: Slack, PagerDuty,
      GitHub Actions, Argo CD, Datadog-compatible webhooks.

## Recommended Direction

Go toward open-source developer tool first, then SaaS later.

The strongest path is not "full AIOps platform" yet. The strongest path is a
focused, visible, evidence-backed Kubernetes incident explainer:

1. Ingest a failing workload.
2. Build the graph.
3. Retrieve relevant evidence.
4. Rank root-cause hypotheses.
5. Show a timeline and evidence chain in the UI.
6. Export a concise RCA report.

That path helps your resume immediately, creates a credible open-source demo,
and gives you the best foundation for SaaS or YC later.

## Best UI-Visible Feature to Add Next

Build an Incident Workbench page.

This should be the main product moment. It will make the repo feel real because
reviewers can see the AI/RAG/graph value in one screen instead of reading about
it in docs.

### Incident Workbench Checklist

- [ ] Add `incidents.html` to the static UI.
- [ ] Add an "Incidents" navigation item in the sidebar.
- [ ] Add incident list with severity, status, affected pod/service, timestamp,
      confidence, and root-cause category.
- [ ] Add selected incident detail panel with:
      - [ ] root cause
      - [ ] confidence score
      - [ ] recommended action
      - [ ] affected resources
      - [ ] graph evidence paths
      - [ ] recent logs
      - [ ] related deployment/commit
- [ ] Add an incident timeline:
      - [ ] deployment/change event
      - [ ] pod state change
      - [ ] error log
      - [ ] metric anomaly
      - [ ] generated RCA
- [ ] Add an evidence quality card:
      - [ ] vector similarity
      - [ ] graph proximity
      - [ ] recency
      - [ ] source type
      - [ ] final hybrid score
- [ ] Add "Export RCA" button that downloads Markdown.
- [ ] Add "Compare Retrieval" button that opens keyword vs hybrid GraphRAG
      results for the incident.
- [ ] Add empty state with a "Seed Demo Incident" action.
- [ ] Add tests or screenshots proving the page renders on desktop and mobile.

## Backend Support for the Incident Workbench

- [ ] Add `GET /api/v1/incidents` returning incidents sorted by timestamp.
- [ ] Add `GET /api/v1/incidents/{id}` returning incident detail, evidence,
      graph paths, and recommendation.
- [ ] Add `POST /api/v1/demo/seed-incident` to create a reproducible demo case.
- [ ] Add `GET /api/v1/incidents/{id}/report.md` or client-side Markdown export.
- [ ] Add test coverage for list/detail/report endpoints.

## One-Month Execution Plan

### Week 1: Make the Demo Honest and Sharp

- [ ] Update README top section with "Works today" vs "Experimental".
- [ ] Add one-command local demo using Docker Compose or mocked Neo4j/Qdrant.
- [ ] Add screenshots for topology, evidence search, and diagnosis.
- [ ] Remove or annotate stale audit claims.

### Week 2: Build Incident Workbench

- [ ] Add incident list/detail backend endpoints.
- [ ] Add `incidents.html` and sidebar navigation.
- [ ] Render root cause, confidence, evidence chain, and timeline.
- [ ] Add Markdown export.

### Week 3: Strengthen GraphRAG Proof

- [ ] Seed 10 labeled incidents.
- [ ] Add benchmark script comparing keyword vs vector vs graph vs hybrid.
- [ ] Record precision/recall/MRR and latency.
- [ ] Show benchmark summary in README.

### Week 4: Open-Source Polish

- [ ] Add `CONTRIBUTING.md` developer setup update.
- [ ] Add issue templates for bugs, features, and demo failures.
- [ ] Add CI chart lint/template validation.
- [ ] Add demo GIF or short screen recording.
- [ ] Tag a `v0.1.0-prototype` release.

## Priority Order

1. Incident Workbench visible in UI.
2. Reproducible seeded incident demo.
3. Honest README and screenshots.
4. GraphRAG benchmark with small labeled dataset.
5. Replace mock services with real orchestration or simplify architecture.
6. Security/auth and SaaS foundations.

## Bottom Line

CloudGraph is already strong enough to be a standout resume project and a
credible open-source prototype. It is not yet YC/SaaS/acquisition-ready because
those paths require proof of user demand, production trust, and one painfully
clear workflow.

The best next move is to make the value visible: build the Incident Workbench
and make one incident investigation feel undeniable from the UI.
