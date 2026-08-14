# Literature Review

Supersedes the Week 1 review (`dissertation/week-1/literature-review.md`,
removed — in git history) and adds the sources the project actually came to
depend on during implementation and evaluation. Numbered citations `[n]` refer
to [`REFERENCES.md`](REFERENCES.md).

Where the Week 1 review anticipated something the project did not end up
building or measuring, that is said here rather than carried forward. Two
such corrections are marked **Revised** below.

---

## 1. Research context

A single cloud-native incident spans application logs, service metrics,
distributed traces, Kubernetes events, deployment history, and source-control
changes. Each of these lives in a different store with a different query
language and a different notion of time. The engineering problem: correlating
heterogeneous evidence rather than searching each source in isolation: is what
motivates automated root cause analysis (RCA), and it is the problem
CloudGraph addresses.

This review covers six areas: retrieval-augmented generation; graph-based
retrieval; knowledge graphs for incident reasoning; AIOps and RCA; multi-agent
LLM systems; and — the area the project's contribution ultimately sits in —
hallucination detection and claim verification.

## 2. Retrieval-augmented generation

Lewis et al. [1] introduced retrieval-augmented generation (RAG) as a way to
combine a model's parametric knowledge with non-parametric retrieved evidence,
grounding generated text in an external corpus rather than model memory alone.
For incident analysis this is the natural baseline: logs, metrics, traces, and
incident notes can be chunked, embedded, retrieved by vector similarity, and
supplied to an LLM as context.

The limitation that motivates the rest of this work is that vector retrieval
returns *semantically similar* evidence with no model of operational topology,
service dependencies, or temporal failure propagation. A log line mentioning
"timeout" is similar to every other timeout in the corpus, whether or not it
lies on the causal path.

CloudGraph implements this baseline directly: `all-MiniLM-L6-v2` [7] produces
384-dimensional normalised embeddings indexed in Qdrant [14], and the `vector`
retrieval mode is one of the three compared conditions.

## 3. GraphRAG and graph-based retrieval

Edge et al. [2] proposed GraphRAG for query-focused summarisation over private
corpora: build an entity graph from the source documents, detect communities
within it, and use those communities to support global sensemaking questions
that flat vector retrieval answers poorly.

CloudGraph adapts the *motivation* rather than the method. Where Edge et al.
derive a graph from unstructured text, an operational system already has a
real graph — services call services, pods run on nodes, deployments are
triggered by commits — so the entity graph does not need to be inferred. The
retrieval question becomes not "which documents resemble the incident" but
"which evidence lies on a short path from the affected entity". This yields
the project's hybrid ranker:

```text
hybrid_score = 0.50·vector_similarity + 0.30·graph_proximity + 0.20·recency
```

The hypothesis is that structured retrieval should help most where the root
cause is not contained in one log line but emerges across hops, for example:

```text
deployment → secret change → database auth failure → payment crash → checkout outage
```

**Revised.** The evaluation did not support this on the benchmark used. Vector
and hybrid retrieval scored *identically on every measure* across all 36
scenarios, so the graph term contributed nothing to retrieval here. The graph
does contribute to claim scoring (Section 7), which is a different mechanism.
This negative result is reported in [`experiments/FINDINGS.html`](../experiments/FINDINGS.html)
rather than suppressed, and it is the single most important thing the Week 1
review got wrong.

## 4. Knowledge graphs for incident reasoning

Knowledge graphs give an explicit, queryable model of entities and their
relationships. Neo4j [13] and Cypher are a natural fit for the CloudGraph
entity set — services, pods, deployments, alerts, metrics, logs, commits,
incidents — and matter specifically for *explainability*: a generated RCA
report can cite the graph path it traversed, rather than presenting an opaque
model summary.

