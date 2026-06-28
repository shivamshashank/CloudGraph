# Research Methodology

## Aim

The aim of CloudGraph is to evaluate whether GraphRAG and confidence-aware
multi-agent reasoning can improve root cause analysis for Kubernetes-based
cloud-native incidents.

## Research Questions

| ID | Research Question |
| --- | --- |
| RQ1 | Can GraphRAG improve root cause analysis accuracy compared to traditional RAG? |
| RQ2 | Does multi-agent reasoning improve investigation quality compared to single-agent analysis? |
| RQ3 | Can knowledge graph retrieval reduce hallucinations during RCA generation? |
| RQ4 | Can GraphRAG-powered investigations reduce Mean Time To Resolution (MTTR)? |

## Hypotheses

| ID | Hypothesis | Expected Evidence |
| --- | --- | --- |
| H1 | GraphRAG achieves higher RCA accuracy than traditional RAG. | Higher precision, recall, F1, and top-k root cause accuracy. |
| H2 | GraphRAG plus multi-agent reasoning outperforms GraphRAG alone. | Better hypothesis ranking and fewer missed evidence sources. |
| H3 | Knowledge graph retrieval reduces hallucination rates. | Lower unsupported-claim percentage in RCA reports. |
| H4 | Confidence-aware agent voting improves recommendation quality and trust. | Higher expert or rubric score for remediation usefulness. |

## Experimental Design

CloudGraph should be evaluated using a controlled incident benchmark containing
synthetic and reproducible Kubernetes incident scenarios.

### Independent Variable

Investigation method:

1. Keyword/log search baseline.
2. Traditional vector RAG.
3. GraphRAG without multi-agent workflow.
4. GraphRAG plus multi-agent workflow.
5. GraphRAG plus multi-agent workflow plus confidence-aware consensus.

### Dependent Variables

- RCA accuracy.
- Precision, recall, and F1 score for evidence retrieval.
- Top-1 and top-3 root cause localization accuracy.
- Hallucination rate in generated RCA reports.
- MTTR or simulated investigation time.
- Explanation path completeness.
- Remediation recommendation quality.

### Controlled Variables

- Same incident dataset across all methods.
- Same LLM model family and temperature settings where possible.
- Same evidence corpus per incident.
- Same evaluation rubric.
- Same incident time windows and ground-truth labels.

## Dataset Plan

The Week 7 dataset should contain at least 100 incidents across the categories
already defined in `README.md` and `ROADMAP.md`.

| Category | Example Incidents | Ground Truth |
| --- | --- | --- |
| Kubernetes | CrashLoopBackOff, ImagePullBackOff, OOMKilled | Pod, deployment, image, or resource root cause |
| Networking | DNS failure, service discovery issue, network partition | Service, DNS, policy, or ingress root cause |
| Security | RBAC misconfiguration, secret rotation failure, IAM error | Policy, secret, service account, or role root cause |
| Deployment | Faulty release, config drift, Terraform error | Commit, rollout, config, or infrastructure root cause |
| Observability | Missing metrics, alert storm, trace breakage | Collector, exporter, scrape target, or instrumentation root cause |

## Evaluation Metrics

| Metric | Definition | Why It Matters |
| --- | --- | --- |
| Precision | Correct retrieved evidence / all retrieved evidence | Measures noise in the investigation context. |
| Recall | Correct retrieved evidence / all relevant evidence | Measures whether key evidence was missed. |
| F1 | Harmonic mean of precision and recall | Balances precision and recall. |
| Top-1 RCA Accuracy | Root cause ranked first matches ground truth | Measures direct RCA correctness. |
| Top-3 RCA Accuracy | Ground truth appears in top three hypotheses | Measures practical investigation usefulness. |
| Hallucination Rate | Unsupported generated claims / total generated claims | Measures trustworthiness. |
| Explanation Completeness | Required graph path elements present / expected elements | Measures explainability. |
| MTTR Proxy | Time or steps needed to reach correct RCA | Measures operational efficiency. |

## Method Flow

```text
Incident Scenario
  -> Evidence Collection
  -> Knowledge Graph Construction
  -> Retrieval Baselines
  -> Agent Investigation
  -> Consensus and RCA Generation
  -> Evaluation Against Ground Truth
```

## Baseline Definitions

### Baseline A: Keyword Search

Search logs and incident notes using direct keyword matching. This baseline is
simple, transparent, and useful for measuring the value added by semantic and
graph-based retrieval.

### Baseline B: Traditional RAG

Chunk logs, traces, metrics summaries, events, and deployment notes. Embed the
chunks and retrieve top-k chunks by vector similarity. Generate RCA from the
retrieved context.

### Baseline C: GraphRAG

Build a knowledge graph of services, resources, evidence, and incidents. Retrieve
context using graph traversal, path expansion, and vector search. Generate RCA
from graph-grounded evidence.

### Baseline D: GraphRAG plus Multi-Agent

Run specialist agents over graph-grounded context. Fuse findings into final
hypotheses using confidence scores and evidence weights.

## Validity Considerations

- Internal validity: use consistent incident windows and model settings.
- Construct validity: ensure "correct root cause" labels are explicitly defined.
- External validity: include different incident categories and service
  topologies.
- Reliability: store dataset, prompts, retrieved evidence, generated RCA output,
  and evaluation results in version-controlled files.

## Dissertation Outputs

The methodology chapter can include:

- Research questions and hypotheses table.
- Dataset design table.
- Baseline comparison diagram.
- Evaluation metrics table.
- Threats-to-validity section.
- Reproducibility checklist.
