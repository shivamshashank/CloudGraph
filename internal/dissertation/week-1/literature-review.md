# Literature Review

## Research Context

Cloud-native systems are distributed, dynamic, and operationally noisy. A single
incident can involve application logs, service metrics, distributed traces,
Kubernetes events, deployment history, cloud infrastructure, and source-control
changes. This creates a strong research case for root cause analysis systems
that can correlate heterogeneous evidence rather than search each data source in
isolation.

CloudGraph focuses on five connected areas:

- AIOps and automated root cause analysis.
- Retrieval-augmented generation.
- GraphRAG and knowledge graph retrieval.
- Multi-agent LLM investigation workflows.
- Explainable incident analysis for Kubernetes observability data.

## 1. Retrieval-Augmented Generation

Lewis et al. introduced Retrieval-Augmented Generation (RAG) as a way to combine
parametric model knowledge with non-parametric retrieved evidence. Their work is
important for CloudGraph because it motivates grounding generated answers in an
external knowledge source rather than relying only on model memory.

For dissertation framing, traditional RAG is the baseline: logs, metrics,
traces, and incident notes can be chunked, embedded, retrieved, and supplied to
an LLM. The limitation is that vector retrieval may return semantically similar
evidence without understanding operational topology, service dependencies, or
temporal failure propagation.

## 2. GraphRAG

Edge et al. proposed GraphRAG for query-focused summarization over private
datasets by building an entity graph and using graph communities to support
global sensemaking. CloudGraph adapts this motivation to cloud incidents:
instead of only asking what documents are similar to the incident, the system
asks how services, pods, deployments, alerts, traces, commits, and infrastructure
changes are connected.

This supports RQ1 because GraphRAG should improve RCA when the root cause is not
contained in one isolated log line but emerges through multi-hop relationships,
for example:

```text
deployment -> secret change -> database auth failure -> payment crash -> checkout outage
```

## 3. Knowledge Graphs for Incident Reasoning

Knowledge graphs provide an explicit model of entities and relationships. Neo4j
and Cypher are suitable for representing CloudGraph entities such as services,
pods, deployments, alerts, metrics, traces, commits, and incidents. This matters
for explainability because generated RCA reports can include graph paths and
evidence chains rather than opaque model summaries.

For CloudGraph, the graph is temporal: relationships should carry timestamps,
source identifiers, confidence values, and incident windows so the investigation
can distinguish historical dependencies from evidence observed during the active
failure.

## 4. AIOps and Root Cause Analysis

AIOps systems commonly target anomaly detection, event correlation, fault
localization, root cause analysis, and automated remediation. Recent RCA
literature for cloud-native systems emphasizes the difficulty of scaling across
complex topologies, correlating multimodal observability data, and producing
interpretable causal explanations.

CloudGraph responds to these limitations by using:

- Observability evidence from logs, metrics, traces, Kubernetes events, and
  deployment history.
- A graph model for system topology and evidence propagation.
- Retrieval and agent reasoning to generate RCA hypotheses.
- Evaluation against baselines such as traditional search, traditional RAG,
  GraphRAG-only, and GraphRAG plus multi-agent reasoning.

## 5. Multi-Agent LLM Systems

LLM-based multi-agent systems divide complex work across specialized agents.
For CloudGraph, this pattern maps naturally to incident investigation because
each evidence source requires a different interpretation strategy:

- Monitoring Agent: metrics, alerts, resource saturation.
- Log Agent: error signatures, repeated exceptions, warning bursts.
- Trace Agent: latency, span errors, dependency bottlenecks.
- Deployment Agent: commits, releases, Terraform changes, configuration drift.
- Security Agent: RBAC, secrets, policy changes, authentication failures.
- Root Cause Agent: evidence fusion, hypothesis ranking, final RCA.

This supports RQ2 and H2: multi-agent reasoning can be compared against a
single-agent GraphRAG baseline to test whether specialization improves
investigation quality.

## 6. Observability Foundation

OpenTelemetry defines core observability signals including traces, metrics, and
logs. Kubernetes provides the orchestration layer where services, pods,
deployments, events, and nodes can be observed. These sources are not merely
implementation details; they define the evidence model used in CloudGraph's
knowledge graph and experiments.

## Research Gap

Existing systems often cover only part of the incident reasoning problem:

- Traditional search is easy to implement but weak at multi-hop dependency
  reasoning.
- Traditional RAG improves grounding but does not inherently model cloud
  topology.
- RCA systems can be accurate but may lack transparent LLM-generated
  explanation paths.
- Multi-agent LLM systems are promising but need controlled evaluation in
  operational cloud scenarios.

CloudGraph's research gap is therefore:

> Can temporal knowledge graph retrieval and confidence-aware multi-agent
> reasoning improve the accuracy, explainability, and trustworthiness of
> Kubernetes root cause analysis compared with search, traditional RAG, and
> single-agent analysis?

## Mapping to CloudGraph Research Questions

| Research Question | Literature Basis | CloudGraph Test |
| --- | --- | --- |
| RQ1: Can GraphRAG improve RCA accuracy compared to traditional RAG? | RAG grounding and GraphRAG graph retrieval | Compare traditional RAG vs graph traversal plus retrieval |
| RQ2: Does multi-agent reasoning improve investigation quality? | LLM multi-agent specialization | Compare single Root Cause Agent vs specialist agents plus consensus |
| RQ3: Can knowledge graph retrieval reduce hallucinations? | External evidence grounding and graph provenance | Measure unsupported claims in generated RCA reports |
| RQ4: Can GraphRAG-powered investigations reduce MTTR? | AIOps RCA automation | Measure investigation time across baseline and CloudGraph workflows |

## Dissertation-Ready Summary

The literature supports CloudGraph's central design choice: cloud incident RCA
requires both semantic evidence retrieval and explicit topology-aware reasoning.
Traditional RAG is useful for grounding LLM outputs, but Kubernetes failures
often propagate across service and infrastructure relationships. A temporal
knowledge graph can represent these relationships, while multi-agent reasoning
can independently inspect specialized evidence streams before a final RCA is
generated.
