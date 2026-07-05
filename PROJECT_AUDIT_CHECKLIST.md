# CloudGraph — Full Codebase Audit & Completion Checklist

**Audit date:** July 2026
**Method:** Every claim below is checked against actual code/config in the
repository, not against the checkmarks already sitting in `ROADMAP.md`. Where
a roadmap box is checked but the underlying code is a stub, that is flagged
explicitly — this repo has a known pattern of "health-check passes ≠ feature
implemented," and this audit follows that discipline.

**Status legend:**

- [x] Completed and verified in code
- [~] Partially implemented or placeholder-only
- [ ] Not implemented yet

## 0. Quick status summary

### Done and verified

- [x] Kubernetes deployment path via Helm + kubeadm/Rancher
- [x] Observability stack and telemetry ingestion pipeline
- [x] Knowledge graph schema and graph/telemetry API endpoints
- [x] CLI installer, deployment, and uninstall workflow
- [x] Static UI shell with topology visualization and live polling

### Partially implemented / placeholder

- [~] Investigation workflow is rule-based and demo-oriented rather than a real RCA engine
- [~] Investigation Engine and Agent Orchestrator are mock services
- [~] Dependency mapping and evidence-chain UI rendering are only partial scaffolding

### Not implemented yet

- [ ] Qdrant + embeddings + GraphRAG retrieval
- [ ] LangGraph multi-agent workflow and consensus engine
- [ ] Full evaluation benchmark and baseline comparison pipeline
- [ ] Dissertation-ready RCA and recommendation system

---

## 1. One-paragraph status

Weeks 1–3 are **genuinely done**: research/design docs, Kubernetes +
observability stack (Prometheus/Grafana/Loki/OTel), Neo4j schema, and real
ingestion adapters (metrics, logs, git, ArgoCD) with a working FastAPI backend
and a solid Go CLI/Helm installer. From Week 4 onward (GraphRAG retrieval,
multi-agent LangGraph system, RCA engine, benchmark dataset, evaluation,
dissertation writing) **almost nothing is implemented yet** — the three
"brains" of the project (Investigation Engine, Agent Orchestrator, and the
current `/investigations/trigger` logic) are either empty mock servers or
simple if/else keyword rules, not GraphRAG/LLM/multi-agent systems. The
main documentation drift has now been cleaned up so the current tested path is
clearly Helm + kubeadm/Rancher, while historical AWS/Terraform references are
marked as optional or deferred.

---

## 1. ✅ What is genuinely completed (verified in code)

### Week 1 — Research & Design

- [x] Literature review, references, research questions (RQ1–RQ4), hypotheses
      (H1–H4), methodology, and dissertation-evidence mapping — all real,
      detailed markdown docs (`docs/week-1/*`).
- [x] Architecture design doc with graph schema, agent design, data-source
      mapping.
- [x] Task evidence matrices tying roadmap checkboxes to files.

### Week 2 — Infrastructure & Observability

- [x] Kubernetes namespace, sample microservice app (checkout/payment) with
      OTel env vars and Prometheus scrape annotations — real manifests.
- [x] Prometheus deployment + RBAC + scrape config (real, functional YAML).
- [x] Grafana deployment wired to Prometheus + Loki datasources (real).
- [x] Loki StatefulSet with filesystem storage (real).
- [x] OTel Collector with OTLP receivers → Prometheus + Loki exporters (real).
- [x] ArgoCD `Application` CRDs for GitOps sync of the above (real).
- [x] Sample-app Helm chart (`deployments/helm/sample-app`) — lints and
      templates checkout/payment services.
- [x] Go integration test (`observability_test.go`) hitting Prometheus
      `/-/healthy`, Loki `/ready`, OTel `/metrics` (skips gracefully outside
      cluster — real test, not a stub).

### Week 3 — Knowledge Graph

- [x] Neo4j Cypher schema: 8 uniqueness constraints + 4 indexes
      (`graph/schema.cypher`) — real and specific.
