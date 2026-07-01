# Demo Requirements for CloudGraph

## Overview

This document summarizes the requirements for visually demoing CloudGraph locally or on AWS.

It also clarifies whether the project uses Mixture of Experts (MoE).

---

## Is Mixture of Experts used?

No. The current CloudGraph project does not explicitly implement a Mixture of Experts (MoE) model.

What the project does use:

- Multi-agent investigation workflows
- GraphRAG retrieval with knowledge graph and vector search
- Specialized agents for logs, deployments, monitoring, and security

Why this is not MoE:

- MoE usually refers to a neural architecture where a gating mechanism selects among multiple expert subnetworks inside an LLM.
- CloudGraph instead combines outputs from multiple investigative agents and graph retrieval.
- That is a multi-agent reasoning design, not a standard MoE parameter-sharing model.

---

## Local demo requirements

### Software

- Docker
- Kubernetes runtime: `kind`, `k3d`, or `minikube`
- Python environment (if the project includes Python ingestion or orchestration code)
- Neo4j container or local instance
- Qdrant container or local instance
- Observability stack containers for:
  - Prometheus
  - Grafana
  - Loki
  - OpenTelemetry collector
- Optional LLM access:
  - Local LLM runtime, or
  - Hosted LLM API such as OpenAI, Anthropic, or others

### Hardware

- RAM: minimum 16 GB, ideally 32 GB for a smooth demo
- CPU: minimum 4 cores
- Disk: 50–100 GB available for images, logs, and data
- Network: internet access if using remote LLM APIs or cloud data sources

### Data sources for demo ingestion

Use one or more of the following:

- Kubernetes application logs via Loki or another log collector
- Prometheus metrics
- OpenTelemetry telemetry through the collector
- Kubernetes events
- Synthetic log files or manually generated incident logs

### Demo flow

1. Start the local k8s/containers.
2. Deploy a sample app that emits logs and metrics.
3. Ingest observability data into CloudGraph.
4. Build the knowledge graph in Neo4j.
5. Execute GraphRAG retrieval and multi-agent investigation.
6. Show RCA output, evidence chain, and remediation suggestions.

---

## AWS demo requirements

### Core AWS infrastructure

- AWS EKS cluster
- EC2 worker nodes (or managed node groups)
- VPC with subnets, security groups, NAT gateway if needed
- IAM roles for EKS, service accounts, and observability tools
- S3 for object storage or artifacts if required
- Optional RDS/managed database for metadata

### Cloud-native services and observability

- Prometheus + Grafana in-cluster or managed service
- Loki or CloudWatch Logs ingestion
- OpenTelemetry-based telemetry ingestion
- CloudWatch metrics and alarms
- Optional AWS-managed Prometheus / Grafana

### Knowledge graph and retrieval

- Neo4j deployed in the cluster or on EC2
- Qdrant deployed in the cluster or on EC2
- Optional managed alternatives if preferred

### Data ingestion sources

- CloudWatch Logs / CloudWatch Metrics
- Kubernetes application logs
- OpenTelemetry telemetry
- Git commit and deployment history from source control
- Deployment history and configuration changes if using GitOps

### Optional supporting infrastructure

- ArgoCD for GitOps deployment
- API Gateway and authentication if a UI or API is exposed
- S3 for backups and persisted data
- Secrets manager for sensitive keys

### Hardware / capacity notes

- EKS cluster size depends on app and observability load.
- Minimum: 2–3 worker nodes for Kubernetes + observability + graph/retrieval services.
- Neo4j and Qdrant each need dedicated memory and CPU for performance.
- Use at least 16 GB RAM across the cluster; 32+ GB is safer for demo workloads.

---

## Demo recommendations

### Best local demo setup

- Run a single-node k8s cluster with Docker + `kind` or `k3d`
- Deploy the demo app and observability stack together
- Use sample or synthetic logs so you can control the incident scenario
- Focus on one clear incident: root cause, evidence graph, recommendation

### Best AWS demo setup

- Use EKS for the app and observability stack
- Deploy Neo4j/Qdrant in the cluster or on dedicated EC2 instances
- Use CloudWatch and OpenTelemetry for real cloud observability data
- Show the complete flow from logs and metrics to RCA output

---

## Notes

- If you want to introduce MoE in the future, it would be a separate modeling layer inside the language reasoning component.
- For now, the project is best described as a GraphRAG + multi-agent RCA platform rather than an MoE system.
