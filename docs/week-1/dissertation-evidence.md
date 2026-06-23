# Dissertation Evidence Plan

This file lists what CloudGraph can show in the dissertation and final
demonstration. It turns the Week 1 research/design work into concrete evidence
artifacts to collect during Weeks 2-8.

## Chapter Evidence Map

| Dissertation Chapter | What To Show | Repository Evidence |
| --- | --- | --- |
| Introduction | Problem, motivation, research questions, hypotheses | `README.md`, `ROADMAP.md`, `docs/week-1/research-methodology.md` |
| Literature Review | RAG, GraphRAG, AIOps, RCA, multi-agent systems | `docs/week-1/literature-review.md`, `docs/week-1/references.md` |
| Methodology | Baselines, dataset, metrics, validity threats | `docs/week-1/research-methodology.md` |
| System Design | Architecture, graph schema, agents, deployment | `docs/week-1/architecture-design.md`, `docs/images/*.png` |
| Implementation | Ingestion, graph, retrieval, agents, dashboard | Future `backend/`, `graph/`, `retrieval/`, `agents/`, `frontend/` |
| Evaluation | Accuracy, F1, hallucination rate, MTTR proxy | Future `experiments/`, `datasets/`, result tables |
| Discussion | Strengths, limitations, threats to validity | Evaluation results and incident case studies |
| Conclusion | Answer RQ1-RQ4 and future work | Final result summary |

## Figures To Include

- High-level CloudGraph architecture.
- GraphRAG investigation pipeline.
- Knowledge graph schema.
- Multi-agent workflow.
- AWS deployment architecture.
- Baseline comparison flow: search vs RAG vs GraphRAG vs multi-agent GraphRAG.
- Example RCA evidence chain.

## Tables To Include

- Research questions and hypotheses.
- Literature comparison table.
- Dataset categories and incident counts.
- Baseline method comparison.
- Evaluation metrics.
- Top-1 and top-3 RCA accuracy results.
- Hallucination rate by method.
- MTTR proxy by method.
- Threats to validity.

## Demonstration Story

Use one clear scenario for the final demo:

```text
Checkout outage
  -> payment service errors
  -> database authentication failures
  -> recent secret/config deployment
  -> graph path identifies root cause
  -> agents vote on evidence
  -> RCA report recommends rollback or secret fix
```

## What To Capture During Implementation

- Screenshots of Kubernetes workloads running.
- Screenshots of Prometheus/Grafana/Loki/Tempo or OpenTelemetry evidence.
- Neo4j graph screenshots showing service and incident relationships.
- Qdrant/vector retrieval logs for traditional RAG baseline.
- Graph traversal output for GraphRAG.
- Agent outputs with confidence scores.
- Final RCA report with evidence chain.
- Evaluation result CSV files.
- Plots comparing methods.

## Dissertation Claims To Support With Evidence

| Claim | Evidence Needed |
| --- | --- |
| GraphRAG improves RCA accuracy | Baseline comparison table with accuracy/F1 |
| Graph traversal improves explainability | Example graph paths and cited evidence nodes |
| Multi-agent reasoning improves coverage | Per-agent findings and consensus output |
| Knowledge graph grounding reduces hallucination | Unsupported-claim audit per method |
| CloudGraph can reduce investigation effort | MTTR proxy or step-count comparison |

## Risks To Address

- Synthetic incidents may not fully represent production complexity.
- LLM output may vary unless prompts and temperature are controlled.
- Ground-truth labels must be consistent and auditable.
- Evaluation should separate retrieval quality from generation quality.
- AWS costs and cluster complexity may require a local `kind`/`k3d` fallback.

## Week 1 Completion Checklist

- [x] Research questions and hypotheses defined.
- [x] Literature review direction documented.
- [x] Methodology and evaluation metrics documented.
- [x] Existing architecture diagrams mapped to dissertation sections.
- [x] Dissertation evidence plan created.