- [x] Neo4j Python driver singleton (`neo4j_client.py`) with `NEO4J_AUTH`
      parsing — real.
- [x] FastAPI backend (`services/api/app/main.py`) with genuinely working
      endpoints: `/health`, `/ready`, metrics/log ingestion, git & ArgoCD
      webhooks, graph linking, pod status history, `/api/v1/graph/data`
      (returns real node/edge JSON for the UI), `/api/v1/graph/discover`
      (live K8s API discovery via `kubernetes` python client — real, not
      mocked), and `/api/v1/investigations/trigger`.
- [x] Prometheus metric adapter, Loki log adapter, Git/ArgoCD webhook
      adapters, entity-linking / dependency-mapping / state-history logic in
      `graph_constructor.py` — all real Cypher, not placeholders.
- [x] `k8s_discovery.py` — real live cluster discovery (nodes, deployments,
      services, pods), including tailing real pod logs and writing them into
      Neo4j, plus synthetic CPU/memory metric injection for pods that don't
      emit real ones yet.
- [x] Pytest suite (`test_graph.py`) with mock-if-offline / real-if-online
      pattern, schema constraint checks, and a 100ms multi-hop latency
      benchmark — real, not vacuous.

### CLI, Packaging, Deployment

- [x] Go CLI (`cmd/cloudgraph`) — `deploy`, `uninstall`, `doctor`, `status`,
      `health`, `ingest`, `version` — all real logic, not stubs (kubeadm
      bootstrap, containerd config, Flannel CNI, Rancher local-path storage,
      NGINX ingress, Helm dependency management, embedded chart fallback via
      `embed.FS`).
- [x] Helm chart (`deployments/helm/cloudgraph`) with templated
      Deployments/Services/RBAC for API, UI, Investigation Engine, Agent
      Orchestrator, OTel Collector, plus Neo4j/Redis/Qdrant as chart
      dependencies.
- [x] CI (`ci.yml`): Go + Python tests with coverage upload; `release.yml`:
      semantic-version tagging, cross-compiled Linux binaries, and 4 Docker
      images pushed to GHCR (api, ui, agent-orchestrator, investigation-engine).
- [x] `install.sh`, `INSTALLATION.md`, `QUICKSTART.md` — accurate for the
      current Helm/kubeadm path.
- [x] Basic UI shell (`services/ui`) — static HTML/CSS/JS dashboard with a
      real SVG force-style topology renderer, live polling of `/health` and
      `/api/v1/graph/data`, a "Run AI Diagnosis" button, and a reverse-proxy
      `mock_service.py` in front of the static files. This is a real,
      working demo UI — just thin, and its "AI Diagnosis" is only as smart as
      the rule-based endpoint behind it (see §2).

---

## 2. ⚠️ Things that *look* done but are stubs/placeholders

### Core Services (Mock Implementations)

| Item | Reality |
| --- | --- |
| **Investigation Engine service** | `services/investigation-engine/mock_service.py` — literally just an HTTP 200 health-check responder with a hardcoded keyword-based `/analyze` endpoint. No GraphRAG, no reasoning, no connection to Neo4j or any real RCA logic. The endpoint only performs simple pattern matching on pod status and error logs. |
| **Agent Orchestrator service** | `services/agent-orchestrator/mock_service.py` — same generic health-check stub with a hardcoded `/orchestrate` endpoint that returns mock agent findings with fixed confidence scores. No LangGraph, no agents, no consensus engine, no actual reasoning exist anywhere in the repo. The "agents" returned are just hardcoded field names (monitoring, logs, deployments, security) with dummy findings. |
| **UI backend** | `services/ui/mock_service.py` is a static-file server + reverse proxy — fine as a thin UI host, but there is no real frontend framework/build system (no React, Vue, or build toolchain), just plain HTML/CSS/JS with hardcoded API endpoints. |

