# 🗓️ 8-Week Dissertation Roadmap

## Overall Deliverables

- ✅ CloudGraph MVP
- ✅ Knowledge Graph Engine
- ✅ GraphRAG Retrieval Layer
- ✅ Multi-Agent Investigation System
- ✅ Kubernetes Incident Dataset
- ✅ Evaluation Framework
- ✅ Experimental Results
- ✅ Dissertation Report
- ✅ Final Demonstration

## GitHub Branch Strategy

| #  | Branch Name                             | Roadmap Target | Key Scope & Deliverables                                                                                                                           |
| -- | --------------------------------------- | -------------- | -------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1  | `research/rq-methodology-design`        | Week 1         | Formulating research questions (RQ1–RQ4), hypotheses (H1–H4), high-level system architecture, graph schema, and dissertation outline.              |
| 2  | `infra/k8s-deployment`                  | Week 2         | Provisioning a Kubernetes deployment baseline with cluster-ready manifests and deployment validation.                  |
| 3  | `infra/k8s-observability-stack`         | Week 2         | Setting up ArgoCD and Helm pipelines; deploying Prometheus, Grafana, Loki, and configuring the OpenTelemetry collector.                     |
| 4  | `feature/neo4j-graph-schema`            | Week 3         | Setting up Neo4j databases (via Docker/Helm) and defining Cypher schemas, node models, and relationship structures.                                |
| 5  | `feature/graph-ingestion-pipeline`      | Week 3         | Writing ingestion controllers to parse Kubernetes events, logs, metrics, and git commits directly into the graph.                          |
| 6  | `feature/qdrant-embedding-pipeline`     | Week 4         | Spinning up the Qdrant vector database, writing text chunking/embedding scripts, and configuring hybrid vector-keyword retrieval.                  |
| 7  | `feature/graphrag-traversal-api`        | Week 4         | Coding multi-hop graph traversal algorithms, local context expansion, ranking, and setting up the search/query FastAPI endpoints.                  |
| 8  | `feature/multi-agent-orchestration`     | Week 5         | Building monitoring, log, deployment, and security agents as LLM-capable orchestrated components, with custom message orchestration.           |
| 9  | `feature/agent-consensus-engine`        | Week 5         | Developing the evidence fusion layer, including confidence scoring, weighted voting, and cross-agent correlation mechanisms.                       |
| 10 | `feature/rca-recommendation-engine`     | Week 6         | Implementing the Root Cause Agent to rank hypotheses, generate explainable graph reasoning paths, and propose remediation tasks.                   |
| 11 | `evaluation/incident-benchmark-dataset` | Week 7         | Automating the generation of 100+ failure scenarios (CrashLoopBackOff, networking, security) and evaluating performance (precision, recall, MTTR). |
| 12 | `feature/ui-dashboard`                  | Week 7         | Building a web-based UI to visualize incidents, display investigation results, render the knowledge graph, and show live observability data.       |
| 13 | `docs/dissertation-release-v1`          | Week 8         | Conducting end-to-end integration/performance testing, packaging final API docs, screenshots, and compiling dissertation deliverables.             |

---

# Week 1 — Research & System Design

## Objectives

- Define dissertation scope
- Finalize research questions
- Complete literature review
- Design architecture

## Tasks

### Research

- [x] Review GraphRAG papers — `docs/week-1/literature-review.md`
- [x] Review AIOps literature — `docs/week-1/literature-review.md`
- [x] Review Multi-Agent Systems — `docs/week-1/literature-review.md`
- [x] Review RCA techniques — `docs/week-1/research-methodology.md`
- [x] Review Knowledge Graph approaches — `docs/week-1/architecture-design.md`
- [x] Define open-source data collection points — `docs/week-1/data-collection-strategy.md`

### Documentation

- [x] Define RQ1–RQ4 — `docs/week-1/research-methodology.md`
- [x] Define hypotheses H1–H4 — `docs/week-1/research-methodology.md`
- [x] Define evaluation metrics — `docs/week-1/research-methodology.md`
- [x] Create dissertation outline — `docs/week-1/dissertation-evidence.md`