The graph must be temporal. Relationships carry timestamps, source
identifiers, and incident windows so that a historical dependency ("service A
has always called service B") can be distinguished from evidence observed
inside the failure window. The project's Week 9 work showed why this matters
concretely: for several weeks every seeded timestamp was written as the same
constant, which silently reduced the three-signal hybrid score to two signals
plus a constant, in a system whose central question was whether structured
retrieval earns its complexity.

## 5. AIOps and root cause analysis

AIOps systems typically target anomaly detection, event correlation, fault
localisation, root cause analysis, and automated remediation. The recurring
difficulties in the cloud-native RCA literature are scaling across large
topologies, correlating multimodal observability data, and producing
explanations a human operator can act on. Recent work approaches this through
meta causal knowledge [4], agentic graph traversal [5], and explicit graphical
causal models [6].

**Benchmarking.** The most consequential source for this dissertation's
evaluation is RCAEval [8], a benchmark of microservice RCA cases in which the
authors deployed three open-source systems (Online Boutique, Sock Shop, Train
Ticket) to Kubernetes and injected faults with chaos tooling, capturing
metrics, logs, and traces through each incident window. CloudGraph's entire
citable evaluation uses 36 cases from its RE2 suite: 3 systems × 6 fault
types × 2 replicates — under the MIT licence, with full provenance recorded in
[`experiments/DATA_PROVENANCE.md`](../experiments/DATA_PROVENANCE.md).

Two scope limits follow directly from that choice and constrain every claim
this dissertation can make:

1. RE2's six fault types are all resource or network faults. It contains no
   configuration errors, security events, deployment failures, DNS faults, or
   certificate expiry. Results generalise to *resource and network faults in
   microservice systems*, not to Kubernetes incidents in general.
2. RCAEval labels which service was faulted, and the adapter passes that
   service to the system as `target_entity`. CloudGraph is therefore evaluated
   on **fault-type diagnosis for a known affected service**: it is asked
   *why* a service failed, never *which* service failed. No result in this
   project demonstrates root-cause service localisation.

## 6. Multi-agent LLM systems

Guo et al. [3] survey LLM-based multi-agent systems, in which specialised
agents divide complex work. The pattern maps onto incident investigation
because each evidence source demands a different interpretation strategy.
CloudGraph implements five specialists:

| Agent | Evidence it interprets |
|---|---|
| Monitoring | Metrics, alerts, resource saturation |
| Log | Error signatures, repeated exceptions, warning bursts |
| Deployment | Commits, releases, configuration drift |
| Topology | Service dependencies, blast radius, propagation paths |
| Security | RBAC, secrets, policy changes, authentication failures |

**Revised.** The Week 1 design listed *seven* agents, including a Trace Agent
and a separate Root Cause Agent. Neither was built. Topology took the place of
Trace (Tempo was never deployed, so no live trace data exists to reason over),
and the final fusion step is a static `ConsensusEngine` aggregation, not an
LLM reasoning agent. Any dissertation text describing seven agents or a
reasoning-based consensus describes the plan, not the system.

The open question the literature does not settle is whether specialisation
*earns its cost*. Five agents means five LLM calls per investigation; a single
LLM sampled five times costs the same. CloudGraph's matched-compute control is
designed to isolate exactly this, but it has only been run under the pipeline
that was later found to leak ground truth, so this dissertation cannot yet
answer it.

## 7. Hallucination detection and claim verification

This is where the project's contribution sits, and it is the area least
represented in the original Week 1 review.

Ji et al. [9] survey hallucination in natural language generation and
establish the vocabulary — intrinsic versus extrinsic hallucination, and the
distinction between fluency and faithfulness: that makes "unsupported claim"
a measurable quantity rather than a complaint.

Two verification strategies bound the design space:

- **Sampling-based, zero-resource.** Wang et al. [10] observe that sampling a
  model repeatedly and looking for agreement improves reasoning reliability;
  Manakul et al. [11] turn the same observation into a hallucination detector
  (SelfCheckGPT) that needs no external knowledge base: a claim that does not
  recur across samples is likely fabricated. This is CloudGraph's **baseline**
  verifier: three samples at temperature 0.8, cosine recurrence ≥ 0.8, a claim
  flagged unsupported when its recurrence rate falls below 0.5.
- **Evidence-grounded.** The alternative is to check each claim against an
  external corpus. CloudGraph's **Graph-Provenance Claim Scoring (GPCS)** does
  this against the incident knowledge graph, combining semantic evidence
  match, graph proximity to the affected entity, source reliability, and a
  hop-distance penalty into a trust score. Full formulation in
  [`docs/design/GPCS_DESIGN.md`](../docs/design/GPCS_DESIGN.md).

The comparison between these two is the dissertation's central experiment, and
it produced a result worth stating precisely, because it is easy to overclaim:
GPCS flags 70.3% of claims unsupported against self-consistency's 57.9%, a
significant difference. But *stricter is not the same as better aimed.* On the
subset of claims for which an automatic correctness label could be derived
from RCAEval's own case metadata, neither verifier discriminates correct
claims from incorrect ones — both gaps are −0.8 percentage points, and both
precision figures sit exactly on the base rate that flagging everything would
score. Settling which verifier is actually better requires human-labelled
correctness on a stratified sample, which this project has not done.

A related methodological point, easy to lose: the primary reported quantity is
**concordance**, not accuracy. It measures whether two verifiers reached the
same verdict. Both can be wrong on the same claim and it counts as agreement.

## 8. Observability foundation

OpenTelemetry [16] defines the signal model (traces, metrics, logs) that the
graph schema is built from, and Kubernetes [12] supplies the entity model
(services, pods, deployments, nodes, events). Prometheus [15] and Loki [17]
are the concrete metric and log sources; kube-state-metrics [18] and
node_exporter [19] extend that to object state and host metrics; Falco [20]
supplies runtime security events and Argo CD [21, 22] deployment and GitOps
events. These are not implementation trivia: they define the evidence model
that the knowledge graph and every experiment are built on.

## 9. Research gap

Each strand covers part of the problem and leaves a gap at the join:

- Keyword search is transparent but cannot reason over multi-hop dependencies.
- Traditional RAG improves grounding but has no model of cloud topology.
- Cloud-native RCA systems can localise faults but often without a transparent,
  human-auditable explanation path.
- Multi-agent LLM systems are promising but rarely evaluated against a
  matched-compute single-agent control, so their cost is not justified.
- Hallucination detectors are evaluated on open-domain text, not on
  operational claims where the evidence corpus is a live system graph.

The gap this dissertation addresses is the last of these:

> Can graph-grounded provenance scoring verify LLM-generated root-cause claims
> more reliably than sampling-based self-consistency, on real Kubernetes
> incident telemetry?

## 10. Mapping to research questions

| RQ | Literature basis | How CloudGraph tests it | Outcome |
|---|---|---|---|
| RQ1 — Does GPCS behave differently from self-consistency, and does either flag track correctness? | [9], [10], [11] | GPCS vs self-consistency on 3,685 claims | ✅ **Answered, partly against.** GPCS is stricter (p<0.0001); neither verifier tracks correctness (both gaps −0.8 pp) |
| RQ2 — Is the measured result real end-to-end? | — | Every baseline re-run on the corrected pipeline | ✅ **Answered — yes**, and smaller than the simulated numbers implied |
| RQ3 — Does graph retrieval beat a raw long-context dump? | [1], [2], [4] | hybrid vs raw context over 36 RCAEval cases | ✅ **Answered — null** (Δ +0.024, CI [−0.028, +0.077], p=0.302) |
| RQ4 — Is the retrieval gain symbolic or neural? | [1], [2] | keyword vs vector vs hybrid retrieval over 36 RCAEval cases | ✅ **Answered — against.** Hybrid beats keyword, but vector ≡ hybrid on all 36 scenarios |
| RQ5 — Do five agents beat one LLM at matched compute? | [3] | Matched-compute control: 5 agents vs 1 LLM sampled 5× | ⏭ **v2** — only ever run on the leaked pipeline |
| RQ6 — Are GCP/GPCS scores calibrated? | [9] | Reliability diagrams, Brier score, weight fitting | ⏭ **v2** — not started; all thresholds hand-set |
| RQ7 — Which claim types are each verifier's blind spot? | [10], [11] | Claim-type-stratified analysis over human labels | ⏭ **v2** — blocked on labels (4.2% automatic coverage) |

> An earlier draft carried a question on **MTTR reduction** [4]. No timing or
> human-workflow measurement exists anywhere in the project, so it was never
> answerable; it is withdrawn rather than left standing. The MTTR literature
> remains cited above as motivation, not as a claim CloudGraph tests.

## 11. Summary

The literature supports the design premise: cloud incident RCA needs both
semantic retrieval and explicit topology-aware reasoning, but the evaluation
supports a narrower conclusion than the premise predicted. On this benchmark,
the graph did not improve *retrieval*; its measurable contribution was to
*claim verification*, where graph-grounded scoring behaves materially
differently from sampling-based self-consistency. The honest form of this
dissertation's contribution is therefore a verification result on real
telemetry with a clearly bounded scope, plus a set of documented negative and
null results, rather than a general claim that GraphRAG improves root cause
analysis.