### Investigation & RCA (Rule-Based Placeholder)

| Item | Reality |
| --- | --- |
| **"AI Diagnosis" in the UI** | Calls `POST /api/v1/investigations/trigger`, whose actual logic in `main.py` is a hard-coded `if "timeout" in log_text / "crashloop" in status / "oom" in log_text` keyword ladder (lines 270–319 in `main.py`). This is a rule-based demo, **not** GraphRAG, not multi-agent, not LLM-backed. It's a good placeholder for demoing the UI flow, but it is **not** the RCA engine the dissertation needs to evaluate. The endpoint creates `Incident` nodes but with no graph traversal, no confidence scoring, and no evidence weighting. |

### Tracing & Observability

| Item | Reality |
| --- | --- |
| **Tempo / tracing adapter** | `services/api/app/adapters/tempo.py::ingest_tempo_trace` implements the Cypher query (lines 4–22), but there is **no API endpoint** exposing this adapter in the FastAPI app (`main.py`) to ingest tracing telemetry. Additionally, Grafana Tempo is **not deployed** in the observability stack (`deployments/kubernetes/observability/`), making distributed tracing entirely missing from the system. The Tempo adapter is essentially a dangling function that cannot be called. |
| **Verify Tracing (Week 2)** | `ROADMAP.md` (Week 2) has `[x] Verify tracing` checked. In reality, `tests/observability/observability_test.go` (lines 29–75) only checks Prometheus, Loki, and OpenTelemetry Collector endpoints. Tracing/Tempo is never hit, and Tempo itself is not deployed anywhere in the stack. The checkbox is misleading. |

### Knowledge Graph Relationships (Not Implemented)

| Item | Reality |
| --- | --- |
| **Dependency mapping logic** | `build_service_dependency_map` in `services/api/app/adapters/graph_constructor.py` (lines 39–48) has a docstring claiming to "build a lightweight service dependency map from the currently discovered Kubernetes service and pod relationships," but the Cypher query only counts the number of Service nodes: `MATCH (s:Service) RETURN count(s) as relationships_created`. It does **not** create any mapping, relationships, or dependency edges. The function returns a count, not a graph structure. This is a fake implementation masquerading as a feature. |
| **Service call relationships (`CALLS` / trace traversal)** | `docs/week-3/ROADMAP.md` (Part 3) and `docs/week-3/task-evidence-matrix.md` check off "trace span call-tree traversal to generate service-to-service dependency maps (`CALLS` relationships)". In reality, there is **no code** in the repository performing call-tree traversal or creating `CALLS` relationships in Neo4j. The Tempo adapter never creates these edges, and no other code does either. |

### Declared but Unused Infrastructure

| Item | Reality |
| --- | --- |
| **Qdrant** | Present in `docker-compose.yml`, Helm chart dependency list (`deployments/helm/cloudgraph/Chart.yaml`), and `values.yaml` (line 198–199: `qdrant: enabled: true`). **Nothing in the codebase writes to it, chunks/embeds anything, or queries it.** Zero embedding pipeline exists. No clients are instantiated, no vectors are stored, and no `/retrieve` endpoint uses it. It's a phantom dependency. |
| **Redis** | Declared in Helm chart as a dependency (`Chart.yaml`) and referenced as `REDIS_HOST` env var in templates (e.g., `deployment/helm/cloudgraph/templates/api.yaml`), but **no service code** (API, orchestrator, engine) ever imports a Redis client or uses it for caching/queueing. It's installed but completely unused. |
| **CRDs** | `values.yaml` (line 250: `crds.enabled: true`) declares CRD support, but **no actual CRD manifests exist in the Helm chart** (`deployments/helm/cloudgraph/templates/`). This is a configuration flag with no backing implementation. |

### GraphRAG Retrieval (Documented but Unimplemented)