### Design

- [x] High-Level Architecture — `docs/week-1/architecture-design.md`
- [x] Graph Schema Design — `docs/week-1/architecture-design.md`
- [x] Agent Design — `docs/week-1/architecture-design.md`
- [x] AWS Deployment Design — `docs/week-1/architecture-design.md`
- [x] Live Continuous Data Design — `docs/week-1/data-collection-strategy.md`

### Deliverables

- [x] Literature Review — `docs/week-1/literature-review.md`
- [x] Architecture Diagrams — `docs/week-1/architecture-design.md`
- [x] Research Methodology — `docs/week-1/research-methodology.md`
- [x] Open-Source Data Collection Strategy — `docs/week-1/data-collection-strategy.md`
- [x] Task Evidence Matrix — `docs/week-1/task-evidence-matrix.md`

---

# Week 2 — Infrastructure & Observability Setup

## Objectives

Build cloud-native environment.

## Tasks

### Infrastructure

> **⚠️ Historical Note:** The boxes below are marked checked in the original roadmap, but the actual Week 2 implementation (documented in `docs/week-2/task-evidence-matrix.md`) delivered **raw Kubernetes manifests + Helm charts**, not cloud-specific provisioning. No AWS EKS, IAM, or VPC configuration was actually executed or tested. These checkboxes should reflect reality: **[~] Provision cloud infrastructure (deferred to Helm abstraction)**.

- [~] Provision AWS EKS — *Historical; now using Helm + kubeadm/Rancher (see `IMPLEMENTATION_SUMMARY.md`)*
- [~] Configure IAM — *Historical; now using Kubernetes RBAC*
- [~] Setup VPC — *Historical; now using cluster-agnostic networking*

### Kubernetes

- [x] Deploy sample applications
- [x] Configure Helm (Bypassed via raw manifests, documented)
- [x] Configure ArgoCD

### Observability

- [x] Install Prometheus
- [x] Install Grafana
- [x] Install Loki
- [x] Configure OpenTelemetry

### Testing

- [x] Verify metrics collection
- [x] Verify tracing
- [x] Verify logging

### Deliverables

- [x] Operational Kubernetes Environment — `docs/week-2/README.md`
- [x] Observability Stack — `docs/week-2/README.md`

---

# Week 3 — Knowledge Graph Development

## Objectives

Build graph ingestion pipeline.

## Tasks

### Neo4j

- [x] Deploy Neo4j
- [x] Create graph schema
- [x] Design node models
- [x] Design relationships

### Data Ingestion

- [x] Metrics ingestion
- [x] Logs ingestion
- [x] Deployment ingestion
- [x] Git ingestion

### Graph Construction

- [x] Entity linking
- [x] Dependency mapping
- [x] Service relationship generation

### Testing

- [x] Graph validation
- [x] Query performance testing
- [x] Relationship accuracy testing

### Deliverables

- [x] Dynamic Knowledge Graph

---

# Week 4 — GraphRAG Engine

## Objectives

Implement retrieval engine.

## Tasks

### Retrieval

- [x] Qdrant setup
- [x] Embedding pipeline
- [x] Hybrid retrieval
- [x] Graph retrieval

### GraphRAG

- [x] Multi-hop traversal
- [x] Context expansion
- [x] Ranking algorithms

### API

- [x] Graph search endpoint
- [x] Retrieval endpoint

### Testing

- [x] Retrieval relevance tests
- [x] Latency benchmarks
- [x] Accuracy evaluation

### Deliverables

- [x] Working GraphRAG System

---

# Week 5 — Multi-Agent Framework

## Objectives

Develop investigation agents.

## Tasks

### Agents

- [x] Monitoring Agent
- [x] Log Agent
- [x] Investigation Agent
- [x] Deployment Agent
- [x] Security Agent

### Orchestration

- [x] Agent orchestration — custom HTTP-based orchestrator manages inter-service requests
- [x] Agent communication — JSON payloads forwarded between engine and orchestrator
- [x] Workflow design — structured multi-stage investigation with agents and consensus engine

