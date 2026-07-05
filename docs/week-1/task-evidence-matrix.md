# Week 1 Task Evidence Matrix

This file maps every checked Week 1 roadmap task to a concrete repository
artifact. Use it as an audit trail when writing the dissertation or explaining
project progress to a supervisor.

## Research

| Roadmap Task | Evidence File | What Was Completed |
| --- | --- | --- |
| Review GraphRAG papers | `docs/week-1/literature-review.md`, `docs/week-1/references.md` | Summarized the role of GraphRAG in topology-aware and multi-hop incident retrieval. |
| Review AIOps literature | `docs/week-1/literature-review.md`, `docs/week-1/references.md` | Framed AIOps around anomaly detection, event correlation, RCA, and explainability. |
| Review Multi-Agent Systems | `docs/week-1/literature-review.md`, `docs/week-1/architecture-design.md` | Connected specialist agents to observability evidence domains and consensus scoring. |
| Review RCA techniques | `docs/week-1/literature-review.md`, `docs/week-1/research-methodology.md` | Defined RCA baselines, root cause accuracy measures, and evaluation comparisons. |
| Review Knowledge Graph approaches | `docs/week-1/literature-review.md`, `docs/week-1/architecture-design.md` | Defined graph entities, relationships, temporal evidence, and traversal-based explanation paths. |
| Define open-source data collection points | `docs/week-1/data-collection-strategy.md`, `README.md` | Added logs, metrics, traces, events, alerts, deployments, Git, infrastructure, security, and synthetic incident sources. |

## Documentation

| Roadmap Task | Evidence File | What Was Completed |
| --- | --- | --- |
| Define RQ1-RQ4 | `docs/week-1/research-methodology.md` | Listed the four research questions and mapped them to measurable experiments. |
| Define hypotheses H1-H4 | `docs/week-1/research-methodology.md` | Defined hypotheses and expected evidence for GraphRAG, agents, hallucination reduction, and confidence scoring. |
| Define evaluation metrics | `docs/week-1/research-methodology.md` | Defined precision, recall, F1, top-k RCA accuracy, hallucination rate, explanation completeness, and MTTR proxy. |
| Create dissertation outline | `docs/week-1/dissertation-evidence.md` | Mapped dissertation chapters to repository artifacts, figures, tables, and evidence to collect. |

## Design

| Roadmap Task | Evidence File | What Was Completed |
| --- | --- | --- |
| High-Level Architecture | `docs/week-1/architecture-design.md`, `docs/images/high-level-architecture.png` | Defined the end-to-end flow from telemetry collection to RCA and remediation. |
| Graph Schema Design | `docs/week-1/architecture-design.md`, `docs/images/knowledge-graph-schema.png` | Listed graph nodes, relationships, and required evidence properties. |
| Agent Design | `docs/week-1/architecture-design.md`, `docs/images/multi-agent-workflow.png` | Defined each investigation agent, its inputs, and its output responsibilities. |
| AWS Deployment Design *(Superseded)* | `docs/week-1/architecture-design.md`, `docs/images/aws-deployment.png`, `DEMO_REQUIREMENTS.md` | **Historical:** Originally connected to AWS EKS. Current deployment now uses Helm + kubeadm/Rancher; see `IMPLEMENTATION_SUMMARY.md` and `INSTALLATION.md`. |
| Live Continuous Data Design | `docs/week-1/data-collection-strategy.md`, `README.md` | Defined pull, push, stream, and batch ingestion modes for open-source telemetry and event sources. |

## Recommendation

The checked boxes in `ROADMAP.md` can stay checked because there are now
traceable Week 1 artifacts for each task. If a supervisor expects deeper
academic detail, the next improvement should be expanding
`literature-review.md` into a formal chapter-style review with citations in the
university-required format.