| Item | Reality |
| --- | --- |
| **GraphRAG retrieval endpoints** | README (lines ~730–800) documents `/api/v1/graphrag/search` and `/api/v1/graphrag/retrieve` endpoints under "API Endpoints" section. These endpoints are **not implemented** in `main.py`. The README implies these are available, but they don't exist. The system has no retrieval API at all, only the keyword-based `/api/v1/investigations/trigger`. |
| **Vector embedding and chunking pipeline** | Week 4 roadmap (`ROADMAP.md`, branch `feature/qdrant-embedding-pipeline`) calls for "text chunking/embedding scripts" and "hybrid vector-keyword retrieval." **This entire pipeline is missing.** No text chunking code exists, no embedding model is loaded, no documents are chunked and embedded into Qdrant, and no retrieval algorithm is implemented. |

### Multi-Agent System (Designed but Not Built)

| Item | Reality |
| --- | --- |
| **Multi-agent LangGraph system** | Architecture design (`docs/week-1/architecture-design.md`, Agent Design table) describes 5+ specialist agents (Monitoring, Log, Trace, Deployment, Security, Root Cause, Recommendation). README promises "Multi-Agent Investigation Workflow." **No LangGraph code exists.** The two mock services return hardcoded, non-agent responses. The actual orchestrator, node graph, state management, and inter-agent messaging do not exist. |
| **Consensus engine** | Architecture design promises "Confidence-Aware Consensus" with weighted voting, evidence scoring, and cross-agent agreement. **This engine does not exist anywhere in the codebase.** The mock orchestrator simply returns fixed confidence scores; there is no actual voting or weighting logic. |
| **Hallucination-checking layer** | RQ3 and H3 (dissertation core) hinge on reducing hallucinations through knowledge graph evidence validation. **This layer does not exist.** There is no mechanism to check whether agent claims are supported by graph evidence, no claim detection, and no unsupported-claim filtering. |

### Agent Implementations (Missing Entirely)

| Item | Reality |
| --- | --- |
| **Root Cause Agent** | Described in architecture as the agent that ranks hypotheses, generates explainable graph reasoning paths, and proposes remediation. **This does not exist as a real agent.** The current `/api/v1/investigations/trigger` endpoint has a keyword ladder, not agent logic. There is no LangGraph node called "Root Cause Agent". |
| **Recommendation Agent** | Described as generating "RCA Report, Confidence Score, Evidence Chain, Remediation Plan, Risk Assessment." **This is not implemented.** The mock orchestrator returns dummy findings, not real recommendations. No actual remediation logic or rollback planning exists. |
| **Per-agent unit and integration tests** | No tests exist for individual agent logic (e.g., "does the Monitoring Agent correctly identify CPU anomalies?"). The test suite (`tests/test_graph.py`) only tests the FastAPI endpoints and schema, not agent behavior. |

### Evidence & Graph Construction (Incomplete)

| Item | Reality |
| --- | --- |
| **TraceSpan, SecurityEvent, ChaosExperiment node types** | Schema (`docs/week-1/architecture-design.md`) lists `TraceSpan`, `SecurityEvent`, and `ChaosExperiment` as core node types. **No adapters or code creates these nodes.** The Tempo adapter creates `Trace` nodes but never `TraceSpan` with parent-child relationships. No security event ingestion endpoint exists. No chaos experiment tracking exists. The schema is aspirational, not implemented. |
| **InfraChange nodes (Terraform/OpenTofu)** | Architecture design mentions parsing Terraform/OpenTofu plans to create `InfraChange` nodes. **This is explicitly deferred** (as noted in Section 3 documentation drift). No parsing code exists, and the infrastructure is now managed via Helm, not Terraform. |
| **Evidence chain visualization in UI** | UI HTML (`services/ui/static/index.html`) and CSS have partial scaffolding for an "evidence-chain" visualization panel (CSS class `.evidence-chain-item`, HTML structure in `rca-output` div). **These are not wired to real data.** The UI renders the keyword-ladder results, not actual evidence chains from the graph. There is no code that traces and renders an actual graph path showing how evidence supports the RCA conclusion. |

