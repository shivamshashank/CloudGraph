<div align="center">

# 🚀 CloudGraph

### GraphRAG-Powered Multi-Agent Root Cause Analysis for Cloud-Native Systems

CloudGraph is an AI-powered AIOps platform that combines Knowledge Graphs,
GraphRAG, Multi-Agent Systems, Kubernetes Observability, and Large Language
Models to automatically investigate incidents, identify root causes, and
generate remediation recommendations across cloud-native environments.

<br />

[![CI](https://img.shields.io/github/actions/workflow/status/shivamshashank/CloudGraph/ci.yml?branch=main&label=CI&logo=githubactions&style=flat-square)](https://github.com/shivamshashank/CloudGraph/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/actions/workflow/status/shivamshashank/CloudGraph/release.yml?branch=main&label=Release&logo=githubactions&style=flat-square)](https://github.com/shivamshashank/CloudGraph/actions/workflows/release.yml)
[![Codecov](https://img.shields.io/codecov/c/github/shivamshashank/CloudGraph?logo=codecov&style=flat-square)](https://codecov.io/gh/shivamshashank/CloudGraph)
[![Go Report Card](https://goreportcard.com/badge/github.com/shivamshashank/CloudGraph?https://img.shields.io/badge/go%20report-A+-brightgreen.svg?style=flat)](https://goreportcard.com/report/github.com/shivamshashank/CloudGraph)
[![GitHub release](https://img.shields.io/github/v/release/shivamshashank/CloudGraph?style=flat-square)](https://github.com/shivamshashank/CloudGraph/releases)
[![GitHub stars](https://img.shields.io/github/stars/shivamshashank/CloudGraph?style=flat-square)](https://github.com/shivamshashank/CloudGraph/stargazers)
[![GitHub forks](https://img.shields.io/github/forks/shivamshashank/CloudGraph?style=flat-square)](https://github.com/shivamshashank/CloudGraph/network/members)
[![License](https://img.shields.io/github/license/shivamshashank/CloudGraph?style=flat-square)](LICENSE)

<br />

![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Kubernetes](https://img.shields.io/badge/Kubernetes-326CE5?style=for-the-badge&logo=kubernetes&logoColor=white)
![AWS](https://img.shields.io/badge/AWS-FF9900?style=for-the-badge&logo=amazonaws&logoColor=white)
![Terraform](https://img.shields.io/badge/Terraform-844FBA?style=for-the-badge&logo=terraform&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white)
![Neo4j](https://img.shields.io/badge/Neo4j-4581C3?style=for-the-badge&logo=neo4j&logoColor=white)
![Prometheus](https://img.shields.io/badge/Prometheus-E6522C?style=for-the-badge&logo=prometheus&logoColor=white)
![Grafana](https://img.shields.io/badge/Grafana-F46800?style=for-the-badge&logo=grafana&logoColor=white)
![OpenTelemetry](https://img.shields.io/badge/OpenTelemetry-000000?style=for-the-badge&logo=opentelemetry&logoColor=white)
![LangGraph](https://img.shields.io/badge/LangGraph-Agentic_AI-1C3C3C?style=for-the-badge)
![Qdrant](https://img.shields.io/badge/Qdrant-DC244C?style=for-the-badge)

</div>

## 📌 Overview

CloudGraph transforms cloud observability data into explainable incident
intelligence.

It continuously ingests:

- Logs
- Metrics
- Traces
- Kubernetes Events
- Kubernetes Object State
- Alerts
- Runtime Security Events
- Git Commits
- Pull Requests
- Terraform Changes
- Deployment History

and constructs a real-time knowledge graph that powers GraphRAG retrieval and
multi-agent reasoning.

CloudGraph is designed to collect this data from open-source observability and
cloud-native tools such as OpenTelemetry, Prometheus, Grafana Loki, Grafana
Tempo, kube-state-metrics, node_exporter, Alertmanager, Argo CD, Falco, and
GitHub/GitLab webhooks. The full Week 1 data strategy is documented in
`docs/week-1/data-collection-strategy.md`.

---

# 🔬 Research Motivation

Modern cloud-native systems generate massive volumes of logs, metrics, traces,
deployment events, and infrastructure changes.

Existing AIOps solutions typically rely on:

- Rule-based correlation
- Keyword search
- Traditional vector-based retrieval

These approaches often struggle to:

- Understand service dependencies
- Correlate infrastructure and application failures
- Explain reasoning paths
- Investigate multi-hop incident chains

CloudGraph explores whether GraphRAG-powered knowledge graph retrieval and
multi-agent reasoning can improve root cause analysis accuracy, explainability,
and incident resolution performance within Kubernetes environments.

---

# 🎯 Research Questions

### RQ1

Can GraphRAG improve root cause analysis accuracy compared to traditional RAG?

### RQ2

Does multi-agent reasoning improve investigation quality compared to
single-agent analysis?

### RQ3

Can knowledge graph retrieval reduce hallucinations during RCA generation?

### RQ4

Can GraphRAG-powered investigations reduce Mean Time To Resolution (MTTR)?

---

# 🧪 Research Hypotheses

### H1

GraphRAG achieves significantly higher RCA accuracy than traditional RAG.

### H2

GraphRAG combined with Multi-Agent Systems outperforms GraphRAG alone.

### H3

Knowledge graph retrieval reduces hallucination rates during incident analysis.

### H4

Confidence-aware agent voting improves recommendation quality and trust.

---

## ✨ Core Features

- 🧠 GraphRAG-Powered Root Cause Analysis
- ☸️ Kubernetes-Native Architecture
- 🤖 Multi-Agent Investigation Workflow
- 🖥️ Unified AIOps Dashboard & Visualization
- 📊 Full Observability Integration
- 🔍 Explainable AI Decisions
- ⚡ Incident Correlation Engine
- 📈 MTTR Reduction Analytics
- 🔐 Security-Aware Investigations
- 🌐 Multi-Cloud Ready
- 📚 Incident Memory & Knowledge Base

---

# 🏆 Research Contributions

CloudGraph contributes the following research innovations:

## Contribution 1

### Temporal Incident Knowledge Graph

A dynamic knowledge graph that captures infrastructure relationships, deployment
history, service dependencies, and incident evolution over time.

## Contribution 2

### GraphRAG-Powered Incident Retrieval

Graph-based retrieval enables multi-hop reasoning across cloud resources,
services, deployments, alerts, and traces.

## Contribution 3

### Confidence-Aware Multi-Agent Investigation

Specialized agents independently investigate incidents and produce weighted
evidence scores used for consensus-driven RCA generation.

## Contribution 4

### Explainable Root Cause Analysis

Every recommendation can be traced back through graph relationships,
observability evidence, and agent reasoning.

## Contribution 5

### Reproducible Cloud Incident Benchmark

A benchmark dataset containing realistic Kubernetes incident scenarios for
GraphRAG evaluation.

---

# 🏗️ Architecture

<table>
  <tr>
    <td align="center" width="33%">
      <b>High-Level Architecture</b><br><br>
      <img src="docs/images/high-level-architecture.png" alt="Architecture">
    </td>
    <td align="center" width="33%">
      <b>GraphRAG Pipeline</b><br><br>
      <img src="docs/images/graphrag-pipeline.png" alt="GraphRAG">
    </td>
    <td align="center" width="33%">
      <b>Multi-Agent Workflow</b><br><br>
      <img src="docs/images/multi-agent-workflow.png" alt="Agents">
    </td>
  </tr>
  <tr>
    <td align="center">
      <b>AWS Deployment</b><br><br>
      <img src="docs/images/aws-deployment.png" alt="AWS Deployment">
    </td>
    <td align="center">
      <b>Knowledge Graph Schema</b><br><br>
      <img src="docs/images/knowledge-graph-schema.png" alt="Knowledge Graph Schema">
    </td>
    <td></td>
  </tr>
</table>

---

# 🧩 System Components

## Cloud Layer

- AWS EKS
- EC2
- IAM
- S3
- CloudWatch

## Kubernetes Layer

- Kubernetes
- Helm
- ArgoCD
- Ingress NGINX

## Observability Layer

- Prometheus
- Grafana
- Loki
- Tempo
- OpenTelemetry
- Alertmanager
- kube-state-metrics
- node_exporter
- Falco
- Argo CD Notifications

## Open-Source Data Collection Layer

CloudGraph can collect both historical and live continuous data from
open-source systems:

| Data | Open-Source Source | Example Evidence |
| --- | --- | --- |
| Logs | OpenTelemetry Collector, Loki, Promtail / Alloy | Exceptions, warnings, retries, kubelet/container logs |
| Metrics | Prometheus, kube-state-metrics, node_exporter | CPU, memory, pod status, restart count, latency, error rate |
| Traces | OpenTelemetry SDK/Collector, Tempo | Request paths, spans, dependency latency, failed calls |
| Kubernetes Events | Kubernetes API/event stream | Scheduling failures, image pull errors, probe failures, restarts |
| Alerts | Alertmanager | Fired/resolved alerts, severity, labels, affected service |
| Deployments | Argo CD notifications/webhooks | Sync status, health state, degraded apps, rollbacks |
| Git Activity | GitHub/GitLab webhooks | Commits, pull requests, changed files, release timestamps |
| Infrastructure Changes | Terraform/OpenTofu output and state | IAM, network, database, cluster, and configuration changes |
| Security Events | Falco | Runtime anomalies, suspicious process/file/network activity |

Live continuous ingestion can be implemented using a mix of pull, push, stream,
and batch modes:

- Pull: query Prometheus, Loki, Tempo, Kubernetes API, and Git APIs on a
  schedule.
- Push: receive webhooks from Alertmanager, Argo CD, GitHub/GitLab, Falco, and
  CI/CD systems.
- Stream: forward telemetry through OpenTelemetry Collector and log collectors.
- Batch: import historical incident datasets for repeatable dissertation
  experiments.

## Knowledge Graph Layer

- Neo4j

Nodes:

- Services
- Pods
- Deployments
- Databases
- Nodes
- Alerts
- Metrics
- Traces
- Commits

Relationships:

- CALLS
- DEPENDS_ON
- AFFECTS
- DEPLOYED_BY
- GENERATES

## Retrieval Layer

- GraphRAG
- Hybrid Search
- Vector Search
- Context Ranking

Vector Database:

- Qdrant

## AI Layer

- GPT-5
- Claude
- Llama 3
- LangGraph
- LangChain

## Frontend Layer

A web-based dashboard that serves as the central interface for CloudGraph. It
provides:

- **Live Observability**: Visualizes incoming logs, metrics, and traces.
- **Incident History**: Stores and displays past incidents and their
  resolutions.
- **Graph Visualization**: Shows the knowledge graph updating in real-time as
  investigations proceed.
- **Agent Monitoring**: Displays the status and findings of individual agents.

- React / Vue / Svelte
- D3.js / Vis.js (for graph visualization)

---

# 🤖 Agent Architecture

## Monitoring Agent

Analyzes:

- Metrics
- Alerts
- Resource Utilization

## Log Agent

Analyzes:

- Application Logs
- System Logs
- Error Patterns

## Trace Agent

Analyzes:

- Distributed Traces
- Latency Bottlenecks

## Deployment Agent

Analyzes:

- Git Commits
- CI/CD Events
- Terraform Changes

## Security Agent

Analyzes:

- RBAC
- Security Policies
- Cluster Events

## Root Cause Agent

Responsibilities:

- Evidence Fusion
- Root Cause Ranking
- Hypothesis Validation
- Confidence Estimation

## Consensus Engine

Aggregates findings from all agents using:

- Weighted Voting
- Confidence Scoring
- Temporal Correlation

---

# 🧪 Experimental Dataset

CloudGraph is evaluated using a reproducible incident benchmark dataset.

## Incident Categories

### Kubernetes

- CrashLoopBackOff
- ImagePullBackOff
- OOMKilled
- Node Failures

### Networking

- DNS Failures
- Service Discovery Issues
- Network Partitions

### Security

- RBAC Misconfigurations
- Secret Rotation Failures
- IAM Errors

### Deployments

- Faulty Releases
- Configuration Drift
- Terraform Errors

### Observability

- Missing Metrics
- Alert Storms
- Trace Breakage

Target Dataset Size:

- 100+ Incidents
- 500+ Services
- 10,000+ Events
- 100,000+ Graph Relationships
- Evidence Correlation

## Recommendation Agent

Generates:

- RCA Report
- Confidence Score
- Evidence Chain
- Remediation Plan
- Risk Assessment

---

# 🕸️ GraphRAG Investigation Pipeline

CloudGraph transforms raw observability telemetry into explainable root cause
analysis through a multi-stage GraphRAG and multi-agent reasoning pipeline.

<img src="docs/images/graphrag-investigation-pipeline.png" alt="GraphRAG Investigation Pipeline">

---

## 🔄 Investigation Workflow

### Stage 1 — Data Collection

CloudGraph continuously ingests:

- 📜 Application Logs
- 📊 Metrics
- 🔍 Distributed Traces
- ☸️ Kubernetes Events
- 🚀 Deployment History
- 📂 Git Activity
- 🛠 Infrastructure Changes

---

### Stage 2 — Knowledge Graph Construction

Observability signals are transformed into graph entities.

#### Nodes

- Services
- Pods
- Deployments
- Nodes
- Databases
- Metrics
- Alerts
- Traces
- Commits
- Incidents

#### Relationships

- CALLS
- DEPENDS_ON
- DEPLOYED_BY
- GENERATES
- AFFECTS
- CONNECTS_TO
- TRIGGERED_BY

---

### Stage 3 — GraphRAG Retrieval

Unlike traditional vector retrieval, GraphRAG enables:

- 🔍 Multi-Hop Reasoning
- 🕸 Dependency Traversal
- 📚 Context Expansion
- ⚡ Incident Correlation
- 🔗 Relationship-Aware Retrieval

---

### Stage 4 — Multi-Agent Investigation

Specialized agents independently investigate incidents.

| Agent               | Responsibility         |
| ------------------- | ---------------------- |
| 📈 Monitoring Agent | Metrics & Alerts       |
| 📜 Log Agent        | Log Analysis           |
| 🔍 Trace Agent      | Distributed Tracing    |
| 🚀 Deployment Agent | Release Analysis       |
| 🔐 Security Agent   | Security Investigation |

---

### Stage 5 — Evidence Fusion

Agent outputs are combined through a consensus engine.

Evidence scoring considers:

- Confidence
- Source Reliability
- Graph Evidence Strength
- Temporal Correlation
- Cross-Agent Agreement

---

### Stage 6 — Root Cause Analysis

The Root Cause Agent:

- Correlates evidence
- Ranks hypotheses
- Computes confidence scores
- Generates explainable RCA reports

---

### Stage 7 — Recommendation Generation

The Recommendation Agent produces:

- Root Cause Summary
- Confidence Score
- Evidence Chain
- Impact Assessment
- Remediation Plan
- Rollback Recommendations

---

## 🏆 Key Research Innovations

### 🧠 Temporal GraphRAG

Captures infrastructure evolution and incident progression over time.

### 🤖 Confidence-Aware Multi-Agent Reasoning

Combines agent findings using weighted evidence aggregation.

### 🔍 Explainable AI for AIOps

Every RCA decision can be traced back to graph relationships, telemetry
evidence, and agent reasoning.

### 📊 Incident Intelligence Layer

Transforms raw observability data into actionable operational knowledge.

---

# 📂 Repository Structure

```text
cloudgraph/

├── agents/
├── backend/
├── frontend/
├── graph/
├── retrieval/
├── observability/
├── deployments/
│   ├── terraform/
│   ├── kubernetes/
│   └── helm/
├── datasets/
├── experiments/
├── docs/
│   └── images/
├── tests/
├── scripts/
├── docker-compose.yml
├── README.md
└── LICENSE
```

---

# 🚨 Example Investigation

## Incident

Checkout service unavailable.

### Collected Evidence

Logs:

```text
database connection timeout
```

Metrics:

```text
error_rate increased
```

Trace:

```text
checkout → payment → postgres
```

Deployment:

```text
payment-service deployed 10 minutes ago
```

### Knowledge Graph Correlation

```text
deployment-v14
    ↓
secret-change
    ↓
database-auth-failure
    ↓
payment-service-crash
    ↓
checkout-outage
```

### Generated RCA

```json
{
  "root_cause": "Invalid database credentials",
  "confidence": 0.94,
  "recommendation": "Rollback deployment v14"
}
```

---

# ⚡ Quick Start

## Clone

```bash
git clone https://github.com/your-org/cloudgraph.git
cd cloudgraph
```

## Docker

```bash
docker compose up -d
```

## Backend

```bash
uvicorn app.main:app --reload
```

## Start Investigation Engine

```bash
python run_agents.py
```

---

# ☸️ Kubernetes Deployment

```bash
kubectl apply -f deployments/kubernetes/
```

Verify:

```bash
kubectl get pods -A
kubectl get svc -n observability
kubectl get svc -n cloudgraph
```

# Week 2 End-to-End Verification

From the repository root, validate and verify the infrastructure and observability stack:

```bash
# Terraform plan-only validation for Week 2 modules
cd tests/terraform
go test -v -timeout 15m -run "TestVPCPlanValidation|TestVariableValidation|TestIAMPlanValidation|TestEKSPlanValidation" ./...

# Observability stack health checks
cd ../observability
go test -v -timeout 5m ./...
```

If you have AWS access and want to deploy the stack end to end:

```bash
cd deployments/terraform
terraform init
terraform plan -var-file=../../environments/dev/terraform.tfvars
terraform apply -var-file=../../environments/dev/terraform.tfvars

# Update kubectl context for EKS
aws eks update-kubeconfig --name cloudgraph-dev --region eu-west-2

# Deploy Kubernetes manifests
kubectl apply -f deployments/kubernetes/
```

---

# 🏗️ Terraform Deployment

```bash
cd deployments/terraform

terraform init
terraform plan
terraform apply
```

Resources:

- EKS Cluster
- VPC
- IAM
- Monitoring Stack

---

# 🗄️ Neo4j Setup

```bash
docker run -d \
  --name neo4j \
  -p 7474:7474 \
  -p 7687:7687 \
  neo4j
```

---

# 🔍 Qdrant Setup

```bash
docker run -d \
  -p 6333:6333 \
  qdrant/qdrant
```

---

# 🌐 API Endpoints

## Health

```http
GET /health
```

## Investigate Incident

```http
POST /api/v1/investigate
```

Request:

```json
{
  "incident_id": "INC-001"
}
```

## Graph Search

```http
POST /api/v1/graph/search
```

## Agent Status

```http
GET /api/v1/agents
```

---

# 📊 Evaluation Framework

Metrics:

- Root Cause Accuracy
- Precision
- Recall
- F1 Score
- MTTR Reduction
- Hallucination Rate
- Retrieval Quality

Comparison Modes:

1. Traditional RAG
2. GraphRAG
3. GraphRAG + Multi-Agent System

---

# 🧪 Experimental Dataset

CloudGraph is evaluated using a reproducible incident benchmark dataset.

## Incident Categories

### Kubernetes

- CrashLoopBackOff
- ImagePullBackOff
- OOMKilled
- Node Failures

### Networking

- DNS Failures
- Service Discovery Issues
- Network Partitions

### Security

- RBAC Misconfigurations
- Secret Rotation Failures
- IAM Errors

### Deployments

- Faulty Releases
- Configuration Drift
- Terraform Errors

### Observability

- Missing Metrics
- Alert Storms
- Trace Breakage

Target Dataset Size:

- 100+ Incidents
- 500+ Services
- 10,000+ Events
- 100,000+ Graph Relationships

---

# 🧪 Testing

```bash
pytest
```

Coverage:

```bash
pytest --cov
```

Lint:

```bash
ruff check .
```

Type Check:

```bash
mypy .
```

---

# 🤝 Contributing

```bash
git checkout -b feature/new-feature
git commit -m "feat: add new feature"
git push origin feature/new-feature
```

---

# 📄 License

MIT License

---

## 👤 Author

**Shivam Shashank**

- 🌐 Portfolio: [shivam-shashank.me](https://www.shivam-shashank.me/)
- 💼 LinkedIn:
  [shivam-shashank-2b5766217](https://www.linkedin.com/in/shivam-shashank-2b5766217/)
- 📧 Email: [shivamkumar872000@gmail.com](mailto:shivamkumar872000@gmail.com)
- 🐙 GitHub: [shivamshashank](https://github.com/shivamshashank)

---

<div align="center">

### ⭐ If CloudGraph helps you, please star the repository

</div>
