# CloudGraph Project Audit Report

**CloudGraph** is a GraphRAG-powered AIOps incident root-cause analysis (RCA) platform designed for Kubernetes environments. It combines property graph topology in Neo4j, vector embeddings in Qdrant, a multi-agent orchestration architecture across 5 specialist domain agents, and mathematical confidence propagation/provenance claim scoring to automate incident diagnosis.

---

## ✅ Completed

- [x] **Core FastAPI Backend (`services/api`)**:
  - Main application entrypoint in [main.py](file:///Users/shivam_shashank/CloudGraph/services/api/app/main.py) with lifespan management for database connections and CORS support.
  - Health checks (`/health`, `/ready`), topology discovery, entity linking, incident CRUD operations, comment tracking, LLM settings persistence, and live log handling.
- [x] **Service Wiring & Microservice Architecture**:
  - Main API service communicates with `agent-orchestrator` (`http://localhost:8082`), which calls `investigation-engine` (`http://localhost:8081`).
  - Full inter-service HTTP request pipeline supporting model delegation to OpenAI (`gpt-4o-mini`), Google Gemini (`gemini-1.5-flash`), or Anthropic Claude (`claude-3-5-sonnet-latest`).
- [x] **Dual Database Storage Integration**:
  - **Neo4j Graph Database**: Implemented schema constraints and performance indexes in [schema.cypher](file:///Users/shivam_shashank/CloudGraph/graph/schema.cypher) for `Service`, `Pod`, `Node`, `Deployment`, `Incident`, `Commit`, `Log`, and `Metric` nodes.
  - **Qdrant Vector Database**: Vector collection lifecycle management and semantic index persistence in [qdrant.py](file:///Users/shivam_shashank/CloudGraph/services/api/app/database/qdrant.py) using `sentence-transformers` (`all-MiniLM-L6-v2`) with TF-IDF fallback when torch is unavailable. Includes backfill script [backfill_qdrant.py](file:///Users/shivam_shashank/CloudGraph/services/api/app/scripts/backfill_qdrant.py).
- [x] **Multi-Agent Specialist RCA & Consensus Pipeline**:
  - **Investigation Engine (`services/investigation-engine`)**: Implements 5 specialist agents ([main.py](file:///Users/shivam_shashank/CloudGraph/services/investigation-engine/main.py)):
    - **Monitoring Agent**: Resource utilization trends & CPU/memory anomaly evaluation.
    - **Log Agent**: Error log pattern classification (OOM, auth failures, network timeouts, panic traces).
    - **Deployment Agent**: Rollout state correlation and Git commit attribution.
    - **Topology Agent**: Noisy neighbor detection and dependency cascade tracking.
    - **Security Agent**: RBAC authorization, secret leaks, and credential failure auditing.
  - **Agent Orchestrator (`services/agent-orchestrator`)**: Implements lead `ConsensusEngine` ([main.py](file:///Users/shivam_shashank/CloudGraph/services/agent-orchestrator/main.py)) aggregating agent findings with weighted scoring or LLM synthesis and robust rule-based fallbacks.
- [x] **Evidence & Provenance Claim Scoring**:
  - **Graph Confidence Propagation (GCP)**: Implemented in [gcp.py](file:///Users/shivam_shashank/CloudGraph/services/api/app/research/gcp.py) using BFS traversal, Noisy-OR mathematical aggregation, edge decay (`0.85`), and graph node confidence updates.
  - **Graph-Provenance Claim Scoring (GPCS)**: Implemented in [gpcs.py](file:///Users/shivam_shashank/CloudGraph/services/api/app/research/gpcs.py) to extract atomic claims from RCA reports, retrieve graph/vector evidence, compute `unsupported_claim_rate`, trust scores, proximity penalties, and source reliability weights.
- [x] **Hybrid Retrieval & GraphRAG Validation**:
  - Implemented [hybrid_ranker.py](file:///Users/shivam_shashank/CloudGraph/services/api/app/retrieval/hybrid_ranker.py) combining semantic vector similarity, graph hop distance, entity importance, and temporal recency decay.
  - Implemented graph traversal retriever in [graph_traversal.py](file:///Users/shivam_shashank/CloudGraph/services/api/app/retrieval/graph_traversal.py).
  - Context comparison endpoint `/api/v1/investigations/context-comparison` for side-by-side evaluation of keyword, vector, hybrid, and agent context modes.
- [x] **Telemetry & OpenTelemetry Ingestion Pipeline**:
  - Implemented `/api/v1/telemetry/traces`, `/api/v1/telemetry/metrics`, `/api/v1/telemetry/logs`, `/api/v1/telemetry/security`, `/api/v1/telemetry/chaos` endpoints in [telemetry.py](file:///Users/shivam_shashank/CloudGraph/services/api/app/routers/telemetry.py).
  - OpenTelemetry Collector configured in Helm values ([values.yaml](file:///Users/shivam_shashank/CloudGraph/deployments/helm/cloudgraph/values.yaml#L143-L159)) and Kubernetes observability manifests ([otel-collector.yaml](file:///Users/shivam_shashank/CloudGraph/deployments/kubernetes/observability/otel-collector.yaml#L36-L51)) with `otlphttp` exporters to automatically stream cluster telemetry to API endpoints.
  - 3-tier service dependency mapping in [graph_constructor.py](file:///Users/shivam_shashank/CloudGraph/services/api/app/adapters/graph_constructor.py#L47-L108) (Trace parent span matching -> Pod env vars -> Naming heuristics).
- [x] **GitHub Push Webhook & Commit Pipeline**:
  - Implemented `POST /api/v1/webhook/github` and `/api/v1/webhooks/github` in [webhooks.py](file:///Users/shivam_shashank/CloudGraph/services/api/app/routers/webhooks.py#L76-L144).
  - Native parsing of GitHub push event webhooks (`head_commit`, `commits`, `repository`, `pusher`).
  - Automatic `Commit` node creation, Cypher deployment correlation via `(c:Commit)-[:TRIGGERED_BY]->(d:Deployment)`, and Qdrant vector indexing.
- [x] **Go CLI Deployment Engine (`cmd/cloudgraph`)**:
  - Single-command Linux installer (`cloudgraph deploy`, `cloudgraph uninstall`, `doctor`, `status`, `health`, `ingest`).
  - Embedded Helm chart extraction ([embedded.go](file:///Users/shivam_shashank/CloudGraph/embedded.go)).
  - Explicit Linux OS requirement enforcement (`runtime.GOOS == "linux"`).
- [x] **UI Dashboard & Persistence (`services/ui`)**:
  - 7 full static HTML/CSS/JS frontend views ([static/](file:///Users/shivam_shashank/CloudGraph/services/ui/static/)): Workbench, Topology Graph, RCA Diagnosis, Evidence Matrix, Live Logs, GPCS Benchmark, and Settings.
  - Python HTTP proxy server in [main.py](file:///Users/shivam_shashank/CloudGraph/services/ui/main.py) routing `/api/*` requests to the API backend.
  - Full UI persistence for LLM credentials, incident status/assignment updates, comment additions, and live log streaming into Neo4j.
- [x] **Deployment & Helm Infrastructure**:
  - Production-ready Helm chart in [deployments/helm/cloudgraph](file:///Users/shivam_shashank/CloudGraph/deployments/helm/cloudgraph) with subcharts for Neo4j (`2026.5.0`), Qdrant (`1.18.2`), and Redis (`27.0.14`). Validated via [validate_helm.sh](file:///Users/shivam_shashank/CloudGraph/deployments/helm/validate_helm.sh).
  - Docker Compose configuration [docker-compose.yml](file:///Users/shivam_shashank/CloudGraph/deployments/docker-compose.yml) orchestrating all 11 core services and observability containers.
- [x] **Automated Test Coverage**:
  - **Python Test Suite**: 77/77 passing unit and integration tests across 16 test files.
  - **Go Test Suite**: Unit tests passing for `cmd/cloudgraph` (`deploy_test.go`, `uninstall_test.go`, `main_test.go`) and observability endpoints ([tests/observability](file:///Users/shivam_shashank/CloudGraph/tests/observability)).

---

## 🔶 Partially Done

*(All previous partially done items have been fully completed)*

---

## ⛔ Still Left

- [ ] **WebSocket / Server-Sent Events (SSE) Live Push**:
  - Live topology updates, incidents, and live logs currently rely on HTTP REST polling (`GET /api/v1/graph/data`, `GET /api/v1/logs`, `GET /api/v1/incidents`). Real-time push notification over WebSockets or SSE is not implemented.
- [ ] **React / Next.js SPA Refactor**:
  - The UI is currently built using standard Vanilla JavaScript, CSS, and HTML5 served by a Python proxy server. While fully functional, the React / Next.js migration referenced in earlier design roadmaps (`docs/GPCS_UI_Benchmark_Roadmap.md`) is not started.
- [ ] **Multi-Cluster & Native Cloud Provider Discovery**:
  - Kubernetes topology discovery ([k8s_discovery.py](file:///Users/shivam_shashank/CloudGraph/services/api/app/adapters/k8s_discovery.py)) interacts with local/in-cluster Kubernetes API servers via standard kubeconfig. Native cloud provider API discovery (AWS EKS, GCP GKE, Azure AKS native SDK calls beyond kubeconfig) and multi-cluster federation described in architectural diagrams (`docs/images/system-overview/06-multi-cluster-architecture.svg`) are unstarted.

---

## 📝 Notes

1. **All Ingestion & Deployment Pipelines Verified**:
   - OpenTelemetry Collector stream forwarding, GitHub push webhook parsing, and Linux-exclusive Go CLI cluster deployment are 100% implemented and tested.
2. **Environment & Keys**:
   - The platform works out-of-the-box in offline/fallback mode using rule-based heuristics. Providing an API key (`OPENAI_API_KEY`, `GEMINI_API_KEY`, or `ANTHROPIC_API_KEY`) via the Settings UI or environment variables seamlessly enables LLM reasoning for agent diagnostics and consensus synthesis.
3. **Automated Testing**:
   - 77/77 Python unit tests and Go tests pass cleanly (`pytest services/api/tests tests/test_cli.py` & `go test ./cmd/cloudgraph/...`).