### Week 7 Evaluation Baselines (Not Implemented)

| Item | Reality |
| --- | --- |
| **Baseline implementations** | Week 7 roadmap specifies "4 baselines end-to-end: keyword search, vector RAG, GraphRAG-only, GraphRAG+agents." **None of these are implemented except the keyword search (which is the current `/api/v1/investigations/trigger`).** Vector RAG cannot be built without embeddings. GraphRAG-only cannot be built without multi-hop traversal. GraphRAG+agents cannot be built without the multi-agent system. The evaluation framework itself does not exist. |
| **Synthetic incident dataset generator** | Week 7 calls for "100+ labeled synthetic incidents across 5 categories (K8s, networking, security, deployment, observability)" with ground-truth labels. **No incident generator exists.** There is no code that creates reproducible failure scenarios. The benchmark is conceptual only. |

### Documentation & API (Missing Components)

| Item | Reality |
| --- | --- |
| **OpenAPI/Swagger schema beyond FastAPI auto-generated** | While FastAPI auto-generates `openapi.json`, there is no custom OpenAPI documentation, no detailed endpoint descriptions, no example payloads, and no explicit schema definitions in `main.py` beyond Pydantic models. The generated schema is minimal. |
| **Timestamp-based query optimization** | Retrieval design (`docs/week-1/architecture-design.md`) mentions "Temporal filtering keeps evidence inside the incident window." **No query optimizer exists.** There is no code that efficiently scans the graph using timestamp ranges or temporal indexes. Graph traversal queries are full-scan. |

---

## 3. ✅ Documentation drift cleaned up (Terraform/EKS → Helm/kubeadm)

**Status:** Completed. All references to Terraform/AWS EKS have been systematically annotated with clarifying notes indicating the superseded path while preserving design history.

### Cleanup Actions Taken

| File | Change | Purpose |
| --- | --- | --- |
| **docs/week-1/architecture-design.md** | Marked "AWS Deployment" diagram row as *(Historical)*; added note: "Superseded by Helm/kubeadm path. See `IMPLEMENTATION_SUMMARY.md`." | Signals to readers that this diagram is historical, not current. |
| **docs/week-1/architecture-design.md** | Marked "Terraform/OpenTofu Changes" data source as *(Deferred)*; added note: "Originally designed for AWS Terraform-based deployment. Not implemented; infrastructure now managed via Helm." | Preserves the conceptual data source in the taxonomy while clarifying it's not implemented. |
| **docs/week-1/task-evidence-matrix.md** | Marked "AWS Deployment Design" row as *(Superseded)*; changed evidence text to: "Historical: Originally connected to AWS EKS. Current deployment now uses Helm + kubeadm/Rancher; see `IMPLEMENTATION_SUMMARY.md` and `INSTALLATION.md`." | Links the historical design to the current implementation path. |
| **docs/week-1/data-collection-strategy.md** | Marked "Infrastructure changes" (Terraform) as *(Deferred)*; changed to: "Originally intended for AWS Terraform pipelines. **Not implemented.** Infrastructure now provisioned and managed via Helm Charts. See `IMPLEMENTATION_SUMMARY.md`." | Makes it clear this row is deferred, not a gap. |
| **DEMO_REQUIREMENTS.md** | Added header to "AWS demo requirements" section: *(Historical — Optional Path)*; prefixed entire section with: "This path is historical and optional. Current implementation uses **Helm + kubeadm/Rancher** for all deployments. See `INSTALLATION.md` and `QUICKSTART.md` for the current, tested deployment path. AWS EKS *can* run Helm charts, but the AWS-specific provisioning path below is **not actively tested or maintained**." | Prevents confusion: AWS path is possible but optional; Helm is the tested/maintained path. |
| **README.md** | Replaced "Cloud Layer" component list. Changed generic "AWS EKS, EC2, IAM, S3, CloudWatch" to tagged items: "AWS EKS *(optional; Helm charts support any Kubernetes)*, EC2 *(not required; local nodes or any K8s worker)*, IAM *(integrable via external-secrets)*, S3 *(optional artifact storage)*, CloudWatch *(optional; currently using open-source Prometheus/Loki/OTel)*". Added note: "CloudGraph is Kubernetes-native and runs on any Kubernetes distribution. **Current deployment uses Helm + kubeadm/Rancher** (not cloud-specific)." | Removes implication that AWS components are required; clarifies that open-source tools are the deployed baseline. |
| **docs/architecture/system-overview.md** | Rewrote "Step 1 — Installation" section. Added: "**Current tested deployment:** Helm + kubeadm/Rancher (documented in `INSTALLATION.md` and `QUICKSTART.md`)." Changed AWS EKS entry to: "AWS EKS *(Helm charts are compatible; AWS-specific Terraform path is historical, not actively tested)*." | Clarifies the tested deployment while noting compatibility. |
| **ROADMAP.md** | Marked Week 2 infrastructure tasks with ⚠️ **Historical Note** header above the "Infrastructure" section. Changed "Provision AWS EKS / Configure IAM / Setup VPC" from `[x]` to `[~]` (partial/deferred). Added notes: "*Historical; now using Helm + kubeadm/Rancher (see `IMPLEMENTATION_SUMMARY.md`)*", "*Historical; now using Kubernetes RBAC*", "*Historical; now using cluster-agnostic networking*". | Corrects the misleading checkmarks to reflect what was actually delivered (Helm/K8s, not cloud provisioning). |

