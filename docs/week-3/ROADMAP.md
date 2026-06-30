# Week 3 — Knowledge Graph Development Roadmap

This dedicated roadmap details the tasks, technical scope, and verification steps for Week 3 of the dissertation project.

## Objectives
Build a dynamic knowledge graph ingestion pipeline and database engine using Neo4j.

---

## 📋 The 4-Part Plan

### Part 1: Neo4j Deployment & Schema Architecture (Technical & Architecture)
* **Goal**: Establish a scalable and structured Neo4j database environment and graph schema.
* **Tasks**:
  - [x] Deploy Neo4j database using Docker Compose (for local development) and Kubernetes Helm charts.
  - [x] Define the initialization Cypher schema scripts (`schema.cypher`).
  - [x] Set up database constraints (e.g., unique node IDs/names) and secondary indexes on time attributes (`timestamp`, `startTime`).
  - [x] Design Node Models:
    - `Service`, `Pod`, `Node`, `Deployment`, `Metric`, `Log`, `Trace`, `Commit`, `Incident`.
  - [x] Design Relationship Edges:
    - `(:Pod)-[:RUNS_ON]->(:Node)`
    - `(:Pod)-[:BELONGS_TO]->(:Service)`
    - `(:Deployment)-[:MANAGES]->(:Pod)`
    - `(:Service)-[:CALLS]->(:Service)` (inferred from trace spans)
    - `(:Pod)-[:GENERATES]->(:Metric|Log|Trace)`
    - `(:Commit)-[:TRIGGERED_BY]->(:Deployment)`
    - `(:Incident)-[:AFFECTS]->(:Service)`

### Part 2: Ingestion & Telemetry Parser Engine (Coding & Engineering)
* **Goal**: Code the ingestion controllers and parsers for metrics, logs, traces, and events.
* **Tasks**:
  - [x] Implement a Prometheus range metrics parser adapter.
  - [x] Implement a Loki logs parser to ingest logs and tag error/warning patterns.
  - [x] Implement a Tempo distributed tracing span tree parser.
  - [x] Implement webhook receivers for ArgoCD status updates and Git repository commits.
  - [x] Build a modular FastAPI ingestion worker supporting both real-time stream processing and batch offline loads.

### Part 3: Graph Construction & Entity Linking (Architecture & Coding)
* **Goal**: Map dynamic runtime dependencies and link entities within the graph database.
* **Tasks**:
  - [x] Code the dynamic entity linker mapping telemetry to Pods, and Pods to Nodes/Deployments.
  - [x] Implement trace span call-tree traversal to automatically generate service-to-service dependency maps (`CALLS` relationships).
  - [x] Write temporal indexing logic to track historical states of configurations and objects.

### Part 4: Validation, Querying & Performance Testing (Testing & QA)
* **Goal**: Ensure the integrity, performance, and accuracy of the generated graph database.
* **Tasks**:
  - [x] Write schema validation scripts verifying node properties and relationship integrity.
  - [x] Develop latency benchmarking tests for multi-hop Cypher traversals.
  - [x] Create an integration test suite injecting synthetic incident payloads to verify the final graph topology.

---

## 🎯 Deliverables
* [x] Dynamic Knowledge Graph: A running Neo4j instance with mapped schemas and loaded models.
* [x] Ingestion Engine Service: A Python-based FastAPI backend processing metrics, logs, and traces.
* [x] Verification Matrix: A documentation checklist confirming test pass rates and data accuracy.
