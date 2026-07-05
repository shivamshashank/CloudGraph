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
| 8  | `feature/multi-agent-langgraph`         | Week 5         | Building monitoring, log, deployment, and security agents as LangGraph nodes, along with their workflow message orchestration.              |
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

- [ ] Qdrant setup
- [ ] Embedding pipeline
- [ ] Hybrid retrieval
- [ ] Graph retrieval

### GraphRAG

- [ ] Multi-hop traversal
- [ ] Context expansion
- [ ] Ranking algorithms

### API

- [ ] Graph search endpoint
- [ ] Retrieval endpoint

### Testing

- [ ] Retrieval relevance tests
- [ ] Latency benchmarks
- [ ] Accuracy evaluation

### Deliverables

- [ ] Working GraphRAG System

---

# Week 5 — Multi-Agent Framework

## Objectives

Develop investigation agents.

## Tasks

### Agents

- [ ] Monitoring Agent
- [ ] Log Agent
- [ ] Investigation Agent
- [ ] Deployment Agent
- [ ] Security Agent

### LangGraph

- [ ] Agent orchestration
- [ ] Agent communication
- [ ] Workflow design

### Consensus Engine

- [ ] Evidence aggregation
- [ ] Confidence scoring
- [ ] Voting mechanism

### Testing

- [ ] Agent unit tests
- [ ] Agent integration tests
- [ ] Consensus validation

### Deliverables

- [ ] Multi-Agent Investigation System

---

# Week 6 — RCA & Recommendation Engine

## Objectives

Generate explainable RCA.

## Tasks

### RCA Engine

- [ ] Hypothesis generation
- [ ] Evidence ranking
- [ ] Root cause scoring

### Recommendations

- [ ] Remediation suggestions
- [ ] Rollback analysis
- [ ] Risk assessment

### Explainability

- [ ] Evidence chains
- [ ] Graph explanation paths

### Testing

- [ ] RCA accuracy tests
- [ ] Hallucination analysis
- [ ] Explainability validation

### Deliverables

- [ ] Explainable RCA Engine

---

# Week 7 — Experimental Evaluation

## Objectives

Run dissertation experiments.

## Tasks

### Dataset

- [ ] Create 100+ incidents
- [ ] Create failure scenarios
- [ ] Label ground truth RCA

### Baselines

- [ ] Traditional Search
- [ ] Traditional RAG
- [ ] GraphRAG
- [ ] GraphRAG + Multi-Agent

### Evaluation

- [ ] Precision
- [ ] Recall
- [ ] F1 Score
- [ ] MTTR Reduction
- [ ] Hallucination Rate

### Statistical Analysis

- [ ] T-Test
- [ ] Wilcoxon Test
- [ ] Confidence Intervals

### Deliverables

- [ ] Experimental Results

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