### Narrative Consistency

All changes follow the **"preserve design narrative while clarifying shipped reality"** principle:

- Design docs keep AWS/Terraform references as historical/aspirational but explicitly mark them as not implemented.
- Deployment docs (INSTALLATION.md, QUICKSTART.md, system-overview.md) now consistently point to Helm + kubeadm as the current, tested path.
- Supervisors/examiners can cross-reference ROADMAP.md against docs/week-2/task-evidence-matrix.md and now see consistent evidence: no AWS EKS/IAM/VPC delivered; instead, raw K8s manifests + Helm charts + observability deployed.

**Result:** Documentation drift from Terraform/EKS → Helm/kubeadm is now transparent and non-misleading. The design/research narrative is preserved, but implementation reality is clear.

---

## 4. 🚧 Full Remaining Work — Week by Week

### Week 4 — GraphRAG Retrieval Engine (0% implemented)

- [ ] Deploy Qdrant collection(s) and connect a Python client from the API/engine.
- [ ] Build a chunking + embedding pipeline for logs, metrics summaries, alerts, and incident notes.
- [ ] Implement vector similarity search (traditional RAG baseline).
- [ ] Implement multi-hop Cypher traversal + context expansion from an incident seed node.
- [ ] Implement hybrid ranking (semantic similarity + graph distance + recency + source reliability).
- [ ] Expose `/api/v1/graphrag/search` and `/api/v1/graphrag/retrieve` endpoints.
- [ ] Replace the Tempo adapter stub with real trace ingestion, and actually deploy Grafana Tempo in `deployments/kubernetes/observability/`.
- [ ] Retrieval relevance tests, latency benchmarks, precision/recall scaffolding.

### Week 5 — Multi-Agent Framework (0% implemented)

- [ ] Stand up LangGraph in `services/agent-orchestrator` (currently an empty mock server).
- [ ] Implement the 5 specialist agents (Monitoring, Log, Trace, Deployment, Security) as LangGraph nodes reading from GraphRAG retrieval, not the current keyword ladder.
- [ ] Agent-to-agent / agent-to-orchestrator message passing and shared state.
- [ ] Consensus engine: confidence scoring, weighted voting, cross-agent agreement.
- [ ] Unit tests per agent + integration test for the full orchestration graph.

