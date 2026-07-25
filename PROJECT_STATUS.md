# CloudGraph Project Status

This document is the single source of truth for the current implementation status, architectural wiring, and roadmap alignment of the **CloudGraph** project.

---

## 📌 Project Overview

**CloudGraph** is a GraphRAG-powered AIOps incident root-cause analysis (RCA) platform designed for Kubernetes. It integrates a property graph in Neo4j and semantic indices in Qdrant using cluster logs, metrics, events, and Git webhook deployments. This knowledge graph is queried using a hybrid ranker to formulate GraphRAG retrieval contexts, which are processed by a multi-agent system comprising 5 domain-specific specialist agents and a central consensus engine. The platform is deployed cluster-agnostically via a custom Go CLI and Helm charts, and contains mathematical layers for Graph Confidence Propagation (GCP) and Graph-Provenance Claim Scoring (GPCS).

---

## ✅ Completed

- **Core FastAPI Backend (`services/api`)**:
  - Live API server implemented in [main.py](file:///Users/shivam_shashank/CloudGraph/services/api/app/main.py) with lifespan connection management and CORS support.
  - Endpoints for health checks (`/health`, `/ready`), dynamic cluster discovery (`/api/v1/graph/discover`), incident CRUD operations, comments, and settings configuration.
  - Webhook routers in [webhooks.py](file:///Users/shivam_shashank/CloudGraph/services/api/app/routers/webhooks.py) handle push events to dynamically generate `Commit` nodes, correlate them to deployment triggers via `(c:Commit)-[:TRIGGERED_BY]->(d:Deployment)`, and index them in Qdrant.
- **Service Wiring and Inter-Service Architecture**:
  - Inter-service HTTP request pipeline: `services/api` calls `services/agent-orchestrator` (port 8082), which delegates to `services/investigation-engine` (port 8081).
  - Integrations for OpenAI, Google Gemini, and Anthropic Claude APIs are configured via the Settings panel and dynamically called when keys are provided, falling back to deterministic rule-based algorithms when keys are absent.
- **Dual Database Storage Integration**:
  - **Neo4j Graph Database**: Graph constraints, schema definitions, and index properties are declared in [schema.cypher](file:///Users/shivam_shashank/CloudGraph/graph/schema.cypher) for `Service`, `Pod`, `Node`, `Deployment`, `Incident`, `Comment`, `LiveLog`, and `Commit` nodes.
  - **Qdrant Vector Database**: Collection creation and semantic index queries are implemented in [qdrant.py](file:///Users/shivam_shashank/CloudGraph/services/api/app/database/qdrant.py) using `sentence-transformers` (`all-MiniLM-L6-v2`), with a fallback to TF-IDF when torch is not loaded. An automated backfill script is available in [backfill_qdrant.py](file:///Users/shivam_shashank/CloudGraph/services/api/scripts/backfill_qdrant.py).
- **Multi-Agent Specialist RCA & Consensus Pipeline**:
  - **Investigation Engine (`services/investigation-engine`)**: Implements 5 specialist agents (Monitoring, Log, Deployment, Topology, Security) in [main.py](file:///Users/shivam_shashank/CloudGraph/services/investigation-engine/main.py). Each agent makes LLM-backed queries, defaulting to rule-based fallback regex and statistics parsers if credentials are absent.
  - **Agent Orchestrator (`services/agent-orchestrator`)**: Uses a `ConsensusEngine` in [main.py](file:///Users/shivam_shashank/CloudGraph/services/agent-orchestrator/main.py) to aggregate agent outputs via weighted rules or LLM consensus synthesis.
- **Evidence & Provenance Claim Scoring**:
  - **Graph Confidence Propagation (GCP)**: Implemented in [gcp.py](file:///Users/shivam_shashank/CloudGraph/services/api/app/research/gcp.py) using BFS traversal, edge weight decay, and Noisy-OR mathematical probability propagation.
  - **Graph-Provenance Claim Scoring (GPCS)**: Fully implemented in [gpcs.py](file:///Users/shivam_shashank/CloudGraph/services/api/app/research/gpcs.py). Extracts atomic claims from generated RCA summaries (via LLM or sentence regex fallback), retrieves supporting evidence via hybrid search and graph traversal, and computes a trust score alongside an `unsupported_claim_rate`. It is fully wired into the pod investigation workflow (`_investigate_pod` in [main.py](file:///Users/shivam_shashank/CloudGraph/services/api/app/main.py)).
- **Hybrid Retrieval & GraphRAG Validation**:
  - Implements multi-hop Cypher traversal in [graph_traversal.py](file:///Users/shivam_shashank/CloudGraph/services/api/app/retrieval/graph_traversal.py) and a hybrid ranker in [hybrid_ranker.py](file:///Users/shivam_shashank/CloudGraph/services/api/app/retrieval/hybrid_ranker.py) combining semantic similarity, graph hop distance, node importance, and temporal recency decay.
  - Exposes context comparison route (`POST /api/v1/investigations/context-comparison`) to compare keyword, vector, hybrid, and agent context modes.
  - Automated tests in [test_graphrag_validation.py](file:///Users/shivam_shashank/CloudGraph/services/api/tests/test_graphrag_validation.py) assert ranking metrics and search latency constraints (<100ms).
- **Telemetry & OpenTelemetry Ingestion Pipeline**:
  - Active ingestion endpoints (`/api/v1/telemetry/traces`, `/metrics`, `/logs`, `/security`, `/chaos`) are implemented in [telemetry.py](file:///Users/shivam_shashank/CloudGraph/services/api/app/routers/telemetry.py).
  - OpenTelemetry Collector configuration is defined in the Helm values and K8s manifests, using `otlphttp` exporters to stream data to the API.
  - Parent-child span mapping is implemented in [graph_constructor.py](file:///Users/shivam_shashank/CloudGraph/services/api/app/adapters/graph_constructor.py) to build service dependency maps.
- **Go CLI Deployment Engine (`cmd/cloudgraph`)**:
  - Native Linux CLI utility supporting commands like `version`, `doctor`, `status`, `health`, `ingest`, `deploy`, and `uninstall` (defined in [cmd/cloudgraph/main.go](file:///Users/shivam_shashank/CloudGraph/cmd/cloudgraph/main.go)).
  - Embeds the Helm chart manifests in [embedded.go](file:///Users/shivam_shashank/CloudGraph/embedded.go).
- **UI Dashboard & Real Persistence**:
  - 7 HTML/CSS/JS frontend pages served from `services/ui/static` (Workbench, Topology Graph, RCA Diagnosis, Evidence Matrix, Live Logs, GPCS Benchmark, Settings).
  - Frontend script in [workbench.html](file:///Users/shivam_shashank/CloudGraph/services/ui/static/workbench.html) and [settings.js](file:///Users/shivam_shashank/CloudGraph/services/ui/static/settings.js) is fully wired to invoke FastAPI endpoints (e.g. `PATCH /api/v1/incidents/{id}`, `POST /api/v1/incidents/{id}/comments`, `GET /api/v1/settings`) for true server-side persistence in Neo4j.
- **Helm & Kubernetes Deployments**:
  - Production-ready Helm chart in [deployments/helm/cloudgraph](file:///Users/shivam_shashank/CloudGraph/deployments/helm/cloudgraph) with subcharts for Neo4j and Qdrant. Validated via [validate_helm.sh](file:///Users/shivam_shashank/CloudGraph/deployments/helm/validate_helm.sh). Redis has been completely removed from the chart dependencies and configurations to keep the stack lean.
- **Automated Test Coverage**:
  - Python test suite: 77/77 passing unit and integration tests (validating `gpcs.py`, `gcp.py`, `hybrid_ranker.py`, webhooks, and routing).
  - Go CLI test suite: passing `deploy_test.go` and `uninstall_test.go` checks.

---

## 🔶 Partially Done

- **Tempo Tracing Deployment**:
  - The OTel ingestion adapter and API endpoints exist in [tempo.py](file:///Users/shivam_shashank/CloudGraph/services/api/app/adapters/tempo.py) and [telemetry.py](file:///Users/shivam_shashank/CloudGraph/services/api/app/routers/telemetry.py). However, Grafana Tempo is not deployed in the observability deployments folder (`deployments/kubernetes/observability`), meaning the tracing pipeline currently lacks a live collector source.
- **Service Dependency Edge (`CALLS`) Generation**:
  - The parent-span mapping logic in [graph_constructor.py](file:///Users/shivam_shashank/CloudGraph/services/api/app/adapters/graph_constructor.py) works, but depends on active trace data. Without a running Tempo instance, these service-to-service dependency edges cannot be constructed dynamically.

---

## ⛔ Still Left

- **WebSocket / Server-Sent Events (SSE) Live Push**:
  - UI page updates for active incidents, topology graph nodes, and live logs currently rely on HTTP REST polling. A real-time push mechanism using WebSockets or SSE is not implemented.
- **React / Next.js SPA Refactor**:
  - The UI is served as static Vanilla HTML/JS files via a Python proxy server. The Next.js migration outlined in the roadmap has not been started.
- **Multi-Cluster & Native Cloud Provider Discovery**:
  - Cluster topology discovery in [k8s_discovery.py](file:///Users/shivam_shashank/CloudGraph/services/api/app/adapters/k8s_discovery.py) is limited to local cluster queries via kubeconfig. SDK integrations for native cloud provider APIs (AWS EKS, GCP GKE, Azure AKS) and multi-cluster federation are absent.
- **True End-to-End Evaluation & Ablation Studies**:
  - The benchmark endpoint in [routers/benchmark.py](file:///Users/shivam_shashank/CloudGraph/services/api/app/routers/benchmark.py) exposes a dataset of 10 scenarios but relies on heuristic calculators (`_calc_kw`, `_calc_vector`, etc.) that return simulated metric offsets. It does not invoke true LLM prompts or run the actual retrieval pipelines across the dataset.
  - Formal human evaluation scoring, Cohen's Kappa agreements, and statistical significance checks (T-Test, Wilcoxon Test) are not implemented in code.
- **Dissertation Chapter Writing**:
  - The repository contains only the structural outline file [dissertation-evidence.md](file:///Users/shivam_shashank/CloudGraph/docs/week-1/dissertation-evidence.md). The actual draft text files for the chapters are missing/blank.

---

## 📝 Notes & Consistency Discrepancies

1. **LangGraph vs. Custom HTTP**: The documentation and roadmap refer to the multi-agent pipeline being built on LangGraph. In the code, there are no LangGraph or LangChain imports; the orchestrator is a custom Python HTTP server forwarding JSON payloads.
2. **Redis Cache**: Redis caching has been completely removed from the chart dependencies, configurations, and documentation to keep the stack lean.
3. **Security Caution**: The LLM settings panel (`/api/v1/settings`) does not implement API authentication or authorization. LLM API keys (OpenAI, Gemini, Claude) are sent from browser settings to the unauthenticated backend, posing credential exposure risks.
