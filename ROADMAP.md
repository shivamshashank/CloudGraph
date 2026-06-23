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

| # | Branch Name | Roadmap Target | Key Scope & Deliverables |
|---|-------------|----------------|--------------------------|
| 1 | `research/rq-methodology-design` | Week 1 | Formulating research questions (RQ1–RQ4), hypotheses (H1–H4), high-level system architecture, graph schema, and dissertation outline. |
| 2 | `infra/aws-eks-terraform` | Week 2 | Provisioning AWS EKS, configuring VPC, subnets, security groups, IAM roles for service accounts (IRSA), and setting up Terraform. |
| 3 | `infra/k8s-observability-stack` | Week 2 | Setting up ArgoCD and Helm pipelines; deploying Prometheus, Grafana, Loki, Tempo, and configuring the OpenTelemetry collector. |
| 4 | `feature/neo4j-graph-schema` | Week 3 | Setting up Neo4j databases (via Docker/Helm) and defining Cypher schemas, node models, and relationship structures. |
| 5 | `feature/graph-ingestion-pipeline` | Week 3 | Writing ingestion controllers to parse Kubernetes events, logs, metrics, traces, and git commits directly into the graph. |
| 6 | `feature/qdrant-embedding-pipeline` | Week 4 | Spinning up the Qdrant vector database, writing text chunking/embedding scripts, and configuring hybrid vector-keyword retrieval. |
| 7 | `feature/graphrag-traversal-api` | Week 4 | Coding multi-hop graph traversal algorithms, local context expansion, ranking, and setting up the search/query FastAPI endpoints. |
| 8 | `feature/multi-agent-langgraph` | Week 5 | Building monitoring, log, trace, deployment, and security agents as LangGraph nodes, along with their workflow message orchestration. |
| 9 | `feature/agent-consensus-engine` | Week 5 | Developing the evidence fusion layer, including confidence scoring, weighted voting, and cross-agent correlation mechanisms. |
| 10 | `feature/rca-recommendation-engine` | Week 6 | Implementing the Root Cause Agent to rank hypotheses, generate explainable graph reasoning paths, and propose remediation tasks. |
| 11 | `evaluation/incident-benchmark-dataset` | Week 7 | Automating the generation of 100+ failure scenarios (CrashLoopBackOff, networking, security) and evaluating performance (precision, recall, MTTR). |
| 12 | `docs/dissertation-release-v1` | Week 8 | Conducting end-to-end integration/performance testing, packaging final API docs, screenshots, and compiling dissertation deliverables. |

---

# Week 1 — Research & System Design

## Objectives

- Define dissertation scope
- Finalize research questions
- Complete literature review
- Design architecture

## Tasks

### Research

- [ ] Review GraphRAG papers
- [ ] Review AIOps literature
- [ ] Review Multi-Agent Systems
- [ ] Review RCA techniques
- [ ] Review Knowledge Graph approaches

### Documentation

- [ ] Define RQ1–RQ4
- [ ] Define hypotheses H1–H4
- [ ] Define evaluation metrics
- [ ] Create dissertation outline

### Design

- [ ] High-Level Architecture
- [ ] Graph Schema Design
- [ ] Agent Design
- [ ] AWS Deployment Design

### Deliverables

- [ ] Literature Review
- [ ] Architecture Diagrams
- [ ] Research Methodology

---

# Week 2 — Infrastructure & Observability Setup

## Objectives

Build cloud-native environment.

## Tasks

### Infrastructure

- [ ] Provision AWS EKS
- [ ] Configure Terraform
- [ ] Configure IAM
- [ ] Setup VPC

### Kubernetes

- [ ] Deploy sample applications
- [ ] Configure Helm
- [ ] Configure ArgoCD

### Observability

- [ ] Install Prometheus
- [ ] Install Grafana
- [ ] Install Loki
- [ ] Install Tempo
- [ ] Configure OpenTelemetry

### Testing

- [ ] Verify metrics collection
- [ ] Verify tracing
- [ ] Verify logging

### Deliverables

- [ ] Operational Kubernetes Environment
- [ ] Observability Stack

---

# Week 3 — Knowledge Graph Development

## Objectives

Build graph ingestion pipeline.

## Tasks

### Neo4j

- [ ] Deploy Neo4j
- [ ] Create graph schema
- [ ] Design node models
- [ ] Design relationships

### Data Ingestion

- [ ] Metrics ingestion
- [ ] Logs ingestion
- [ ] Traces ingestion
- [ ] Deployment ingestion
- [ ] Git ingestion

### Graph Construction

- [ ] Entity linking
- [ ] Dependency mapping
- [ ] Service relationship generation

### Testing

- [ ] Graph validation
- [ ] Query performance testing
- [ ] Relationship accuracy testing

### Deliverables

- [ ] Dynamic Knowledge Graph

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
- [ ] Trace Agent
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
