# CloudGraph Repository Audit Report

## Project Summary

CloudGraph is a GraphRAG-powered AIOps incident-analysis platform for Kubernetes that combines a Neo4j knowledge graph, a Qdrant-backed semantic store, a custom HTTP-based multi-agent investigation pipeline, and research-oriented scoring modules for GCP and GPCS. The repository contains a substantially implemented codebase with a Go CLI, FastAPI services, deployment manifests, and a static web UI, but some of the more ambitious evaluation and publication work remains incomplete or only partially wired.

## ✅ Completed

- [x] Core feature implementation is present across the main services: the FastAPI backend exposes health and readiness routes, graph discovery, telemetry ingestion, webhooks, logs/settings persistence, and investigation triggers in [services/api/app/main.py](services/api/app/main.py) and its routers.
- [x] Service wiring is implemented end to end: the API calls the agent orchestrator and investigation engine over HTTP, and the orchestrator/engine services contain specialist agents and a consensus layer in [services/agent-orchestrator/main.py](services/agent-orchestrator/main.py) and [services/investigation-engine/main.py](services/investigation-engine/main.py).
- [x] Trace ingestion and graph relationship coverage are implemented: telemetry routes for traces, metrics, logs, security events, and chaos experiments exist in [services/api/app/routers/telemetry.py](services/api/app/routers/telemetry.py), and graph construction logic for Pod/Node/Service/Deployment links and service dependency edges is in [services/api/app/adapters/graph_constructor.py](services/api/app/adapters/graph_constructor.py).
- [x] Evidence and claim scoring work is present: GCP is implemented in [services/api/app/research/gcp.py](services/api/app/research/gcp.py), and GPCS is implemented in [services/api/app/research/gpcs.py](services/api/app/research/gpcs.py) with claim extraction, evidence retrieval, and unsupported-claim scoring wired into the investigation flow.
- [x] UI persistence and storage integration are real, not mocked: the static UI in [services/ui/static](services/ui/static) calls backend endpoints for settings, logs, and investigations, while the backend persists settings and live logs to Neo4j via [services/api/app/routers/settings.py](services/api/app/routers/settings.py) and [services/api/app/routers/logs.py](services/api/app/routers/logs.py).
- [x] Deployment and infrastructure assets are present: the Go CLI in [cmd/cloudgraph](cmd/cloudgraph) and the Helm/Kubernetes manifests under [deployments](deployments) provide a concrete deployment path for the platform.

## 🔶 Partially Done

- [~] Trace ingestion is implemented, but the live tracing story is not fully complete in the deployment environment: the API accepts traces and builds dependency relationships, yet the repository notes indicate that the Tempo deployment path is not fully wired into the live demo stack, so some graph edges remain dependent on fallback heuristics rather than real trace-driven topology.
- [~] Benchmarking is partly real: the evaluation layer in [services/api/app/research/evaluation.py](services/api/app/research/evaluation.py) executes actual retrieval and scoring steps, but the benchmark endpoint in [services/api/app/routers/benchmark.py](services/api/app/routers/benchmark.py) still uses fixed baseline unsupported-claim-rate values for several baselines and exposes static benchmark metadata as a fallback.
- [~] Documentation is partly aligned with the implementation: some docs now describe the custom orchestrator and Helm/kubeadm reality, but other top-level docs still contain older wording around frontend tech and AWS-centric architecture that does not match the current static UI and deployment path.

## ⛔ Still Left

- [ ] Real-time live push for the UI via WebSocket or SSE is not implemented; the UI still relies on polling.
- [ ] Multi-cluster or native cloud-provider discovery is not implemented; discovery is currently centered on local Kubernetes topology access.
- [ ] GPCS self-consistency comparison work is not present in the repository.
- [ ] Formal statistical significance testing, held-out calibration, and human evaluation are not implemented in the codebase.
- [ ] Authentication and authorization for the settings and other API routes are not implemented, and the settings endpoint currently stores API keys without an auth layer.
- [ ] Dissertation chapter drafting and full evaluation/discussion writing are still missing; the repository contains documentation outlines but not finished chapter content.

## 📝 Notes

- The repository’s own status documents and roadmap explicitly call out several of these gaps, which matches the code and manifests reviewed here.
- The strongest implemented areas are the backend services, graph ingestion, GCP/GPCS scoring, and the deployment packaging; the biggest remaining gaps are in evaluation rigor, security hardening, and real-time UI behavior.
- The next highest-value work would be to finish the benchmark evaluation path so all baselines are measured rather than partially fixed, implement the GPCS self-consistency baseline, add real statistical evaluation, and harden API authentication before broader use.