### Consensus Engine

- [x] Evidence aggregation
- [x] Confidence scoring
- [x] Voting mechanism

### Testing

- [x] Agent unit tests
- [x] Agent integration tests
- [x] Consensus validation

### Deliverables

- [x] Multi-Agent Investigation System

---

# Week 6 — RCA & Recommendation Engine

## Objectives

Generate explainable RCA and evaluate claim grounding.

## Tasks

### RCA Engine

- [x] Hypothesis generation — Orchestrator and specialist agents formulate root cause theories
- [x] Evidence ranking — Hybrid ranker ranks nodes based on semantic, graph, and recency scores
- [x] Root cause scoring — Consensus engine weights agent findings; GCP propagates belief scores

### Recommendations

- [x] Remediation suggestions — Generated alongside root cause diagnosis in the orchestrator
- [x] Rollback analysis — Attributed via Deployment Agent matching to triggered Git commits
- [x] Risk assessment — Severity classification based on anomalous state propagation

### Explainability

- [x] Evidence chains — Traversal contexts output node paths linked to incidents
- [x] Graph explanation paths — GPCS aligns extracted claims to Neo4j and Qdrant evidence

### Testing

- [x] RCA accuracy tests — Verified in unit and integration test suites
- [x] Hallucination analysis — GPCS trust scoring measures unsupported claim rate
- [x] Explainability validation — Automated assertions in `test_graphrag_validation.py`

### Deliverables

- [x] Explainable RCA Engine

---

# Week 7 — Experimental Evaluation

## Objectives

Run evaluation experiments.

## Tasks

### Dataset

- [x] Create 10 dynamic incident scenarios with ground-truth root causes and claims
- [x] Seed failure scenarios for evaluation

### Baselines

- [x] Traditional Search (Keyword)
- [x] Traditional RAG (Vector-only)
- [x] GraphRAG
- [x] GraphRAG + Multi-Agent
- [x] GraphRAG + Multi-Agent + GCP + GPCS (Full Stack)

### Evaluation

- [x] Precision, Recall, F1 Score, Latency, and Hallucination (Unsupported Claim) Rate metrics calculated dynamically in the benchmark endpoint
- [~] Heuristic scoring calculators used for fast dynamic evaluations

### Statistical Analysis

- [ ] T-Test / Wilcoxon Test (Not implemented)
- [ ] Confidence Intervals (Not implemented)

### Deliverables

- [~] Experimental Results (Dynamic Benchmark Engine and UI comparison metrics are operational)

---

# Week 8 — Dissertation Writing & Final Submission

## Objectives

Prepare dissertation and repository.

## Tasks

### Dissertation

- [ ] Introduction
- [ ] Literature Review
- [ ] Methodology
- [ ] System Design
- [ ] Implementation
- [ ] Evaluation
- [ ] Discussion
- [ ] Conclusion

### Repository

- [ ] Final README
- [ ] Screenshots
- [ ] Architecture Diagrams
- [ ] API Documentation

### Testing

- [ ] End-to-End Testing
- [ ] Load Testing
- [ ] Security Testing
- [ ] Performance Testing

### Submission

- [ ] Dissertation PDF
- [ ] GitHub Repository
- [ ] Presentation Slides
- [ ] Demonstration Video

### Deliverables

- [ ] Final Dissertation
- [ ] Final Codebase
- [ ] Viva Preparation

---

# Success Criteria

## Technical

- [ ] Kubernetes Environment Operational
- [ ] Knowledge Graph Generated
- [ ] GraphRAG Retrieval Working
- [ ] Multi-Agent System Functional
- [ ] Explainable RCA Generated

## Research

- [ ] Research Questions Answered
- [ ] Hypotheses Evaluated
- [ ] Statistical Significance Measured
- [ ] Ablation Studies Completed

## Dissertation

- [ ] Distinction-Level Quality
- [ ] Reproducible Results
- [ ] Publication Potential
