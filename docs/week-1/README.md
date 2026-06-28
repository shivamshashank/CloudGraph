# Week 1 Research and System Design Pack

This directory contains the Week 1 deliverables from `ROADMAP.md`.

## Deliverables

| Deliverable | File | Dissertation Use |
| --- | --- | --- |
| Literature Review | [literature-review.md](literature-review.md) | Chapter 2: related work, research gap, and design justification |
| Research Methodology | [research-methodology.md](research-methodology.md) | Chapter 3: research design, hypotheses, metrics, experiment plan |
| Architecture Diagrams | [architecture-design.md](architecture-design.md) | Chapter 4: system design, graph schema, agent workflow, deployment view |
| Data Collection Strategy | [data-collection-strategy.md](data-collection-strategy.md) | Open-source telemetry sources and live continuous ingestion plan |
| Dissertation Evidence Plan | [dissertation-evidence.md](dissertation-evidence.md) | Chapter planning, demo evidence, screenshots, tables, evaluation artifacts |
| Reference Library | [references.md](references.md) | Sources used for Week 1 design decisions |
| Task Evidence Matrix | [task-evidence-matrix.md](task-evidence-matrix.md) | Audit trail proving each checked roadmap item has a concrete artifact |

## Existing Diagram Assets

The Week 1 design work references the current architecture images:

- `docs/images/high-level-architecture.png`
- `docs/images/graphrag-pipeline.png`
- `docs/images/multi-agent-workflow.png`
- `docs/images/aws-deployment.png`
- `docs/images/knowledge-graph-schema.png`
- `docs/images/graphrag-investigation-pipeline.png`

## Week 1 Outcome

CloudGraph is positioned as a dissertation prototype for evaluating whether a
temporal incident knowledge graph, GraphRAG retrieval, and confidence-aware
multi-agent reasoning can improve explainable root cause analysis for
Kubernetes-based cloud-native systems. It is also designed to collect live,
continuous evidence from open-source tools such as OpenTelemetry, Prometheus,
Loki, Tempo, kube-state-metrics, node_exporter, Alertmanager, Argo CD, Falco,
and Git webhooks.