### Week 6 — RCA & Recommendation Engine (0% implemented)

- [ ] Root Cause Agent: hypothesis generation/ranking from fused agent evidence.
- [ ] Explainable graph-path output (the evidence chain the README's example JSON promises).
- [ ] Remediation/rollback recommendation generation.
- [ ] Hallucination-checking layer (unsupported-claim detection against graph evidence) — this is the whole basis of RQ3/H3 and doesn't exist yet in any form.
- [ ] Replace `/api/v1/investigations/trigger`'s hard-coded if/else logic with calls into the real Investigation Engine + Agent Orchestrator once built.

### Week 7 — Experimental Evaluation (0% implemented)

- [ ] Build 100+ labeled synthetic incidents across the 5 categories already defined in the methodology (K8s, networking, security, deployment, observability).
- [ ] Ground-truth root-cause labels per incident.
- [ ] Implement the 4 baselines end-to-end: keyword search, vector RAG, GraphRAG-only, GraphRAG+agents.
- [ ] Compute precision/recall/F1, top-1/top-3 RCA accuracy, hallucination rate, MTTR proxy for each baseline.
- [ ] Statistical tests (t-test, Wilcoxon) + confidence intervals comparing baselines against H1–H4.
- [ ] UI dashboard work beyond the current topology view: incident list, evidence-chain visualization, per-agent findings panel (partially scaffolded in `style.css`/`index.html` but not wired to real data).

### Week 8 — Dissertation & Final Submission (0% implemented)

- [ ] All dissertation chapters (only the *plan* for what goes in each chapter exists today, in `dissertation-evidence.md`).
- [ ] Final README/screenshots/demo video.
- [ ] End-to-end, load, security, performance testing passes.

---

## 5. 🧹 Smaller but real gaps (from `PROJECT_COMPLETION_CHECKLIST.md`, still open)

- [ ] No authentication/authorization anywhere (API or UI).
- [ ] No secrets management — Neo4j password is a literal `"changeme"` / `cloudgraph_dev_password` in multiple files.
- [ ] No TLS, network policies, or pod disruption budgets.
- [ ] No OpenAPI/Swagger docs beyond FastAPI's auto-generated schema.
- [ ] No CRDs despite `crds.enabled: true`.
- [ ] Redis declared but entirely unused.
- [ ] No end-to-end test proving telemetry → graph → retrieval → RCA in one pass (the single most valuable missing test).

---

## 6. 🎯 Recommended Next Step (single most valuable action)

Everything above is real work, but the highest-leverage next move — the one
that turns "strong infrastructure prototype" into "a system that can answer
RQ1–RQ4" — is:

1. **Qdrant + embeddings** (smallest Week 4 slice): stand up Qdrant, embed
   existing Log/Metric nodes already flowing into Neo4j, and expose one
   `/retrieve` endpoint that does plain vector search. This gives you your
   first real baseline (Baseline B: traditional RAG) with almost no new
   infra — the data's already being ingested.
2. **One graph-traversal retrieval function** on top of what's already in
   Neo4j (services/pods/deployments/logs are already linked) — this gives
   you Baseline C (GraphRAG) without touching agents at all.
3. **Wire those two into `/api/v1/investigations/trigger`** so the existing
   UI's "Run AI Diagnosis" button starts reflecting real retrieval instead
   of the keyword ladder — you get a visible, demoable upgrade for very
   little net-new surface area.
4. Only after that, start LangGraph/agents (Week 5) — building agents before
   there's a retrieval layer for them to read from doesn't buy you anything
   testable yet.

In parallel (low effort, low risk): do the documentation drift cleanup in
§3, since a supervisor or examiner cross-referencing `ROADMAP.md` against
`docs/week-2/task-evidence-matrix.md` will immediately notice the EKS/IAM/VPC
checkboxes have no matching evidence.
